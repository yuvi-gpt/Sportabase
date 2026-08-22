from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.claim_state import (
    build_claim_state,
    build_story_claim_state_overview,
)
from app.routes import intelligence_admin


NOW = "2026-08-22T07:00:00+00:00"
EARLIER = "2026-08-01T07:00:00+00:00"


class ClaimStateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"
        conn = self.factory()
        try:
            conn.executescript(SCHEMA)
            self._seed(conn)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def _seed(self, conn):
        for source_id, key, name, domain in (
            ("source-a", "source:a", "Outlet A", "a.example"),
            ("source-b", "source:b", "Outlet B", "b.example"),
            ("source-c", "source:c", "Outlet C", "c.example"),
        ):
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type, canonical_domain,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, 'publisher', ?, ?, ?, '{}')
                """,
                (source_id, key, name, domain, EARLIER, NOW),
            )

        conn.execute(
            """
            INSERT INTO intelligence_reporters (
              id, identity_key, display_name, first_seen_at, last_seen_at, metadata_json
            ) VALUES ('reporter-a', 'reporter:a', 'Reporter A', ?, ?, '{}')
            """,
            (EARLIER, NOW),
        )

        for claim_id, canonical_key, subject_key, text in (
            (
                "claim-1",
                "claim:one",
                "player:one",
                "Player One agrees move to Arsenal",
            ),
            (
                "claim-2",
                "claim:two",
                "player:two",
                "Player Two remains at Club",
            ),
        ):
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id, canonical_key, subject_key, canonical_text, claim_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, ?, 'assertion', ?, ?, '{}')
                """,
                (claim_id, canonical_key, subject_key, text, EARLIER, NOW),
            )

        conn.execute(
            """
            INSERT INTO intelligence_stories (
              id, canonical_key, canonical_title, status,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'story-1', 'story:one', 'Transfer story', 'developing', ?, ?, '{}'
            )
            """,
            (EARLIER, NOW),
        )
        for claim_id in ("claim-1", "claim-2"):
            conn.execute(
                """
                INSERT INTO story_claim_links (
                  story_id, claim_id, relationship_type, link_basis,
                  linked_at, metadata_json
                ) VALUES (
                  'story-1', ?, 'exact_claim_group',
                  'downstream_exact_common_claim_id', ?, '{}'
                )
                """,
                (claim_id, NOW),
            )

        for observation_id, source_id in (
            ("obs-a", "source-a"),
            ("obs-b", "source-b"),
        ):
            conn.execute(
                """
                INSERT INTO source_observations (
                  id, source_id, subject_key, observation_type, status,
                  claim_summary, provenance_url, observed_at, recorded_at, metadata_json
                ) VALUES (?, ?, 'player:one', 'article_headline_report', 'unresolved',
                          'Player One agrees move to Arsenal', '', ?, ?, '{}')
                """,
                (observation_id, source_id, NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO claim_links (
                  id, claim_id, source_observation_id, relationship_type,
                  observed_at, recorded_at, metadata_json
                ) VALUES (?, 'claim-1', ?, 'reports', ?, ?, '{}')
                """,
                ("link-" + observation_id, observation_id, NOW, NOW),
            )

        conn.execute(
            """
            INSERT INTO reporter_observations (
              id, reporter_id, source_id, subject_key, observation_type,
              status, claim_summary, provenance_url,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'reporter-obs-a', 'reporter-a', 'source-a', 'player:one',
              'social_report', 'unresolved', 'Player One move update', '', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, reporter_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'link-reporter-obs-a', 'claim-1', 'reporter-obs-a', 'reports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )

        conn.execute(
            """
            INSERT INTO source_observations (
              id, source_id, subject_key, observation_type, status,
              claim_summary, provenance_url, observed_at, recorded_at, metadata_json
            ) VALUES (
              'obs-a-history', 'source-a', 'player:one', 'article_update', 'resolved',
              'Older Player One report', '', ?, ?, '{}'
            )
            """,
            (EARLIER, EARLIER),
        )

        self._insert_evidence(
            conn,
            evidence_id="support-evidence",
            evidence_key="evidence:support",
            subject_key="player:one",
            relationship_type="supports",
            claim_id="claim-1",
            verification_status="verified",
        )

        conn.execute(
            """
            INSERT INTO source_observations (
              id, source_id, subject_key, observation_type, status,
              claim_summary, provenance_url, observed_at, recorded_at, metadata_json
            ) VALUES (
              'obs-c', 'source-c', 'player:two', 'article_headline_report', 'unresolved',
              'Player Two remains at Club', '', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, source_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'link-obs-c', 'claim-2', 'obs-c', 'reports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )

    def _insert_evidence(
        self,
        conn,
        *,
        evidence_id,
        evidence_key,
        subject_key,
        relationship_type,
        claim_id,
        verification_status="verified",
        evidence_type="official_statement",
    ):
        conn.execute(
            """
            INSERT INTO evidence_records (
              id, evidence_key, evidence_type, subject_key, claim_summary,
              verification_status, observed_at, recorded_at, metadata_json
            ) VALUES (?, ?, ?, ?, 'Evidence record', ?, ?, ?, '{}')
            """,
            (
                evidence_id,
                evidence_key,
                evidence_type,
                subject_key,
                verification_status,
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, evidence_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, '{}')
            """,
            (
                "link-" + evidence_id,
                claim_id,
                evidence_id,
                relationship_type,
                NOW,
                NOW,
            ),
        )

    def _add_verified_independence(self):
        conn = self.factory()
        try:
            self._insert_evidence(
                conn,
                evidence_id="independence-evidence",
                evidence_key="evidence:independence",
                subject_key="player:one",
                relationship_type="context",
                claim_id="claim-1",
                verification_status="verified",
                evidence_type="provenance_review",
            )
            conn.execute(
                """
                INSERT INTO observation_independence_assertions (
                  id,
                  observation_a_source_observation_id,
                  observation_b_source_observation_id,
                  provenance_evidence_id,
                  verification_status,
                  confidence,
                  observed_at,
                  recorded_at,
                  metadata_json
                ) VALUES (
                  'independence-a-b', 'obs-a', 'obs-b', 'independence-evidence',
                  'verified', 0.98, ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

    def test_verified_supporting_evidence_is_distinct_from_truth(self):
        result = build_claim_state(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["claim_state"],
            "verified_supporting_evidence_present",
        )
        self.assertEqual(result["evidence"]["counts"]["verified_supporting"], 1)
        self.assertEqual(result["support"]["distinct_sources"], 2)
        self.assertEqual(result["support"]["verified_independent_pairs"], 0)
        self.assertTrue(
            result["policy"]["claim_state_is_evidence_posture_not_truth"]
        )
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_verified_independence_upgrades_provenance_state_without_truth_inference(self):
        self._add_verified_independence()

        result = build_claim_state(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(
            result["claim_state"],
            "verified_supporting_evidence_and_independence",
        )
        self.assertEqual(result["support"]["verified_independent_pairs"], 1)
        self.assertTrue(result["policy"]["independence_requires_verified_provenance"])

    def test_verified_support_and_counterevidence_surface_conflict(self):
        conn = self.factory()
        try:
            self._insert_evidence(
                conn,
                evidence_id="counter-evidence",
                evidence_key="evidence:counter",
                subject_key="player:one",
                relationship_type="contradicts",
                claim_id="claim-1",
                verification_status="verified",
            )
            conn.commit()
        finally:
            conn.close()

        result = build_claim_state(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["claim_state"], "verified_evidence_conflict")
        self.assertEqual(result["evidence"]["counts"]["verified_conflicting"], 1)
        self.assertEqual(result["conflict_signals"][0]["type"], "verified_evidence_conflict")

    def test_reporting_history_is_descriptive_and_subject_scoped(self):
        result = build_claim_state(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        source_a = next(
            item
            for item in result["reporting_history"]["sources"]
            if item["identity_id"] == "source-a"
        )
        reporter_a = result["reporting_history"]["reporters"][0]

        self.assertEqual(source_a["observation_count"], 2)
        self.assertEqual(source_a["by_observation_type"]["article_update"], 1)
        self.assertEqual(source_a["by_observation_type"]["article_headline_report"], 1)
        self.assertEqual(reporter_a["identity_id"], "reporter-a")
        self.assertEqual(reporter_a["observation_count"], 1)
        self.assertTrue(result["policy"]["history_is_descriptive_not_reputation_scoring"])
        self.assertTrue(result["policy"]["no_arbitrary_source_authority_weights"])

    def test_story_rollup_preserves_claim_boundaries_and_mixed_evidence(self):
        conn = self.factory()
        try:
            self._insert_evidence(
                conn,
                evidence_id="claim-2-counter",
                evidence_key="evidence:claim-2-counter",
                subject_key="player:two",
                relationship_type="refutes",
                claim_id="claim-2",
                verification_status="verified",
            )
            conn.commit()
        finally:
            conn.close()

        result = build_story_claim_state_overview(
            story_id="story-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["story_state"], "mixed_verified_evidence_across_claims")
        self.assertEqual(result["counts"]["claims"], 2)
        self.assertEqual(
            result["counts"]["claims_with_verified_supporting_evidence"], 1
        )
        self.assertEqual(
            result["counts"]["claims_with_verified_counterevidence"], 1
        )
        self.assertTrue(
            result["policy"]["different_claims_do_not_corroborate_each_other"]
        )

    def test_not_found_and_admin_routes(self):
        missing_claim = build_claim_state(
            claim_id="missing",
            connection_factory=self.factory,
        )
        missing_story = build_story_claim_state_overview(
            story_id="missing",
            connection_factory=self.factory,
        )
        self.assertEqual(missing_claim["status"], "not_found")
        self.assertEqual(missing_story["status"], "not_found")

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

        claim_response = client.get("/admin/intelligence/claims/claim-1/state")
        story_response = client.get(
            "/admin/intelligence/stories/story-1/claim-state-overview"
        )
        missing_response = client.get("/admin/intelligence/claims/missing/state")

        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(story_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(len(guarded), 3)


if __name__ == "__main__":
    unittest.main()
