from __future__ import annotations

import io
import unittest

from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace

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
        self.calls.append({
            "model": model,
            "contents": contents,
        })
        if self.error is not None:
            raise self.error
        return self.response


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.models = _FakeModels(
            response=response,
            error=error,
        )


class TestBudgetedGenerator(unittest.TestCase):
    def test_default_budget_is_hard_max(self):
        generator = golden_live_budget.BudgetedGeminiGenerator()
        self.assertEqual(generator.max_calls, 24)

    def test_zero_budget_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=0)

    def test_budget_above_hard_max_rejected(self):
        with self.assertRaises(golden_live_budget.MultimodalGoldenLiveInputError):
            golden_live_budget.BudgetedGeminiGenerator(max_calls=25)

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
        generator(
            client=client,
            client_key="eval",
            mode="mode-a",
            model="gemini-test",
            contents="one",
        )
        generator(
            client=client,
            client_key="eval",
            mode="mode-b",
            model="gemini-test",
            contents="two",
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

    def test_provider_error_is_wrapped(self):
        client = _FakeClient(error=RuntimeError("provider down"))
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
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
            total_token_count=15,
            cached_content_token_count=2,
            thoughts_token_count=1,
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
        self.assertEqual(summary["candidate_tokens"], 5)
        self.assertEqual(summary["total_tokens"], 15)
        self.assertEqual(summary["cached_tokens"], 2)
        self.assertEqual(summary["thought_tokens"], 1)

    def test_usage_metadata_mapping_is_aggregated(self):
        usage = {
            "prompt_token_count": 7,
            "candidates_token_count": 3,
            "total_token_count": 10,
        }
        client = _FakeClient(response=_FakeResponse(usage=usage))
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=1)
        generator(
            client=client,
            client_key="eval",
            mode="mode-a",
            model="gemini-test",
            contents="one",
        )
        self.assertEqual(generator.summary()["total_tokens"], 10)

    def test_summary_groups_calls_by_mode(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=3)
        for mode in ("fusion", "fusion", "observation"):
            generator(
                client=client,
                client_key="eval",
                mode=mode,
                model="gemini-test",
                contents="one",
            )
        self.assertEqual(
            generator.summary()["calls_by_mode"],
            {"fusion": 2, "observation": 1},
        )

    def test_summary_groups_calls_by_model(self):
        client = _FakeClient()
        generator = golden_live_budget.BudgetedGeminiGenerator(max_calls=2)
        for model in ("gemini-a", "gemini-b"):
            generator(
                client=client,
                client_key="eval",
                mode="fusion",
                model=model,
                contents="one",
            )
        self.assertEqual(
            generator.summary()["calls_by_model"],
            {"gemini-a": 1, "gemini-b": 1},
        )
