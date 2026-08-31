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
from app.intelligence.claims.repository import record_claim_link
from app.intelligence.reporting_coverage import build_claim_reporting_coverage
from app.intelligence.source_dependency_graph import (
    build_claim_source_dependency_graph,
)
from app.routes import intelligence_admin
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
    materialize_canonical_claim_story,
)


NOW = "2026-08-31T10:00:00+00:00"
SUBJECT = "player|one"


class SourceDependencyGraphTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "source-dependency.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            for source_id in ("source-a", "source-b", "source-c"):
                conn.execute(
                    "INSERT INTO intelligence_sources "
                    "(id, source_key, display_name, source_type, canonical_domain, "
                    "first_seen_at, last_seen_at, metadata_json) VALUES "
                    "(?, ?, ?, 'publisher', ?, ?, ?, '{}')",
                    (
                        source_id,
                        "key-" + source_id,
                        source_id,
                        source_id + ".example",
                        NOW,
                        NOW,
                    ),
                )
            for reporter_id in ("reporter-a", "reporter-b"):
                conn.execute(
                    "INSERT INTO intelligence_reporters "
                    "(id, identity_key, display_name, first_seen_at, last_seen_at, metadata_json) VALUES "
                    "(?, ?, ?, ?, ?, '{}')",
                    (reporter_id, "key-" + reporter_id, reporter_id, NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def candidate(**changes):
        value = {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {"destination": "club|arsenal"},
            "facets": {},
        }
        value.update(changes)
        return value

    def observation(
        self,
        suffix,
        *,
        source="source-a",
        reporter=None,
        media_suffix=None,
        subject=SUBJECT,
    ):
        observation_id = "obs-" + suffix
        media_id = "media-" + (media_suffix or suffix)
        conn = self.factory()
        try:
            if conn.execute("SELECT id FROM media_items WHERE id = ?", (media_id,)).fetchone() is None:
                conn.execute(
                    "INSERT INTO media_items "
                    "(id, canonical_url, mode, source_id, reporter_id, title, published_at, "
                    "latest_content_hash, first_seen_at, last_seen_at, metadata_json) VALUES "
                    "(?, ?, 'article', ?, NULL, ?, NULL, ?, ?, ?, '{}')",
                    (
                        media_id,
                        "https://example.test/" + media_id,
                        source,
                        media_id,
                        "hash-" + media_id,
                        NOW,
                        NOW,
                    ),
                )
            if reporter:
                conn.execute(
                    "INSERT INTO reporter_observations "
                    "(id, reporter_id, source_id, media_item_id, subject_key, "
                    "observation_type, status, observed_at, recorded_at, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, 'report', 'reported', ?, ?, '{}')",
                    (observation_id, reporter, source, media_id, subject, NOW, NOW),
                )
            else:
                conn.execute(
                    "INSERT INTO source_observations "
                    "(id, source_id, media_item_id, subject_key, observation_type, "
                    "status, observed_at, recorded_at, metadata_json) "
                    "VALUES (?, ?, ?, ?, 'report', 'reported', ?, ?, '{}')",
                    (observation_id, source, media_id, subject, NOW, NOW),
                )
            conn.commit()
        finally:
            conn.close()
        return observation_id, media_id

    def claim(self, observation_id, *, reporter=False, candidate=None):
        result = materialize_canonical_claim(
            candidate=candidate or self.candidate(),
            claim_text="Player One completed a move to Arsenal",
            observed_at=NOW,
            connection_factory=self.factory,
            reporter_observation_id=observation_id if reporter else None,
            source_observation_id=None if reporter else observation_id,
            relationship_type="reports",
        )
        return result["claim"]["id"]

    def link(self, claim_id, observation_id, *, reporter=False):
        return record_claim_link(
            claim_id=claim_id,
            relationship_type="reports",
            observed_at=NOW,
            reporter_observation_id=observation_id if reporter else None,
            source_observation_id=None if reporter else observation_id,
            connection_factory=self.factory,
        )

    def ready(self, rows):
        first, _ = rows[0]
        claim_id = self.claim(first[0], reporter=first[1])
        for (observation_id, reporter), _media_id in rows[1:]:
            self.link(claim_id, observation_id, reporter=reporter)
        materialize_canonical_claim_story(
            claim_id=claim_id, connection_factory=self.factory
        )
        return claim_id

    def graph(self, claim_id):
        return build_claim_source_dependency_graph(
            canonical_claim_id=claim_id, connection_factory=self.factory
        )

    def dependency(
        self,
        dependency_id,
        downstream,
        *,
        upstream_observation=None,
        upstream_source=None,
        upstream_reporter=None,
        relationship="derived_from",
        reporter_downstream=False,
        metadata="{}",
        observed_at=NOW,
        recorded_at=NOW,
        foreign_keys=True,
    ):
        conn = self.factory()
        try:
            if not foreign_keys:
                conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO observation_dependencies "
                "(id, downstream_source_observation_id, downstream_reporter_observation_id, "
                "upstream_source_observation_id, upstream_source_id, upstream_reporter_id, "
                "relationship_type, observed_at, recorded_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    dependency_id,
                    None if reporter_downstream else downstream,
                    downstream if reporter_downstream else None,
                    upstream_observation,
                    upstream_source,
                    upstream_reporter,
                    relationship,
                    observed_at,
                    recorded_at,
                    metadata,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def independence(
        self,
        assertion_id,
        left,
        right,
        *,
        assertion_status="verified",
        evidence_status="verified",
        left_reporter=False,
        right_reporter=False,
        evidence_metadata="{}",
    ):
        evidence_id = "evidence-" + assertion_id
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO evidence_records "
                "(id, evidence_key, evidence_type, subject_key, verification_status, "
                "observed_at, recorded_at, metadata_json) VALUES "
                "(?, ?, 'independence_verification', ?, ?, ?, ?, ?)",
                (
                    evidence_id,
                    "key-" + evidence_id,
                    SUBJECT,
                    evidence_status,
                    NOW,
                    NOW,
                    evidence_metadata,
                ),
            )
            conn.execute(
                "INSERT INTO observation_independence_assertions "
                "(id, observation_a_source_observation_id, observation_a_reporter_observation_id, "
                "observation_b_source_observation_id, observation_b_reporter_observation_id, "
                "provenance_evidence_id, verification_status, observed_at, recorded_at, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')",
                (
                    assertion_id,
                    None if left_reporter else left,
                    left if left_reporter else None,
                    None if right_reporter else right,
                    right if right_reporter else None,
                    evidence_id,
                    assertion_status,
                    NOW,
                    NOW,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def two(self, *, same_source=False):
        a = self.observation("a", source="source-a")
        b = self.observation("b", source="source-a" if same_source else "source-b")
        return a, b, self.ready([((a[0], False), a[1]), ((b[0], False), b[1])])

    def test_dependency_direction_unknown_and_summary_contract(self):
        a, b, claim_id = self.two()
        self.dependency("dep-1", b[0], upstream_observation=a[0])
        result = self.graph(claim_id)
        edge = result["dependency_edges"][0]
        self.assertEqual(edge["downstream_observation_key"], "source_observation:obs-b")
        self.assertEqual(edge["upstream_target"], {"type": "source_observation", "id": "obs-a"})
        self.assertEqual(edge["dependency_assertion_kind"], "recorded_direct_dependency")
        self.assertEqual(result["classified_relationships"][0]["status"], "dependent")
        self.assertEqual(result["summary"]["unknown_observation_pairs"], 0)
        self.assertNotIn("independent_source_count", result["summary"])

    def test_verified_unverified_and_unverified_evidence_semantics(self):
        for suffix, assertion_status, evidence_status, expected in (
            ("verified", "verified", "verified", "independent"),
            ("unverified", "unverified", "verified", None),
            ("evidence-gap", "verified", "unverified", None),
        ):
            with self.subTest(suffix=suffix):
                a, b, claim_id = self.two()
                self.independence(
                    "assert-" + suffix,
                    a[0],
                    b[0],
                    assertion_status=assertion_status,
                    evidence_status=evidence_status,
                )
                result = self.graph(claim_id)
                states = [row["status"] for row in result["classified_relationships"]]
                self.assertEqual(states, [expected] if expected else [])
                self.assertEqual(
                    result["independence_assertions"][0]["qualified_verified_independence"],
                    expected == "independent",
                )
                self.tearDown()
                self.setUp()

    def test_dependency_and_independence_conflict_preserves_both_records(self):
        a, b, claim_id = self.two()
        self.dependency("dep-conflict", b[0], upstream_observation=a[0])
        self.independence("assert-conflict", a[0], b[0])
        result = self.graph(claim_id)
        relationship = result["classified_relationships"][0]
        self.assertEqual(relationship["status"], "conflicting_evidence")
        self.assertEqual(relationship["dependency_edge_ids"], ["dep-conflict"])
        self.assertEqual(relationship["independence_assertion_ids"], ["assert-conflict"])
        assertion = result["independence_assertions"][0]
        self.assertTrue(assertion["evidence_qualified_verified_independence"])
        self.assertTrue(assertion["dependency_conflict"])
        self.assertFalse(assertion["qualified_verified_independence"])

    def test_malformed_dependencies_block_independence_without_establishing_dependency(self):
        cases = (
            ("bad-observed", "not-a-time", NOW, "{}"),
            ("bad-recorded", NOW, "not-a-time", "{}"),
            ("bad-metadata", NOW, NOW, "[]"),
        )
        for dependency_id, observed_at, recorded_at, metadata in cases:
            with self.subTest(dependency_id=dependency_id):
                a, b, claim_id = self.two()
                self.dependency(
                    dependency_id,
                    b[0],
                    upstream_observation=a[0],
                    observed_at=observed_at,
                    recorded_at=recorded_at,
                    metadata=metadata,
                )
                self.independence("assert-" + dependency_id, a[0], b[0])
                result = self.graph(claim_id)
                self.assertEqual(result["classified_relationships"], [])
                self.assertEqual(result["summary"]["known_dependency_pairs"], 0)
                self.assertEqual(result["summary"]["known_dependency_edges"], 0)
                self.assertEqual(result["summary"]["unknown_observation_pairs"], 1)
                self.assertFalse(
                    result["independence_assertions"][0][
                        "qualified_verified_independence"
                    ]
                )
                self.assertFalse(
                    result["dependency_edges"][0]["dependency_structurally_valid"]
                )
                self.assertTrue(result["anomalies"])
                self.tearDown()
                self.setUp()

    def test_identity_diversity_never_implies_independence(self):
        cases = []
        cases.append(self.two(same_source=True))
        for a, b, claim_id in cases:
            result = self.graph(claim_id)
            self.assertEqual(result["summary"]["unknown_observation_pairs"], 1)
            self.assertEqual(result["media_projection"], [])

    def test_reporter_and_mixed_pairs_are_observation_authoritative(self):
        source = self.observation("source", source="source-a")
        reporter = self.observation(
            "reporter", source="source-b", reporter="reporter-b"
        )
        claim_id = self.ready(
            [((source[0], False), source[1]), ((reporter[0], True), reporter[1])]
        )
        self.independence(
            "assert-mixed", source[0], reporter[0], right_reporter=True
        )
        result = self.graph(claim_id)
        self.assertEqual(
            [row["observation_type"] for row in result["observations"]],
            ["reporter_observation", "source_observation"],
        )
        self.assertEqual(result["classified_relationships"][0]["status"], "independent")

    def test_same_media_dedupes_projection_and_never_emits_self_media_pair(self):
        source = self.observation("same-source", source="source-a", media_suffix="same")
        reporter = self.observation(
            "same-reporter",
            source="source-a",
            reporter="reporter-a",
            media_suffix="same",
        )
        other = self.observation("other", source="source-b")
        claim_id = self.ready(
            [
                ((source[0], False), source[1]),
                ((reporter[0], True), reporter[1]),
                ((other[0], False), other[1]),
            ]
        )
        self.dependency("same-media-basis", other[0], upstream_observation=source[0])
        result = self.graph(claim_id)
        self.assertEqual(result["summary"]["reporting_media"], 2)
        self.assertEqual(len(result["media_projection"]), 1)
        self.assertEqual(len(result["media_projection"][0]["basis_observation_pairs"]), 2)
        self.assertEqual(result["media_projection"][0]["status"], "dependent")

    def test_external_and_actor_target_resolution_is_conservative(self):
        a, b, claim_id = self.two()
        self.dependency("actor-zero", b[0], upstream_source="source-c")
        self.dependency("actor-one", b[0], upstream_source="source-a")
        result = self.graph(claim_id)
        by_id = {row["dependency_id"]: row for row in result["dependency_edges"]}
        self.assertEqual(by_id["actor-zero"]["scope"], "external_to_claim_scope")
        self.assertEqual(by_id["actor-zero"]["linked_observation_pairs"], [])
        self.assertEqual(by_id["actor-one"]["scope"], "in_scope")
        self.assertEqual(result["summary"]["known_dependency_pairs"], 1)

    def test_dangling_observation_and_actor_targets_are_not_external_provenance(self):
        a, b, claim_id = self.two()
        self.dependency(
            "dangling-observation",
            b[0],
            upstream_observation="missing-observation",
            foreign_keys=False,
        )
        self.dependency(
            "dangling-source",
            b[0],
            upstream_source="missing-source",
            foreign_keys=False,
        )
        self.dependency(
            "dangling-reporter",
            b[0],
            upstream_reporter="missing-reporter",
            foreign_keys=False,
        )
        result = self.graph(claim_id)
        self.assertEqual(
            {edge["scope"] for edge in result["dependency_edges"]},
            {"dangling_target"},
        )
        self.assertEqual(result["summary"]["known_dependency_pairs"], 0)
        dangling = [
            row for row in result["anomalies"]
            if row["type"] == "dangling_dependency_target"
        ]
        self.assertEqual(
            [row["stable_id"] for row in dangling],
            ["dangling-observation", "dangling-reporter", "dangling-source"],
        )

    def test_actor_multiple_matches_is_ambiguous_and_blocks_optimism(self):
        a1 = self.observation("a1", source="source-a")
        a2 = self.observation("a2", source="source-a")
        b = self.observation("b", source="source-b")
        claim_id = self.ready(
            [((a1[0], False), a1[1]), ((a2[0], False), a2[1]), ((b[0], False), b[1])]
        )
        self.dependency("actor-many", b[0], upstream_source="source-a")
        self.independence("assert-blocked", a1[0], b[0])
        result = self.graph(claim_id)
        self.assertEqual(result["summary"]["known_dependency_pairs"], 0)
        self.assertFalse(result["independence_assertions"][0]["qualified_verified_independence"])
        self.assertIn("ambiguous_actor_dependency_target", {a["type"] for a in result["anomalies"]})

    def test_unknown_vocabulary_self_edge_and_malformed_metadata_are_anomalies(self):
        a, b, claim_id = self.two()
        self.dependency("unknown", b[0], upstream_observation=a[0], relationship="syndicates")
        self.dependency("self", a[0], upstream_observation=a[0])
        self.dependency("bad-meta", b[0], upstream_source="source-c", metadata="[]")
        result = self.graph(claim_id)
        self.assertEqual(result["summary"]["known_dependency_pairs"], 0)
        kinds = {row["type"] for row in result["anomalies"]}
        self.assertTrue(
            {"unknown_dependency_relationship", "self_dependency", "malformed_dependency_metadata"}
            <= kinds
        )

    def test_cycles_are_detected_without_transitive_inference(self):
        a = self.observation("a", source="source-a")
        b = self.observation("b", source="source-b")
        c = self.observation("c", source="source-c")
        claim_id = self.ready(
            [((a[0], False), a[1]), ((b[0], False), b[1]), ((c[0], False), c[1])]
        )
        self.dependency("ab", a[0], upstream_observation=b[0])
        self.dependency("bc", b[0], upstream_observation=c[0])
        result = self.graph(claim_id)
        self.assertEqual(result["summary"]["known_dependency_pairs"], 2)
        self.assertEqual(result["summary"]["unknown_observation_pairs"], 1)
        self.dependency("ca", c[0], upstream_observation=a[0])
        result = self.graph(claim_id)
        cycles = [row for row in result["anomalies"] if row["type"] == "dependency_cycle"]
        self.assertEqual(len(cycles), 1)
        self.assertEqual(len(cycles[0]["observation_keys"]), 3)

    def test_multiple_rows_preserve_edges_and_dedupe_pair_classification(self):
        a, b, claim_id = self.two()
        self.dependency("dep-b", b[0], upstream_observation=a[0])
        self.dependency("dep-a", b[0], upstream_observation=a[0], relationship="attributed_to")
        self.independence("assert-b", a[0], b[0])
        self.independence("assert-a", a[0], b[0])
        result = self.graph(claim_id)
        self.assertEqual(len(result["dependency_edges"]), 2)
        self.assertEqual(len(result["independence_assertions"]), 2)
        self.assertEqual(len(result["classified_relationships"]), 1)
        self.assertEqual(result["classified_relationships"][0]["status"], "conflicting_evidence")

    def test_legacy_equivalent_included_cross_claim_external_does_not_expand_scope(self):
        canonical = self.observation("canonical", source="source-a")
        claim_id = self.claim(canonical[0])
        legacy = self.observation("legacy", source="source-b")
        external = self.observation("external", source="source-c")
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO intelligence_claims "
                "(id, canonical_key, subject_key, canonical_text, claim_type, first_seen_at, last_seen_at, metadata_json) VALUES "
                "('legacy-claim', 'legacy-key', ?, 'Legacy', 'assertion', ?, ?, '{}')",
                (SUBJECT, NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_identity_mappings VALUES "
                "('legacy-claim', ?, ?, 'verified_equivalent', 'test', ?, ?, '{}')",
                (claim_id, SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        self.link("legacy-claim", legacy[0])
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.dependency("cross", legacy[0], upstream_observation=external[0])
        result = self.graph(claim_id)
        self.assertEqual(result["summary"]["reporting_observations"], 2)
        self.assertEqual(result["dependency_edges"][0]["scope"], "external_to_claim_scope")
        self.assertNotIn("obs-external", {row["observation_id"] for row in result["observations"]})

    def test_unknown_count_is_formula_without_unknown_relationship_rows(self):
        rows = [self.observation(str(index), source="source-a") for index in range(20)]
        claim_id = self.ready([((row[0], False), row[1]) for row in rows])
        result = self.graph(claim_id)
        self.assertEqual(result["summary"]["unknown_observation_pairs"], 190)
        self.assertEqual(result["classified_relationships"], [])
        self.assertEqual(result["media_projection"], [])

    def test_touched_media_projection_aggregates_unknown_conservatively(self):
        cases = ("independent_unknown", "dependent_unknown", "dependency_independence")
        for case in cases:
            with self.subTest(case=case):
                a1 = self.observation("a1", source="source-a", media_suffix="a")
                a2 = self.observation("a2", source="source-a", media_suffix="a")
                b1 = self.observation("b1", source="source-b", media_suffix="b")
                b2 = self.observation("b2", source="source-b", media_suffix="b")
                claim_id = self.ready(
                    [
                        ((a1[0], False), a1[1]),
                        ((a2[0], False), a2[1]),
                        ((b1[0], False), b1[1]),
                        ((b2[0], False), b2[1]),
                    ]
                )
                if case == "independent_unknown":
                    self.independence("assert-one", a1[0], b1[0])
                    expected = "unknown"
                elif case == "dependent_unknown":
                    self.dependency("dep-one", b1[0], upstream_observation=a1[0])
                    expected = "dependent"
                else:
                    self.dependency("dep-one", b1[0], upstream_observation=a1[0])
                    self.independence("assert-two", a2[0], b2[0])
                    expected = "conflicting_evidence"
                result = self.graph(claim_id)
                self.assertEqual(len(result["media_projection"]), 1)
                self.assertEqual(result["media_projection"][0]["status"], expected)
                self.assertEqual(
                    len(result["media_projection"][0]["basis_observation_pairs"]), 4
                )
                self.tearDown()
                self.setUp()

    def test_reporting_coverage_unchanged_and_graph_is_read_only_offline(self):
        a, b, claim_id = self.two()
        before_coverage = build_claim_reporting_coverage(
            canonical_claim_id=claim_id, connection_factory=self.factory
        )
        self.dependency("dep", b[0], upstream_observation=a[0])
        self.independence("assert", a[0], b[0])
        database_before = self.db_path.read_bytes()
        with patch.object(socket, "create_connection", side_effect=AssertionError):
            first = self.graph(claim_id)
            second = self.graph(claim_id)
        self.assertEqual(first, second)
        self.assertEqual(database_before, self.db_path.read_bytes())
        self.assertEqual(
            before_coverage,
            build_claim_reporting_coverage(
                canonical_claim_id=claim_id, connection_factory=self.factory
            ),
        )
        self.assertFalse(first["policy"]["provider_call_performed"])

    def test_route_success_missing_and_noncanonical_integrity(self):
        a = self.observation("route")
        claim_id = self.ready([((a[0], False), a[1])])
        conn = self.factory()
        try:
            conn.execute(
                "INSERT INTO intelligence_claims "
                "(id, canonical_key, subject_key, canonical_text, claim_type, first_seen_at, last_seen_at, metadata_json) VALUES "
                "('not-canonical', 'ordinary', ?, '', 'assertion', ?, ?, '{}')",
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        guarded = []
        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=lambda request: guarded.append(request.url.path),
                connection_factory=self.factory,
            )
        )
        client = TestClient(app)
        path = "/admin/intelligence/claims/{}/source-dependency-graph"
        self.assertEqual(client.get(path.format(claim_id)).status_code, 200)
        self.assertEqual(client.get(path.format("missing")).status_code, 404)
        self.assertEqual(client.get(path.format("not-canonical")).status_code, 409)
        self.assertEqual(len(guarded), 3)

    def test_malformed_legacy_mapping_fails_closed_and_policy_is_explicit(self):
        a = self.observation("mapping")
        claim_id = self.claim(a[0])
        conn = self.factory()
        try:
            for legacy in ("legacy-a", "legacy-b"):
                conn.execute(
                    "INSERT INTO intelligence_claims "
                    "(id, canonical_key, subject_key, canonical_text, claim_type, first_seen_at, last_seen_at, metadata_json) "
                    "VALUES (?, ?, ?, '', 'assertion', ?, ?, '{}')",
                    (legacy, "key-" + legacy, SUBJECT, NOW, NOW),
                )
            conn.execute(
                "INSERT INTO claim_identity_mappings VALUES "
                "('legacy-a', ?, ?, 'verified_equivalent', 'test', ?, ?, '{}')",
                (claim_id, SUBJECT, NOW, NOW),
            )
            conn.execute(
                "INSERT INTO claim_identity_mappings VALUES "
                "('legacy-b', 'legacy-a', ?, 'verified_equivalent', 'test', ?, ?, '{}')",
                (SUBJECT, NOW, NOW),
            )
            conn.commit()
        finally:
            conn.close()
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.graph(claim_id)


if __name__ == "__main__":
    unittest.main()
