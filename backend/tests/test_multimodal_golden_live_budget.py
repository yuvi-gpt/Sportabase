from __future__ import annotations

import unittest

from types import SimpleNamespace

from evals import golden_live_budget


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


class TestBudgetedGenerator(unittest.TestCase):
    def test_default_budget_is_twelve(self):
        generator = golden_live_budget.BudgetedGeminiGenerator()
        self.assertEqual(generator.max_calls, 12)

    def test_hard_max_is_twelve(self):
        self.assertEqual(golden_live_budget.HARD_MAX_PROVIDER_CALLS, 12)

    def test_zero_budget_is_allowed(self):
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=0)
        self.assertEqual(generator.max_calls, 0)
        self.assertEqual(generator.call_count, 0)

    def test_zero_budget_blocks_before_provider_call(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=0)
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveBudgetExceeded):
            generator(
                client=client,
                client_key="eval",
                mode="fusion",
                model="gemini-test",
                contents="never sent",
            )
        self.assertEqual(client.models.calls, [])

    def test_budget_above_hard_max_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=13)

    def test_negative_budget_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=-1)

    def test_boolean_budget_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=True)

    def test_provider_call_is_forwarded_once(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        response = generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="hello",
        )
        self.assertIs(response, client.models.response)
        self.assertEqual(len(client.models.calls), 1)

    def test_next_call_is_blocked_before_provider_call(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="one",
        )
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveBudgetExceeded):
            generator(
                client=client,
                client_key="eval",
                mode="observation",
                model="gemini-test",
                contents="two",
            )
        self.assertEqual(len(client.models.calls), 1)
        self.assertTrue(generator.budget_exhausted)

    def test_usage_metadata_is_aggregated_exactly(self):
        usage = SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=5,
            total_token_count=18,
            cached_content_token_count=2,
            thoughts_token_count=3,
        )
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="one",
        )
        summary = generator.summary()
        self.assertEqual(summary["prompt_tokens"], 10)
        self.assertEqual(summary["output_tokens"], 5)
        self.assertEqual(summary["thought_tokens"], 3)
        self.assertEqual(summary["cached_tokens"], 2)
        self.assertEqual(summary["total_tokens"], 18)

    def test_total_tokens_fall_back_when_provider_total_missing(self):
        usage = {
            "prompt_token_count": 7,
            "candidates_token_count": 3,
            "thoughts_token_count": 2,
            "total_token_count": 0,
        }
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="one",
        )
        self.assertEqual(generator.summary()["total_tokens"], 12)

    def test_logger_receives_start_and_completed_events(self):
        events = []
        usage = {
            "prompt_token_count": 4,
            "candidates_token_count": 2,
            "thoughts_token_count": 1,
            "total_token_count": 7,
        }
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(
            max_calls=2,
            event_sink=events.append,
        )
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="secret prompt",
        )
        self.assertEqual(
            [event["event"] for event in events],
            ["provider_call_started", "provider_call_completed"],
        )
        self.assertEqual(events[-1]["cumulative_total_tokens"], 7)
        self.assertEqual(events[-1]["remaining_calls"], 1)

    def test_logger_never_receives_prompt_contents(self):
        events = []
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(
            max_calls=1,
            event_sink=events.append,
        )
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="super-secret-prompt",
        )
        serialized = repr(events)
        self.assertNotIn("super-secret-prompt", serialized)
        self.assertNotIn("contents", serialized)

    def test_summary_contains_sanitized_per_call_log(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="not logged",
        )
        summary = generator.summary()
        self.assertEqual(len(summary["call_log"]), 1)
        self.assertNotIn("contents", summary["call_log"][0])
        self.assertNotIn("client_key", summary["call_log"][0])

    def test_provider_error_logs_failed_attempt(self):
        events = []
        client = _FakeClient(error=RuntimeError("provider down"))
        generator = golden_live_budget.BudgetedGeminiGenerator(
            max_calls=1,
            event_sink=events.append,
        )
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveProviderError):
            generator(
                client=client,
                client_key="eval",
                mode="fusion",
                model="gemini-test",
                contents="one",
            )
        self.assertEqual(generator.call_count, 1)
        self.assertEqual(events[-1]["event"], "provider_call_failed")

    def test_summary_groups_calls_by_mode_and_model(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=3)
        for mode, model in (
            ("fusion", "gemini-a"),
            ("fusion", "gemini-a"),
            ("observation", "gemini-b"),
        ):
            generator(
                client=client,
                client_key="eval",
                mode=mode,
                model=model,
                contents="one",
            )
        summary = generator.summary()
        self.assertEqual(summary["calls_by_mode"], {"fusion": 2, "observation": 1})
        self.assertEqual(summary["calls_by_model"], {"gemini-a": 2, "gemini-b": 1})


if __name__ == "__main__":
    unittest.main()
