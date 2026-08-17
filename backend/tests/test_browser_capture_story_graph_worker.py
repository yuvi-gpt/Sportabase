from __future__ import annotations

import inspect
import unittest

from pathlib import Path


from app.services import browser_capture_automation as automation
from app.services import inbox_story_cluster_orchestration as cluster
from app.services import story_claim_graph_materialization as graph


ANCHOR = "anchor-1"
SUBJECT = "entity-1"


def safe_cluster():
    return {
        "version": cluster.MULTIMODAL_INBOX_STORY_CLUSTER_VERSION,
        "status": "completed_shadow",
        "anchor_capture_record_id": ANCHOR,
        "execution_mode": "article_history_merit",
        "claim_id": "claim-1",
        "claim_ids": ["claim-1"],
        "selected_candidate_capture_record_id": "candidate-1",
        "selected_candidate_capture_record_ids": ["candidate-1"],
        "selected_subject_entity_id": SUBJECT,
        "baseline_resolution": {},
        "policy": {
            "cluster_is_routing_candidate_only": True,
            "cluster_selection_is_read_only": True,
            "same_story_not_established_by_cluster": True,
            "claim_groups_formed_only_from_downstream_exact_claim_ids": True,
            "each_completed_member_passed_exact_common_claim_gate": True,
            "each_member_revalidated_by_candidate_gate": True,
            "cluster_does_not_write_story_records_directly": True,
            "cluster_does_not_link_story_media_directly": True,
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
        },
    }


def safe_graph():
    return {
        "version": graph.STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION,
        "status": "materialized",
        "anchor_capture_record_id": ANCHOR,
        "selected_subject_entity_id": SUBJECT,
        "claim_ids": ["claim-1"],
        "story_ids": ["story-1"],
        "story_count": 1,
        "stories": [{"large": "not for queue summary"}],
        "policy": {
            "source_cluster_version_required": True,
            "materialization_requires_downstream_exact_claim_groups": True,
            "nested_binding_provenance_required": True,
            "persisted_claim_subject_must_match_cluster_subject": True,
            "persisted_media_identity_required": True,
            "one_deterministic_story_per_exact_claim_id": True,
            "story_claim_edge_persisted": True,
            "story_media_links_persisted": True,
            "materialization_is_atomic": True,
            "materialization_is_idempotent": True,
            "raw_candidate_scores_not_persisted": True,
            "rejected_cluster_members_not_persisted": True,
            "structural_link_confidence_is_not_truth_confidence": True,
            "story_membership_does_not_establish_truth": True,
            "story_membership_does_not_establish_authority": True,
            "story_membership_does_not_establish_independence": True,
            "story_membership_does_not_verify_evidence": True,
            "live_release_not_called": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }


class BrowserCaptureStoryGraphWorkerTests(unittest.TestCase):
    def test_worker_imports_story_graph_materializer(self):
        source = Path(automation.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "from app.services import story_claim_graph_materialization",
            source,
        )

    def test_default_cluster_runner_remains_locked_31_runtime(self):
        signature = inspect.signature(
            automation.execute_claimed_browser_capture_job
        )
        default = signature.parameters["cluster_runner"].default
        self.assertIs(
            default,
            cluster.execute_multisource_inbox_story_cluster_shadow,
        )

    def test_default_graph_materializer_is_product32_runtime(self):
        signature = inspect.signature(
            automation.execute_claimed_browser_capture_job
        )
        default = signature.parameters[
            "story_graph_materializer"
        ].default
        self.assertIs(
            default,
            graph.materialize_story_claim_graph,
        )

    def test_legacy_pair_injection_surface_remains_available(self):
        signature = inspect.signature(
            automation.execute_claimed_browser_capture_job
        )
        self.assertIsNone(signature.parameters["runner"].default)
        self.assertIsNone(
            signature.parameters["non_article_runner"].default
        )

    def test_safe_story_graph_is_accepted(self):
        result = automation._validate_story_graph_materialization(
            safe_graph(),
            cluster_result=safe_cluster(),
        )
        self.assertEqual(result["story_ids"], ["story-1"])

    def test_wrong_graph_version_fails(self):
        value = safe_graph()
        value["version"] = "wrong"
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )

    def test_wrong_graph_status_fails(self):
        value = safe_graph()
        value["status"] = "partial"
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )

    def test_graph_anchor_scope_must_match_cluster(self):
        value = safe_graph()
        value["anchor_capture_record_id"] = "other"
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )

    def test_graph_subject_scope_must_match_cluster(self):
        value = safe_graph()
        value["selected_subject_entity_id"] = "other"
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )

    def test_graph_claim_scope_must_match_cluster_exactly(self):
        value = safe_graph()
        value["claim_ids"] = ["claim-2"]
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )

    def test_graph_story_count_must_match_unique_ids(self):
        value = safe_graph()
        value["story_count"] = 2
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )
        value = safe_graph()
        value["story_ids"] = ["story-1", "story-1"]
        value["story_count"] = 2
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_story_graph_materialization(
                value,
                cluster_result=safe_cluster(),
            )

    def test_every_graph_safety_boundary_is_required(self):
        required = (
            "source_cluster_version_required",
            "materialization_requires_downstream_exact_claim_groups",
            "nested_binding_provenance_required",
            "persisted_claim_subject_must_match_cluster_subject",
            "persisted_media_identity_required",
            "one_deterministic_story_per_exact_claim_id",
            "story_claim_edge_persisted",
            "story_media_links_persisted",
            "materialization_is_atomic",
            "materialization_is_idempotent",
            "raw_candidate_scores_not_persisted",
            "rejected_cluster_members_not_persisted",
            "structural_link_confidence_is_not_truth_confidence",
            "story_membership_does_not_establish_truth",
            "story_membership_does_not_establish_authority",
            "story_membership_does_not_establish_independence",
            "story_membership_does_not_verify_evidence",
            "live_release_not_called",
        )
        for field in required:
            value = safe_graph()
            value["policy"][field] = False
            with self.subTest(field=field):
                with self.assertRaises(
                    automation.BrowserCaptureAutomationIntegrityError
                ):
                    automation._validate_story_graph_materialization(
                        value,
                        cluster_result=safe_cluster(),
                    )

    def test_graph_cannot_establish_truth_or_affect_merit(self):
        for field in (
            "score_effect_applied",
            "establishes_truth",
            "establishes_authority",
            "establishes_independence",
            "affects_live_merit",
        ):
            value = safe_graph()
            value["policy"][field] = True
            with self.subTest(field=field):
                with self.assertRaises(
                    automation.BrowserCaptureAutomationIntegrityError
                ):
                    automation._validate_story_graph_materialization(
                        value,
                        cluster_result=safe_cluster(),
                    )

    def test_queue_result_summary_retains_only_compact_story_audit(self):
        value = safe_cluster()
        value["story_graph_materialization"] = safe_graph()
        result = automation._result_summary(value)
        self.assertEqual(result["story_ids"], ["story-1"])
        self.assertEqual(result["story_count"], 1)
        self.assertNotIn("stories", result)
        self.assertNotIn("story_graph_materialization", result)

    def test_cluster_is_validated_before_materialization(self):
        source = inspect.getsource(
            automation.execute_claimed_browser_capture_job
        )
        validation_index = source.index(
            "result = _validate_cluster_shadow_result("
        )
        materialize_index = source.index(
            "story_graph_materializer("
        )
        self.assertLess(validation_index, materialize_index)

    def test_legacy_injected_pair_path_bypasses_materialization(self):
        source = inspect.getsource(
            automation.execute_claimed_browser_capture_job
        )
        legacy_start = source.index("if legacy_runner_injected:")
        cluster_start = source.index("else:", legacy_start)
        materialize_index = source.index("story_graph_materializer(")
        self.assertGreater(materialize_index, cluster_start)
        self.assertEqual(source.count("story_graph_materializer("), 1)

    def test_graph_persistence_error_is_retryable(self):
        source = inspect.getsource(
            automation.execute_claimed_browser_capture_job
        )
        self.assertIn(
            "StoryClaimGraphMaterializationPersistenceError",
            source,
        )
        self.assertIn(
            'outcome="story_graph_persistence_unavailable"',
            source,
        )

    def test_graph_input_and_integrity_errors_are_terminal(self):
        source = inspect.getsource(
            automation.execute_claimed_browser_capture_job
        )
        self.assertIn(
            "StoryClaimGraphMaterializationInputError",
            source,
        )
        self.assertIn(
            "StoryClaimGraphMaterializationIntegrityError",
            source,
        )
        self.assertIn(
            'last_outcome="terminal_integrity_or_input_failure"',
            source,
        )

    def test_worker_policy_exposes_graph_boundaries(self):
        source = Path(automation.__file__).read_text(encoding="utf-8")
        for marker in (
            '"validated_story_graph_materialization": True',
            '"story_materialization_requires_exact_claim_groups": True',
            '"story_claim_edges_persisted": True',
            '"story_membership_does_not_establish_truth": True',
            '"story_membership_does_not_establish_independence": True',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
