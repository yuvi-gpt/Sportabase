from __future__ import annotations

from dataclasses import dataclass

from app.ai.resources import (
    AIResourceSpec,
    resource_spec,
)
from app.ai.tasks import (
    task_policy,
)


RESOURCE_ROUTER_VERSION = "google-ai-resource-router-v2"


@dataclass(frozen=True)
class ResourceRoute:
    task_id: str
    resource_id: str
    selection_source: str
    production_enabled: bool
    automatic_fallback_enabled: bool
    fallback_resource_ids: tuple[str, ...]
    evaluation_resource_ids: tuple[str, ...]
    requires_project_capacity_config: bool
    resource_kind: str
    execution_backend: str

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "resource_id": self.resource_id,
            "selection_source": self.selection_source,
            "production_enabled": self.production_enabled,
            "automatic_fallback_enabled": (
                self.automatic_fallback_enabled
            ),
            "fallback_resource_ids": list(
                self.fallback_resource_ids
            ),
            "evaluation_resource_ids": list(
                self.evaluation_resource_ids
            ),
            "requires_project_capacity_config": (
                self.requires_project_capacity_config
            ),
            "resource_kind": self.resource_kind,
            "execution_backend": self.execution_backend,
        }


def _validate_requested_resource(
    *,
    task_id: str,
    requested_resource_id: str,
) -> AIResourceSpec:
    policy = task_policy(
        task_id
    )
    spec = resource_spec(
        requested_resource_id
    )

    if (
        spec.resource_id
        not in policy.evaluation_resource_ids
    ):
        raise ValueError(
            "Requested AI resource is not approved for task evaluation: "
            + policy.task_id
        )

    if (
        spec.resource_kind
        not in policy.allowed_resource_kinds
    ):
        raise ValueError(
            "Requested AI resource kind is not allowed for task: "
            + policy.task_id
        )

    return spec


def route_task(
    task_id: str,
    *,
    requested_resource_id: str | None = None,
) -> ResourceRoute:
    policy = task_policy(
        task_id
    )

    if requested_resource_id is None:
        if (
            not policy.production_enabled
            or not policy.primary_resource_id
        ):
            raise RuntimeError(
                "AI task has no production route; an explicit evaluation resource is required: "
                + policy.task_id
            )

        spec = resource_spec(
            policy.primary_resource_id
        )
        selection_source = "task_primary"
    else:
        spec = _validate_requested_resource(
            task_id=policy.task_id,
            requested_resource_id=(
                requested_resource_id
            ),
        )
        selection_source = (
            "explicit_evaluation_override"
        )

    return ResourceRoute(
        task_id=policy.task_id,
        resource_id=spec.resource_id,
        selection_source=selection_source,
        production_enabled=(
            policy.production_enabled
        ),
        automatic_fallback_enabled=(
            policy.automatic_fallback_enabled
        ),
        fallback_resource_ids=(
            policy.fallback_resource_ids
        ),
        evaluation_resource_ids=(
            policy.evaluation_resource_ids
        ),
        requires_project_capacity_config=(
            spec.requires_project_capacity_config
        ),
        resource_kind=spec.resource_kind,
        execution_backend=(
            spec.execution_backend
        ),
    )


def resolve_model_for_task(
    task_id: str,
    *,
    requested_model: str | None = None,
) -> str:
    return route_task(
        task_id,
        requested_resource_id=(
            requested_model
        ),
    ).resource_id
