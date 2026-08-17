from __future__ import annotations

from typing import Any, Dict, Mapping

from .golden_capture import clean

DEFAULT_MAX_PROVIDER_CALLS = 24
HARD_MAX_PROVIDER_CALLS = 24


class MultimodalGoldenLiveError(RuntimeError):
    pass


class MultimodalGoldenLiveInputError(MultimodalGoldenLiveError):
    pass


class MultimodalGoldenLiveBudgetExceeded(MultimodalGoldenLiveError):
    pass


class MultimodalGoldenLiveProviderError(MultimodalGoldenLiveError):
    pass


def bounded_calls(value: Any) -> int:
    if isinstance(value, bool):
        raise MultimodalGoldenLiveInputError("Provider call budget must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalGoldenLiveInputError("Provider call budget must be an integer.") from error
    if result < 1 or result > HARD_MAX_PROVIDER_CALLS:
        raise MultimodalGoldenLiveInputError(
            f"Provider call budget must be between 1 and {HARD_MAX_PROVIDER_CALLS}."
        )
    return result


def _usage_value(usage: Any, field: str) -> int:
    if usage is None:
        return 0
    raw = usage.get(field) if isinstance(usage, Mapping) else getattr(usage, field, 0)
    if isinstance(raw, bool):
        return 0
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


class BudgetedGeminiGenerator:
    """Evaluation-only Gemini generator with a pre-call hard budget."""

    def __init__(self, *, max_calls: int = DEFAULT_MAX_PROVIDER_CALLS):
        self.max_calls = bounded_calls(max_calls)
        self.calls = []
        self.budget_exhausted = False

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def __call__(self, *, client, client_key: str, mode: str, model: str, contents):
        if self.call_count >= self.max_calls:
            self.budget_exhausted = True
            raise MultimodalGoldenLiveBudgetExceeded(
                "Live golden evaluation reached its provider call budget."
            )
        model_name = clean(model)
        mode_name = clean(mode)
        if not model_name:
            raise MultimodalGoldenLiveProviderError("Gemini model name is required.")
        if client is None or not hasattr(client, "models"):
            raise MultimodalGoldenLiveProviderError("Gemini client is unavailable.")

        row = {
            "call_index": self.call_count + 1,
            "mode": mode_name,
            "model": model_name,
            "client_key": clean(client_key) or "anonymous",
            "status": "started",
            "prompt_tokens": 0,
            "candidate_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "thought_tokens": 0,
        }
        self.calls.append(row)
        try:
            response = client.models.generate_content(model=model_name, contents=contents)
        except MultimodalGoldenLiveError:
            row["status"] = "failed"
            raise
        except Exception as error:
            row["status"] = "failed"
            row["error_type"] = type(error).__name__
            raise MultimodalGoldenLiveProviderError("Gemini provider call failed.") from error

        usage = getattr(response, "usage_metadata", None)
        row.update({
            "status": "completed",
            "prompt_tokens": _usage_value(usage, "prompt_token_count"),
            "candidate_tokens": _usage_value(usage, "candidates_token_count"),
            "total_tokens": _usage_value(usage, "total_token_count"),
            "cached_tokens": _usage_value(usage, "cached_content_token_count"),
            "thought_tokens": _usage_value(usage, "thoughts_token_count"),
        })
        return response

    def summary(self) -> Dict[str, Any]:
        by_mode: Dict[str, int] = {}
        by_model: Dict[str, int] = {}
        for row in self.calls:
            mode = clean(row.get("mode"))
            model = clean(row.get("model"))
            if mode:
                by_mode[mode] = by_mode.get(mode, 0) + 1
            if model:
                by_model[model] = by_model.get(model, 0) + 1
        return {
            "call_count": self.call_count,
            "max_calls": self.max_calls,
            "budget_exhausted": self.budget_exhausted,
            "calls_by_mode": dict(sorted(by_mode.items())),
            "calls_by_model": dict(sorted(by_model.items())),
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in self.calls),
            "candidate_tokens": sum(int(row.get("candidate_tokens") or 0) for row in self.calls),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in self.calls),
            "cached_tokens": sum(int(row.get("cached_tokens") or 0) for row in self.calls),
            "thought_tokens": sum(int(row.get("thought_tokens") or 0) for row in self.calls),
        }
