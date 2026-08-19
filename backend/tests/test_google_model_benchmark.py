from __future__ import annotations

import json
import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark import (
    ARTICLE_BENCHMARK_VERSION,
    DEFAULT_CHALLENGER_RESOURCE_IDS,
    DEFAULT_LIVE_BENCHMARK_CASE_IDS,
    GOLDEN_ARTICLE_SINGLE_PASS_CASES,
    article_benchmark_case,
    build_article_single_pass_benchmark_plan,
    compile_article_single_pass_evaluation_cases,
    score_article_single_pass_observation,
    score_article_single_pass_run,
    select_article_benchmark_cases,
)
from app.ai.evaluation import (
    EvaluationBudget,
    EvaluationBudgetExceeded,
    EvaluationObservation,
    EvaluationRun,
)
from app.ai.tasks import ARTICLE_SINGLE_PASS
from app.services.article_rules import AI_ARTICLE_TYPE_VALUES


class GoogleModelBenchmarkCorpusTests(unittest.TestCase):
    def test_golden_cases_are_unique_and_supported(self):
        case_ids = [
            case.case_id
            for case in GOLDEN_ARTICLE_SINGLE_PASS_CASES
        ]

        self.assertEqual(len(case_ids), len(set(case_ids)))
        self.assertGreaterEqual(len(case_ids), 4)

        for case in GOLDEN_ARTICLE_SINGLE_PASS_CASES:
            with self.subTest(case=case.case_id):
                self.assertIn(
                    case.expected_article_type,
                    AI_ARTICLE_TYPE_VALUES,
                )
                self.assertGreaterEqual(len(case.required_facts), 2)

    def test_default_live_set_is_two_transfer_boundary_cases(self):
        self.assertEqual(
            DEFAULT_LIVE_BENCHMARK_CASE_IDS,
            (
                "transfer-official-clear",
                "transfer-rumor-hedged",
            ),
        )

        cases = select_article_benchmark_cases()

        self.assertEqual(
            tuple(case.case_id for case in cases),
            DEFAULT_LIVE_BENCHMARK_CASE_IDS,
        )
        self.assertEqual(
            tuple(case.expected_article_type for case in cases),
            (
                "transfer_official",
                "transfer_rumor",
            ),
        )

    def test_unknown_case_fails_closed(self):
        with self.assertRaises(KeyError):
            article_benchmark_case("not-a-case")

    def test_duplicate_selection_fails_closed(self):
        with self.assertRaises(ValueError):
            select_article_benchmark_cases(
                (
                    "transfer-official-clear",
                    "transfer-official-clear",
                )
            )

    def test_compiler_reuses_production_single_pass_prompt(self):
        case = article_benchmark_case(
            "transfer-official-clear"
        )

        compiled = compile_article_single_pass_evaluation_cases(
            (case,)
        )

        self.assertEqual(len(compiled), 1)
        evaluation_case = compiled[0]

        self.assertEqual(
            evaluation_case.task_id,
            ARTICLE_SINGLE_PASS,
        )
        self.assertEqual(
            evaluation_case.case_id,
            case.case_id,
        )
        self.assertIn(
            "Return ONLY valid JSON.",
            evaluation_case.contents,
        )
        self.assertIn(
            "Allowed article_type values:",
            evaluation_case.contents,
        )
        self.assertIn(case.title, evaluation_case.contents)
        self.assertIn(case.text, evaluation_case.contents)
        self.assertIn(case.url, evaluation_case.contents)
        self.assertIn(
            "Do not call a transfer official unless",
            evaluation_case.contents,
        )

    def test_default_plan_is_six_calls_and_capacity_gated(self):
        cases, plan = build_article_single_pass_benchmark_plan(
            capacity_configured_resolver=lambda _: False,
        )

        self.assertEqual(len(cases), 2)
        self.assertEqual(
            DEFAULT_CHALLENGER_RESOURCE_IDS,
            (
                "gemini-3.6-flash",
                "gemma-4-26b-a4b-it",
            ),
        )
        self.assertEqual(plan.planned_provider_calls, 6)
        self.assertEqual(plan.executable_provider_calls, 2)
        self.assertEqual(plan.blocked_provider_calls, 4)
        self.assertLessEqual(
            plan.planned_provider_calls,
            plan.budget.max_provider_calls,
        )

        resources_by_case = {}

        for item in plan.items:
            resources_by_case.setdefault(
                item.case_id,
                [],
            ).append(item.resource_id)

        for case in cases:
            self.assertEqual(
                resources_by_case[case.case_id],
                [
                    "gemini-3.5-flash",
                    "gemini-3.6-flash",
                    "gemma-4-26b-a4b-it",
                ],
            )

    def test_expanding_default_matrix_past_budget_fails_closed(self):
        with self.assertRaises(EvaluationBudgetExceeded):
            build_article_single_pass_benchmark_plan(
                case_ids=(
                    "transfer-official-clear",
                    "transfer-rumor-hedged",
                    "transfer-roundup-grades",
                ),
                capacity_configured_resolver=lambda _: True,
                budget=EvaluationBudget(
                    max_provider_calls=8,
                    max_estimated_input_tokens=100_000,
                ),
            )


class GoogleModelBenchmarkScoringTests(unittest.TestCase):
    def _observation(
        self,
        *,
        case_id,
        resource_id="gemini-3.5-flash",
        article_type="transfer_official",
        bullets=None,
        success=True,
        latency_ms=100,
        total_tokens=50,
    ):
        if bullets is None:
            bullets = [
                "Mateo Silva joined Northbridge FC on a permanent transfer.",
                "Silva signed a four-year contract running until June 2030.",
                "Portside United separately confirmed the completed move.",
            ]

        payload = {
            "article_type": article_type,
            "article_subtype": "benchmark",
            "confidence": 0.9,
            "reason": "Classification based on the supplied source.",
            "bullets": bullets,
            "ui_labels": {},
        }

        return EvaluationObservation(
            case_id=case_id,
            task_id=ARTICLE_SINGLE_PASS,
            resource_id=resource_id,
            success=success,
            latency_ms=latency_ms,
            prompt_tokens=30,
            output_tokens=20,
            thought_tokens=0,
            total_tokens=total_tokens,
            output={
                "text": json.dumps(payload),
                "usage": {
                    "prompt_tokens": 30,
                    "output_tokens": 20,
                    "total_tokens": total_tokens,
                },
            },
        )

    def test_perfect_observation_scores_one(self):
        case = article_benchmark_case(
            "transfer-official-clear"
        )
        observation = self._observation(
            case_id=case.case_id
        )

        score = score_article_single_pass_observation(
            observation,
            case=case,
        )

        self.assertTrue(score.success)
        self.assertTrue(score.json_valid)
        self.assertTrue(score.classification_correct)
        self.assertTrue(score.bullet_contract_met)
        self.assertEqual(
            score.required_fact_hits,
            score.required_fact_count,
        )
        self.assertEqual(score.required_fact_coverage, 1.0)
        self.assertEqual(score.overall_score, 1.0)

    def test_wrong_classification_loses_classification_weight(self):
        case = article_benchmark_case(
            "transfer-official-clear"
        )
        observation = self._observation(
            case_id=case.case_id,
            article_type="transfer_rumor",
        )

        score = score_article_single_pass_observation(
            observation,
            case=case,
        )

        self.assertFalse(score.classification_correct)
        self.assertEqual(score.overall_score, 0.55)

    def test_failed_observation_scores_zero(self):
        case = article_benchmark_case(
            "transfer-official-clear"
        )
        observation = self._observation(
            case_id=case.case_id,
            success=False,
        )

        score = score_article_single_pass_observation(
            observation,
            case=case,
        )

        self.assertEqual(score.overall_score, 0.0)

    def test_report_aggregates_resources_deterministically(self):
        official = article_benchmark_case(
            "transfer-official-clear"
        )
        rumor = article_benchmark_case(
            "transfer-rumor-hedged"
        )

        observations = (
            self._observation(
                case_id=official.case_id,
                resource_id="gemini-3.5-flash",
                article_type="transfer_official",
                latency_ms=120,
                total_tokens=50,
            ),
            self._observation(
                case_id=rumor.case_id,
                resource_id="gemini-3.5-flash",
                article_type="transfer_rumor",
                bullets=[
                    "Eastport United are monitoring Jonas Keller ahead of the summer window.",
                    "Westhaven have received no formal offer from Eastport United.",
                    "There is no agreement with the player or his club.",
                ],
                latency_ms=100,
                total_tokens=40,
            ),
            self._observation(
                case_id=official.case_id,
                resource_id="gemma-4-26b-a4b-it",
                article_type="transfer_rumor",
                latency_ms=80,
                total_tokens=35,
            ),
            self._observation(
                case_id=rumor.case_id,
                resource_id="gemma-4-26b-a4b-it",
                article_type="transfer_rumor",
                bullets=[
                    "Eastport United are monitoring Jonas Keller ahead of the summer window.",
                    "Westhaven have received no formal offer from Eastport United.",
                    "There is no agreement with the player or his club.",
                ],
                latency_ms=70,
                total_tokens=30,
            ),
        )

        _, plan = build_article_single_pass_benchmark_plan(
            case_ids=(
                official.case_id,
                rumor.case_id,
            ),
            candidate_resource_ids=(
                "gemma-4-26b-a4b-it",
            ),
            capacity_configured_resolver=lambda _: True,
        )

        run = EvaluationRun(
            version="test-run",
            plan=plan,
            observations=observations,
        )

        report = score_article_single_pass_run(
            run,
            cases=(official, rumor),
        )

        self.assertEqual(
            report.version,
            ARTICLE_BENCHMARK_VERSION,
        )
        self.assertEqual(len(report.resource_summaries), 2)
        self.assertEqual(
            report.resource_summaries[0].resource_id,
            "gemini-3.5-flash",
        )
        self.assertGreater(
            report.resource_summaries[0].average_score,
            report.resource_summaries[1].average_score,
        )
        self.assertEqual(
            report.resource_summaries[0].classification_accuracy,
            1.0,
        )
        self.assertEqual(
            report.resource_summaries[1].classification_accuracy,
            0.5,
        )

    def test_malformed_json_is_scored_without_crashing(self):
        case = article_benchmark_case(
            "transfer-official-clear"
        )
        observation = EvaluationObservation(
            case_id=case.case_id,
            task_id=ARTICLE_SINGLE_PASS,
            resource_id="gemini-3.5-flash",
            success=True,
            latency_ms=10,
            prompt_tokens=1,
            output_tokens=1,
            thought_tokens=0,
            total_tokens=2,
            output={"text": "not-json"},
        )

        score = score_article_single_pass_observation(
            observation,
            case=case,
        )

        self.assertFalse(score.json_valid)
        self.assertFalse(score.classification_correct)
        self.assertFalse(score.bullet_contract_met)
        self.assertEqual(score.overall_score, 0.0)


if __name__ == "__main__":
    unittest.main()
