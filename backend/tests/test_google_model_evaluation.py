import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.evaluation import (
    MODEL_EVALUATION_VERSION,
    EvaluationBudget,
    EvaluationBudgetExceeded,
    EvaluationCapacityBlocked,
    EvaluationCase,
    EvaluationExecutionDisabled,
    build_generation_evaluation_plan,
    run_generation_evaluation,
)
from app.ai.tasks import (
    ARTICLE_CLASSIFIER,
    ARTICLE_TLDR,
    RETRIEVAL_EMBEDDING,
)


class GoogleModelEvaluationTests(unittest.TestCase):
    def test_version_is_explicit(self):
        self.assertEqual(
            MODEL_EVALUATION_VERSION,
            "google-model-evaluation-v1",
        )

    def test_primary_only_plan_preserves_current_model(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello world",
                ),
            ),
            capacity_configured_resolver=lambda _: False,
        )

        self.assertEqual(plan.planned_provider_calls, 1)
        self.assertEqual(
            plan.items[0].resource_id,
            "gemini-3.5-flash",
        )
        self.assertEqual(
            plan.items[0].selection_source,
            "task_primary",
        )
        self.assertFalse(
            plan.items[0].capacity_blocked
        )
        self.assertFalse(
            plan.items[0].automatic_fallback_enabled
        )

    def test_candidate_plan_deduplicates_primary(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_CLASSIFIER,
                    contents="example article",
                ),
            ),
            candidate_resource_ids=(
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
            ),
            capacity_configured_resolver=lambda _: True,
        )

        self.assertEqual(
            [item.resource_id for item in plan.items],
            [
                "gemini-3.5-flash",
                "gemini-3.5-flash-lite",
            ],
        )
        self.assertEqual(plan.planned_provider_calls, 2)

    def test_new_resource_is_reported_blocked_without_capacity_config(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            ),
            candidate_resource_ids=(
                "gemma-4-26b-a4b-it",
            ),
            capacity_configured_resolver=lambda resource_id: False,
        )

        self.assertEqual(plan.blocked_provider_calls, 1)
        self.assertEqual(plan.executable_provider_calls, 1)

        blocked = [
            item
            for item in plan.items
            if item.capacity_blocked
        ]

        self.assertEqual(
            [item.resource_id for item in blocked],
            ["gemma-4-26b-a4b-it"],
        )

    def test_configured_candidate_is_not_blocked(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            ),
            candidate_resource_ids=(
                "gemini-3.6-flash",
            ),
            capacity_configured_resolver=lambda resource_id: True,
        )

        self.assertEqual(plan.blocked_provider_calls, 0)
        self.assertEqual(plan.executable_provider_calls, 2)

    def test_provider_call_budget_fails_closed(self):
        with self.assertRaises(EvaluationBudgetExceeded):
            build_generation_evaluation_plan(
                (
                    EvaluationCase(
                        case_id="case-1",
                        task_id=ARTICLE_TLDR,
                        contents="hello",
                    ),
                    EvaluationCase(
                        case_id="case-2",
                        task_id=ARTICLE_TLDR,
                        contents="world",
                    ),
                ),
                candidate_resource_ids=(
                    "gemini-3.5-flash-lite",
                ),
                budget=EvaluationBudget(
                    max_provider_calls=3,
                    max_estimated_input_tokens=10_000,
                ),
                capacity_configured_resolver=lambda _: True,
            )

    def test_token_budget_fails_closed(self):
        with self.assertRaises(EvaluationBudgetExceeded):
            build_generation_evaluation_plan(
                (
                    EvaluationCase(
                        case_id="case-1",
                        task_id=ARTICLE_TLDR,
                        contents="hello",
                    ),
                ),
                budget=EvaluationBudget(
                    max_provider_calls=8,
                    max_estimated_input_tokens=9,
                ),
                token_estimator=lambda _: 10,
            )

    def test_duplicate_case_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            build_generation_evaluation_plan(
                (
                    EvaluationCase(
                        case_id="same",
                        task_id=ARTICLE_TLDR,
                        contents="a",
                    ),
                    EvaluationCase(
                        case_id="same",
                        task_id=ARTICLE_TLDR,
                        contents="b",
                    ),
                )
            )

    def test_empty_case_set_fails_closed(self):
        with self.assertRaises(ValueError):
            build_generation_evaluation_plan(())

    def test_case_without_selected_resource_fails_closed(self):
        with self.assertRaises(ValueError):
            build_generation_evaluation_plan(
                (
                    EvaluationCase(
                        case_id="case-1",
                        task_id=ARTICLE_TLDR,
                        contents="hello",
                    ),
                ),
                include_primary=False,
                candidate_resource_ids=(),
            )

    def test_non_generation_resource_is_rejected(self):
        with self.assertRaises(ValueError):
            build_generation_evaluation_plan(
                (
                    EvaluationCase(
                        case_id="case-1",
                        task_id=RETRIEVAL_EMBEDDING,
                        contents="hello",
                    ),
                ),
                include_primary=False,
                candidate_resource_ids=(
                    "gemini-embedding-2",
                ),
                capacity_configured_resolver=lambda _: True,
            )

    def test_execution_is_disabled_by_default_before_executor_runs(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            )
        )

        calls = []

        with self.assertRaises(EvaluationExecutionDisabled):
            run_generation_evaluation(
                plan,
                executor=lambda item: calls.append(item),
            )

        self.assertEqual(calls, [])

    def test_blocked_plan_stops_before_any_executor_call(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            ),
            candidate_resource_ids=(
                "gemma-4-31b-it",
            ),
            capacity_configured_resolver=lambda _: False,
        )

        calls = []

        with self.assertRaises(EvaluationCapacityBlocked):
            run_generation_evaluation(
                plan,
                executor=lambda item: calls.append(item),
                allow_provider_execution=True,
            )

        self.assertEqual(calls, [])

    def test_fake_execution_records_success_latency_and_usage(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            ),
            capacity_configured_resolver=lambda _: True,
        )

        ticks = iter((1.0, 1.025))

        result = run_generation_evaluation(
            plan,
            executor=lambda item: {
                "resource": item.resource_id,
                "text": "ok",
            },
            allow_provider_execution=True,
            usage_counter=lambda output: {
                "prompt_tokens": 10,
                "output_tokens": 4,
                "thought_tokens": 2,
                "total_tokens": 16,
            },
            clock=lambda: next(ticks),
        )

        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.failure_count, 0)
        self.assertEqual(result.total_tokens, 16)
        self.assertEqual(result.total_latency_ms, 25)

        observation = result.observations[0]
        self.assertTrue(observation.success)
        self.assertEqual(observation.prompt_tokens, 10)
        self.assertEqual(observation.output_tokens, 4)
        self.assertEqual(observation.thought_tokens, 2)
        self.assertEqual(observation.resource_id, "gemini-3.5-flash")

    def test_usage_total_falls_back_to_component_sum(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            )
        )

        ticks = iter((1.0, 1.0))

        result = run_generation_evaluation(
            plan,
            executor=lambda item: "ok",
            allow_provider_execution=True,
            usage_counter=lambda output: {
                "prompt_tokens": 3,
                "output_tokens": 2,
                "thought_tokens": 1,
                "total_tokens": 0,
            },
            clock=lambda: next(ticks),
        )

        self.assertEqual(result.total_tokens, 6)

    def test_executor_failure_is_recorded_and_run_continues(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="a",
                ),
                EvaluationCase(
                    case_id="case-2",
                    task_id=ARTICLE_TLDR,
                    contents="b",
                ),
            ),
            budget=EvaluationBudget(
                max_provider_calls=2,
                max_estimated_input_tokens=10_000,
            ),
        )

        calls = []

        def executor(item):
            calls.append(item.case_id)
            if item.case_id == "case-1":
                raise RuntimeError("provider failed")
            return "ok"

        ticks = iter((1.0, 1.01, 2.0, 2.02))

        result = run_generation_evaluation(
            plan,
            executor=executor,
            allow_provider_execution=True,
            clock=lambda: next(ticks),
        )

        self.assertEqual(calls, ["case-1", "case-2"])
        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(
            result.observations[0].failure_type,
            "RuntimeError",
        )
        self.assertIn(
            "provider failed",
            result.observations[0].failure_detail,
        )
        self.assertTrue(result.observations[1].success)

    def test_plan_summary_contains_no_case_contents(self):
        secret = "do-not-leak-this-content"

        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents=secret,
                ),
            )
        )

        self.assertNotIn(
            secret,
            repr(plan.as_dict()),
        )

    def test_candidate_order_is_stable(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            ),
            include_primary=False,
            candidate_resource_ids=(
                "gemma-4-26b-a4b-it",
                "gemini-3.6-flash",
                "gemini-3.5-flash-lite",
            ),
            budget=EvaluationBudget(
                max_provider_calls=3,
                max_estimated_input_tokens=10_000,
            ),
            capacity_configured_resolver=lambda _: True,
        )

        self.assertEqual(
            [item.resource_id for item in plan.items],
            [
                "gemma-4-26b-a4b-it",
                "gemini-3.6-flash",
                "gemini-3.5-flash-lite",
            ],
        )

    def test_plan_as_dict_reports_budget_and_blocking(self):
        plan = build_generation_evaluation_plan(
            (
                EvaluationCase(
                    case_id="case-1",
                    task_id=ARTICLE_TLDR,
                    contents="hello",
                ),
            ),
            candidate_resource_ids=(
                "gemini-3.6-flash",
            ),
            capacity_configured_resolver=lambda _: False,
        )

        payload = plan.as_dict()

        self.assertEqual(payload["planned_provider_calls"], 2)
        self.assertEqual(payload["blocked_provider_calls"], 1)
        self.assertEqual(payload["executable_provider_calls"], 1)
        self.assertEqual(
            payload["budget"]["max_provider_calls"],
            8,
        )


if __name__ == "__main__":
    unittest.main()
