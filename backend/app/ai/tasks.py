from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.ai.models import (
    DEFAULT_GEMINI_MODEL,
    FREE_GEMINI_MODEL_IDS,
    model_spec,
)


TASK_REGISTRY_VERSION = "ai-task-registry-v1"

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


@dataclass(frozen=True)
class TaskPolicy:
    task_id: str
    primary_model: str
    evaluation_models: tuple[str, ...]
    fallback_models: tuple[str, ...] = ()
    automatic_fallback_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "primary_model": self.primary_model,
            "evaluation_models": list(
                self.evaluation_models
            ),
            "fallback_models": list(
                self.fallback_models
            ),
            "automatic_fallback_enabled": (
                self.automatic_fallback_enabled
            ),
        }


_TASK_IDS = (
    ARTICLE_TLDR,
    ARTICLE_SINGLE_PASS,
    ARTICLE_CLASSIFIER,
    VIDEO_ANALYSIS,
    CORROBORATION_CANDIDATE_SEMANTICS,
    CORROBORATION_COLLECTION_SEMANTICS,
)


def _build_policy(
    task_id: str,
) -> TaskPolicy:
    policy = TaskPolicy(
        task_id=task_id,
        primary_model=DEFAULT_GEMINI_MODEL,
        evaluation_models=(
            FREE_GEMINI_MODEL_IDS
        ),
        fallback_models=(),
        automatic_fallback_enabled=False,
    )

    model_spec(
        policy.primary_model
    )

    for model_id in (
        policy.evaluation_models
    ):
        model_spec(
            model_id
        )

    if (
        policy.primary_model
        not in policy.evaluation_models
    ):
        raise RuntimeError(
            "Task primary model must be present in its evaluation pool."
        )

    if (
        policy.automatic_fallback_enabled
        and not policy.fallback_models
    ):
        raise RuntimeError(
            "Automatic fallback requires explicit fallback models."
        )

    return policy


_TASK_REGISTRY: Mapping[str, TaskPolicy] = MappingProxyType(
    {
        task_id: _build_policy(
            task_id
        )
        for task_id in _TASK_IDS
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
