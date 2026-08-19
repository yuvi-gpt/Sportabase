from __future__ import annotations

from dataclasses import dataclass

from app.ai.models import (
    model_spec,
)
from app.ai.tasks import (
    task_policy,
)


MODEL_ROUTER_VERSION = "google-model-router-v1"


@dataclass(frozen=True)
class ModelRoute:
    task_id: str
    model_id: str
    selection_source: str
    automatic_fallback_enabled: bool
    fallback_models: tuple[str, ...]
    evaluation_models: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "model_id": self.model_id,
            "selection_source": (
                self.selection_source
            ),
            "automatic_fallback_enabled": (
                self.automatic_fallback_enabled
            ),
            "fallback_models": list(
                self.fallback_models
            ),
            "evaluation_models": list(
                self.evaluation_models
            ),
        }


def route_task(
    task_id: str,
    *,
    requested_model: str | None = None,
) -> ModelRoute:
    policy = task_policy(
        task_id
    )

    if requested_model is None:
        model_id = policy.primary_model
        selection_source = "task_primary"
    else:
        model_id = model_spec(
            requested_model
        ).model_id

        if (
            model_id
            not in policy.evaluation_models
        ):
            raise ValueError(
                "Requested model is not approved for task evaluation: "
                + policy.task_id
            )

        selection_source = (
            "explicit_evaluation_override"
        )

    model_spec(
        model_id
    )

    return ModelRoute(
        task_id=policy.task_id,
        model_id=model_id,
        selection_source=selection_source,
        automatic_fallback_enabled=(
            policy.automatic_fallback_enabled
        ),
        fallback_models=(
            policy.fallback_models
        ),
        evaluation_models=(
            policy.evaluation_models
        ),
    )


def resolve_model_for_task(
    task_id: str,
    *,
    requested_model: str | None = None,
) -> str:
    return route_task(
        task_id,
        requested_model=requested_model,
    ).model_id
