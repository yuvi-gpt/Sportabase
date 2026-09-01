from __future__ import annotations

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_materialization import materialize_canonical_claim
from app.intelligence.claim_state import build_claim_state
from app.intelligence.claim_support_graph import (
    build_claim_support_graph,
    build_story_support_overview,
)
from app.routes import intelligence_admin
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
    materialize_canonical_claim_story,
)


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
        self.assertEqual(
            result["evidence_graph_version"], "claim-evidence-graph-v1"
        )
        self.assertEqual(result["version"], "claim-support-graph-v1")
        self.assertIn("claim:claim-1", {node["id"] for node in result["nodes"]})
        self.assertEqual(result["graph_summary"]["report_edge_count"], 2)
        self.assertEqual(result["graph_summary"]["support_edge_count"], 1)
        report_edges = [
            edge for edge in result["edges"]
            if edge["edge_category"] == "claim_link"
            and edge["relationship_type"] == "reports"
        ]
        self.assertEqual(len(report_edges), 2)
        self.assertTrue(all(edge["relationship_type"] != "supports" for edge in report_edges))
        self.assertTrue(result["policy"]["reports_does_not_establish_support"])
        self.assertNotIn("independent_source_count", result["graph_summary"])

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

    def test_evidence_graph_preserves_open_vocabulary_and_full_evidence(self):
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE evidence_records SET evidence_type='primary_document', "
                "canonical_url='https://official.example/document', "
                "reference_key='document:1', published_at=?, metadata_json=? "
                "WHERE id='direct-evidence'",
                (NOW, '{"provenance_class":"structured_fact"}'),
            )
            conn.execute(
                "INSERT INTO claim_links (id,claim_id,evidence_id,relationship_type,"
                "observed_at,recorded_at,metadata_json) VALUES "
                "('alias-link','claim-1','direct-evidence','confirm',?,?, '{}'),"
                "('unknown-link','claim-1','direct-evidence','mentions',?,?, '{}')",
                (NOW, NOW, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()

        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        evidence = next(node for node in result["nodes"] if node["id"] == "evidence:direct-evidence")
        self.assertEqual(evidence["evidence_type"], "primary_document")
        self.assertTrue(evidence["recognized_evidence_type"])
        self.assertEqual(evidence["reference_key"], "document:1")
        self.assertEqual(evidence["metadata"]["provenance_class"], "structured_fact")
        relationships = {
            edge["relationship_type"]: edge["relationship_classification"]
            for edge in result["edges"] if edge["edge_category"] == "claim_link"
        }
        self.assertEqual(relationships["confirm"], "recognized_aggregation_alias")
        self.assertEqual(relationships["mentions"], "unrecognized")
        self.assertEqual(result["graph_summary"]["support_edge_count"], 1)
        self.assertIn(
            "unrecognized_claim_relationship",
            {item["anomaly_type"] for item in result["anomalies"]},
        )
        self.assertFalse(result["policy"]["establishes_truth"])

    def test_evidence_links_and_observation_context_are_first_class(self):
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO media_items (id,canonical_url,mode,source_id,title,"
                "latest_content_hash,first_seen_at,last_seen_at,metadata_json) "
                "VALUES ('media-a','https://a.example/story','article','source-a',"
                "'Story','hash',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute("UPDATE source_observations SET media_item_id='media-a', story_id='story-1' WHERE id='obs-a'")
            for link_id, column, target in (
                ("ev-media", "media_item_id", "media-a"),
                ("ev-story", "story_id", "story-1"),
                ("ev-source", "source_id", "source-a"),
                ("ev-reporter", "reporter_id", "reporter-c"),
            ):
                conn.execute(
                    f"INSERT INTO evidence_links (id,evidence_id,{column},relationship_type,linked_at,metadata_json) VALUES (?, 'direct-evidence', ?, 'provenance', ?, '{{}}')",
                    (link_id, target, NOW),
                )
            conn.commit()
        finally:
            conn.close()

        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        node_ids = {node["id"] for node in result["nodes"]}
        self.assertTrue({"media:media-a", "source:source-a", "reporter:reporter-c", "story:story-1"} <= node_ids)
        evidence_edges = [edge for edge in result["edges"] if edge["edge_category"] == "evidence_context"]
        self.assertEqual(len(evidence_edges), 4)
        structural = {edge["relationship_type"] for edge in result["edges"] if edge["edge_category"] == "structural_context"}
        self.assertTrue({"observed_by_source", "reported_in_media", "associated_exact_story"} <= structural)

    def test_dependency_direction_cycle_and_unknown_are_conservative(self):
        self._add_dependency()
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO observation_dependencies (id,downstream_source_observation_id,"
                "upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) "
                "VALUES ('dependency-b-a','obs-a','obs-b','derived_from',?,?, '{}'),"
                "('dependency-unknown','obs-a','obs-b','copied_from',?,?, '{}')",
                (NOW, NOW, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        dependency = next(edge for edge in result["edges"] if edge["id"] == "dependency:dependency-a-b")
        self.assertEqual(dependency["source"], "source_observation:obs-b")
        self.assertEqual(dependency["target"], "source_observation:obs-a")
        anomaly_types = {item["anomaly_type"] for item in result["anomalies"]}
        self.assertIn("dependency_cycle", anomaly_types)
        self.assertIn("potential_or_malformed_dependency", anomaly_types)

    def test_route_returns_409_for_unsafe_graph_json(self):
        conn = self.factory()
        try:
            conn.execute("UPDATE evidence_records SET metadata_json='not-json' WHERE id='direct-evidence'")
            conn.commit()
        finally:
            conn.close()
        app = FastAPI()
        app.include_router(intelligence_admin.build_router(require_admin=lambda request: None, connection_factory=self.factory))
        response = TestClient(app).get("/admin/intelligence/claims/claim-1/support-graph")
        self.assertEqual(response.status_code, 409)

    def test_all_canonical_claim_relationships_remain_literal(self):
        conn = self.factory()
        try:
            for relationship in ("contradicts", "aligned_to"):
                conn.execute(
                    "INSERT INTO claim_links (id,claim_id,evidence_id,relationship_type,"
                    "observed_at,recorded_at,metadata_json) VALUES (?,?,?,?,?,?, '{}')",
                    ("link-" + relationship, "claim-1", "direct-evidence", relationship, NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        relationships = {
            edge["relationship_type"]: edge["relationship_classification"]
            for edge in result["edges"] if edge["edge_category"] == "claim_link"
        }
        self.assertEqual(
            {name: relationships[name] for name in ("reports", "supports", "contradicts", "aligned_to")},
            {name: "canonical" for name in ("reports", "supports", "contradicts", "aligned_to")},
        )
        self.assertEqual(result["graph_summary"]["report_edge_count"], 2)
        self.assertEqual(result["graph_summary"]["support_edge_count"], 1)
        self.assertEqual(result["graph_summary"]["contradiction_edge_count"], 1)
        self.assertEqual(result["graph_summary"]["aligned_edge_count"], 1)

    def test_unknown_evidence_and_evidence_link_vocabularies_remain_open(self):
        conn = self.factory()
        try:
            conn.execute("UPDATE evidence_records SET evidence_type='field_note' WHERE id='direct-evidence'")
            conn.execute(
                "INSERT INTO evidence_links (id,evidence_id,source_id,relationship_type,linked_at,metadata_json) "
                "VALUES ('unknown-evidence-link','direct-evidence','source-a','verifies_entity_participation',?, '{}')",
                (NOW,),
            )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        evidence = next(node for node in result["nodes"] if node["node_type"] == "evidence")
        self.assertEqual(evidence["evidence_type"], "field_note")
        self.assertFalse(evidence["recognized_evidence_type"])
        edge = next(edge for edge in result["edges"] if edge["id"] == "evidence_link:unknown-evidence-link")
        self.assertEqual(edge["relationship_type"], "verifies_entity_participation")
        self.assertIn("unrecognized_evidence_link_relationship", {item["anomaly_type"] for item in result["anomalies"]})
        self.assertFalse(result["policy"]["establishes_truth"])

    def test_cross_subject_and_malformed_evidence_fail_closed(self):
        for assignment in (
            "subject_key='player:other'",
            "metadata_json='not-json'",
            "observed_at='2026-08-22T06:30:00'",
        ):
            with self.subTest(assignment=assignment):
                conn = self.factory()
                try:
                    original = dict(conn.execute("SELECT * FROM evidence_records WHERE id='direct-evidence'").fetchone())
                    conn.execute("UPDATE evidence_records SET " + assignment + " WHERE id='direct-evidence'")
                    conn.commit()
                finally:
                    conn.close()
                with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
                    build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
                conn = self.factory()
                try:
                    conn.execute(
                        "UPDATE evidence_records SET subject_key=?,metadata_json=?,observed_at=? WHERE id='direct-evidence'",
                        (original["subject_key"], original["metadata_json"], original["observed_at"]),
                    )
                    conn.commit()
                finally:
                    conn.close()

    def test_non_strict_claim_state_cannot_reintroduce_optimistic_posture(self):
        self._add_independence()
        conn = self.factory()
        try:
            conn.execute("UPDATE evidence_records SET metadata_json='not-json' WHERE id='direct-evidence'")
            conn.commit()
        finally:
            conn.close()
        result = build_claim_state(claim_id="claim-1", connection_factory=self.factory)
        self.assertTrue(result["support_graph"]["integrity_blocked"])
        self.assertEqual(result["support_state"], "integrity_blocked_incomplete")
        self.assertEqual(result["support"]["verified_independent_pairs"], 0)
        self.assertEqual(result["evidence"]["counts"]["verified_supporting"], 0)
        self.assertNotIn("verified", result["claim_state"])

    def test_dependency_unknown_and_unresolved_actor_block_independence(self):
        self._add_independence()
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO observation_dependencies (id,downstream_source_observation_id,"
                "upstream_source_id,relationship_type,observed_at,recorded_at,metadata_json) "
                "VALUES ('unresolved-actor','obs-a','source-c','derived_from',?,?, '{}')",
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        assertion = result["graph_independence_assertions"][0]
        self.assertFalse(assertion["qualified_verified_independence"])
        self.assertTrue(assertion["potential_dependency_blocker"])
        edge = next(edge for edge in result["edges"] if edge["id"] == "dependency:unresolved-actor")
        self.assertEqual(edge["target"], "source:source-c")
        self.assertEqual(edge["linked_observation_pairs"], [])

    def test_malformed_independence_metadata_and_timestamp_never_qualify(self):
        for column, value in (("metadata_json", "not-json"), ("observed_at", "bad-time")):
            with self.subTest(column=column):
                self._add_independence(assertion_id="malformed-" + column)
                conn = self.factory()
                try:
                    conn.execute(
                        f"UPDATE observation_independence_assertions SET {column}=? WHERE id=?",
                        (value, "malformed-" + column),
                    )
                    conn.commit()
                finally:
                    conn.close()
                result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
                assertion = next(item for item in result["graph_independence_assertions"] if item["assertion_id"] == "malformed-" + column)
                self.assertFalse(assertion["qualified_verified_independence"])
                self.assertFalse(assertion["structurally_valid"])
                conn = self.factory()
                try:
                    conn.execute("DELETE FROM observation_independence_assertions WHERE id=?", ("malformed-" + column,))
                    conn.commit()
                finally:
                    conn.close()

    def test_pairwise_independence_is_not_transitive(self):
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) "
                "VALUES ('obs-c','source-c','player:one','report','unresolved',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) "
                "VALUES ('link-obs-c','claim-1','obs-c','reports',?,?, '{}')",
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self._add_independence(assertion_id="independence-a-b")
        evidence_id = "evidence-independence-b-c"
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO evidence_records (id,evidence_key,evidence_type,subject_key,verification_status,observed_at,recorded_at,metadata_json) VALUES (?,?, 'provenance_review','player:one','verified',?,?, '{}')",
                (evidence_id, "key:b-c", NOW, NOW),
            )
            conn.execute(
                "INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES ('independence-b-c','obs-b','obs-c',?,'verified',?,?, '{}')",
                (evidence_id, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        pairs = {tuple(pair) for pair in result["graph_verified_independent_pairs"]}
        self.assertEqual(len(pairs), 2)
        self.assertNotIn(tuple(sorted(("source_observation:obs-a", "source_observation:obs-c"))), pairs)

    def test_deterministic_replay(self):
        self._add_independence()
        first = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        second = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        for field in ("nodes", "edges", "anomalies", "graph_independence_assertions", "graph_verified_independent_pairs"):
            self.assertEqual(first[field], second[field])

    def test_combined_observation_limit_and_truncation_block_independence(self):
        self._add_independence()
        conn = self.factory()
        try:
            for index in range(201):
                source_id = f"bulk-source-{index:03d}"
                reporter_id = f"bulk-reporter-{index:03d}"
                conn.execute(
                    "INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES (?,?, 'player:one','report','unresolved',?,?, '{}')",
                    (source_id, "source-a", NOW, NOW),
                )
                conn.execute(
                    "INSERT INTO reporter_observations (id,reporter_id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES (?,?,?,'player:one','report','unresolved',?,?, '{}')",
                    (reporter_id, "reporter-c", "source-a", NOW, NOW),
                )
                conn.execute(
                    "INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?, 'claim-1',?,'reports',?,?, '{}')",
                    ("link-" + source_id, source_id, NOW, NOW),
                )
                conn.execute(
                    "INSERT INTO claim_links (id,claim_id,reporter_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?, 'claim-1',?,'reports',?,?, '{}')",
                    ("link-" + reporter_id, reporter_id, NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        observation_nodes = [node for node in result["nodes"] if node["node_type"] in {"source_observation", "reporter_observation"}]
        self.assertEqual(len(observation_nodes), 400)
        self.assertGreater(result["graph_summary"]["observations_eligible"], 400)
        self.assertEqual(result["graph_summary"]["observations_retained"], 400)
        self.assertIn("observations", result["graph_limits"]["truncated_categories"])
        self.assertEqual(result["graph_limits"]["independence_completeness"], "incomplete")
        self.assertEqual(result["graph_verified_independent_pairs"], [])

    def test_corrupt_claim_link_beyond_output_limit_fails_closed(self):
        conn = self.factory()
        try:
            for index in range(798):
                conn.execute(
                    "INSERT INTO claim_links (id,claim_id,evidence_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?, 'claim-1','direct-evidence','aligned_to',?,?, '{}')",
                    (f"bulk-link-{index:04d}", NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                "INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('zzzz-dangling','claim-1','missing-observation','reports','2026-08-23T00:00:00+00:00','2026-08-23T00:00:00+00:00','{}')"
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)

    def test_malformed_dependency_cardinality_blocks_independence(self):
        self._add_independence()
        conn = self.factory()
        try:
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute(
                "INSERT INTO reporter_observations (id,reporter_id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('reporter-obs','reporter-c','source-c','player:one','report','unresolved',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_links (id,claim_id,reporter_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('link-reporter-obs','claim-1','reporter-obs','reports',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute(
                "INSERT INTO observation_dependencies (id,downstream_source_observation_id,downstream_reporter_observation_id,upstream_source_observation_id,upstream_source_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('malformed-cardinality','obs-a','reporter-obs','obs-b','source-c','derived_from',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute(
                "INSERT INTO observation_dependencies (id,downstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('missing-upstream','obs-b','derived_from',?,?, '{}')",
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        result = build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        assertion = result["graph_independence_assertions"][0]
        self.assertFalse(assertion["qualified_verified_independence"])
        anomaly = next(item for item in result["anomalies"] if item["stable_id"] == "malformed-cardinality")
        self.assertEqual(anomaly["downstream_cardinality"], 2)
        self.assertEqual(anomaly["upstream_cardinality"], 2)
        missing = next(item for item in result["anomalies"] if item["stable_id"] == "missing-upstream")
        self.assertEqual(missing["upstream_cardinality"], 0)

    def test_malformed_and_dangling_evidence_links_fail_closed(self):
        conn = self.factory()
        try:
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute(
                "INSERT INTO evidence_links (id,evidence_id,source_id,reporter_id,relationship_type,linked_at,metadata_json) VALUES ('malformed-evidence-link','direct-evidence','source-a','reporter-c','supports',?, '{}')",
                (NOW,),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("DELETE FROM evidence_links WHERE id='malformed-evidence-link'")
            conn.commit()
        finally:
            conn.close()
        conn = self.factory()
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                "INSERT INTO evidence_links (id,evidence_id,media_item_id,relationship_type,linked_at,metadata_json) VALUES ('dangling-evidence-link','direct-evidence','missing-media','supports',?, '{}')",
                (NOW,),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id="claim-1", connection_factory=self.factory)


class ProductionClaimEvidenceGraphTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "production-graph.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            for source_id in ("source-a", "source-b"):
                conn.execute(
                    "INSERT INTO intelligence_sources (id,source_key,display_name,source_type,canonical_domain,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,'publisher',?,?,?, '{}')",
                    (source_id, "key:" + source_id, source_id, source_id + ".example", NOW, NOW),
                )
            conn.execute(
                "INSERT INTO media_items (id,canonical_url,mode,source_id,title,latest_content_hash,first_seen_at,last_seen_at,metadata_json) VALUES ('media-base','https://source-a.example/base','article','source-a','Base','hash',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute(
                "INSERT INTO source_observations (id,source_id,media_item_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES ('production-observation','source-a','media-base','player|one','report','reported',?,?, '{}')",
                (NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        materialized = materialize_canonical_claim(
            candidate=self.candidate(), claim_text="Player One completed a move to Arsenal",
            observed_at=NOW, source_observation_id="production-observation",
            relationship_type="reports", connection_factory=self.factory,
        )
        self.claim_id = materialized["claim"]["id"]
        story = materialize_canonical_claim_story(
            claim_id=self.claim_id, connection_factory=self.factory
        )
        self.story_id = story["story_id"]
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE source_observations SET story_id=? WHERE id='production-observation'",
                (self.story_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def candidate():
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": "player|one",
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {"destination": "club|arsenal"},
            "facets": {},
        }

    def add_legacy(self, suffix="one", *, claim_subject="player|one", mapping_subject="player|one"):
        legacy_id = "legacy-" + suffix
        observation_id = "legacy-observation-" + suffix
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO intelligence_claims (id,canonical_key,subject_key,canonical_text,claim_type,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,'Legacy report','assertion',?,?, '{}')",
                (legacy_id, "legacy-key-" + suffix, claim_subject, NOW, NOW),
            )
            conn.execute(
                "INSERT INTO source_observations (id,source_id,subject_key,observation_type,status,observed_at,recorded_at,metadata_json) VALUES (?,'source-b',?,'report','reported',?,?, '{}')",
                (observation_id, claim_subject, NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES (?,?,?,'reports',?,?, '{}')",
                ("legacy-link-" + suffix, legacy_id, observation_id, NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES (?,?,?,'verified_equivalent','test',?,?, '{}')",
                (legacy_id, self.claim_id, mapping_subject, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        return legacy_id, observation_id

    def test_verified_legacy_contributes_without_legacy_claim_node(self):
        legacy_id, observation_id = self.add_legacy()
        result = build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)
        claim_nodes = [node for node in result["nodes"] if node["node_type"] == "claim"]
        self.assertEqual([node["id"] for node in claim_nodes], ["claim:" + self.claim_id])
        self.assertNotIn("claim:" + legacy_id, {node["id"] for node in result["nodes"]})
        edge = next(edge for edge in result["edges"] if edge.get("source_claim_id") == legacy_id)
        self.assertEqual(edge["source"], "claim:" + self.claim_id)
        self.assertEqual(edge["target"], "source_observation:" + observation_id)
        self.assertTrue(edge["legacy_scoped"])

    def test_mapping_chain_and_canonical_as_source_fail_closed(self):
        legacy_id, _ = self.add_legacy()
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO intelligence_claims (id,canonical_key,subject_key,canonical_text,claim_type,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy-chain','legacy-chain-key','player|one','Chain','assertion',?,?, '{}')",
                (NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES ('legacy-chain',?,'player|one','verified_equivalent','test',?,?, '{}')",
                (legacy_id, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("DELETE FROM claim_identity_mappings WHERE production_claim_id='legacy-chain'")
            conn.execute(
                "INSERT INTO claim_identity_mappings (production_claim_id,canonical_claim_id,subject_key,mapping_status,mapping_basis,first_seen_at,last_seen_at,metadata_json) VALUES (?,?, 'player|one','verified_equivalent','test',?,?, '{}')",
                (self.claim_id, self.claim_id, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)

    def test_unverified_and_wrong_subject_mappings_fail_closed(self):
        legacy_id, _ = self.add_legacy(mapping_subject="player|other")
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute(
                "UPDATE claim_identity_mappings SET subject_key='player|one',mapping_status='unverified' WHERE production_claim_id=?",
                (legacy_id,),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)

    def test_exact_story_identity_and_link_provenance_fail_closed(self):
        conn = self.factory()
        try:
            original_key = conn.execute("SELECT canonical_key FROM intelligence_stories WHERE id=?", (self.story_id,)).fetchone()[0]
            conn.execute("UPDATE intelligence_stories SET canonical_key='corrupt-story-key' WHERE id=?", (self.story_id,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute("UPDATE story_claim_links SET relationship_type='exact_claim_group',link_basis='wrong-basis' WHERE story_id=?", (self.story_id,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("UPDATE intelligence_stories SET canonical_key=? WHERE id=?", (original_key, self.story_id))
            conn.execute("PRAGMA ignore_check_constraints=ON")
            conn.execute("UPDATE story_claim_links SET relationship_type='mentions' WHERE story_id=?", (self.story_id,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=self.factory)

    def test_graph_is_read_only_provider_and_network_free(self):
        statements = []
        connections = []

        def traced_factory():
            conn = self.factory()
            conn.set_trace_callback(statements.append)
            connections.append(conn)
            return conn

        with patch.object(socket.socket, "connect", side_effect=AssertionError("network called")):
            result = build_claim_support_graph(claim_id=self.claim_id, connection_factory=traced_factory)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP")) for statement in statements))

    def test_query_count_is_bulk_not_per_legacy_mapping(self):
        self.add_legacy("query-00")

        def count_selects():
            statements = []
            def traced_factory():
                conn = self.factory()
                conn.set_trace_callback(statements.append)
                return conn
            build_claim_support_graph(claim_id=self.claim_id, connection_factory=traced_factory)
            return sum(statement.lstrip().upper().startswith("SELECT") for statement in statements)

        small_count = count_selects()
        for index in range(1, 20):
            self.add_legacy(f"query-{index:02d}")
        large_count = count_selects()
        self.assertLessEqual(large_count, small_count + 4)


if __name__ == "__main__":
    unittest.main()
