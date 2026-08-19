from __future__ import annotations

import time

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from app.ai.quota import estimate_prompt_tokens
from app.ai.resources import GENERATION
from app.ai.router import ResourceRoute, route_task
from app.ai.routed_generation import project_capacity_configured


MODEL_EVALUATION_VERSION = "google-model-evaluation-v1"
DEFAULT_EVALUATION_MAX_PROVIDER_CALLS = 8
DEFAULT_EVALUATION_MAX_ESTIMATED_INPUT_TOKENS = 100_000


class EvaluationError(RuntimeError):
    pass


class EvaluationBudgetExceeded(EvaluationError):
    pass


class EvaluationExecutionDisabled(EvaluationError):
    pass


class EvaluationCapacityBlocked(EvaluationError):
    pass


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    task_id: str
    contents: Any

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Evaluation case ID is required.")
        if not str(self.task_id or "").strip():
            raise ValueError("Evaluation task ID is required.")


@dataclass(frozen=True)
class EvaluationBudget:
    max_provider_calls: int = DEFAULT_EVALUATION_MAX_PROVIDER_CALLS
    max_estimated_input_tokens: int = (
        DEFAULT_EVALUATION_MAX_ESTIMATED_INPUT_TOKENS
    )

    def __post_init__(self) -> None:
        if int(self.max_provider_calls) < 1:
            raise ValueError("Evaluation provider-call budget must be >= 1.")
        if int(self.max_estimated_input_tokens) < 1:
            raise ValueError(
                "Evaluation estimated-input-token budget must be >= 1."
            )

    def as_dict(self) -> dict[str, int]:
        return {
            "max_provider_calls": int(self.max_provider_calls),
            "max_estimated_input_tokens": int(
                self.max_estimated_input_tokens
            ),
        }


@dataclass(frozen=True)
class EvaluationPlanItem:
    case_id: str
    task_id: str
    contents: Any
    resource_id: str
    selection_source: str
    estimated_input_tokens: int
    requires_project_capacity_config: bool
    project_capacity_configured: bool
    automatic_fallback_enabled: bool

    @property
    def capacity_blocked(self) -> bool:
        return bool(
            self.requires_project_capacity_config
            and not self.project_capacity_configured
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "selection_source": self.selection_source,
            "estimated_input_tokens": int(self.estimated_input_tokens),
            "requires_project_capacity_config": (
                self.requires_project_capacity_config
            ),
            "project_capacity_configured": (
                self.project_capacity_configured
            ),
            "capacity_blocked": self.capacity_blocked,
            "automatic_fallback_enabled": (
                self.automatic_fallback_enabled
            ),
        }


@dataclass(frozen=True)
class EvaluationPlan:
    version: str
    budget: EvaluationBudget
    items: tuple[EvaluationPlanItem, ...]

    @property
    def planned_provider_calls(self) -> int:
        return len(self.items)

    @property
    def total_estimated_input_tokens(self) -> int:
        return sum(
            int(item.estimated_input_tokens)
            for item in self.items
        )

    @property
    def blocked_provider_calls(self) -> int:
        return sum(
            1
            for item in self.items
            if item.capacity_blocked
        )

    @property
    def executable_provider_calls(self) -> int:
        return self.planned_provider_calls - self.blocked_provider_calls

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "budget": self.budget.as_dict(),
            "planned_provider_calls": self.planned_provider_calls,
            "blocked_provider_calls": self.blocked_provider_calls,
            "executable_provider_calls": self.executable_provider_calls,
            "total_estimated_input_tokens": (
                self.total_estimated_input_tokens
            ),
            "items": [
                item.as_dict()
                for item in self.items
            ],
        }


@dataclass(frozen=True)
class EvaluationObservation:
    case_id: str
    task_id: str
    resource_id: str
    success: bool
    latency_ms: int
    prompt_tokens: int
    output_tokens: int
    thought_tokens: int
    total_tokens: int
    output: Any = None
    failure_type: str = ""
    failure_detail: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "success": self.success,
            "latency_ms": int(self.latency_ms),
            "prompt_tokens": int(self.prompt_tokens),
            "output_tokens": int(self.output_tokens),
            "thought_tokens": int(self.thought_tokens),
            "total_tokens": int(self.total_tokens),
            "output": self.output,
            "failure_type": self.failure_type,
            "failure_detail": self.failure_detail,
        }


@dataclass(frozen=True)
class EvaluationRun:
    version: str
    plan: EvaluationPlan
    observations: tuple[EvaluationObservation, ...]

    @property
    def success_count(self) -> int:
        return sum(
            1
            for observation in self.observations
            if observation.success
        )

    @property
    def failure_count(self) -> int:
        return len(self.observations) - self.success_count

    @property
    def total_tokens(self) -> int:
        return sum(
            int(observation.total_tokens)
            for observation in self.observations
        )

    @property
    def total_latency_ms(self) -> int:
        return sum(
            int(observation.latency_ms)
            for observation in self.observations
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "plan": self.plan.as_dict(),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "observations": [
                observation.as_dict()
                for observation in self.observations
            ],
        }


def _generation_route(
    *,
    task_id: str,
    requested_resource_id: str | None,
) -> ResourceRoute:
    route = route_task(
        task_id,
        requested_resource_id=requested_resource_id,
    )

    if route.resource_kind != GENERATION:
        raise ValueError(
            "Generation evaluation requires a generation resource: "
            + route.resource_id
        )

    if route.automatic_fallback_enabled:
        raise RuntimeError(
            "Evaluation requires automatic fallback to remain disabled: "
            + route.task_id
        )

    return route


def build_generation_evaluation_plan(
    cases: Sequence[EvaluationCase],
    *,
    candidate_resource_ids: Sequence[str] = (),
    include_primary: bool = True,
    budget: EvaluationBudget | None = None,
    token_estimator: Callable[[Any], int] = estimate_prompt_tokens,
    capacity_configured_resolver: Callable[[Any], bool] = (
        project_capacity_configured
    ),
) -> EvaluationPlan:
    resolved_budget = budget or EvaluationBudget()
    normalized_cases = tuple(cases)

    if not normalized_cases:
        raise ValueError("At least one evaluation case is required.")

    seen_case_ids: set[str] = set()
    items: list[EvaluationPlanItem] = []

    for case in normalized_cases:
        case_id = str(case.case_id).strip()

        if case_id in seen_case_ids:
            raise ValueError(
                "Duplicate evaluation case ID: "
                + case_id
            )

        seen_case_ids.add(case_id)

        estimated_input_tokens = max(
            1,
            int(token_estimator(case.contents)),
        )

        routes: list[ResourceRoute] = []

        if include_primary:
            routes.append(
                _generation_route(
                    task_id=case.task_id,
                    requested_resource_id=None,
                )
            )

        for resource_id in candidate_resource_ids:
            routes.append(
                _generation_route(
                    task_id=case.task_id,
                    requested_resource_id=resource_id,
                )
            )

        unique_routes: list[ResourceRoute] = []
        seen_resource_ids: set[str] = set()

        for route in routes:
            if route.resource_id in seen_resource_ids:
                continue
            seen_resource_ids.add(route.resource_id)
            unique_routes.append(route)

        if not unique_routes:
            raise ValueError(
                "Evaluation case has no selected generation resources: "
                + case_id
            )

        for route in unique_routes:
            configured = (
                True
                if not route.requires_project_capacity_config
                else bool(
                    capacity_configured_resolver(
                        route.resource_id
                    )
                )
            )

            items.append(
                EvaluationPlanItem(
                    case_id=case_id,
                    task_id=route.task_id,
                    contents=case.contents,
                    resource_id=route.resource_id,
                    selection_source=route.selection_source,
                    estimated_input_tokens=estimated_input_tokens,
                    requires_project_capacity_config=(
                        route.requires_project_capacity_config
                    ),
                    project_capacity_configured=configured,
                    automatic_fallback_enabled=(
                        route.automatic_fallback_enabled
                    ),
                )
            )

    plan = EvaluationPlan(
        version=MODEL_EVALUATION_VERSION,
        budget=resolved_budget,
        items=tuple(items),
    )

    if (
        plan.planned_provider_calls
        > resolved_budget.max_provider_calls
    ):
        raise EvaluationBudgetExceeded(
            "Evaluation plan exceeds provider-call budget: "
            f"{plan.planned_provider_calls} > "
            f"{resolved_budget.max_provider_calls}."
        )

    if (
        plan.total_estimated_input_tokens
        > resolved_budget.max_estimated_input_tokens
    ):
        raise EvaluationBudgetExceeded(
            "Evaluation plan exceeds estimated-input-token budget: "
            f"{plan.total_estimated_input_tokens} > "
            f"{resolved_budget.max_estimated_input_tokens}."
        )

    return plan


def _normalized_usage_counts(
    value: Mapping[str, Any] | None,
) -> dict[str, int]:
    raw = value or {}

    def read(name: str) -> int:
        try:
            return max(
                0,
                int(raw.get(name, 0) or 0),
            )
        except (TypeError, ValueError):
            return 0

    prompt_tokens = read("prompt_tokens")
    output_tokens = read("output_tokens")
    thought_tokens = read("thought_tokens")
    total_tokens = read("total_tokens")

    if total_tokens <= 0:
        total_tokens = (
            prompt_tokens
            + output_tokens
            + thought_tokens
        )

    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thought_tokens": thought_tokens,
        "total_tokens": total_tokens,
    }


def run_generation_evaluation(
    plan: EvaluationPlan,
    *,
    executor: Callable[[EvaluationPlanItem], Any],
    allow_provider_execution: bool = False,
    usage_counter: Callable[[Any], Mapping[str, Any]] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> EvaluationRun:
    if not allow_provider_execution:
        raise EvaluationExecutionDisabled(
            "Live/provider evaluation execution is disabled by default."
        )

    blocked = tuple(
        item
        for item in plan.items
        if item.capacity_blocked
    )

    if blocked:
        raise EvaluationCapacityBlocked(
            "Evaluation plan contains resources without explicit project "
            "capacity configuration: "
            + ", ".join(
                sorted(
                    {
                        item.resource_id
                        for item in blocked
                    }
                )
            )
        )

    observations: list[EvaluationObservation] = []

    for item in plan.items:
        started = clock()

        try:
            output = executor(item)
            elapsed_ms = max(
                0,
                int(round((clock() - started) * 1000)),
            )
            counts = _normalized_usage_counts(
                usage_counter(output)
                if usage_counter is not None
                else None
            )

            observations.append(
                EvaluationObservation(
                    case_id=item.case_id,
                    task_id=item.task_id,
                    resource_id=item.resource_id,
                    success=True,
                    latency_ms=elapsed_ms,
                    prompt_tokens=counts["prompt_tokens"],
                    output_tokens=counts["output_tokens"],
                    thought_tokens=counts["thought_tokens"],
                    total_tokens=counts["total_tokens"],
                    output=output,
                )
            )

        except Exception as error:
            elapsed_ms = max(
                0,
                int(round((clock() - started) * 1000)),
            )

            observations.append(
                EvaluationObservation(
                    case_id=item.case_id,
                    task_id=item.task_id,
                    resource_id=item.resource_id,
                    success=False,
                    latency_ms=elapsed_ms,
                    prompt_tokens=0,
                    output_tokens=0,
                    thought_tokens=0,
                    total_tokens=0,
                    output=None,
                    failure_type=type(error).__name__,
                    failure_detail=str(error or "")[:500],
                )
            )

    return EvaluationRun(
        version=MODEL_EVALUATION_VERSION,
        plan=plan,
        observations=tuple(observations),
    )


__all__ = [
    "MODEL_EVALUATION_VERSION",
    "DEFAULT_EVALUATION_MAX_PROVIDER_CALLS",
    "DEFAULT_EVALUATION_MAX_ESTIMATED_INPUT_TOKENS",
    "EvaluationError",
    "EvaluationBudgetExceeded",
    "EvaluationExecutionDisabled",
    "EvaluationCapacityBlocked",
    "EvaluationCase",
    "EvaluationBudget",
    "EvaluationPlanItem",
    "EvaluationPlan",
    "EvaluationObservation",
    "EvaluationRun",
    "build_generation_evaluation_plan",
    "run_generation_evaluation",
]
