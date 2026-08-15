import copy
import json
import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main

from app.analysis.observation_semantics import (
    normalize_claim_observation_semantics,
)

from app.analysis.snapshot_assembly import (
    build_model_assisted_evidence_snapshot,
)

from app.services.snapshot_persistence import (
    MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION,
    persist_model_assisted_evidence_snapshot,
)


class ModelAssistedSnapshotPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = (
            main.DB_PATH
        )
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )
        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "snapshot-persistence.db"
        )

        main.init_db()

        self.source = (
            main.upsert_intelligence_source(
                url=(
                    "https://example.com/"
                    "team-statement"
                ),
                display_name=(
                    "Example Source"
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

        self.claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|player-a|"
                    "team-a|join"
                ),
                subject_key=(
                    "transfer|player-a|team-a"
                ),
                canonical_text=(
                    "Player A will join Team A."
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )
        self.temp_dir.cleanup()

    @staticmethod
    def normalize_url(value):
        return str(
            value or ""
        ).strip()

    def raw_semantics(
        self,
        **overrides,
    ):
        data = {
            "claim_relevance": (
                "same_claim"
            ),
            "source_role": (
                "primary_stakeholder"
            ),
            "authority_class": (
                "direct"
            ),
            "reliability_class": (
                "unknown"
            ),
            "provenance_class": (
                "direct_statement"
            ),
            "stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_targets": [],
            "field_evidence": [
                (
                    "Team A announces "
                    "Player A will join."
                )
            ],
            "source_role_confidence": 0.99,
            "authority_confidence": 0.99,
            "reliability_confidence": 0.50,
            "provenance_confidence": 0.98,
            "stance_confidence": 0.99,
            "dependency_confidence": 0.90,
        }

        data.update(overrides)
        return data

    def build(
        self,
        *,
        raw=None,
        actor_id="team-a",
    ):
        source_url = (
            "https://example.com/"
            "team-statement"
        )

        assessment = (
            normalize_claim_observation_semantics(
                (
                    raw
                    or self.raw_semantics()
                ),
                claim_id=self.claim["id"],
                source_url=source_url,
                context={},
                evaluator_id=(
                    "semantic-model-v1"
                ),
            )
        )

        return (
            build_model_assisted_evidence_snapshot(
                claim={
                    "id": self.claim["id"],
                    "canonical_text": (
                        self.claim[
                            "canonical_text"
                        ]
                    ),
                },
                source={
                    "url": source_url,
                    "actor_id": actor_id,
                    "published_at": (
                        "2026-08-15T02:00:00Z"
                    ),
                    "observed_at": (
                        "2026-08-15T02:05:00Z"
                    ),
                },
                semantic_assessment=(
                    assessment
                ),
                as_of=(
                    "2026-08-15T03:00:00Z"
                ),
            )
        )

    def persist(
        self,
        assembly,
        **overrides,
    ):
        args = {
            "assembly": assembly,
            "source_id": (
                self.source["id"]
            ),
            "subject_key": (
                self.claim["subject_key"]
            ),
            "recorded_at": (
                "2026-08-15T03:01:00Z"
            ),
            "normalize_url": (
                self.normalize_url
            ),
            "connection_factory": (
                main.db_conn
            ),
        }

        args.update(overrides)

        return (
            persist_model_assisted_evidence_snapshot(
                **args
            )
        )

    def count(
        self,
        table,
    ):
        conn = main.db_conn()

        try:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def rows(
        self,
        table,
    ):
        conn = main.db_conn()

        try:
            return [
                dict(row)
                for row in conn.execute(
                    (
                        f"SELECT * FROM {table} "
                        "ORDER BY id"
                    )
                ).fetchall()
            ]
        finally:
            conn.close()

    def test_persists_untrusted_snapshot_into_existing_intelligence_tables(
        self,
    ):
        assembly = self.build()
        result = self.persist(assembly)

        self.assertEqual(
            result["version"],
            (
                MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION
            ),
        )
        self.assertEqual(
            result["status"],
            "persisted",
        )
        self.assertEqual(
            result[
                "persisted_observation"
            ]["kind"],
            "source_observation",
        )

        # #81 assembly IDs and persisted DB IDs
        # intentionally remain separate identities.
        self.assertNotEqual(
            result[
                "assembly_observation_id"
            ],
            result[
                "persisted_observation"
            ]["id"],
        )
        self.assertEqual(
            result[
                "observation_id_map"
            ][
                result[
                    "assembly_observation_id"
                ]
            ],
            result[
                "persisted_observation"
            ]["id"],
        )

        observation = (
            self.rows(
                "source_observations"
            )[0]
        )
        observation_metadata = (
            json.loads(
                observation["metadata_json"]
            )
        )

        self.assertEqual(
            observation["status"],
            "unresolved",
        )
        self.assertEqual(
            observation["claim_summary"],
            "",
        )
        self.assertFalse(
            observation_metadata[
                "training_eligible"
            ]
        )

        evidence = (
            self.rows(
                "evidence_records"
            )[0]
        )
        evidence_metadata = (
            json.loads(
                evidence["metadata_json"]
            )
        )

        self.assertEqual(
            evidence[
                "verification_status"
            ],
            "unverified",
        )
        self.assertEqual(
            evidence["reference_key"],
            (
                f"{assembly['snapshot_id']}:"
                f"{result['snapshot_content_sha256']}"
            ),
        )
        self.assertFalse(
            evidence_metadata[
                "trust"
            ][
                "training_eligible"
            ]
        )
        self.assertEqual(
            evidence_metadata[
                "lineage"
            ][
                "snapshot_content_sha256"
            ],
            result[
                "snapshot_content_sha256"
            ],
        )

        links = self.rows(
            "claim_links"
        )

        self.assertEqual(
            len(links),
            2,
        )
        self.assertEqual(
            {
                row[
                    "relationship_type"
                ]
                for row in links
            },
            {
                "aligned_to"
            },
        )

        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            0,
        )

        source = self.rows(
            "intelligence_sources"
        )[0]

        # The model's claim-specific source role
        # did not mutate the source registry.
        self.assertEqual(
            source["source_type"],
            "publisher",
        )

        self.assertTrue(
            result["policy"][
                "persistence_does_not_change_live_merit"
            ]
        )

    def test_exact_replay_is_idempotent_without_evidence_inflation(
        self,
    ):
        assembly = self.build()

        first = self.persist(
            assembly
        )
        second = self.persist(
            assembly
        )

        self.assertTrue(
            first[
                "persisted_observation"
            ][
                "created"
            ]
        )
        self.assertTrue(
            first[
                "snapshot_evidence"
            ][
                "created"
            ]
        )
        self.assertTrue(
            first[
                "claim_links"
            ][
                "observation"
            ][
                "created"
            ]
        )
        self.assertTrue(
            first[
                "claim_links"
            ][
                "snapshot"
            ][
                "created"
            ]
        )

        self.assertFalse(
            second[
                "persisted_observation"
            ][
                "created"
            ]
        )
        self.assertFalse(
            second[
                "snapshot_evidence"
            ][
                "created"
            ]
        )
        self.assertFalse(
            second[
                "claim_links"
            ][
                "observation"
            ][
                "created"
            ]
        )
        self.assertFalse(
            second[
                "claim_links"
            ][
                "snapshot"
            ][
                "created"
            ]
        )

        self.assertEqual(
            first[
                "persisted_observation"
            ]["id"],
            second[
                "persisted_observation"
            ]["id"],
        )
        self.assertEqual(
            first[
                "snapshot_evidence"
            ]["id"],
            second[
                "snapshot_evidence"
            ]["id"],
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )
        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )
        self.assertEqual(
            self.count(
                "claim_links"
            ),
            2,
        )

    def test_unresolved_dependency_target_is_preserved_without_fake_edge(
        self,
    ):
        assembly = self.build(
            raw=self.raw_semantics(
                source_role="publisher",
                authority_class="none",
                provenance_class=(
                    "attributed_reporting"
                ),
                dependency_status=(
                    "explicit_dependency"
                ),
                dependency_targets=[
                    "Reporter A"
                ],
            )
        )

        result = self.persist(
            assembly
        )

        self.assertEqual(
            result[
                "unresolved_dependency_targets"
            ],
            [
                "Reporter A"
            ],
        )
        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            0,
        )

        evidence = self.rows(
            "evidence_records"
        )[0]
        metadata = json.loads(
            evidence["metadata_json"]
        )

        self.assertEqual(
            metadata[
                "lineage"
            ][
                "unresolved_dependency_targets"
            ],
            [
                "Reporter A"
            ],
        )

    def test_resolved_reporter_identity_selects_reporter_observation_table(
        self,
    ):
        assembly = self.build(
            raw=self.raw_semantics(
                source_role=(
                    "privileged_reporter"
                ),
                authority_class="none",
                provenance_class=(
                    "firsthand_reporting"
                ),
            ),
            actor_id="reporter-a",
        )

        reporter = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    "reporter-a"
                ),
                display_name=(
                    "Reporter A"
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

        result = self.persist(
            assembly,
            reporter_id=reporter["id"],
        )

        self.assertEqual(
            result[
                "persisted_observation"
            ]["kind"],
            "reporter_observation",
        )
        self.assertEqual(
            self.count(
                "source_observations"
            ),
            0,
        )
        self.assertEqual(
            self.count(
                "reporter_observations"
            ),
            1,
        )
        self.assertTrue(
            result["policy"][
                "observation_table_follows_resolved_identity_not_model_role"
            ]
        )

    def test_claim_specific_semantics_do_not_pollute_shared_observation_metadata(
        self,
    ):
        first_assembly = self.build()
        first = self.persist(
            first_assembly
        )

        second_claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|player-a|team-a|"
                    "contract-length"
                ),
                subject_key=(
                    self.claim["subject_key"]
                ),
                canonical_text=(
                    "Player A will sign a "
                    "five-year contract."
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

        source_url = (
            "https://example.com/"
            "team-statement"
        )

        second_assessment = (
            normalize_claim_observation_semantics(
                self.raw_semantics(
                    stance="contradicts"
                ),
                claim_id=(
                    second_claim["id"]
                ),
                source_url=source_url,
                context={},
                evaluator_id=(
                    "semantic-model-v1"
                ),
            )
        )

        second_assembly = (
            build_model_assisted_evidence_snapshot(
                claim={
                    "id": (
                        second_claim["id"]
                    ),
                    "canonical_text": (
                        second_claim[
                            "canonical_text"
                        ]
                    ),
                },
                source={
                    "url": source_url,
                    "actor_id": "team-a",
                    "published_at": (
                        "2026-08-15T02:00:00Z"
                    ),
                    "observed_at": (
                        "2026-08-15T02:05:00Z"
                    ),
                },
                semantic_assessment=(
                    second_assessment
                ),
                as_of=(
                    "2026-08-15T03:00:00Z"
                ),
            )
        )

        second = (
            persist_model_assisted_evidence_snapshot(
                assembly=second_assembly,
                source_id=(
                    self.source["id"]
                ),
                subject_key=(
                    second_claim[
                        "subject_key"
                    ]
                ),
                recorded_at=(
                    "2026-08-15T03:01:00Z"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

        # Same physical reporting observation,
        # different claim-specific evidence.
        self.assertEqual(
            first[
                "persisted_observation"
            ]["id"],
            second[
                "persisted_observation"
            ]["id"],
        )
        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )
        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            2,
        )
        self.assertEqual(
            self.count(
                "claim_links"
            ),
            4,
        )

        observation_metadata = (
            json.loads(
                self.rows(
                    "source_observations"
                )[0][
                    "metadata_json"
                ]
            )
        )

        self.assertNotIn(
            "stance",
            observation_metadata,
        )
        self.assertNotIn(
            "authority_class",
            observation_metadata,
        )
        self.assertNotIn(
            "snapshot_id",
            observation_metadata,
        )

        evidence_metadata = [
            json.loads(
                row["metadata_json"]
            )
            for row in self.rows(
                "evidence_records"
            )
        ]

        proposed_stances = {
            metadata[
                "lineage"
            ][
                "stance"
            ]
            for metadata
            in evidence_metadata
        }

        self.assertEqual(
            proposed_stances,
            {
                "supports",
                "contradicts",
            },
        )

    def test_same_logical_snapshot_changed_semantics_appends_hashed_revision(
        self,
    ):
        first_assembly = self.build()
        first = self.persist(
            first_assembly
        )

        changed_assembly = self.build(
            raw=self.raw_semantics(
                stance="contradicts"
            )
        )

        # #81 logical snapshot ID intentionally
        # remains the same here.
        self.assertEqual(
            first_assembly[
                "snapshot_id"
            ],
            changed_assembly[
                "snapshot_id"
            ],
        )

        second = self.persist(
            changed_assembly
        )

        self.assertEqual(
            first[
                "persisted_observation"
            ]["id"],
            second[
                "persisted_observation"
            ]["id"],
        )

        # But changed snapshot content must never
        # silently overwrite/reuse the old revision.
        self.assertNotEqual(
            first[
                "snapshot_content_sha256"
            ],
            second[
                "snapshot_content_sha256"
            ],
        )
        self.assertNotEqual(
            first[
                "snapshot_evidence"
            ]["id"],
            second[
                "snapshot_evidence"
            ]["id"],
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )
        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            2,
        )

        # One shared neutral observation link +
        # one snapshot link per revision.
        self.assertEqual(
            self.count(
                "claim_links"
            ),
            3,
        )

        stances = {
            json.loads(
                row["metadata_json"]
            )[
                "lineage"
            ][
                "stance"
            ]
            for row in self.rows(
                "evidence_records"
            )
        }

        self.assertEqual(
            stances,
            {
                "supports",
                "contradicts",
            },
        )

    def test_preflight_rejects_wrong_source_and_training_eligible_tamper(
        self,
    ):
        assembly = self.build()

        wrong_source = (
            main.upsert_intelligence_source(
                url=(
                    "https://other.example/"
                    "report"
                ),
                display_name=(
                    "Other Source"
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

        with self.assertRaises(
            ValueError
        ):
            self.persist(
                assembly,
                source_id=(
                    wrong_source["id"]
                ),
            )

        tampered = copy.deepcopy(
            assembly
        )
        tampered[
            "authority_adjudication"
        ][
            "learning_signal"
        ][
            "training_eligible"
        ] = True

        with self.assertRaises(
            ValueError
        ):
            self.persist(
                tampered
            )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            0,
        )
        self.assertEqual(
            self.count(
                "reporter_observations"
            ),
            0,
        )
        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            0,
        )
        self.assertEqual(
            self.count(
                "claim_links"
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
