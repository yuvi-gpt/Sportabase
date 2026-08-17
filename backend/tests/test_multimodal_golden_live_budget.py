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

    def test_hard_budget_is_twelve(self):
        self.assertEqual(golden_live_budget.HARD_MAX_PROVIDER_CALLS, 12)

    def test_zero_budget_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=0)

    def test_budget_above_hard_max_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=13)

    def test_boolean_budget_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=True)

    def test_call_is_forwarded_to_client(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=2)
        response = generator(
            client=client,
            client_key="eval",
            mode="mode-a",
            model="gemini-test",
            contents="hello",
        )
        self.assertIs(response, client.models.response)
        self.assertEqual(len(client.models.calls), 1)
        self.assertEqual(client.models.calls[0]["model"], "gemini-test")

    def test_call_count_increments_once_per_provider_attempt(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=2)
        for mode in ("mode-a", "mode-b"):
            generator(
                client=client,
                client_key="eval",
                mode=mode,
                model="gemini-test",
                contents="payload",
            )
        self.assertEqual(generator.call_count, 2)

    def test_next_call_is_blocked_before_provider_call(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="mode-a",
            model="gemini-test",
            contents="one",
        )
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveBudgetExceeded):
            generator(
                client=client,
                client_key="eval",
                mode="mode-b",
                model="gemini-test",
                contents="two",
            )
        self.assertEqual(len(client.models.calls), 1)
        self.assertTrue(generator.budget_exhausted)

    def test_provider_error_is_wrapped_and_logged(self):
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
                mode="mode-a",
                model="gemini-test",
                contents="one",
            )
        self.assertEqual(generator.call_count, 1)
        self.assertEqual(generator.calls[0]["status"], "failed")
        self.assertEqual(events[-1]["event"], "provider_call_failed")

    def test_missing_client_is_rejected_without_counting_call(self):
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveProviderError):
            generator(
                client=None,
                client_key="eval",
                mode="mode-a",
                model="gemini-test",
                contents="one",
            )
        self.assertEqual(generator.call_count, 0)

    def test_missing_model_is_rejected_without_counting_call(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveProviderError):
            generator(
                client=client,
                client_key="eval",
                mode="mode-a",
                model="",
                contents="one",
            )
        self.assertEqual(generator.call_count, 0)

    def test_usage_metadata_object_is_aggregated(self):
        usage = SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=5,
            total_token_count=17,
            cached_content_token_count=2,
            thoughts_token_count=2,
        )
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="mode-a",
            model="gemini-test",
            contents="one",
        )
        summary = generator.summary()
        self.assertEqual(summary["prompt_tokens"], 10)
        self.assertEqual(summary["output_tokens"], 5)
        self.assertEqual(summary["candidate_tokens"], 5)
        self.assertEqual(summary["thought_tokens"], 2)
        self.assertEqual(summary["total_tokens"], 17)
        self.assertEqual(summary["cached_tokens"], 2)

    def test_total_tokens_fall_back_when_provider_total_is_missing(self):
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

    def test_event_sink_gets_start_and_completed_without_contents(self):
        events = []
        usage = {
            "prompt_token_count": 7,
            "candidates_token_count": 3,
            "thoughts_token_count": 2,
            "total_token_count": 12,
        }
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(
            max_calls=1,
            event_sink=events.append,
        )
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="secret prompt",
        )
        self.assertEqual([event["event"] for event in events], [
            "provider_call_started",
            "provider_call_completed",
        ])
        self.assertFalse(any("contents" in event for event in events))
        self.assertFalse(any("secret prompt" in repr(event) for event in events))
        self.assertEqual(events[-1]["cumulative_total_tokens"], 12)

    def test_summary_retains_sanitized_per_call_token_log(self):
        usage = {
            "prompt_token_count": 4,
            "candidates_token_count": 2,
            "thoughts_token_count": 1,
            "total_token_count": 7,
        }
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=2)
        generator(
            client=client,
            client_key="eval",
            mode="fusion",
            model="gemini-test",
            contents="payload",
        )
        summary = generator.summary()
        self.assertEqual(summary["remaining_calls"], 1)
        self.assertEqual(len(summary["call_log"]), 1)
        self.assertEqual(summary["call_log"][0]["output_tokens"], 2)
        self.assertNotIn("contents", summary["call_log"][0])

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
