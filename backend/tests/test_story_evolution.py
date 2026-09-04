from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_evolution import reconcile_claim_evolution
from app.intelligence.claim_materialization import materialize_canonical_claim
from app.intelligence.claims.repository import record_claim_link
from app.intelligence.story_evolution import build_story_evolution
from app.routes import intelligence_runtime_admin
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
    materialize_canonical_claim_story,
)


SUBJECT = "player|one"
DESTINATION = "club|arsenal"
T0 = "2026-08-20T10:00:00+00:00"
T1 = "2026-08-21T10:00:00+00:00"
T2 = "2026-08-22T10:00:00+00:00"


class StoryEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "story-evolution.sqlite3"
        initialize_database(self.factory, SCHEMA)
        conn = self.factory()
        try:
            for suffix in ("one", "two", "three"):
                conn.execute(
                    """INSERT INTO intelligence_sources
                       (id, source_key, display_name, source_type, canonical_domain,
                        first_seen_at, last_seen_at, metadata_json)
                       VALUES (?, ?, ?, 'publisher', ?, ?, ?, '{}')""",
                    ("source-" + suffix, "publisher|" + suffix, suffix.title(), suffix + ".example", T0, T0),
                )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def candidate(state="interest", *, negated=False):
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": state,
            "negated": negated,
            "roles": {"destination": DESTINATION},
            "facets": {},
        }

    def observation(self, suffix, *, source="one", observed=T0, published=None):
        media_id = "media-" + suffix
        observation_id = "observation-" + suffix
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO media_items
                   (id, canonical_url, mode, source_id, title, published_at,
                    latest_content_hash, first_seen_at, last_seen_at, metadata_json)
                   VALUES (?, ?, 'article', ?, ?, ?, ?, ?, ?, '{}')""",
                (media_id, "https://example.test/" + suffix, "source-" + source, suffix, published, "hash-" + suffix, observed, observed),
            )
            conn.execute(
                """INSERT INTO source_observations
                   (id, source_id, media_item_id, subject_key, observation_type,
                    status, observed_at, recorded_at, metadata_json)
                   VALUES (?, ?, ?, ?, 'report', 'reported', ?, ?, '{}')""",
                (observation_id, "source-" + source, media_id, SUBJECT, observed, T2),
            )
            conn.commit()
        finally:
            conn.close()
        return observation_id, media_id

    def claim(self, state, suffix, *, observed=T0, published=None, negated=False):
        observation_id, media_id = self.observation(
            suffix, source={"a": "one", "b": "two", "c": "three"}.get(suffix, "one"),
            observed=observed, published=published,
        )
        result = materialize_canonical_claim(
            candidate=self.candidate(state, negated=negated),
            claim_text="claim " + suffix,
            observed_at=observed,
            source_observation_id=observation_id,
            relationship_type="reports",
            connection_factory=self.factory,
        )
        claim_id = result["claim"]["id"]
        story = materialize_canonical_claim_story(
            claim_id=claim_id, connection_factory=self.factory
        )
        return claim_id, story["story_id"], observation_id, media_id

    def build(self, claim_id, limit=100):
        return build_story_evolution(
            canonical_claim_id=claim_id,
            connection_factory=self.factory,
            limit=limit,
        )

    def verified_independence(self, left, right, suffix):
        evidence_id = "evidence-" + suffix
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO evidence_records
                   (id, evidence_key, evidence_type, subject_key,
                    verification_status, observed_at, recorded_at, metadata_json)
                   VALUES (?, ?, 'independent_report', ?, 'verified', ?, ?, '{}')""",
                (evidence_id, "independent:" + suffix, SUBJECT, T2, T2),
            )
            conn.execute(
                """INSERT INTO observation_independence_assertions
                   (id, observation_a_source_observation_id,
                    observation_b_source_observation_id, provenance_evidence_id,
                    verification_status, observed_at, recorded_at, metadata_json)
                   VALUES (?, ?, ?, ?, 'verified', ?, ?, '{}')""",
                ("independence-" + suffix, left, right, evidence_id, T2, T2),
            )
            conn.commit()
        finally:
            conn.close()

    def test_single_claim_has_exact_history_without_family_membership(self):
        claim_id, story_id, _, _ = self.claim("interest", "a", published=T0)
        result = self.build(claim_id)
        self.assertIsNone(result["evolution_family"]["family_key"])
        self.assertEqual(result["summary"]["family_claims"], 1)
        self.assertEqual(result["timeline"][0]["event_type"], "first_report_observed")
        self.assertEqual(result["timeline"][0]["story_id"], story_id)
        self.assertEqual(result["timeline"][0]["published_at"], T0)
        self.assertEqual(result["timeline"][0]["observed_at"], T0)

    def test_complete_family_keeps_exact_stories_separate_and_does_not_infer_transitive_link(self):
        first, first_story, _, _ = self.claim("interest", "a", observed=T0)
        middle, middle_story, _, _ = self.claim("negotiating", "b", observed=T1)
        last, last_story, _, _ = self.claim("completed", "c", observed=T2)
        reconcile_claim_evolution(claim_id=last, connection_factory=self.factory)
        result = self.build(middle)
        self.assertEqual(result["summary"]["family_claims"], 3)
        self.assertEqual(
            {row["story_id"] for row in result["evolution_family"]["exact_stories"]},
            {first_story, middle_story, last_story},
        )
        transitions = [row for row in result["timeline"] if row["event_type"] == "claim_progresses_to"]
        self.assertEqual(len(transitions), 2)
        self.assertNotIn((first, last), {(row["predecessor_claim_id"], row["successor_claim_id"]) for row in transitions})

    def test_resolves_and_contradicts_use_only_persisted_links(self):
        first, _, _, _ = self.claim("negotiating", "a", observed=T0)
        failed, _, _, _ = self.claim("failed", "b", observed=T1)
        reconcile_claim_evolution(claim_id=failed, connection_factory=self.factory)
        self.assertIn("claim_resolves_to", {row["event_type"] for row in self.build(first)["timeline"]})

        completed, _, _, _ = self.claim("completed", "c", observed=T2)
        denied_observation, denied_media = self.observation("denied", source="two", observed="2026-08-23T10:00:00+00:00")
        denied_result = materialize_canonical_claim(
            candidate=self.candidate("completed", negated=True), claim_text="denied",
            observed_at="2026-08-23T10:00:00+00:00", source_observation_id=denied_observation,
            relationship_type="reports", connection_factory=self.factory,
        )
        denied = denied_result["claim"]["id"]
        materialize_canonical_claim_story(claim_id=denied, connection_factory=self.factory)
        reconcile_claim_evolution(claim_id=denied, connection_factory=self.factory)
        self.assertIn("claim_contradiction_observed", {row["event_type"] for row in self.build(completed)["timeline"]})
        self.assertTrue(denied_media)

    def test_additional_dependent_and_verified_independent_reports(self):
        claim_id, _, first_observation, _ = self.claim("interest", "a", observed=T0)
        second_observation, _ = self.observation("second", source="two", observed=T1)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=second_observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        result = self.build(claim_id)
        self.assertIn("additional_report_observed", {row["event_type"] for row in result["timeline"]})
        self.assertEqual(result["summary"]["verified_independent_reports"], 0)

        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO observation_dependencies
                   (id, downstream_source_observation_id, upstream_source_observation_id,
                    relationship_type, observed_at, recorded_at, metadata_json)
                   VALUES ('dependency-1', ?, ?, 'derived_from', ?, ?, '{}')""",
                (second_observation, first_observation, T1, T2),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.build(claim_id)
        self.assertIn("dependent_report_observed", {row["event_type"] for row in result["timeline"]})

        third_observation, _ = self.observation("third", source="three", observed=T2)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T2, source_observation_id=third_observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO evidence_records
                   (id, evidence_key, evidence_type, subject_key, verification_status,
                    observed_at, recorded_at, metadata_json)
                   VALUES ('evidence-independent', 'independent:1', 'independent_report', ?,
                           'verified', ?, ?, '{}')""",
                (SUBJECT, T2, T2),
            )
            conn.execute(
                """INSERT INTO observation_independence_assertions
                   (id, observation_a_source_observation_id, observation_b_source_observation_id,
                    provenance_evidence_id, verification_status, observed_at, recorded_at, metadata_json)
                   VALUES ('independence-1', ?, ?, 'evidence-independent', 'verified', ?, ?, '{}')""",
                (first_observation, third_observation, T2, T2),
            )
            conn.commit()
        finally:
            conn.close()
        result = self.build(claim_id)
        self.assertIn("verified_independent_report_observed", {row["event_type"] for row in result["timeline"]})

    def test_dependency_independence_conflict_is_not_independent(self):
        claim_id, _, first, _ = self.claim("interest", "a", observed=T0)
        second, _ = self.observation("conflict", source="two", observed=T1)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=second, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("INSERT INTO evidence_records (id,evidence_key,evidence_type,subject_key,verification_status,observed_at,recorded_at,metadata_json) VALUES ('ev','ev','independent_report',?,'verified',?,?,'{}')", (SUBJECT, T1, T1))
            conn.execute("INSERT INTO observation_dependencies (id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,observed_at,recorded_at,metadata_json) VALUES ('dep',?,?,'attributed_to',?,?,'{}')", (second, first, T1, T1))
            conn.execute("INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,observed_at,recorded_at,metadata_json) VALUES ('ind',?,?,'ev','verified',?,?,'{}')", (first, second, T1, T1))
            conn.commit()
        finally:
            conn.close()
        result = self.build(claim_id)
        self.assertEqual(result["summary"]["verified_independent_reports"], 0)
        self.assertEqual(result["summary"]["known_dependent_reports"], 1)

    def test_unknown_dependency_blocks_independence_without_becoming_dependent(self):
        claim_id, _, first, _ = self.claim("interest", "a", observed=T0)
        second, _ = self.observation("unknown", source="two", observed=T1)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=second, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.verified_independence(first, second, "unknown")
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO observation_dependencies
                   (id, downstream_source_observation_id,
                    upstream_source_observation_id, relationship_type,
                    observed_at, recorded_at, metadata_json)
                   VALUES ('dependency-unknown', ?, ?, 'quoted_by', ?, ?, '{}')""",
                (second, first, T1, T2),
            )
            conn.commit()
        finally:
            conn.close()
        event_types = {row["event_type"] for row in self.build(claim_id)["timeline"]}
        self.assertNotIn("verified_independent_report_observed", event_types)
        self.assertNotIn("dependent_report_observed", event_types)

    def test_ambiguous_actor_dependency_blocks_independence_without_becoming_dependent(self):
        claim_id, _, first, _ = self.claim("interest", "a", observed=T0)
        same_actor, _ = self.observation("same-actor", source="one", observed=T1)
        second, _ = self.observation("actor-downstream", source="two", observed=T2)
        for observation_id, observed_at in ((same_actor, T1), (second, T2)):
            record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=observed_at, source_observation_id=observation_id, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.verified_independence(first, second, "actor")
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO observation_dependencies
                   (id, downstream_source_observation_id, upstream_source_id,
                    relationship_type, observed_at, recorded_at, metadata_json)
                   VALUES ('dependency-actor', ?, 'source-one', 'derived_from',
                           ?, ?, '{}')""",
                (second, T2, T2),
            )
            conn.commit()
        finally:
            conn.close()
        event_types = {row["event_type"] for row in self.build(claim_id)["timeline"]}
        self.assertNotIn("verified_independent_report_observed", event_types)
        self.assertNotIn("dependent_report_observed", event_types)

    def test_malformed_potential_dependency_blocks_independence(self):
        claim_id, _, first, _ = self.claim("interest", "a", observed=T0)
        second, _ = self.observation("malformed", source="two", observed=T1)
        record_claim_link(claim_id=claim_id, relationship_type="reports", observed_at=T1, source_observation_id=second, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        self.verified_independence(first, second, "malformed")
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO observation_dependencies
                   (id, downstream_source_observation_id,
                    upstream_source_observation_id, relationship_type,
                    observed_at, recorded_at, metadata_json)
                   VALUES ('dependency-malformed', ?, ?, 'derived_from',
                           ?, ?, 'not-json')""",
                (second, first, T1, T2),
            )
            conn.commit()
        finally:
            conn.close()
        event_types = {row["event_type"] for row in self.build(claim_id)["timeline"]}
        self.assertNotIn("verified_independent_report_observed", event_types)
        self.assertNotIn("dependent_report_observed", event_types)

    def test_verified_legacy_equivalent_reporting_is_included(self):
        claim_id, _, _, canonical_media = self.claim("interest", "a", observed=T0)
        legacy_observation, legacy_media = self.observation("legacy", source="two", observed=T1)
        conn = self.factory()
        try:
            conn.execute(
                """INSERT INTO intelligence_claims
                   (id, canonical_key, subject_key, canonical_text, claim_type,
                    first_seen_at, last_seen_at, metadata_json)
                   VALUES ('legacy-claim', 'legacy-key', ?, 'Legacy', 'assertion',
                           ?, ?, '{}')""",
                (SUBJECT, T0, T1),
            )
            conn.execute(
                """INSERT INTO claim_identity_mappings
                   (production_claim_id, canonical_claim_id, subject_key,
                    mapping_status, mapping_basis, first_seen_at, last_seen_at,
                    metadata_json)
                   VALUES ('legacy-claim', ?, ?, 'verified_equivalent', 'test',
                           ?, ?, '{}')""",
                (claim_id, SUBJECT, T0, T1),
            )
            conn.commit()
        finally:
            conn.close()
        record_claim_link(claim_id="legacy-claim", relationship_type="reports", observed_at=T1, source_observation_id=legacy_observation, connection_factory=self.factory)
        materialize_canonical_claim_story(claim_id=claim_id, connection_factory=self.factory)
        result = self.build(claim_id)
        report_media = {
            row["media_item_id"]
            for row in result["timeline"]
            if row["event_type"] in {"first_report_observed", "additional_report_observed"}
        }
        self.assertEqual(report_media, {canonical_media, legacy_media})
        self.assertEqual(result["summary"]["reports"], 2)

    def test_adjudication_and_persisted_correction_are_separate_events(self):
        claim_id, _, _, _ = self.claim("interest", "a")
        before = {"tier": "silver", "value": "old"}
        after = {"tier": "auto_gold", "value": "new"}
        conn = self.factory()
        try:
            conn.execute("INSERT INTO adjudication_state_revisions (id,claim_id,state_version,adjudication_version,adjudication_sha256,as_of,trigger_type,trigger_evidence_ids_json,revision_json,recorded_at) VALUES ('rev-1',?,'v','v','sha',?,'initial_evaluation','[]','{}',?)", (claim_id, T0, T2))
            conn.execute("INSERT INTO adjudication_state_revisions (id,claim_id,state_version,adjudication_version,adjudication_sha256,as_of,previous_revision_id,trigger_type,trigger_evidence_ids_json,revision_json,recorded_at) VALUES ('rev-2',?,'v','v','sha2',?,'rev-1','canonical_outcome','[\"evidence-1\"]','{}',?)", (claim_id, T1, T2))
            conn.execute("INSERT INTO adjudication_state_transitions (id,revision_id,claim_id,field,kind,from_state_json,to_state_json,recorded_at) VALUES ('transition-1','rev-2',?,'stance','value_changed',?,?,?)", (claim_id, json.dumps(before), json.dumps(after), T2))
            payload = json.dumps({"previous_state": before, "corrected_state": after})
            conn.execute("INSERT INTO automatic_correction_events (id,claim_id,field,signature,previous_revision_id,current_revision_id,event_version,event_json,recorded_at) VALUES ('correction-1',?,'stance','signature','rev-1','rev-2','v',?,?)", (claim_id, payload, T2))
            conn.commit()
        finally:
            conn.close()
        with patch("app.analysis.correction_memory_history.process_automatic_correction_memory") as processor:
            result = self.build(claim_id)
        processor.assert_not_called()
        by_type = {row["event_type"]: row for row in result["timeline"]}
        self.assertEqual(by_type["adjudication_state_transition"]["before"], before)
        self.assertEqual(by_type["automatic_correction_recorded"]["correction_scope"], "adjudication_system")
        self.assertFalse({"retraction", "supersession", "refinement"} & set(by_type))

    def test_order_ids_limit_and_read_only_policy(self):
        claim_id, _, _, _ = self.claim("interest", "a")
        first = self.build(claim_id, limit=1)
        second = self.build(claim_id, limit=1)
        self.assertEqual(first["timeline"], second["timeline"])
        self.assertEqual(first["pagination"]["limit"], 1)
        self.assertTrue(first["timeline"][0]["event_id"].startswith("story-evolution-"))
        self.assertFalse(first["policy"]["provider_call_performed"])
        self.assertFalse(first["policy"]["read_path_performs_writes"])
        self.assertFalse(first["policy"]["get_reconciles_evolution"])

    def test_family_corruption_fails_closed(self):
        first, _, _, _ = self.claim("interest", "a", observed=T0)
        second, _, _, _ = self.claim("negotiating", "b", observed=T1)
        reconcile_claim_evolution(claim_id=second, connection_factory=self.factory)
        conn = self.factory()
        try:
            conn.execute("UPDATE intelligence_claims SET subject_key='other' WHERE id=?", (second,))
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(StoryClaimGraphMaterializationIntegrityError):
            self.build(first)

    def test_route_200_404_conflict_and_get_does_not_reconcile(self):
        claim_id, _, _, _ = self.claim("interest", "a")
        app = FastAPI()
        app.include_router(intelligence_runtime_admin.build_router(app=app, require_admin=lambda request: None, connection_factory=self.factory))
        client = TestClient(app)
        with patch("app.routes.intelligence_runtime_admin.reconcile_claim_evolution_safely") as reconcile:
            response = client.get(f"/admin/intelligence/claims/{claim_id}/evolution?limit=10")
        self.assertEqual(response.status_code, 200)
        reconcile.assert_not_called()
        self.assertEqual(client.get("/admin/intelligence/claims/missing/evolution").status_code, 404)
        conn = self.factory()
        try:
            conn.execute("DELETE FROM story_claim_links WHERE claim_id=?", (claim_id,))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(client.get(f"/admin/intelligence/claims/{claim_id}/evolution").status_code, 409)


if __name__ == "__main__":
    unittest.main()
