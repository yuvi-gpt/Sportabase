from __future__ import annotations

import inspect
import unittest

from pathlib import Path


from app.services import browser_capture_automation as automation
from app.services import inbox_story_cluster_orchestration as cluster


ANCHOR = "anchor-1"


def safe_cluster(
    *,
    execution_mode="article_history_merit",
):
    legacy = execution_mode == "article_history_merit"
    return {
        "version": cluster.MULTIMODAL_INBOX_STORY_CLUSTER_VERSION,
        "status": "completed_shadow",
        "anchor_capture_record_id": ANCHOR,
        "execution_mode": execution_mode,
        "claim_id": "claim-1",
        "claim_ids": ["claim-1", "claim-2"],
        "selected_candidate_capture_record_id": "",
        "selected_candidate_capture_record_ids": ["c1", "c2"],
        "selected_subject_entity_id": "entity-1",
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
            "merit_baseline_mode": (
                "legacy_merit" if legacy else "not_applicable"
            ),
            "merit_baseline_available": legacy,
            "merit_shadow_evaluated_per_completed_member": legacy,
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


class BrowserCaptureStoryClusterWorkerTests(unittest.TestCase):
    def test_worker_imports_story_cluster_runtime(self):
        source = Path(automation.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "from app.services import inbox_story_cluster_orchestration",
            source,
        )

    def test_default_cluster_runner_is_multisource_runtime(self):
        signature = inspect.signature(
            automation.execute_claimed_browser_capture_job
        )
        default = signature.parameters["cluster_runner"].default
        self.assertIs(
            default,
            cluster.execute_multisource_inbox_story_cluster_shadow,
        )

    def test_legacy_test_injection_surface_remains_available(self):
        signature = inspect.signature(
            automation.execute_claimed_browser_capture_job
        )
        self.assertIn("runner", signature.parameters)
        self.assertIn("non_article_runner", signature.parameters)
        self.assertIsNone(signature.parameters["runner"].default)
        self.assertIsNone(
            signature.parameters["non_article_runner"].default
        )

    def test_article_cluster_result_is_accepted(self):
        result = automation._validate_cluster_shadow_result(
            safe_cluster(execution_mode="article_history_merit"),
            capture_record_id=ANCHOR,
            execution_mode="article_history_merit",
        )
        self.assertEqual(result["claim_ids"], ["claim-1", "claim-2"])

    def test_non_article_cluster_result_is_accepted(self):
        result = automation._validate_cluster_shadow_result(
            safe_cluster(execution_mode="non_article_no_merit"),
            capture_record_id=ANCHOR,
            execution_mode="non_article_no_merit",
        )
        self.assertFalse(result["policy"]["merit_baseline_available"])

    def test_wrong_cluster_version_fails(self):
        value = safe_cluster()
        value["version"] = "wrong"
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_cluster_shadow_result(
                value,
                capture_record_id=ANCHOR,
                execution_mode="article_history_merit",
            )

    def test_wrong_cluster_execution_mode_fails(self):
        value = safe_cluster()
        value["execution_mode"] = "non_article_no_merit"
        with self.assertRaises(
            automation.BrowserCaptureAutomationIntegrityError
        ):
            automation._validate_cluster_shadow_result(
                value,
                capture_record_id=ANCHOR,
                execution_mode="article_history_merit",
            )

    def test_story_claim_safety_policy_is_required(self):
        for field in (
            "cluster_is_routing_candidate_only",
            "cluster_selection_is_read_only",
            "same_story_not_established_by_cluster",
            "claim_groups_formed_only_from_downstream_exact_claim_ids",
            "each_completed_member_passed_exact_common_claim_gate",
            "each_member_revalidated_by_candidate_gate",
            "cluster_does_not_write_story_records_directly",
            "cluster_does_not_link_story_media_directly",
        ):
            value = safe_cluster()
            value["policy"][field] = False
            with self.subTest(field=field):
                with self.assertRaises(
                    automation.BrowserCaptureAutomationIntegrityError
                ):
                    automation._validate_cluster_shadow_result(
                        value,
                        capture_record_id=ANCHOR,
                        execution_mode="article_history_merit",
                    )

    def test_cluster_cannot_apply_merit_or_establish_truth(self):
        for field in (
            "cluster_merit_aggregation_performed",
            "synthetic_merit_baseline_used",
            "score_effect_applied",
            "affects_live_merit",
            "establishes_truth",
            "establishes_authority",
            "establishes_independence",
        ):
            value = safe_cluster()
            value["policy"][field] = True
            with self.subTest(field=field):
                with self.assertRaises(
                    automation.BrowserCaptureAutomationIntegrityError
                ):
                    automation._validate_cluster_shadow_result(
                        value,
                        capture_record_id=ANCHOR,
                        execution_mode="article_history_merit",
                    )

    def test_cluster_requires_nonempty_claim_and_member_lists(self):
        for field in (
            "claim_ids",
            "selected_candidate_capture_record_ids",
        ):
            value = safe_cluster()
            value[field] = []
            with self.subTest(field=field):
                with self.assertRaises(
                    automation.BrowserCaptureAutomationIntegrityError
                ):
                    automation._validate_cluster_shadow_result(
                        value,
                        capture_record_id=ANCHOR,
                        execution_mode="article_history_merit",
                    )

    def test_result_summary_retains_multisource_ids_without_orchestration(self):
        value = safe_cluster()
        value["completed_members"] = [{"secret": "large"}]
        result = automation._result_summary(value)
        self.assertEqual(result["claim_ids"], ["claim-1", "claim-2"])
        self.assertEqual(
            result["selected_candidate_capture_record_ids"],
            ["c1", "c2"],
        )
        self.assertNotIn("completed_members", result)

    def test_worker_source_maps_cluster_failures(self):
        source = Path(automation.__file__).read_text(encoding="utf-8")
        for marker in (
            "MultimodalInboxStoryClusterNotReady",
            "MultimodalInboxStoryClusterLookupError",
            "MultimodalInboxStoryClusterProviderUnavailable",
            "MultimodalInboxStoryClusterExecutionError",
            "MultimodalInboxStoryClusterInputError",
            "MultimodalInboxStoryClusterIntegrityError",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_worker_policy_exposes_cluster_safety_boundaries(self):
        source = Path(automation.__file__).read_text(encoding="utf-8")
        for marker in (
            '"multisource_story_cluster_execution": True',
            '"cluster_selection_is_read_only": True',
            '"cluster_does_not_establish_same_story": True',
            '"cluster_member_exact_claim_gate_required": True',
            '"cluster_merit_aggregation_performed": False',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)


if __name__ == "__main__":
    unittest.main()
