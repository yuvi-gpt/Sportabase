from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.ai.models import (
    DEFAULT_GEMINI_MODEL,
    GEMMA_HOSTED_MODEL_IDS,
    HOSTED_GENERATION_MODEL_IDS,
)
from app.ai.resources import (
    EMBEDDING,
    GENERATION,
    LOCAL_EMBEDDING,
    MANAGED_AGENT,
    resource_spec,
)


TASK_REGISTRY_VERSION = "ai-task-registry-v5"

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
CLAIM_SHADOW_REVIEW = "claim_shadow_review"
CLAIM_DEEP_SHADOW_REVIEW = "claim_deep_shadow_review"
RETRIEVAL_EMBEDDING = "retrieval_embedding"
LOCAL_RETRIEVAL_EMBEDDING = "local_retrieval_embedding"
PROVENANCE_RESEARCH = "provenance_research"
PROVENANCE_RESEARCH_MAX = "provenance_research_max"
AGENTIC_PROVENANCE_INSPECTION = "agentic_provenance_inspection"

# Production role map. These constants are intentionally explicit so model
# changes are reviewable configuration, not incidental caller behavior.
FAST_UTILITY_GENERATION_MODEL = "gemini-3.5-flash-lite"
GENERAL_ANALYSIS_GENERATION_MODEL = "gemini-3.6-flash"
EVIDENCE_SEMANTICS_GENERATION_MODEL = DEFAULT_GEMINI_MODEL
COMPATIBILITY_GENERATION_FALLBACK = DEFAULT_GEMINI_MODEL
GEMMA_SHADOW_MODEL = "gemma-4-26b-a4b-it"
GEMMA_DEEP_SHADOW_MODEL = "gemma-4-31b-it"
HOSTED_RETRIEVAL_EMBEDDING_MODEL = "gemini-embedding-2"
LOCAL_RETRIEVAL_EMBEDDING_MODEL = "google/embeddinggemma-300m"
PROVENANCE_RESEARCH_AGENT = "deep-research-preview-04-2026"
PROVENANCE_RESEARCH_MAX_AGENT = "deep-research-max-preview-04-2026"
AGENTIC_PROVENANCE_AGENT = "antigravity-preview-05-2026"


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


def _resource_policy(
    *,
    task_id: str,
    primary_resource_id: str,
    evaluation_resource_ids: tuple[str, ...],
    allowed_resource_kinds: tuple[str, ...],
    fallback_resource_ids: tuple[str, ...] = (),
) -> TaskPolicy:
    return _validate_policy(
        TaskPolicy(
            task_id=task_id,
            production_enabled=True,
            primary_resource_id=primary_resource_id,
            evaluation_resource_ids=(
                evaluation_resource_ids
            ),
            allowed_resource_kinds=(
                allowed_resource_kinds
            ),
            automatic_fallback_enabled=bool(
                fallback_resource_ids
            ),
            fallback_resource_ids=(
                fallback_resource_ids
            ),
        )
    )


def _generation_policy(
    *,
    task_id: str,
    primary_resource_id: str,
    fallback_resource_ids: tuple[str, ...] = (),
    evaluation_resource_ids: tuple[str, ...] = (
        HOSTED_GENERATION_MODEL_IDS
    ),
) -> TaskPolicy:
    return _resource_policy(
        task_id=task_id,
        primary_resource_id=primary_resource_id,
        evaluation_resource_ids=(
            evaluation_resource_ids
        ),
        allowed_resource_kinds=(
            GENERATION,
        ),
        fallback_resource_ids=(
            fallback_resource_ids
        ),
    )


_TASK_POLICIES = [
    _generation_policy(
        task_id=ARTICLE_TLDR,
        primary_resource_id=(
            FAST_UTILITY_GENERATION_MODEL
        ),
        fallback_resource_ids=(
            COMPATIBILITY_GENERATION_FALLBACK,
        ),
    ),
    _generation_policy(
        task_id=ARTICLE_CLASSIFIER,
        primary_resource_id=(
            FAST_UTILITY_GENERATION_MODEL
        ),
        fallback_resource_ids=(
            COMPATIBILITY_GENERATION_FALLBACK,
        ),
    ),
    _generation_policy(
        task_id=ARTICLE_SINGLE_PASS,
        primary_resource_id=(
            GENERAL_ANALYSIS_GENERATION_MODEL
        ),
        fallback_resource_ids=(
            COMPATIBILITY_GENERATION_FALLBACK,
        ),
    ),
    _generation_policy(
        task_id=VIDEO_ANALYSIS,
        primary_resource_id=(
            GENERAL_ANALYSIS_GENERATION_MODEL
        ),
        fallback_resource_ids=(
            COMPATIBILITY_GENERATION_FALLBACK,
        ),
    ),
    _generation_policy(
        task_id=(
            CORROBORATION_CANDIDATE_SEMANTICS
        ),
        primary_resource_id=(
            EVIDENCE_SEMANTICS_GENERATION_MODEL
        ),
    ),
    _generation_policy(
        task_id=(
            CORROBORATION_COLLECTION_SEMANTICS
        ),
        primary_resource_id=(
            EVIDENCE_SEMANTICS_GENERATION_MODEL
        ),
    ),
    _generation_policy(
        task_id=CLAIM_SHADOW_REVIEW,
        primary_resource_id=(
            GEMMA_SHADOW_MODEL
        ),
        evaluation_resource_ids=(
            GEMMA_HOSTED_MODEL_IDS
        ),
    ),
    _generation_policy(
        task_id=CLAIM_DEEP_SHADOW_REVIEW,
        primary_resource_id=(
            GEMMA_DEEP_SHADOW_MODEL
        ),
        evaluation_resource_ids=(
            GEMMA_HOSTED_MODEL_IDS
        ),
    ),
    _resource_policy(
        task_id=RETRIEVAL_EMBEDDING,
        primary_resource_id=(
            HOSTED_RETRIEVAL_EMBEDDING_MODEL
        ),
        evaluation_resource_ids=(
            HOSTED_RETRIEVAL_EMBEDDING_MODEL,
        ),
        allowed_resource_kinds=(
            EMBEDDING,
        ),
    ),
    _resource_policy(
        task_id=LOCAL_RETRIEVAL_EMBEDDING,
        primary_resource_id=(
            LOCAL_RETRIEVAL_EMBEDDING_MODEL
        ),
        evaluation_resource_ids=(
            LOCAL_RETRIEVAL_EMBEDDING_MODEL,
        ),
        allowed_resource_kinds=(
            LOCAL_EMBEDDING,
        ),
    ),
    _resource_policy(
        task_id=PROVENANCE_RESEARCH,
        primary_resource_id=(
            PROVENANCE_RESEARCH_AGENT
        ),
        evaluation_resource_ids=(
            PROVENANCE_RESEARCH_AGENT,
            PROVENANCE_RESEARCH_MAX_AGENT,
            AGENTIC_PROVENANCE_AGENT,
        ),
        allowed_resource_kinds=(
            MANAGED_AGENT,
        ),
    ),
    _resource_policy(
        task_id=PROVENANCE_RESEARCH_MAX,
        primary_resource_id=(
            PROVENANCE_RESEARCH_MAX_AGENT
        ),
        evaluation_resource_ids=(
            PROVENANCE_RESEARCH_AGENT,
            PROVENANCE_RESEARCH_MAX_AGENT,
            AGENTIC_PROVENANCE_AGENT,
        ),
        allowed_resource_kinds=(
            MANAGED_AGENT,
        ),
    ),
    _resource_policy(
        task_id=AGENTIC_PROVENANCE_INSPECTION,
        primary_resource_id=(
            AGENTIC_PROVENANCE_AGENT
        ),
        evaluation_resource_ids=(
            AGENTIC_PROVENANCE_AGENT,
            PROVENANCE_RESEARCH_AGENT,
            PROVENANCE_RESEARCH_MAX_AGENT,
        ),
        allowed_resource_kinds=(
            MANAGED_AGENT,
        ),
    ),
]

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
