from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional

from .golden_capture import clean


DEFAULT_MAX_PROVIDER_CALLS = 12
HARD_MAX_PROVIDER_CALLS = 12


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
        raise MultimodalGoldenLiveInputError(
            "Provider call budget must be an integer."
        )
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalGoldenLiveInputError(
            "Provider call budget must be an integer."
        ) from error
    if result < 0 or result > HARD_MAX_PROVIDER_CALLS:
        raise MultimodalGoldenLiveInputError(
            f"Provider call budget must be between 0 and {HARD_MAX_PROVIDER_CALLS}."
        )
    return result


def _usage_value(usage: Any, field: str) -> int:
    if usage is None:
        return 0
    raw = (
        usage.get(field)
        if isinstance(usage, Mapping)
        else getattr(usage, field, 0)
    )
    if isinstance(raw, bool):
        return 0
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


class BudgetedGeminiGenerator:
    """Evaluation-only Gemini generator with pre-call budget and token telemetry."""

    def __init__(
        self,
        *,
        max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
        event_sink: Optional[Callable[[Mapping[str, Any]], None]] = None,
    ):
        self.max_calls = bounded_calls(max_calls)
        self.calls = []
        self.budget_exhausted = False
        self.event_sink = event_sink

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def _emit(self, event: str, row: Mapping[str, Any]) -> None:
        if not callable(self.event_sink):
            return
        payload = {
            "event": event,
            "call_index": int(row.get("call_index") or 0),
            "max_calls": self.max_calls,
            "mode": clean(row.get("mode")),
            "model": clean(row.get("model")),
            "status": clean(row.get("status")),
            "prompt_tokens": int(row.get("prompt_tokens") or 0),
            "output_tokens": int(row.get("output_tokens") or 0),
            "thought_tokens": int(row.get("thought_tokens") or 0),
            "cached_tokens": int(row.get("cached_tokens") or 0),
            "total_tokens": int(row.get("total_tokens") or 0),
            "remaining_calls": max(0, self.max_calls - self.call_count),
        }
        totals = self._token_totals()
        payload.update(
            {
                "cumulative_calls": self.call_count,
                "cumulative_prompt_tokens": totals["prompt_tokens"],
                "cumulative_output_tokens": totals["output_tokens"],
                "cumulative_thought_tokens": totals["thought_tokens"],
                "cumulative_cached_tokens": totals["cached_tokens"],
                "cumulative_total_tokens": totals["total_tokens"],
            }
        )
        self.event_sink(payload)

    def _token_totals(self) -> Dict[str, int]:
        return {
            "prompt_tokens": sum(
                int(row.get("prompt_tokens") or 0) for row in self.calls
            ),
            "output_tokens": sum(
                int(row.get("output_tokens") or 0) for row in self.calls
            ),
            "thought_tokens": sum(
                int(row.get("thought_tokens") or 0) for row in self.calls
            ),
            "cached_tokens": sum(
                int(row.get("cached_tokens") or 0) for row in self.calls
            ),
            "total_tokens": sum(
                int(row.get("total_tokens") or 0) for row in self.calls
            ),
        }

    def __call__(
        self,
        *,
        client,
        client_key: str,
        mode: str,
        model: str,
        contents,
    ):
        if self.call_count >= self.max_calls:
            self.budget_exhausted = True
            raise MultimodalGoldenLiveBudgetExceeded(
                "Live golden evaluation reached its provider call budget."
            )

        model_name = clean(model)
        mode_name = clean(mode)
        if not model_name:
            raise MultimodalGoldenLiveProviderError(
                "Gemini model name is required."
            )
        if client is None or not hasattr(client, "models"):
            raise MultimodalGoldenLiveProviderError(
                "Gemini client is unavailable."
            )

        row = {
            "call_index": self.call_count + 1,
            "mode": mode_name,
            "model": model_name,
            "status": "started",
            "prompt_tokens": 0,
            "output_tokens": 0,
            "thought_tokens": 0,
            "cached_tokens": 0,
            "total_tokens": 0,
        }
        self.calls.append(row)
        self._emit("provider_call_started", row)

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
        except MultimodalGoldenLiveError:
            row["status"] = "failed"
            self._emit("provider_call_failed", row)
            raise
        except Exception as error:
            row["status"] = "failed"
            row["error_type"] = type(error).__name__
            self._emit("provider_call_failed", row)
            raise MultimodalGoldenLiveProviderError(
                "Gemini provider call failed."
            ) from error

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = _usage_value(usage, "prompt_token_count")
        output_tokens = _usage_value(usage, "candidates_token_count")
        thought_tokens = _usage_value(usage, "thoughts_token_count")
        cached_tokens = _usage_value(usage, "cached_content_token_count")
        total_tokens = _usage_value(usage, "total_token_count")
        if total_tokens <= 0:
            total_tokens = prompt_tokens + output_tokens + thought_tokens

        row.update(
            {
                "status": "completed",
                "prompt_tokens": prompt_tokens,
                "output_tokens": output_tokens,
                "thought_tokens": thought_tokens,
                "cached_tokens": cached_tokens,
                "total_tokens": total_tokens,
            }
        )
        self._emit("provider_call_completed", row)
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

        totals = self._token_totals()
        safe_log = [
            {
                "call_index": int(row.get("call_index") or 0),
                "mode": clean(row.get("mode")),
                "model": clean(row.get("model")),
                "status": clean(row.get("status")),
                "prompt_tokens": int(row.get("prompt_tokens") or 0),
                "output_tokens": int(row.get("output_tokens") or 0),
                "thought_tokens": int(row.get("thought_tokens") or 0),
                "cached_tokens": int(row.get("cached_tokens") or 0),
                "total_tokens": int(row.get("total_tokens") or 0),
                **(
                    {"error_type": clean(row.get("error_type"))}
                    if clean(row.get("error_type"))
                    else {}
                ),
            }
            for row in self.calls
        ]
        return {
            "call_count": self.call_count,
            "max_calls": self.max_calls,
            "budget_exhausted": self.budget_exhausted,
            "remaining_calls": max(0, self.max_calls - self.call_count),
            "calls_by_mode": dict(sorted(by_mode.items())),
            "calls_by_model": dict(sorted(by_model.items())),
            **totals,
            "call_log": safe_log,
        }
