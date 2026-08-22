from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.claim_support_graph import (
    build_claim_support_graph,
    build_story_support_overview,
)
from app.routes import intelligence_admin


NOW = "2026-08-22T06:30:00+00:00"


class ClaimSupportGraphTests(unittest.TestCase):
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
        for source_id, source_key, domain in (
            ("source-a", "source:a", "a.example"),
            ("source-b", "source:b", "b.example"),
            ("source-c", "source:c", "c.example"),
        ):
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type, canonical_domain,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, 'publisher', ?, ?, ?, '{}')
                """,
                (source_id, source_key, source_id, domain, NOW, NOW),
            )

        conn.execute(
            """
            INSERT INTO intelligence_reporters (
              id, identity_key, display_name, first_seen_at, last_seen_at, metadata_json
            ) VALUES ('reporter-c', 'reporter:c', 'Reporter C', ?, ?, '{}')
            """,
            (NOW, NOW),
        )

        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'claim-1', 'claim:one', 'player:one',
              'Player One agrees move to Arsenal', 'assertion', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO intelligence_stories (
              id, canonical_key, canonical_title, status,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'story-1', 'story:one', 'Player One to Arsenal',
              'developing', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO story_claim_links (
              story_id, claim_id, relationship_type, link_basis,
              linked_at, metadata_json
            ) VALUES (
              'story-1', 'claim-1', 'exact_claim_group',
              'downstream_exact_common_claim_id', ?, '{}'
            )
            """,
            (NOW,),
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
            INSERT INTO evidence_records (
              id, evidence_key, evidence_type, subject_key, claim_summary,
              verification_status, observed_at, recorded_at, metadata_json
            ) VALUES (
              'direct-evidence', 'evidence:direct', 'official_statement',
              'player:one', 'Direct evidence', 'verified', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, evidence_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'link-direct-evidence', 'claim-1', 'direct-evidence',
              'supports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )

    def _add_dependency(self):
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO observation_dependencies (
                  id,
                  downstream_source_observation_id,
                  upstream_source_observation_id,
                  relationship_type,
                  confidence,
                  observed_at,
                  recorded_at,
                  metadata_json
                ) VALUES (
                  'dependency-a-b', 'obs-b', 'obs-a',
                  'derived_from', 0.95, ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

    def _add_independence(
        self,
        *,
        assertion_status="verified",
        evidence_status="verified",
        assertion_id="independence-a-b",
    ):
        evidence_id = "evidence-" + assertion_id
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO evidence_records (
                  id, evidence_key, evidence_type, subject_key, claim_summary,
                  verification_status, observed_at, recorded_at, metadata_json
                ) VALUES (?, ?, 'provenance_review', 'player:one',
                          'Independence provenance', ?, ?, ?, '{}')
                """,
                (
                    evidence_id,
                    "key:" + assertion_id,
                    evidence_status,
                    NOW,
                    NOW,
                ),
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
                ) VALUES (?, 'obs-a', 'obs-b', ?, ?, 0.97, ?, ?, '{}')
                """,
                (
                    assertion_id,
                    evidence_id,
                    assertion_status,
                    NOW,
                    NOW,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_two_different_sources_do_not_imply_independence(self):
        result = build_claim_support_graph(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["support_state"],
            "multiple_observations_dependency_unknown",
        )
        self.assertEqual(result["counts"]["observations"], 2)
        self.assertEqual(result["counts"]["distinct_sources"], 2)
        self.assertEqual(
            result["counts"]["qualified_verified_independent_pairs"], 0
        )
        self.assertTrue(
            result["policy"]["different_sources_do_not_imply_independence"]
        )
        self.assertFalse(result["policy"]["establishes_truth"])
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_explicit_dependency_is_surfaced_and_not_counted_independent(self):
        self._add_dependency()

        result = build_claim_support_graph(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["support_state"], "dependency_present")
        self.assertEqual(result["counts"]["dependency_edges"], 1)
        self.assertEqual(result["counts"]["dependency_pairs"], 1)
        self.assertEqual(
            result["counts"]["qualified_verified_independent_pairs"], 0
        )
        self.assertEqual(
            result["dependency_edges"][0]["relationship_type"],
            "derived_from",
        )

    def test_verified_assertion_with_verified_provenance_qualifies_pair(self):
        self._add_independence()

        result = build_claim_support_graph(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(
            result["support_state"], "verified_independence_present"
        )
        self.assertEqual(
            result["counts"]["qualified_verified_independent_pairs"], 1
        )
        self.assertEqual(len(result["verified_independent_pairs"]), 1)
        self.assertTrue(
            result["independence_assertions"][0]
            ["qualified_verified_independence"]
        )
        self.assertFalse(result["policy"]["establishes_truth"])

    def test_unverified_assertion_remains_unverified(self):
        self._add_independence(assertion_status="unverified")

        result = build_claim_support_graph(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(
            result["support_state"],
            "multiple_observations_independence_unverified",
        )
        self.assertEqual(
            result["counts"]["unverified_independence_assertions"], 1
        )
        self.assertEqual(
            result["counts"]["qualified_verified_independent_pairs"], 0
        )

    def test_verified_assertion_with_unverified_evidence_is_incomplete(self):
        self._add_independence(evidence_status="unverified")

        result = build_claim_support_graph(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(
            result["support_state"], "independence_verification_incomplete"
        )
        self.assertEqual(
            result["counts"]["independence_verification_gaps"], 1
        )
        self.assertEqual(
            result["counts"]["qualified_verified_independent_pairs"], 0
        )

    def test_dependency_and_verified_independence_conflict_fails_closed(self):
        self._add_dependency()
        self._add_independence()

        result = build_claim_support_graph(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["support_state"], "provenance_conflict")
        self.assertEqual(result["counts"]["provenance_conflicts"], 1)
        self.assertEqual(len(result["provenance_conflicts"]), 1)
        self.assertTrue(
            result["policy"]
            ["dependency_and_verified_independence_conflict_is_surfaced"]
        )

    def test_story_overview_preserves_claim_boundaries(self):
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id, canonical_key, subject_key, canonical_text, claim_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (
                  'claim-2', 'claim:two', 'player:two',
                  'Player Two remains at Club', 'assertion', ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.execute(
                """
                INSERT INTO story_claim_links (
                  story_id, claim_id, relationship_type, link_basis,
                  linked_at, metadata_json
                ) VALUES (
                  'story-1', 'claim-2', 'exact_claim_group',
                  'downstream_exact_common_claim_id', ?, '{}'
                )
                """,
                (NOW,),
            )
            conn.execute(
                """
                INSERT INTO reporter_observations (
                  id, reporter_id, source_id, subject_key, observation_type,
                  status, claim_summary, provenance_url,
                  observed_at, recorded_at, metadata_json
                ) VALUES (
                  'obs-c', 'reporter-c', 'source-c', 'player:two',
                  'article_headline_report', 'unresolved',
                  'Player Two remains at Club', '', ?, ?, '{}'
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
                  'link-obs-c', 'claim-2', 'obs-c', 'reports', ?, ?, '{}'
                )
                """,
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

        result = build_story_support_overview(
            story_id="story-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["claims"], 2)
        self.assertEqual(len(result["claims"]), 2)
        self.assertEqual(
            set(item["claim"]["id"] for item in result["claims"]),
            {"claim-1", "claim-2"},
        )
        self.assertTrue(
            result["policy"]
            ["different_claims_are_not_collapsed_into_one_corroboration_result"]
        )
        self.assertFalse(result["policy"]["establishes_truth"])

    def test_missing_records_return_explicit_not_found(self):
        claim = build_claim_support_graph(
            claim_id="missing",
            connection_factory=self.factory,
        )
        story = build_story_support_overview(
            story_id="missing",
            connection_factory=self.factory,
        )

        self.assertEqual(claim["status"], "not_found")
        self.assertEqual(story["status"], "not_found")

    def test_admin_support_routes_are_guarded(self):
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

        claim_response = client.get(
            "/admin/intelligence/claims/claim-1/support-graph"
        )
        story_response = client.get(
            "/admin/intelligence/stories/story-1/support-overview"
        )
        missing_response = client.get(
            "/admin/intelligence/claims/missing/support-graph"
        )

        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(story_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(len(guarded), 3)


if __name__ == "__main__":
    unittest.main()
