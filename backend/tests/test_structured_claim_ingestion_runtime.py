from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.structured_claim_ingestion import (
    CLAIM_IDENTITY_MAPPING_VERSION,
    STRUCTURED_CLAIM_INGESTION_VERSION,
    build_structured_claim_allowlist,
    load_claim_identity_mapping,
    materialize_selected_structured_claim,
    materialize_selected_structured_claim_safely,
)
from app.routes import intelligence_admin
from app.services import multimodal_intelligence_runtime
from app.services.multimodal_shadow_api_enhanced import (
    MULTIMODAL_STRUCTURED_INGESTION_ADAPTER_VERSION,
    execute_multimodal_shadow_api,
)


NOW = "2026-08-22T06:30:00+00:00"
SUBJECT = "player|one"
DESTINATION = "club|arsenal"
PRODUCTION_CLAIM = "legacy-claim-1"
LEFT_OBSERVATION = "source-observation-left"
RIGHT_OBSERVATION = "source-observation-right"


class StructuredClaimIngestionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            self._seed_entities(conn)
            self._seed_legacy_claim_scope(conn)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def _seed_entities(self, conn):
        entities = [
            ("entity-player-one", SUBJECT, "player", "Player One"),
            ("entity-arsenal", DESTINATION, "club", "Arsenal"),
            (
                "entity-manchester-united",
                "club|manchester-united",
                "club",
                "Manchester United",
            ),
            (
                "entity-newcastle-united",
                "club|newcastle-united",
                "club",
                "Newcastle United",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO canonical_entities (
              id, entity_key, entity_type, sport_key, canonical_name,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, 'football', ?, ?, ?, '{}')
            """,
            [
                (entity_id, entity_key, entity_type, name, NOW, NOW)
                for entity_id, entity_key, entity_type, name in entities
            ],
        )

        aliases = [
            (
                "alias-player-one",
                "entity-player-one",
                "Player One",
                "player one",
                "canonical_name",
            ),
            (
                "alias-arsenal",
                "entity-arsenal",
                "Arsenal",
                "arsenal",
                "canonical_name",
            ),
            (
                "alias-manchester-united-short",
                "entity-manchester-united",
                "United",
                "united",
                "short_name",
            ),
            (
                "alias-newcastle-united-short",
                "entity-newcastle-united",
                "United",
                "united",
                "short_name",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO entity_aliases (
              id, entity_id, alias_text, normalized_alias, alias_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
            """,
            [
                (*row, NOW, NOW)
                for row in aliases
            ],
        )

    def _seed_legacy_claim_scope(self, conn):
        for source_id, domain in (
            ("source-left", "left.example"),
            ("source-right", "right.example"),
        ):
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type, canonical_domain,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, 'publisher', ?, ?, ?, '{}')
                """,
                (
                    source_id,
                    "publisher|" + domain,
                    domain,
                    domain,
                    NOW,
                    NOW,
                ),
            )

        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, ?, 'multimodal_candidate', ?, ?, '{}')
            """,
            (
                PRODUCTION_CLAIM,
                "multimodal|player-one|legacy-text-hash",
                SUBJECT,
                "Player One completed a move to Arsenal",
                NOW,
                NOW,
            ),
        )

        for observation_id, source_id, url in (
            (
                LEFT_OBSERVATION,
                "source-left",
                "https://left.example/player-one-arsenal",
            ),
            (
                RIGHT_OBSERVATION,
                "source-right",
                "https://right.example/player-one-arsenal",
            ),
        ):
            conn.execute(
                """
                INSERT INTO source_observations (
                  id, source_id, subject_key, observation_type, status,
                  claim_summary, provenance_url, observed_at, recorded_at,
                  metadata_json
                ) VALUES (?, ?, ?, 'report', 'unresolved', ?, ?, ?, ?, '{}')
                """,
                (
                    observation_id,
                    source_id,
                    SUBJECT,
                    "Player One completed a move to Arsenal",
                    url,
                    NOW,
                    NOW,
                ),
            )

    @staticmethod
    def full_candidate(*, effective_period=None, destination=DESTINATION):
        facets = {}
        if effective_period is not None:
            facets["effective_period"] = effective_period
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {
                "destination": destination,
            },
            "facets": facets,
        }

    @classmethod
    def shadow_report(cls, candidate_id, *, candidate=None, route="full_identity"):
        return {
            "version": "structured-claim-shadow-bridge-v1",
            "status": "active",
            "candidate_rows": [
                {
                    "candidate_id": candidate_id,
                    "production_claim_id": PRODUCTION_CLAIM,
                    "shadow_status": "evaluated",
                    "router_status": (
                        "extracted" if route == "full_identity" else "partial"
                    ),
                    "route": route,
                    "reason": "",
                    "candidate": candidate,
                    "identity_complete": route == "full_identity",
                    "missing_identity_fields": (
                        [] if route == "full_identity" else ["roles.destination"]
                    ),
                    "core_key": "",
                    "core_fingerprint": "",
                    "specific_fingerprint": "",
                }
            ],
        }

    def count(self, table):
        conn = self.factory()
        try:
            return int(
                conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            )
        finally:
            conn.close()

    def test_allowlist_uses_exact_aliases_and_excludes_ambiguity(self):
        result = build_structured_claim_allowlist(
            subject_key=SUBJECT,
            left_capture={
                "payload": {
                    "title": "Player One joins Arsenal",
                    "body": "Player One completed the move to Arsenal.",
                }
            },
            right_capture={
                "payload": {
                    "caption": "United also discussed the move, according to the post."
                }
            },
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ready")
        self.assertIn(SUBJECT, result["allowed_entity_keys"])
        self.assertIn(DESTINATION, result["allowed_entity_keys"])
        self.assertNotIn("club|manchester-united", result["allowed_entity_keys"])
        self.assertNotIn("club|newcastle-united", result["allowed_entity_keys"])
        self.assertEqual(
            result["counts"]["ambiguous_aliases_excluded"],
            1,
        )
        self.assertFalse(result["policy"]["provider_call_performed"])
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_allowlist_degrades_to_subject_only_when_alias_lookup_fails(self):
        def broken_resolver(**_kwargs):
            raise RuntimeError("alias store unavailable")

        result = build_structured_claim_allowlist(
            subject_key=SUBJECT,
            left_capture={"title": "Player One moves"},
            right_capture={"caption": "Arsenal move"},
            connection_factory=self.factory,
            resolver=broken_resolver,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["resolution_status"], "subject_only")
        self.assertEqual(result["resolution_error_type"], "RuntimeError")
        self.assertEqual(result["allowed_entity_keys"], [SUBJECT])

    def test_dual_full_identity_materializes_and_maps_legacy_claim(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate=self.full_candidate(effective_period="2026"),
        )

        result = materialize_selected_structured_claim(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=left,
            right_shadow_report=right,
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=self.factory,
        )

        self.assertEqual(result["version"], STRUCTURED_CLAIM_INGESTION_VERSION)
        self.assertEqual(result["status"], "materialized")
        self.assertTrue(result["canonical_claim_id"])
        self.assertEqual(result["mapping_status"], "verified_equivalent")
        self.assertIn(
            result["compatibility"]["status"],
            {"exact_specific_match", "same_core_no_material_conflict"},
        )
        self.assertEqual(self.count("claim_identity_mappings"), 1)

        conn = self.factory()
        try:
            canonical_links = conn.execute(
                """
                SELECT source_observation_id
                FROM claim_links
                WHERE claim_id = ?
                  AND relationship_type = 'reports'
                ORDER BY source_observation_id
                """,
                (result["canonical_claim_id"],),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(
            [row[0] for row in canonical_links],
            [LEFT_OBSERVATION, RIGHT_OBSERVATION],
        )
        self.assertFalse(result["policy"]["additional_provider_call_performed"])
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_materialization_replay_is_idempotent(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate=self.full_candidate(),
        )

        kwargs = {
            "production_claim_id": PRODUCTION_CLAIM,
            "subject_key": SUBJECT,
            "left_candidate_id": "candidate-left",
            "right_candidate_id": "candidate-right",
            "left_shadow_report": left,
            "right_shadow_report": right,
            "left_source_observation_id": LEFT_OBSERVATION,
            "right_source_observation_id": RIGHT_OBSERVATION,
            "connection_factory": self.factory,
        }

        first = materialize_selected_structured_claim(**kwargs)
        second = materialize_selected_structured_claim(**kwargs)

        self.assertEqual(first["canonical_claim_id"], second["canonical_claim_id"])
        self.assertEqual(self.count("claim_identity_mappings"), 1)

        conn = self.factory()
        try:
            rows = conn.execute(
                "SELECT COUNT(*) FROM claim_links WHERE claim_id = ?",
                (first["canonical_claim_id"],),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(int(rows), 2)

    def test_partial_output_never_mints_identity(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate={
                "subject_key": SUBJECT,
                "event_type": "transfer",
                "state": "completed",
                "negated": False,
                "roles": {},
                "facets": {},
            },
            route="partial_semantics",
        )

        result = materialize_selected_structured_claim(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=left,
            right_shadow_report=right,
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "not_materialized")
        self.assertEqual(result["reason"], "dual_full_identity_unavailable")
        self.assertEqual(self.count("claim_identity_mappings"), 0)

    def test_different_core_fails_closed(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate=self.full_candidate(destination="club|chelsea"),
        )

        result = materialize_selected_structured_claim(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=left,
            right_shadow_report=right,
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["reason"], "different_core")
        self.assertEqual(self.count("claim_identity_mappings"), 0)

    def test_same_core_material_conflict_fails_closed(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(effective_period="2026"),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate=self.full_candidate(effective_period="2027"),
        )

        result = materialize_selected_structured_claim(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=left,
            right_shadow_report=right,
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["reason"], "material_conflict")
        self.assertEqual(self.count("claim_identity_mappings"), 0)

    def test_safe_materializer_hides_database_error_message(self):
        def broken_factory():
            raise RuntimeError("secret database endpoint failed")

        result = materialize_selected_structured_claim_safely(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=self.shadow_report(
                "candidate-left",
                candidate=self.full_candidate(),
            ),
            right_shadow_report=self.shadow_report(
                "candidate-right",
                candidate=self.full_candidate(),
            ),
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=broken_factory,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertNotIn("secret database", json.dumps(result))

    def test_mapping_read_model_is_bounded(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate=self.full_candidate(),
        )
        materialized = materialize_selected_structured_claim(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=left,
            right_shadow_report=right,
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=self.factory,
        )

        result = load_claim_identity_mapping(
            production_claim_id=PRODUCTION_CLAIM,
            connection_factory=self.factory,
        )

        self.assertEqual(result["version"], CLAIM_IDENTITY_MAPPING_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["canonical_claim_id"],
            materialized["canonical_claim_id"],
        )
        self.assertNotIn("metadata_json", result)
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_database_migration_creates_identity_mapping_table(self):
        other_path = Path(self.tempdir.name) / "migration.sqlite3"

        def other_factory():
            return connect_database(other_path)

        initialize_database(other_factory, SCHEMA)
        conn = other_factory()
        try:
            row = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'claim_identity_mappings'
                """
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)

    def test_admin_mapping_endpoint_is_protected_and_returns_mapping(self):
        left = self.shadow_report(
            "candidate-left",
            candidate=self.full_candidate(),
        )
        right = self.shadow_report(
            "candidate-right",
            candidate=self.full_candidate(),
        )
        materialize_selected_structured_claim(
            production_claim_id=PRODUCTION_CLAIM,
            subject_key=SUBJECT,
            left_candidate_id="candidate-left",
            right_candidate_id="candidate-right",
            left_shadow_report=left,
            right_shadow_report=right,
            left_source_observation_id=LEFT_OBSERVATION,
            right_source_observation_id=RIGHT_OBSERVATION,
            connection_factory=self.factory,
        )

        calls = []

        def require_admin(request):
            calls.append(request.url.path)

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=require_admin,
                connection_factory=self.factory,
            )
        )
        client = TestClient(app)
        response = client.get(
            "/admin/intelligence/claims/"
            + PRODUCTION_CLAIM
            + "/identity-mapping"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mapping_status"], "verified_equivalent")
        self.assertEqual(calls, [response.request.url.path])

    def test_enhanced_shadow_adapter_enables_fusion_without_second_provider_call(self):
        conn = self.factory()
        try:
            for source_id, url in (
                ("shadow-source-left", "https://shadow-left.example/post"),
                ("shadow-source-right", "https://shadow-right.example/post"),
            ):
                conn.execute(
                    """
                    INSERT INTO intelligence_sources (
                      id, source_key, display_name, source_type, canonical_domain,
                      first_seen_at, last_seen_at, metadata_json
                    ) VALUES (?, ?, ?, 'publisher', ?, ?, ?, '{}')
                    """,
                    (
                        source_id,
                        "publisher|" + source_id,
                        source_id,
                        url.split("//", 1)[1].split("/", 1)[0],
                        NOW,
                        NOW,
                    ),
                )

            conn.execute(
                """
                INSERT INTO media_items (
                  id, canonical_url, mode, source_id, title, latest_content_hash,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (
                  'shadow-media-left', 'https://shadow-left.example/post',
                  'article', 'shadow-source-left', 'Left', 'left-hash', ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO media_items (
                  id, canonical_url, mode, source_id, title, latest_content_hash,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (
                  'shadow-media-right', 'https://shadow-right.example/post',
                  'article', 'shadow-source-right', 'Right', 'right-hash', ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

        captured = {}

        def fake_runtime(**kwargs):
            captured.update(kwargs)
            return {
                "version": (
                    multimodal_intelligence_runtime
                    .MULTIMODAL_INTELLIGENCE_RUNTIME_VERSION
                ),
                "status": "completed_shadow",
                "claim_id": "legacy-shadow-claim",
                "subject_key": SUBJECT,
                "left_media_item_id": "shadow-media-left",
                "right_media_item_id": "shadow-media-right",
                "left_candidate_id": "candidate-left",
                "right_candidate_id": "candidate-right",
                "stages": {},
                "live_score": {"total": 70.0},
                "shadow": {
                    "proposed_adjustment": 0.0,
                    "proposed_shadow_total": 70.0,
                    "boost_eligible": False,
                },
                "policy": {
                    "exact_common_claim_required": True,
                    "heuristic_cross_item_claim_matching": False,
                    "verified_bindings_rechecked_downstream": True,
                    "adjudication_intake_is_candidate_scoped": True,
                    "multimodal_evidence_remains_unverified": True,
                    "model_output_does_not_establish_truth": True,
                    "model_output_does_not_establish_independence": True,
                    "independence_uses_existing_verifier_only": True,
                    "merit_shadow_only": True,
                    "merit_baseline_mode": "legacy_merit",
                    "merit_baseline_available": True,
                    "merit_shadow_evaluated": True,
                    "synthetic_merit_baseline_used": False,
                    "live_release_not_called": True,
                    "release_certificate_not_consumed": True,
                    "live_enablement_authorized": False,
                    "score_effect_applied": False,
                    "establishes_truth": False,
                    "affects_live_merit": False,
                },
            }

        interpreter = object()
        interpreter_factory = Mock(return_value=interpreter)
        generator = Mock()

        result = execute_multimodal_shadow_api(
            request_payload={
                "subject_key": SUBJECT,
                "left": {
                    "capture": {
                        "payload": {
                            "title": "Player One joins Arsenal",
                            "body": "Player One completed the move to Arsenal.",
                        }
                    },
                    "source_id": "shadow-source-left",
                    "media_item_id": "shadow-media-left",
                    "story_id": "",
                },
                "right": {
                    "capture": {
                        "payload": {
                            "title": "Arsenal sign Player One",
                            "body": "Arsenal completed the move for Player One.",
                        }
                    },
                    "source_id": "shadow-source-right",
                    "media_item_id": "shadow-media-right",
                    "story_id": "",
                },
                "target_claim_id": "",
                "legacy_score": {"total": 70.0},
                "merit_baseline_mode": "legacy_merit",
            },
            connection_factory=self.factory,
            gemini_client=object(),
            gemini_client_key="test-client",
            gemini_generator=generator,
            runtime_runner=fake_runtime,
            interpreter_factory=interpreter_factory,
            now_provider=lambda: NOW,
        )

        self.assertEqual(result["status"], "completed_shadow")
        self.assertTrue(captured["structured_claim_shadow_enabled"])
        self.assertIn(
            SUBJECT,
            captured["structured_claim_allowed_entity_keys"],
        )
        self.assertIn(
            DESTINATION,
            captured["structured_claim_allowed_entity_keys"],
        )
        self.assertIs(captured["semantic_interpreter"], interpreter)
        self.assertEqual(
            result["result"]["structured_claim_ingestion"]["version"],
            MULTIMODAL_STRUCTURED_INGESTION_ADAPTER_VERSION,
        )
        self.assertEqual(
            result["result"]["structured_claim_ingestion"]["policy"][
                "additional_provider_calls"
            ],
            0,
        )
        generator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
