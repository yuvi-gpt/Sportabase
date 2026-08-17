from __future__ import annotations

import copy
import inspect
import unittest

from pathlib import Path


from evals import multimodal_golden as golden
from evals import multimodal_golden_cases as cases_module


class MultimodalGoldenDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = golden.build_golden_cases()
        cls.descriptor = golden.golden_dataset_descriptor()

    def test_versions_are_frozen(self):
        self.assertEqual(
            cases_module.MULTIMODAL_GOLDEN_SET_VERSION,
            "multimodal-golden-set-v1",
        )
        self.assertEqual(
            golden.MULTIMODAL_GOLDEN_EVAL_VERSION,
            "multimodal-golden-eval-v1",
        )
        self.assertEqual(
            golden.MULTIMODAL_GOLDEN_OBSERVED_VERSION,
            "multimodal-golden-observed-v1",
        )

    def test_dataset_has_large_case_count(self):
        self.assertEqual(len(self.cases), 21)
        self.assertGreaterEqual(len(self.cases), 20)

    def test_dataset_has_large_capture_count(self):
        self.assertEqual(self.descriptor["capture_count"], 117)
        self.assertGreaterEqual(self.descriptor["capture_count"], 100)

    def test_dataset_covers_both_sports(self):
        self.assertEqual(self.descriptor["sports"], ["f1", "football"])

    def test_dataset_covers_all_browser_capture_platforms(self):
        self.assertTrue(
            {
                "web",
                "x",
                "instagram",
                "tiktok",
                "reddit",
                "facebook",
                "youtube",
            }.issubset(set(self.descriptor["platforms"]))
        )

    def test_dataset_case_ids_are_unique(self):
        values = [case["case_id"] for case in self.cases]
        self.assertEqual(len(values), len(set(values)))

    def test_each_case_has_exactly_one_anchor_label(self):
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                self.assertIn("anchor", case["captures"])
                self.assertEqual(case["captures"]["anchor"]["role"], "anchor")
                self.assertEqual(
                    sum(value["role"] == "anchor" for value in case["captures"].values()),
                    1,
                )

    def test_corpus_is_explicitly_paraphrased_and_offline(self):
        policy = self.descriptor["corpus_policy"]
        self.assertTrue(policy["historical_scenario_derived"])
        self.assertTrue(policy["capture_text_is_original_paraphrase"])
        self.assertFalse(policy["publisher_verbatim_text_included"])
        self.assertFalse(policy["network_fetch_required"])
        self.assertFalse(policy["gemini_required_for_default_run"])

    def test_golden_labels_are_not_truth_or_authority(self):
        policy = self.descriptor["corpus_policy"]
        self.assertTrue(policy["golden_labels_are_evaluation_labels_not_truth_authority"])
        self.assertFalse(policy["live_merit_effect_allowed"])

    def test_dataset_digest_is_deterministic(self):
        first = golden.golden_dataset_descriptor()["dataset_digest"]
        second = golden.golden_dataset_descriptor()["dataset_digest"]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_standard_cases_keep_same_subject_hard_negative(self):
        standard = next(
            case for case in self.cases
            if case["case_id"] == "f1_hamilton_ferrari_2024"
        )
        self.assertIn(
            "hard_negative_same_subject",
            standard["expectations"]["required_shortlist_labels"],
        )
        self.assertIn(
            "hard_negative_same_subject",
            standard["expectations"]["full_pipeline"]["required_reject_labels"],
        )

    def test_same_url_duplicate_is_a_discovery_exclusion_label(self):
        standard = next(
            case for case in self.cases
            if case["case_id"] == "football_mbappe_real_madrid_2024"
        )
        self.assertIn(
            "same_url_duplicate",
            standard["expectations"]["forbidden_shortlist_labels"],
        )

    def test_multilingual_case_is_present(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "multilingual_hamilton_ferrari"
        )
        labels = set(case["captures"])
        self.assertIn("spanish_related", labels)
        self.assertIn("french_related", labels)

    def test_ambiguous_case_fails_closed_by_label(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "ambiguous_liverpool_transition"
        )
        self.assertEqual(
            case["expectations"]["selection_status"],
            "not_ready_ambiguous",
        )
        self.assertEqual(
            case["expectations"]["full_pipeline"]["expected_status"],
            "not_ready",
        )

    def test_multiple_shared_entity_case_requires_rejection(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "multiple_shared_entities_rejected"
        )
        self.assertEqual(
            case["expectations"]["required_rejected_labels"],
            ["double_shared"],
        )
        self.assertEqual(
            case["expectations"]["required_member_labels"],
            ["single_shared"],
        )

    def test_no_signal_case_is_expected_not_ready(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "no_signal_fail_closed"
        )
        self.assertEqual(case["expectations"]["discovery_status"], "no_candidates")
        self.assertEqual(case["expectations"]["selection_status"], "not_ready_no_candidates")


class MultimodalGoldenRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = golden.build_golden_cases()

    def test_default_runner_hardcodes_zero_semantic_assessments(self):
        source = inspect.getsource(golden.evaluate_golden_case)
        self.assertIn("semantic_assessments=0", source)
        self.assertIn("gemini_client=None", source)
        self.assertIn("gemini_generator=None", source)

    def test_default_runner_uses_temporary_database(self):
        source = inspect.getsource(golden.evaluate_golden_case)
        self.assertIn("TemporaryDirectory", source)
        self.assertIn('Path(tmp) / "golden.db"', source)
        self.assertNotIn("sportabase.db", source)

    def test_eval_library_does_not_import_live_merit_release(self):
        source = Path(golden.__file__).read_text(encoding="utf-8")
        self.assertNotIn("live_merit_release", source)
        self.assertNotIn("apply_certified_live_merit", source)

    def test_one_standard_case_executes_real_discovery_and_selection(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "f1_hamilton_ferrari_2024"
        )
        report = golden.evaluate_golden_case(case)
        self.assertEqual(report["case_id"], case["case_id"])
        self.assertEqual(report["discovery_status"], "candidates_available")
        self.assertTrue(report["safety_policy_pass"])
        self.assertIn("hard_negative_same_subject", report["shortlist_labels"])
        self.assertNotIn("same_url_duplicate", report["shortlist_labels"])

    def test_ambiguous_case_executes_fail_closed(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "ambiguous_liverpool_transition"
        )
        report = golden.evaluate_golden_case(case)
        self.assertEqual(report["selection_status"], "not_ready_ambiguous")
        self.assertTrue(report["safety_policy_pass"])

    def test_no_signal_case_executes_without_inventing_candidate(self):
        case = next(
            item for item in self.cases
            if item["case_id"] == "no_signal_fail_closed"
        )
        report = golden.evaluate_golden_case(case)
        self.assertEqual(report["discovery_status"], "no_candidates")
        self.assertEqual(report["shortlist_labels"], [])
        self.assertEqual(report["selection_status"], "not_ready_no_candidates")

    def test_full_deterministic_report_is_offline_and_no_gemini(self):
        report = golden.evaluate_deterministic_golden_set()
        self.assertEqual(len(report["cases"]), 21)
        self.assertEqual(report["network_fetches"], 0)
        self.assertEqual(report["gemini_calls"], 0)
        self.assertFalse(report["real_database_used"])
        self.assertTrue(report["temporary_database_per_case"])
        self.assertEqual(report["metrics"]["safety_policy_pass_rate"], 1.0)
        self.assertEqual(len(report["report_digest"]), 64)

    def test_report_distinguishes_hard_thresholds_from_quality_targets(self):
        report = golden.evaluate_deterministic_golden_set()
        self.assertEqual(
            set(report["hard_thresholds"]),
            {"forbidden_shortlist_leakage", "safety_policy_pass_rate"},
        )
        self.assertIn("required_shortlist_recall", report["quality_targets"])
        self.assertIn("selection_status_accuracy", report["quality_targets"])


class MultimodalGoldenObservedTests(unittest.TestCase):
    def test_observed_template_matches_dataset(self):
        template = golden.observed_template()
        self.assertEqual(template["version"], golden.MULTIMODAL_GOLDEN_OBSERVED_VERSION)
        self.assertEqual(template["dataset_id"], cases_module.MULTIMODAL_GOLDEN_DATASET_ID)
        self.assertEqual(len(template["cases"]), 21)

    def test_observed_template_scores_cleanly(self):
        report = golden.evaluate_observed_artifact(golden.observed_template())
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["case_pass_rate"], 1.0)
        self.assertEqual(report["case_failures"], [])

    def test_observed_scoring_rejects_synthetic_merit_baseline(self):
        artifact = golden.observed_template()
        case = next(item for item in artifact["cases"] if item["status"] == "completed")
        case["synthetic_merit_baseline_used"] = True
        report = golden.evaluate_observed_artifact(artifact)
        failed = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
        self.assertIn("synthetic_merit_baseline", failed["failures"])
        self.assertEqual(report["status"], "fail")

    def test_observed_scoring_rejects_live_merit_effect(self):
        artifact = golden.observed_template()
        case = next(item for item in artifact["cases"] if item["status"] == "completed")
        case["affects_live_merit"] = True
        report = golden.evaluate_observed_artifact(artifact)
        failed = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
        self.assertIn("live_merit_effect", failed["failures"])

    def test_observed_scoring_rejects_truth_establishment(self):
        artifact = golden.observed_template()
        case = next(item for item in artifact["cases"] if item["status"] == "completed")
        case["establishes_truth"] = True
        report = golden.evaluate_observed_artifact(artifact)
        failed = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
        self.assertIn("establishes_truth", failed["failures"])

    def test_observed_scoring_rejects_wrong_story_count(self):
        artifact = golden.observed_template()
        case = next(item for item in artifact["cases"] if item["status"] == "completed")
        case["story_count"] += 1
        report = golden.evaluate_observed_artifact(artifact)
        failed = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
        self.assertIn("story_count", failed["failures"])

    def test_observed_scoring_rejects_missing_required_member(self):
        artifact = golden.observed_template()
        case = next(
            item for item in artifact["cases"]
            if item.get("accepted_member_labels")
        )
        case["accepted_member_labels"] = []
        report = golden.evaluate_observed_artifact(artifact)
        failed = next(item for item in report["cases"] if item["case_id"] == case["case_id"])
        self.assertIn("accepted_member_recall", failed["failures"])

    def test_observed_scoring_rejects_unknown_case(self):
        artifact = golden.observed_template()
        artifact["cases"].append({"case_id": "unknown-case", "status": "not_ready"})
        report = golden.evaluate_observed_artifact(artifact)
        self.assertIn("unknown-case", report["unknown_case_ids"])
        self.assertIn("unknown_cases", report["case_failures"])

    def test_observed_scoring_rejects_duplicate_case_ids(self):
        artifact = golden.observed_template()
        artifact["cases"].append(copy.deepcopy(artifact["cases"][0]))
        with self.assertRaises(golden.MultimodalGoldenObservedError):
            golden.evaluate_observed_artifact(artifact)

    def test_observed_scoring_rejects_wrong_version(self):
        artifact = golden.observed_template()
        artifact["version"] = "wrong"
        with self.assertRaises(golden.MultimodalGoldenObservedError):
            golden.evaluate_observed_artifact(artifact)


if __name__ == "__main__":
    unittest.main()
