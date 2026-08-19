from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.ai.models import (
    DEFAULT_GEMINI_MODEL,
    HOSTED_GENERATION_MODEL_IDS,
)
from app.ai.resources import (
    EMBEDDING,
    LOCAL_EMBEDDING,
    MANAGED_AGENT,
    resource_spec,
)


TASK_REGISTRY_VERSION = "ai-task-registry-v3"

ARTICLE_TLDR = "article_tldr"
ARTICLE_SINGLE_PASS = "article_single_pass"
ARTICLE_CLASSIFIER = "article_classifier"
VIDEO_ANALYSIS = "video_analysis"
CORROBORATION_CANDIDATE_SEMANTICS = (
    "corroboration_candidate_semantics"
)
CORROBORATION_COLLECTION_SEMANTICS = (
    "corroboration_collection_semantics"
)
RETRIEVAL_EMBEDDING = "retrieval_embedding"
PROVENANCE_RESEARCH = "provenance_research"


@dataclass(frozen=True)
class TaskPolicy:
    task_id: str
    production_enabled: bool
    primary_resource_id: str | None
    evaluation_resource_ids: tuple[str, ...]
    allowed_resource_kinds: tuple[str, ...]
    automatic_fallback_enabled: bool = False
    fallback_resource_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "production_enabled": self.production_enabled,
            "primary_resource_id": self.primary_resource_id,
            "evaluation_resource_ids": list(
                self.evaluation_resource_ids
            ),
            "allowed_resource_kinds": list(
                self.allowed_resource_kinds
            ),
            "automatic_fallback_enabled": (
                self.automatic_fallback_enabled
            ),
            "fallback_resource_ids": list(
                self.fallback_resource_ids
            ),
        }


def _validate_policy(
    policy: TaskPolicy,
) -> TaskPolicy:
    if (
        policy.production_enabled
        and not policy.primary_resource_id
    ):
        raise RuntimeError(
            "Production AI task requires a primary resource."
        )

    if policy.primary_resource_id:
        primary = resource_spec(
            policy.primary_resource_id
        )

        if (
            primary.resource_kind
            not in policy.allowed_resource_kinds
        ):
            raise RuntimeError(
                "Task primary resource has an invalid resource kind."
            )

        if (
            policy.primary_resource_id
            not in policy.evaluation_resource_ids
        ):
            raise RuntimeError(
                "Task primary resource must be in its evaluation pool."
            )

    for resource_id in (
        policy.evaluation_resource_ids
        + policy.fallback_resource_ids
    ):
        spec = resource_spec(
            resource_id
        )

        if (
            spec.resource_kind
            not in policy.allowed_resource_kinds
        ):
            raise RuntimeError(
                "Task resource has an invalid resource kind: "
                + resource_id
            )

    if (
        policy.automatic_fallback_enabled
        and not policy.fallback_resource_ids
    ):
        raise RuntimeError(
            "Automatic fallback requires explicit fallback resources."
        )

    return policy


_LIVE_GENERATION_TASKS = (
    ARTICLE_TLDR,
    ARTICLE_SINGLE_PASS,
    ARTICLE_CLASSIFIER,
    VIDEO_ANALYSIS,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
)

_TASK_POLICIES = [
    _validate_policy(
        TaskPolicy(
            task_id=task_id,
            production_enabled=True,
            primary_resource_id=(
                DEFAULT_GEMINI_MODEL
            ),
            evaluation_resource_ids=(
                HOSTED_GENERATION_MODEL_IDS
            ),
            allowed_resource_kinds=(
                "generation",
            ),
            automatic_fallback_enabled=False,
            fallback_resource_ids=(),
        )
    )
    for task_id in _LIVE_GENERATION_TASKS
]

_TASK_POLICIES.extend(
    (
        _validate_policy(
            TaskPolicy(
                task_id=RETRIEVAL_EMBEDDING,
                production_enabled=False,
                primary_resource_id=None,
                evaluation_resource_ids=(
                    "gemini-embedding-2",
                    "google/embeddinggemma-300M",
                ),
                allowed_resource_kinds=(
                    EMBEDDING,
                    LOCAL_EMBEDDING,
                ),
                automatic_fallback_enabled=False,
                fallback_resource_ids=(),
            )
        ),
        _validate_policy(
            TaskPolicy(
                task_id=PROVENANCE_RESEARCH,
                production_enabled=False,
                primary_resource_id=None,
                evaluation_resource_ids=(
                    "antigravity-preview-05-2026",
                    "deep-research-preview-04-2026",
                    "deep-research-max-preview-04-2026",
                ),
                allowed_resource_kinds=(
                    MANAGED_AGENT,
                ),
                automatic_fallback_enabled=False,
                fallback_resource_ids=(),
            )
        ),
    )
)

_TASK_REGISTRY: Mapping[
    str,
    TaskPolicy,
] = MappingProxyType(
    {
        policy.task_id: policy
        for policy in _TASK_POLICIES
    }
)


def registered_task_ids() -> tuple[str, ...]:
    return tuple(
        _TASK_REGISTRY.keys()
    )


def task_policy(
    task_id: str,
) -> TaskPolicy:
    normalized = str(
        task_id or ""
    ).strip().lower()

    if not normalized:
        raise KeyError(
            "AI task ID is required."
        )

    try:
        return _TASK_REGISTRY[
            normalized
        ]
    except KeyError as error:
        raise KeyError(
            "Unregistered AI task: "
            + normalized
        ) from error
