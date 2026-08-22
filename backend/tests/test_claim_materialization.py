from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.claim_materialization import (
    ClaimMaterializationConflictError,
    ClaimMaterializationError,
    route_and_materialize_claim_semantics,
)
from app.intelligence.claims.router import (
    CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
)
from app.routes import intelligence_admin


NOW = "2026-08-22T07:00:00+00:00"
SUBJECT = "football|player|jude-bellingham"
DESTINATION = "football|club|real-madrid"
ORIGIN_A = "football|club|borussia-dortmund"
ORIGIN_B = "football|club|bayern-munich"
ALLOWED = [SUBJECT, DESTINATION, ORIGIN_A, ORIGIN_B]


class ClaimMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"
        conn = self.factory()
        try:
            conn.executescript(SCHEMA)
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type, canonical_domain,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (
                  'source-a', 'source:a', 'Source A', 'publisher',
                  'a.example', ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO source_observations (
                  id, source_id, subject_key, observation_type, status,
                  claim_summary, provenance_url, confidence,
                  observed_at, recorded_at, metadata_json
                ) VALUES (
                  'obs-a', 'source-a', ?, 'article_headline_report',
                  'unresolved', 'Bellingham completed move to Real Madrid',
                  '', 0.9, ?, ?, '{}'
                )
                """,
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def _output(
        self,
        *,
        status="extracted",
        origin=None,
        effective_period=None,
        reason="",
    ):
        if status == "insufficient":
            return {
                "version": CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
                "status": "insufficient",
                "candidate": None,
                "reason": reason or "Not enough structured semantics.",
            }

        roles = {}
        facets = {}
        if status == "extracted":
            roles["destination"] = DESTINATION
        if origin:
            roles["origin"] = origin
        if effective_period:
            facets["effective_period"] = effective_period

        return {
            "version": CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
            "status": status,
            "candidate": {
                "subject_key": SUBJECT,
                "event_type": "transfer",
                "state": "completed",
                "negated": False,
                "roles": roles,
                "facets": facets,
            },
            "reason": reason,
        }

    def _materialize(self, output=None, **kwargs):
        values = {
            "router_output": output or self._output(),
            "expected_subject_key": SUBJECT,
            "allowed_entity_keys": ALLOWED,
            "claim_text": "Bellingham completed move to Real Madrid",
            "observed_at": NOW,
            "connection_factory": self.factory,
            "source_observation_id": "obs-a",
            "relationship_type": "reports",
            "confidence": 0.9,
        }
        values.update(kwargs)
        return route_and_materialize_claim_semantics(**values)

    def _claim_rows(self):
        conn = self.factory()
        try:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM intelligence_claims ORDER BY id"
                ).fetchall()
            ]
        finally:
            conn.close()

    def _claim_links(self):
        conn = self.factory()
        try:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM claim_links ORDER BY id"
                ).fetchall()
            ]
        finally:
            conn.close()

    def test_extracted_semantics_materialize_link_and_projection(self):
        result = self._materialize()

        self.assertEqual(result["status"], "materialized")
        self.assertTrue(result["created"])
        self.assertEqual(result["router_status"], "extracted")
        self.assertEqual(result["route"], "full_identity")
        self.assertEqual(result["claim"]["subject_key"], SUBJECT)
        self.assertTrue(result["claim"]["canonical_key"].startswith("structured-claim|"))
        self.assertEqual(result["link"]["target_type"], "source_observation")
        self.assertTrue(result["link"]["created"])
        self.assertEqual(result["projection"]["status"], "ok")
        self.assertEqual(
            result["projection"]["claim_state"]["support"]["observation_count"],
            1,
        )
        self.assertEqual(result["subject_timeline"]["status"], "ok")
        self.assertEqual(result["subject_timeline"]["counts"]["claims"], 1)
        self.assertTrue(result["policy"]["no_model_call_performed"])
        self.assertFalse(result["policy"]["affects_live_merit"])

        rows = self._claim_rows()
        links = self._claim_links()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(links), 1)
        metadata = json.loads(rows[0]["metadata_json"])
        self.assertEqual(
            metadata["structured_claim"]["roles"]["destination"],
            DESTINATION,
        )

    def test_same_core_non_conflicting_specificity_merges_into_one_claim(self):
        first = self._materialize(
            self._output(origin=ORIGIN_A),
            source_observation_id=None,
        )
        second = self._materialize(
            self._output(origin=ORIGIN_A, effective_period="2023"),
            source_observation_id=None,
            observed_at="2026-08-22T07:05:00+00:00",
        )

        self.assertEqual(first["claim"]["id"], second["claim"]["id"])
        self.assertFalse(second["created"])
        self.assertEqual(
            second["identity"]["candidate"]["roles"]["origin"],
            ORIGIN_A,
        )
        self.assertEqual(
            second["identity"]["candidate"]["facets"]["effective_period"],
            "2023",
        )
        self.assertEqual(len(second["identity"]["specific_fingerprints"]), 2)
        self.assertEqual(len(self._claim_rows()), 1)

    def test_same_core_material_conflict_fails_closed_without_mutation(self):
        first = self._materialize(
            self._output(origin=ORIGIN_A),
            source_observation_id=None,
        )
        rows_before = self._claim_rows()

        with self.assertRaises(ClaimMaterializationConflictError):
            self._materialize(
                self._output(origin=ORIGIN_B),
                source_observation_id=None,
                observed_at="2026-08-22T07:10:00+00:00",
            )

        rows_after = self._claim_rows()
        self.assertEqual(rows_before, rows_after)
        self.assertEqual(len(rows_after), 1)
        self.assertEqual(rows_after[0]["id"], first["claim"]["id"])

    def test_partial_semantics_do_not_create_claim_identity(self):
        result = self._materialize(
            self._output(status="partial", reason="Destination is missing."),
            source_observation_id=None,
        )

        self.assertEqual(result["status"], "not_materialized")
        self.assertEqual(result["router_status"], "partial")
        self.assertEqual(result["route"], "partial_semantics")
        self.assertIsNone(result["claim"])
        self.assertIsNone(result["projection"])
        self.assertEqual(len(self._claim_rows()), 0)
        self.assertTrue(
            result["policy"]["partial_semantics_are_not_persisted_as_claim_identity"]
        )

    def test_insufficient_semantics_do_not_create_claim_identity(self):
        result = self._materialize(
            self._output(status="insufficient"),
            source_observation_id=None,
        )

        self.assertEqual(result["status"], "not_materialized")
        self.assertEqual(result["router_status"], "insufficient")
        self.assertEqual(result["route"], "none")
        self.assertEqual(len(self._claim_rows()), 0)

    def test_idempotent_replay_does_not_duplicate_claim_or_link(self):
        first = self._materialize()
        second = self._materialize()

        self.assertEqual(first["claim"]["id"], second["claim"]["id"])
        self.assertFalse(second["created"])
        self.assertFalse(second["link"]["created"])
        self.assertEqual(len(self._claim_rows()), 1)
        self.assertEqual(len(self._claim_links()), 1)

    def test_multiple_link_targets_fail_before_writes(self):
        with self.assertRaises(ClaimMaterializationError):
            self._materialize(
                source_observation_id="obs-a",
                evidence_id="evidence-does-not-matter",
            )

        self.assertEqual(len(self._claim_rows()), 0)
        self.assertEqual(len(self._claim_links()), 0)

    def test_missing_link_target_rolls_back_claim_atomically(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._materialize(source_observation_id="missing-observation")

        self.assertEqual(len(self._claim_rows()), 0)
        self.assertEqual(len(self._claim_links()), 0)

    def test_admin_materialization_route_is_guarded_and_returns_projection(self):
        guarded = []

        def require_admin(request):
            guarded.append(request.url.path)

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=require_admin,
                connection_factory=self.factory,
            )
        )
        client = TestClient(app)

        response = client.post(
            "/admin/intelligence/claims/materialize-semantic-router",
            json={
                "expected_subject_key": SUBJECT,
                "claim_text": "Bellingham completed move to Real Madrid",
                "allowed_entity_keys": ALLOWED,
                "router_output": self._output(),
                "observed_at": NOW,
                "source_observation_id": "obs-a",
                "relationship_type": "reports",
                "confidence": 0.9,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "materialized")
        self.assertEqual(payload["projection"]["status"], "ok")
        self.assertEqual(
            guarded,
            ["/admin/intelligence/claims/materialize-semantic-router"],
        )

    def test_admin_materialization_conflict_returns_409_and_preserves_claim(self):
        guarded = []

        def require_admin(request):
            guarded.append(request.url.path)

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=require_admin,
                connection_factory=self.factory,
            )
        )
        client = TestClient(app)

        base = {
            "expected_subject_key": SUBJECT,
            "claim_text": "Bellingham completed move to Real Madrid",
            "allowed_entity_keys": ALLOWED,
            "observed_at": NOW,
        }
        first = client.post(
            "/admin/intelligence/claims/materialize-semantic-router",
            json={**base, "router_output": self._output(origin=ORIGIN_A)},
        )
        second = client.post(
            "/admin/intelligence/claims/materialize-semantic-router",
            json={
                **base,
                "observed_at": "2026-08-22T07:10:00+00:00",
                "router_output": self._output(origin=ORIGIN_B),
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("conflicts", second.json()["detail"])
        self.assertEqual(len(self._claim_rows()), 1)
        self.assertEqual(len(guarded), 2)


if __name__ == "__main__":
    unittest.main()
