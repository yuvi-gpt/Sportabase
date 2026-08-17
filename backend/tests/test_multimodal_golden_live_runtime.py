from __future__ import annotations

import io
import unittest

from contextlib import redirect_stderr, redirect_stdout

from evals import golden_live
from evals import golden_live_budget
from evals import golden_live_scoring
from evals import run_multimodal_golden_live


class _FakeResponse:
    def __init__(self, text="{}", usage=None):
        self.text = text
        self.usage_metadata = usage


class _FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response or _FakeResponse()
        self.error = error
        self.calls = []

    def generate_content(self, *, model, contents):
        self.calls.append({"model": model, "contents": contents})
        if self.error is not None:
            raise self.error
        return self.response


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.models = _FakeModels(response=response, error=error)


class TestLiveSubsetContract(unittest.TestCase):
    def test_frozen_subset_has_one_full_case(self):
        self.assertEqual(len(golden_live_scoring.DEFAULT_LIVE_CASE_IDS), 1)

    def test_frozen_subset_is_bellingham_case(self):
        self.assertEqual(
            golden_live_scoring.DEFAULT_LIVE_CASE_IDS,
            ("football_bellingham_real_madrid_2023",),
        )

    def test_selected_cases_resolve_frozen_ids(self):
        selected = golden_live_scoring.selected_cases(
            golden_live_scoring.DEFAULT_LIVE_CASE_IDS
        )
        self.assertEqual(
            [row["case_id"] for row in selected],
            list(golden_live_scoring.DEFAULT_LIVE_CASE_IDS),
        )

    def test_provider_plan_keeps_all_three_routed_members(self):
        plan = golden_live_scoring.provider_call_plan()
        self.assertEqual(plan["candidate_pair_count"], 3)
        self.assertEqual(
            plan["cases"][0]["candidate_labels"],
            ["related_primary", "related_secondary", "hard_negative_same_subject"],
        )

    def test_provider_plan_is_six_to_twelve_calls(self):
        plan = golden_live_scoring.provider_call_plan()
        self.assertEqual(plan["guaranteed_semantic_calls"], 6)
        self.assertEqual(plan["conditional_observation_calls"], 6)
        self.assertEqual(plan["minimum_calls"], 6)
        self.assertEqual(plan["maximum_calls"], 12)
        self.assertEqual(plan["possible_actual_calls"], [6, 8, 10, 12])
        self.assertFalse(plan["exact_pre_run_count_available"])

    def test_unknown_case_is_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_scoring.selected_cases(["not-a-case"])

    def test_duplicate_case_is_rejected(self):
        case_id = golden_live_scoring.DEFAULT_LIVE_CASE_IDS[0]
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_scoring.selected_cases([case_id, case_id])

    def test_empty_case_list_is_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_scoring.selected_cases([])

    def test_true_flag_walk_finds_nested_safety_flags(self):
        found = golden_live_scoring.walk_true_flags(
            {
                "a": {"establishes_truth": True, "affects_live_merit": False},
                "b": [{"establishes_independence": True}],
            },
            ("establishes_truth", "affects_live_merit", "establishes_independence"),
        )
        self.assertEqual(found, {"establishes_truth", "establishes_independence"})

    def test_true_flag_walk_ignores_false_flags(self):
        found = golden_live_scoring.walk_true_flags(
            {"establishes_truth": False},
            ("establishes_truth",),
        )
        self.assertEqual(found, set())

    def test_score_passes_matching_completed_case(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary", "related_secondary"],
            "rejected_member_labels": ["hard_negative_same_subject"],
            "story_count": 1,
            "merit_baseline_mode": "not_applicable",
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertEqual(score["quality_status"], "pass")
        self.assertEqual(score["hard_safety_status"], "pass")

    def test_score_reports_missing_accept_member(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary"],
            "rejected_member_labels": ["hard_negative_same_subject"],
            "story_count": 1,
            "merit_baseline_mode": "not_applicable",
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertIn("accepted_member_recall", score["quality_failures"])

    def test_score_reports_missing_rejected_member(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary", "related_secondary"],
            "rejected_member_labels": [],
            "story_count": 1,
            "merit_baseline_mode": "not_applicable",
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertIn("rejected_member_recall", score["quality_failures"])

    def test_score_reports_story_count_mismatch(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary", "related_secondary"],
            "rejected_member_labels": ["hard_negative_same_subject"],
            "story_count": 2,
            "merit_baseline_mode": "not_applicable",
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertIn("story_count", score["quality_failures"])

    def test_score_reports_synthetic_merit_as_hard_failure(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary", "related_secondary"],
            "rejected_member_labels": ["hard_negative_same_subject"],
            "story_count": 1,
            "merit_baseline_mode": "not_applicable",
            "synthetic_merit_baseline_used": True,
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertIn("synthetic_merit_baseline_used", score["hard_safety_failures"])

    def test_score_reports_live_merit_as_hard_failure(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary", "related_secondary"],
            "rejected_member_labels": ["hard_negative_same_subject"],
            "story_count": 1,
            "merit_baseline_mode": "not_applicable",
            "affects_live_merit": True,
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertIn("affects_live_merit", score["hard_safety_failures"])

    def test_score_reports_truth_as_hard_failure(self):
        case = golden_live_scoring.selected_cases(golden_live_scoring.DEFAULT_LIVE_CASE_IDS)[0]
        observed = {
            "status": "completed",
            "accepted_member_labels": ["related_primary", "related_secondary"],
            "rejected_member_labels": ["hard_negative_same_subject"],
            "story_count": 1,
            "merit_baseline_mode": "not_applicable",
            "establishes_truth": True,
        }
        score = golden_live_scoring.score_case(case=case, observed=observed)
        self.assertIn("establishes_truth", score["hard_safety_failures"])


class TestLiveEvaluationControl(unittest.TestCase):
    def _budget(self):
        return golden_live_budget.BudgetedGeminiGenerator(max_calls=12)

    def test_missing_api_key_requires_client(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live.evaluate_live_golden_subset(api_key="")

    def test_runtime_rejects_budget_that_cannot_cover_full_case(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live.evaluate_live_golden_subset(
                api_key="",
                client=_FakeClient(),
                generator=golden_live_budget.BudgetedGeminiGenerator(max_calls=10),
            )

    def test_not_ready_is_quality_failure_not_hard_safety_failure(self):
        def cluster_runner(**kwargs):
            raise golden_live.inbox_story_cluster_orchestration.MultimodalInboxStoryClusterNotReady(
                "no exact common claim"
            )

        report = golden_live.evaluate_live_golden_subset(
            api_key="",
            client=_FakeClient(),
            generator=self._budget(),
            cluster_runner=cluster_runner,
        )
        self.assertTrue(report["provider_complete"])
        self.assertEqual(report["hard_safety_status"], "pass")
        self.assertEqual(report["quality_case_failures"], [
            golden_live_scoring.DEFAULT_LIVE_CASE_IDS[0]
        ])

    def test_provider_unavailable_marks_run_incomplete(self):
        def cluster_runner(**kwargs):
            raise golden_live.inbox_story_cluster_orchestration.MultimodalInboxStoryClusterProviderUnavailable(
                "provider unavailable"
            )

        report = golden_live.evaluate_live_golden_subset(
            api_key="",
            client=_FakeClient(),
            generator=self._budget(),
            cluster_runner=cluster_runner,
        )
        self.assertFalse(report["provider_complete"])
        self.assertEqual(report["hard_safety_status"], "pass")

    def test_integrity_error_marks_hard_failure(self):
        def cluster_runner(**kwargs):
            raise golden_live.inbox_story_cluster_orchestration.MultimodalInboxStoryClusterIntegrityError(
                "bad provenance"
            )

        report = golden_live.evaluate_live_golden_subset(
            api_key="",
            client=_FakeClient(),
            generator=self._budget(),
            cluster_runner=cluster_runner,
        )
        self.assertEqual(report["hard_safety_status"], "fail")
        self.assertEqual(len(report["infrastructure_failures"]), 1)

    def test_report_includes_call_plan_and_logging_policy(self):
        def cluster_runner(**kwargs):
            raise golden_live.inbox_story_cluster_orchestration.MultimodalInboxStoryClusterNotReady(
                "expected"
            )

        report = golden_live.evaluate_live_golden_subset(
            api_key="",
            client=_FakeClient(),
            generator=self._budget(),
            cluster_runner=cluster_runner,
        )
        self.assertEqual(report["provider_plan"]["maximum_calls"], 12)
        self.assertTrue(report["policy"]["provider_call_plan_logged_before_calls"])
        self.assertTrue(report["policy"]["exact_pre_run_call_count_not_fabricated"])
        self.assertTrue(report["policy"]["per_call_token_usage_logged"])
        self.assertFalse(report["policy"]["production_usage_ledger_written"])
        self.assertFalse(report["policy"]["real_database_used"])

    def test_describe_cli_uses_zero_provider_calls_and_prints_plan(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = run_multimodal_golden_live.main(["--describe"])
        text = output.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("default max provider calls: 12", text)
        self.assertIn("minimum provider calls: 6", text)
        self.assertIn("maximum provider calls: 12", text)
        self.assertIn("possible actual provider calls: 6, 8, 10, 12", text)
        self.assertIn("provider calls made by --describe: 0", text)

    def test_cli_refuses_live_run_without_explicit_opt_in(self):
        error = io.StringIO()
        with redirect_stderr(error):
            code = run_multimodal_golden_live.main([])
        self.assertEqual(code, 2)
        self.assertIn("explicit --live opt-in", error.getvalue())

    def test_cli_rejects_ten_call_budget_before_api_key_or_provider(self):
        output = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = run_multimodal_golden_live.main(["--live", "--max-calls", "10"])
        self.assertEqual(code, 2)
        self.assertIn("cannot cover", error.getvalue())
        self.assertIn("configured hard cap: 10", output.getvalue())


if __name__ == "__main__":
    unittest.main()
