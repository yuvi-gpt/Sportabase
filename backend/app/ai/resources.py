from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


AI_RESOURCE_REGISTRY_VERSION = "google-ai-resource-registry-v1"

GENERATION = "generation"
EMBEDDING = "embedding"
MANAGED_AGENT = "managed_agent"
LOCAL_EMBEDDING = "local_embedding"

GENERATE_CONTENT = "gemini_api_generate_content"
EMBED_CONTENT = "gemini_api_embed_content"
INTERACTIONS_AGENT = "gemini_api_interactions_agent"
LOCAL_SENTENCE_TRANSFORMERS = "local_sentence_transformers"


@dataclass(frozen=True)
class AIResourceSpec:
    resource_id: str
    provider: str
    family: str
    resource_kind: str
    execution_backend: str
    hosted: bool
    stable: bool
    preview: bool
    open_weights: bool
    requires_project_capacity_config: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "provider": self.provider,
            "family": self.family,
            "resource_kind": self.resource_kind,
            "execution_backend": self.execution_backend,
            "hosted": self.hosted,
            "stable": self.stable,
            "preview": self.preview,
            "open_weights": self.open_weights,
            "requires_project_capacity_config": (
                self.requires_project_capacity_config
            ),
        }


_RESOURCE_SPECS = (
    AIResourceSpec(
        resource_id="gemini-3.6-flash",
        provider="google",
        family="gemini",
        resource_kind=GENERATION,
        execution_backend=GENERATE_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="gemini-3.5-flash",
        provider="google",
        family="gemini",
        resource_kind=GENERATION,
        execution_backend=GENERATE_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=False,
        requires_project_capacity_config=False,
    ),
    AIResourceSpec(
        resource_id="gemini-3.5-flash-lite",
        provider="google",
        family="gemini",
        resource_kind=GENERATION,
        execution_backend=GENERATE_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="gemini-3.1-flash-lite",
        provider="google",
        family="gemini",
        resource_kind=GENERATION,
        execution_backend=GENERATE_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="gemma-4-31b-it",
        provider="google",
        family="gemma",
        resource_kind=GENERATION,
        execution_backend=GENERATE_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=True,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="gemma-4-26b-a4b-it",
        provider="google",
        family="gemma",
        resource_kind=GENERATION,
        execution_backend=GENERATE_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=True,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="gemini-embedding-2",
        provider="google",
        family="gemini_embedding",
        resource_kind=EMBEDDING,
        execution_backend=EMBED_CONTENT,
        hosted=True,
        stable=True,
        preview=False,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="antigravity-preview-05-2026",
        provider="google",
        family="antigravity",
        resource_kind=MANAGED_AGENT,
        execution_backend=INTERACTIONS_AGENT,
        hosted=True,
        stable=False,
        preview=True,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="deep-research-preview-04-2026",
        provider="google",
        family="deep_research",
        resource_kind=MANAGED_AGENT,
        execution_backend=INTERACTIONS_AGENT,
        hosted=True,
        stable=False,
        preview=True,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="deep-research-max-preview-04-2026",
        provider="google",
        family="deep_research",
        resource_kind=MANAGED_AGENT,
        execution_backend=INTERACTIONS_AGENT,
        hosted=True,
        stable=False,
        preview=True,
        open_weights=False,
        requires_project_capacity_config=True,
    ),
    AIResourceSpec(
        resource_id="google/embeddinggemma-300M",
        provider="google",
        family="embeddinggemma",
        resource_kind=LOCAL_EMBEDDING,
        execution_backend=LOCAL_SENTENCE_TRANSFORMERS,
        hosted=False,
        stable=True,
        preview=False,
        open_weights=True,
        requires_project_capacity_config=False,
    ),
)

_RESOURCE_REGISTRY: Mapping[
    str,
    AIResourceSpec,
] = MappingProxyType(
    {
        spec.resource_id.lower(): spec
        for spec in _RESOURCE_SPECS
    }
)


def registered_resource_ids() -> tuple[str, ...]:
    return tuple(
        spec.resource_id
        for spec in _RESOURCE_SPECS
    )


def resources_by_kind(
    resource_kind: str,
) -> tuple[AIResourceSpec, ...]:
    normalized = str(
        resource_kind or ""
    ).strip().lower()

    return tuple(
        spec
        for spec in _RESOURCE_SPECS
        if spec.resource_kind == normalized
    )


def resource_spec(
    resource_id: str,
) -> AIResourceSpec:
    normalized = str(
        resource_id or ""
    ).strip().lower()

    if not normalized:
        raise KeyError(
            "AI resource ID is required."
        )

    try:
        return _RESOURCE_REGISTRY[
            normalized
        ]
    except KeyError as error:
        raise KeyError(
            "Unregistered AI resource: "
            + normalized
        ) from error


def is_registered_resource(
    resource_id: str,
) -> bool:
    try:
        resource_spec(
            resource_id
        )
    except KeyError:
        return False

    return True
