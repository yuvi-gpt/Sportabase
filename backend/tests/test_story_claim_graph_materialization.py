from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path


from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_materialization import materialize_canonical_claim
from app.intelligence.stories import story_id_for_canonical_key
from app.services import inbox_candidate_shadow_orchestration
from app.services import inbox_story_cluster_orchestration
from app.services import multimodal_binding_registration
from app.services import multimodal_inbox_shadow_orchestration
from app.services import multimodal_shadow_orchestration
from app.services import story_claim_graph_materialization as graph


ANCHOR_CAPTURE = "anchor-capture"
SUBJECT_ID = "entity-1"
SUBJECT_KEY = "player:one"
ANCHOR_MEDIA = "media-anchor"


def cluster_policy():
    return {
        "cluster_is_routing_candidate_only": True,
        "cluster_selection_is_read_only": True,
        "same_story_not_established_by_cluster": True,
        "same_claim_not_established_by_cluster": True,
        "claim_groups_formed_only_from_downstream_exact_claim_ids": True,
        "each_completed_member_passed_exact_common_claim_gate": True,
        "each_member_revalidated_by_candidate_gate": True,
        "candidate_scores_are_ranking_only": True,
        "cluster_does_not_write_story_records_directly": True,
        "cluster_does_not_link_story_media_directly": True,
        "cluster_level_corroboration_not_established": True,
        "cluster_level_independence_not_established": True,
        "cluster_merit_aggregation_performed": False,
        "merit_baseline_mode": "legacy_merit",
        "merit_baseline_available": True,
        "merit_shadow_evaluated_per_completed_member": True,
        "synthetic_merit_baseline_used": False,
        "live_merit_shadow_only": True,
        "live_release_not_called": True,
        "score_effect_applied": False,
        "establishes_truth": False,
        "establishes_authority": False,
        "establishes_independence": False,
        "affects_live_merit": False,
    }


def registration(
    *,
    right_media: str,
    subject_id: str = SUBJECT_ID,
    subject_key: str = SUBJECT_KEY,
    left_media: str = ANCHOR_MEDIA,
):
    return {
        "version": (
            multimodal_binding_registration
            .MULTIMODAL_BINDING_REGISTRATION_VERSION
        ),
        "status": "registered",
        "subject": {
            "entity_id": subject_id,
            "entity_key": subject_key,
            "entity_type": "player",
            "canonical_name": "Player One",
            "sport_key": "football",
        },
        "subject_key": subject_key,
        "left": {
            "source_id": "source-anchor",
            "media_item_id": left_media,
            "story_id": "",
        },
        "right": {
            "source_id": "source-peer",
            "media_item_id": right_media,
            "story_id": "",
        },
        "policy": {
            "source_and_media_persisted_atomically": True,
            "story_record_created": False,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }


def completed_member(
    capture_id: str,
    claim_id: str,
    media_id: str,
    *,
    left_media: str = ANCHOR_MEDIA,
):
    shadow = {
        "version": (
            multimodal_shadow_orchestration
            .MULTIMODAL_SHADOW_ORCHESTRATION_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": claim_id,
        "registration": registration(
            right_media=media_id,
            left_media=left_media,
        ),
    }
    inbox = {
        "version": (
            multimodal_inbox_shadow_orchestration
            .MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": claim_id,
        "left_capture_record_id": ANCHOR_CAPTURE,
        "right_capture_record_id": capture_id,
        "orchestration": shadow,
    }
    candidate = {
        "version": (
            inbox_candidate_shadow_orchestration
            .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": claim_id,
        "anchor_capture_record_id": ANCHOR_CAPTURE,
        "candidate_capture_record_id": capture_id,
        "subject_entity_id": SUBJECT_ID,
        "orchestration": inbox,
    }
    return {
        "capture_record_id": capture_id,
        "claim_id": claim_id,
        "candidate_score": 0.91,
        "candidate_reasons": ["lexical_overlap"],
        "orchestration": candidate,
    }


def safe_cluster(*, two_claims=True):
    members = [
        completed_member("capture-1", "claim-1", "media-1"),
        completed_member("capture-2", "claim-1", "media-2"),
    ]
    groups = [
        {
            "claim_id": "claim-1",
            "member_capture_record_ids": [
                "capture-1",
                "capture-2",
            ],
            "member_count": 2,
        }
    ]
    claim_ids = ["claim-1"]

    if two_claims:
        members.append(
            completed_member(
                "capture-3",
                "claim-2",
                "media-3",
            )
        )
        groups.append({
            "claim_id": "claim-2",
            "member_capture_record_ids": [
                "capture-3",
            ],
            "member_count": 1,
        })
        claim_ids.append("claim-2")

    return {
        "version": (
            inbox_story_cluster_orchestration
            .MULTIMODAL_INBOX_STORY_CLUSTER_VERSION
        ),
        "status": "completed_shadow",
        "anchor_capture_record_id": ANCHOR_CAPTURE,
        "execution_mode": "article_history_merit",
        "claim_id": (
            claim_ids[0]
            if len(claim_ids) == 1
            else ""
        ),
        "claim_ids": claim_ids,
        "claim_groups": groups,
        "selected_subject_entity_id": SUBJECT_ID,
        "selected_candidate_capture_record_id": "",
        "selected_candidate_capture_record_ids": [
            item["capture_record_id"]
            for item in members
        ],
        "completed_members": members,
        "rejected_members": [{
            "capture_record_id": "rejected-1",
            "reason": "downstream_no_exact_common_claim",
            "candidate_score": 0.99,
        }],
        "baseline_resolution": {},
        "policy": cluster_policy(),
    }


class StoryClaimGraphMaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "story-graph.db"
        conn = connect_database(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id, entity_key, entity_type, sport_key,
                  canonical_name, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, 'player', 'football', ?, ?, ?, '{}')
                """,
                (
                    SUBJECT_ID,
                    SUBJECT_KEY,
                    "Player One",
                    "2026-08-17T00:00:00Z",
                    "2026-08-17T00:00:00Z",
                ),
            )
            for claim_id, text in (
                ("claim-1", "Player One agrees transfer terms"),
                ("claim-2", "Club schedules medical for Player One"),
            ):
                conn.execute(
                    """
                    INSERT INTO intelligence_claims (
                      id, canonical_key, subject_key, canonical_text,
                      claim_type, first_seen_at, last_seen_at,
                      metadata_json
                    ) VALUES (?, ?, ?, ?, 'assertion', ?, ?, '{}')
                    """,
                    (
                        claim_id,
                        "key:" + claim_id,
                        SUBJECT_KEY,
                        text,
                        "2026-08-17T00:00:00Z",
                        "2026-08-17T00:00:00Z",
                    ),
                )
            for media_id in (
                ANCHOR_MEDIA,
                "media-1",
                "media-2",
                "media-3",
            ):
                conn.execute(
                    """
                    INSERT INTO media_items (
                      id, canonical_url, mode, source_id,
                      reporter_id, title, published_at,
                      latest_content_hash, first_seen_at,
                      last_seen_at, metadata_json
                    ) VALUES (?, ?, 'article', NULL, NULL, '', NULL, ?, ?, ?, '{}')
                    """,
                    (
                        media_id,
                        "https://example.com/" + media_id,
                        "hash-" + media_id,
                        "2026-08-17T00:00:00Z",
                        "2026-08-17T00:00:00Z",
                    ),
                )
            conn.commit()
        finally:
            conn.close()

        self.factory = lambda: connect_database(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def one(self, sql, params=()):
        conn = self.factory()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def count(self, table):
        conn = self.factory()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM " + table
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def run_graph(self, value=None, *, now="2026-08-17T12:00:00Z"):
        return graph.materialize_story_claim_graph(
            cluster_result=(value if value is not None else safe_cluster()),
            connection_factory=self.factory,
            now_provider=lambda: now,
        )

    def interoperable_claim_and_cluster(self):
        initialize_database(self.factory, SCHEMA)
        claim = materialize_canonical_claim(
            candidate={
                "version": "canonical-claim-contract-v1",
                "subject_key": SUBJECT_KEY,
                "event_type": "transfer",
                "state": "completed",
                "negated": False,
                "roles": {"destination": "club:arsenal"},
                "facets": {},
            },
            claim_text="Player One joins Arsenal",
            observed_at="2026-08-17T10:00:00Z",
            connection_factory=self.factory,
        )
        claim_id = claim["claim"]["id"]
        members = [
            completed_member("capture-1", claim_id, "media-1"),
            completed_member("capture-2", claim_id, "media-2"),
        ]
        cluster = safe_cluster(two_claims=False)
        cluster["claim_id"] = claim_id
        cluster["claim_ids"] = [claim_id]
        cluster["claim_groups"] = [{
            "claim_id": claim_id,
            "member_capture_record_ids": ["capture-1", "capture-2"],
            "member_count": 2,
        }]
        cluster["completed_members"] = members
        return claim_id, cluster

    def assert_interoperable_story(
        self,
        *,
        claim_id,
        expected_generic_version,
        expect_graph,
        expect_canonical,
        expect_subject_entity=True,
    ):
        canonical_key = "multimodal-exact-claim-v1|claim:" + claim_id
        story_id = story_id_for_canonical_key(canonical_key)
        row = self.one(
            "SELECT * FROM intelligence_stories WHERE id = ?",
            (story_id,),
        )
        self.assertIsNotNone(row)
        metadata = json.loads(row["metadata_json"])
        self.assertEqual(metadata["materialization_version"], expected_generic_version)
        self.assertEqual(
            metadata.get("subject_entity_id"),
            SUBJECT_ID if expect_subject_entity else None,
        )
        self.assertEqual(
            metadata.get("story_claim_graph_materialization_version"),
            graph.STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION if expect_graph else None,
        )
        self.assertEqual(
            metadata.get("canonical_claim_story_materialization_version"),
            (
                graph.CANONICAL_CLAIM_STORY_MATERIALIZATION_VERSION
                if expect_canonical
                else None
            ),
        )
        self.assertEqual(self.count("intelligence_stories"), 1)
        self.assertEqual(self.count("story_claim_links"), 1)
        return story_id

    def test_version_is_stable(self):
        self.assertEqual(
            graph.STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION,
            "story-claim-graph-materialization-v1",
        )

    def test_schema_has_direct_story_claim_edge_table(self):
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS story_claim_links",
            SCHEMA,
        )
        self.assertIn(
            "downstream_exact_common_claim_id",
            SCHEMA,
        )

    def test_single_claim_materializes_one_story(self):
        result = self.run_graph(safe_cluster(two_claims=False))
        self.assertEqual(result["story_count"], 1)
        self.assertEqual(self.count("intelligence_stories"), 1)
        self.assertEqual(self.count("story_claim_links"), 1)
        self.assertEqual(self.count("story_media_links"), 3)

    def test_two_exact_claims_materialize_two_stories(self):
        result = self.run_graph()
        self.assertEqual(result["story_count"], 2)
        self.assertEqual(self.count("intelligence_stories"), 2)
        self.assertEqual(self.count("story_claim_links"), 2)
        self.assertEqual(self.count("story_media_links"), 5)

    def test_story_identity_is_deterministic_from_exact_claim(self):
        result = self.run_graph(safe_cluster(two_claims=False))
        expected = story_id_for_canonical_key(
            "multimodal-exact-claim-v1|claim:claim-1"
        )
        self.assertEqual(result["story_ids"], [expected])

    def test_story_title_comes_from_persisted_claim_text(self):
        result = self.run_graph(safe_cluster(two_claims=False))
        row = self.one(
            "SELECT canonical_title FROM intelligence_stories WHERE id = ?",
            (result["story_ids"][0],),
        )
        self.assertEqual(
            row["canonical_title"],
            "Player One agrees transfer terms",
        )

    def test_repeated_materialization_is_idempotent(self):
        first = self.run_graph()
        second = self.run_graph(now="2026-08-17T13:00:00Z")
        self.assertEqual(first["story_ids"], second["story_ids"])
        self.assertEqual(self.count("intelligence_stories"), 2)
        self.assertEqual(self.count("story_claim_links"), 2)
        self.assertEqual(self.count("story_media_links"), 5)

    def test_multimodal_then_canonical_alternating_replay_preserves_provenance(self):
        claim_id, cluster = self.interoperable_claim_and_cluster()
        expected_story_id = story_id_for_canonical_key(
            "multimodal-exact-claim-v1|claim:" + claim_id
        )

        for index, path in enumerate(("graph", "canonical", "graph", "canonical")):
            if path == "graph":
                result = self.run_graph(cluster, now=f"2026-08-17T1{2 + index}:00:00Z")
                self.assertEqual(result["story_ids"], [expected_story_id])
            else:
                result = graph.materialize_canonical_claim_story(
                    claim_id=claim_id,
                    connection_factory=self.factory,
                    now_provider=lambda index=index: (
                        f"2026-08-17T1{2 + index}:00:00Z"
                    ),
                )
                self.assertEqual(result["story_id"], expected_story_id)
            self.assertEqual(
                self.assert_interoperable_story(
                    claim_id=claim_id,
                    expected_generic_version=(
                        graph.STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION
                    ),
                    expect_graph=True,
                    expect_canonical=index >= 1,
                ),
                expected_story_id,
            )
            self.assertEqual(self.count("story_media_links"), 3)

    def test_canonical_then_multimodal_alternating_replay_preserves_provenance(self):
        claim_id, cluster = self.interoperable_claim_and_cluster()
        expected_story_id = story_id_for_canonical_key(
            "multimodal-exact-claim-v1|claim:" + claim_id
        )

        for index, path in enumerate(("canonical", "graph", "canonical", "graph")):
            if path == "canonical":
                result = graph.materialize_canonical_claim_story(
                    claim_id=claim_id,
                    connection_factory=self.factory,
                    now_provider=lambda index=index: (
                        f"2026-08-17T1{2 + index}:00:00Z"
                    ),
                )
                self.assertEqual(result["story_id"], expected_story_id)
            else:
                result = self.run_graph(cluster, now=f"2026-08-17T1{2 + index}:00:00Z")
                self.assertEqual(result["story_ids"], [expected_story_id])
            self.assertEqual(
                self.assert_interoperable_story(
                    claim_id=claim_id,
                    expected_generic_version=(
                        graph.CANONICAL_CLAIM_STORY_MATERIALIZATION_VERSION
                    ),
                    expect_graph=index >= 1,
                    expect_canonical=True,
                    expect_subject_entity=index >= 1,
                ),
                expected_story_id,
            )
            self.assertEqual(
                self.count("story_media_links"),
                3 if index >= 1 else 0,
            )

    def test_existing_story_status_is_not_downgraded(self):
        first = self.run_graph(safe_cluster(two_claims=False))
        story_id = first["story_ids"][0]
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE intelligence_stories SET status = 'resolved' WHERE id = ?",
                (story_id,),
            )
            conn.commit()
        finally:
            conn.close()
        self.run_graph(safe_cluster(two_claims=False))
        row = self.one(
            "SELECT status FROM intelligence_stories WHERE id = ?",
            (story_id,),
        )
        self.assertEqual(row["status"], "resolved")

    def test_story_claim_edge_records_exact_basis(self):
        self.run_graph(safe_cluster(two_claims=False))
        row = self.one("SELECT * FROM story_claim_links")
        self.assertEqual(
            row["relationship_type"],
            "exact_claim_group",
        )
        self.assertEqual(
            row["link_basis"],
            "downstream_exact_common_claim_id",
        )

    def test_story_media_link_uses_structural_relationship(self):
        self.run_graph(safe_cluster(two_claims=False))
        conn = self.factory()
        try:
            rows = conn.execute(
                "SELECT * FROM story_media_links ORDER BY media_item_id"
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row["relationship_type"], "exact_claim_member")
            self.assertEqual(float(row["confidence"]), 1.0)

    def test_structural_confidence_is_explicitly_not_truth_confidence(self):
        result = self.run_graph(safe_cluster(two_claims=False))
        self.assertTrue(
            result["policy"][
                "structural_link_confidence_is_not_truth_confidence"
            ]
        )
        self.assertFalse(result["policy"]["establishes_truth"])

    def test_raw_candidate_scores_are_not_persisted(self):
        self.run_graph(safe_cluster(two_claims=False))
        row = self.one("SELECT metadata_json FROM intelligence_stories")
        self.assertNotIn("0.91", row["metadata_json"])
        self.assertNotIn("candidate_score", row["metadata_json"])

    def test_rejected_members_are_not_linked(self):
        self.run_graph(safe_cluster(two_claims=False))
        conn = self.factory()
        try:
            rows = conn.execute(
                "SELECT media_item_id FROM story_media_links"
            ).fetchall()
        finally:
            conn.close()
        self.assertNotIn(
            "rejected-1",
            [row["media_item_id"] for row in rows],
        )

    def test_missing_subject_row_fails_closed_and_rolls_back(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM canonical_entities")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))
        self.assertEqual(self.count("intelligence_stories"), 0)

    def test_subject_key_mismatch_fails_closed(self):
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE canonical_entities SET entity_key = 'different:key'"
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))

    def test_missing_claim_fails_closed_and_rolls_back(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM intelligence_claims WHERE id = 'claim-1'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))
        self.assertEqual(self.count("intelligence_stories"), 0)

    def test_claim_subject_mismatch_fails_closed(self):
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE intelligence_claims SET subject_key = 'other:key' WHERE id = 'claim-1'"
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))

    def test_missing_media_fails_closed_and_rolls_back(self):
        conn = self.factory()
        try:
            conn.execute("DELETE FROM media_items WHERE id = 'media-2'")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))
        self.assertEqual(self.count("intelligence_stories"), 0)

    def test_wrong_cluster_version_fails_before_writes(self):
        value = safe_cluster(two_claims=False)
        value["version"] = "wrong"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)
        self.assertEqual(self.count("intelligence_stories"), 0)

    def test_wrong_cluster_status_fails_before_writes(self):
        value = safe_cluster(two_claims=False)
        value["status"] = "partial"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_unsafe_cluster_truth_policy_fails(self):
        value = safe_cluster(two_claims=False)
        value["policy"]["establishes_truth"] = True
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_missing_same_story_boundary_fails(self):
        value = safe_cluster(two_claims=False)
        value["policy"]["same_story_not_established_by_cluster"] = False
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_candidate_shadow_version_mismatch_fails(self):
        value = safe_cluster(two_claims=False)
        value["completed_members"][0]["orchestration"]["version"] = "wrong"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_inbox_shadow_scope_mismatch_fails(self):
        value = safe_cluster(two_claims=False)
        inbox = value["completed_members"][0]["orchestration"]["orchestration"]
        inbox["right_capture_record_id"] = "other"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_binding_subject_mismatch_fails(self):
        value = safe_cluster(two_claims=False)
        reg = (
            value["completed_members"][0]
            ["orchestration"]["orchestration"]
            ["orchestration"]["registration"]
        )
        reg["subject"]["entity_id"] = "other-entity"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_anchor_media_identity_must_be_stable_across_members(self):
        value = safe_cluster(two_claims=False)
        second = value["completed_members"][1]
        reg = (
            second["orchestration"]["orchestration"]
            ["orchestration"]["registration"]
        )
        reg["left"]["media_item_id"] = "other-anchor"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_duplicate_completed_member_fails(self):
        value = safe_cluster(two_claims=False)
        value["completed_members"].append(value["completed_members"][0])
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_duplicate_selected_member_id_fails(self):
        value = safe_cluster(two_claims=False)
        value["selected_candidate_capture_record_ids"].append("capture-1")
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_selected_member_scope_mismatch_fails(self):
        value = safe_cluster(two_claims=False)
        value["selected_candidate_capture_record_ids"] = ["capture-1"]
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_claim_ids_must_be_sorted_unique(self):
        value = safe_cluster()
        value["claim_ids"] = ["claim-2", "claim-1"]
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_group_member_ids_must_be_sorted_unique(self):
        value = safe_cluster(two_claims=False)
        value["claim_groups"][0]["member_capture_record_ids"] = [
            "capture-2",
            "capture-1",
        ]
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_group_member_count_must_match(self):
        value = safe_cluster(two_claims=False)
        value["claim_groups"][0]["member_count"] = 99
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_group_claim_must_match_member_claim(self):
        value = safe_cluster(two_claims=False)
        value["completed_members"][0]["claim_id"] = "claim-2"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_group_cannot_omit_completed_member(self):
        value = safe_cluster(two_claims=False)
        value["claim_groups"][0]["member_capture_record_ids"] = ["capture-1"]
        value["claim_groups"][0]["member_count"] = 1
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_member_cannot_appear_in_two_claim_groups(self):
        value = safe_cluster()
        value["claim_groups"][1]["member_capture_record_ids"] = [
            "capture-1",
            "capture-3",
        ]
        value["claim_groups"][1]["member_count"] = 2
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_duplicate_media_identity_in_group_fails(self):
        value = safe_cluster(two_claims=False)
        reg = (
            value["completed_members"][1]
            ["orchestration"]["orchestration"]
            ["orchestration"]["registration"]
        )
        reg["right"]["media_item_id"] = "media-1"
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(value)

    def test_empty_timestamp_fails_before_writes(self):
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False), now="")
        self.assertEqual(self.count("intelligence_stories"), 0)

    def test_missing_connection_factory_is_input_error(self):
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationInputError
        ):
            graph.materialize_story_claim_graph(
                cluster_result=safe_cluster(two_claims=False),
                connection_factory=None,
            )

    def test_connection_factory_failure_is_persistence_error(self):
        def broken():
            raise RuntimeError("db offline")
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationPersistenceError
        ):
            graph.materialize_story_claim_graph(
                cluster_result=safe_cluster(two_claims=False),
                connection_factory=broken,
            )

    def test_missing_story_claim_table_is_persistence_error(self):
        conn = self.factory()
        try:
            conn.execute("DROP TABLE story_claim_links")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationPersistenceError
        ):
            self.run_graph(safe_cluster(two_claims=False))

    def test_conflicting_existing_story_media_link_fails_closed(self):
        canonical_key = "multimodal-exact-claim-v1|claim:claim-1"
        story_id = story_id_for_canonical_key(canonical_key)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id, canonical_key, canonical_title, status,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, '', 'developing', ?, ?, '{}')
                """,
                (
                    story_id,
                    canonical_key,
                    "2026-08-17T00:00:00Z",
                    "2026-08-17T00:00:00Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO story_media_links (
                  story_id, media_item_id, relationship_type,
                  confidence, linked_at
                ) VALUES (?, ?, 'reports', 0.5, ?)
                """,
                (
                    story_id,
                    ANCHOR_MEDIA,
                    "2026-08-17T00:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))
        self.assertEqual(self.count("story_claim_links"), 0)

    def test_deterministic_story_id_collision_fails_closed(self):
        canonical_key = "multimodal-exact-claim-v1|claim:claim-1"
        story_id = story_id_for_canonical_key(canonical_key)
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id, canonical_key, canonical_title, status,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, 'other:key', '', 'developing', ?, ?, '{}')
                """,
                (
                    story_id,
                    "2026-08-17T00:00:00Z",
                    "2026-08-17T00:00:00Z",
                ),
            )
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(
            graph.StoryClaimGraphMaterializationIntegrityError
        ):
            self.run_graph(safe_cluster(two_claims=False))

    def test_materialization_does_not_create_evidence_or_observation_rows(self):
        self.run_graph()
        for table in (
            "evidence_records",
            "source_observations",
            "reporter_observations",
            "observation_dependencies",
            "observation_independence_assertions",
        ):
            with self.subTest(table=table):
                self.assertEqual(self.count(table), 0)

    def test_policy_marks_materialization_atomic_and_idempotent(self):
        result = self.run_graph(safe_cluster(two_claims=False))
        self.assertTrue(result["policy"]["materialization_is_atomic"])
        self.assertTrue(result["policy"]["materialization_is_idempotent"])
        self.assertTrue(result["policy"]["story_claim_edge_persisted"])
        self.assertTrue(result["policy"]["story_media_links_persisted"])

    def test_policy_never_establishes_truth_authority_or_independence(self):
        policy = self.run_graph(safe_cluster(two_claims=False))["policy"]
        self.assertFalse(policy["establishes_truth"])
        self.assertFalse(policy["establishes_authority"])
        self.assertFalse(policy["establishes_independence"])
        self.assertFalse(policy["affects_live_merit"])

    def test_source_contains_no_live_merit_release_calls(self):
        source = Path(graph.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "apply_certified_live_merit",
            "evaluate_live_merit_release",
            "validate_merit_score_release_certificate",
        ):
            self.assertNotIn(forbidden, source)

    def test_story_metadata_contains_no_candidate_score_or_rejected_member(self):
        self.run_graph(safe_cluster(two_claims=False))
        row = self.one("SELECT metadata_json FROM intelligence_stories")
        metadata = json.loads(row["metadata_json"])
        self.assertNotIn("candidate_score", metadata)
        self.assertNotIn("rejected_members", metadata)
        self.assertEqual(metadata["claim_id"], "claim-1")
        self.assertFalse(metadata["truth_established"])


if __name__ == "__main__":
    unittest.main()
