from __future__ import annotations

import os
import re

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from app.ai.resources import (
    EMBEDDING,
    GENERATION,
    LOCAL_EMBEDDING,
    MANAGED_AGENT,
    resource_spec,
)
from app.ai.router import route_task
from app.ai.tasks import (
    AGENTIC_PROVENANCE_INSPECTION,
    CLAIM_DEEP_SHADOW_REVIEW,
    CLAIM_SHADOW_REVIEW,
    LOCAL_RETRIEVAL_EMBEDDING,
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_MAX,
    RETRIEVAL_EMBEDDING,
)


SPECIALIZED_AI_RUNTIME_VERSION = "google-specialized-ai-runtime-v1"

MAX_EMBEDDING_ITEMS = 32
MAX_EMBEDDING_ITEM_CHARS = 12_000
MAX_EMBEDDING_TOTAL_CHARS = 48_000
DEFAULT_EMBEDDING_DIMENSION = 768
MIN_EMBEDDING_DIMENSION = 128
MAX_EMBEDDING_DIMENSION = 3072
MAX_SHADOW_PROMPT_CHARS = 24_000
MAX_SHADOW_OUTPUT_CHARS = 12_000
MAX_PROVENANCE_PROMPT_CHARS = 16_000
DEFAULT_ANTIGRAVITY_TOKEN_BUDGET = 30_000
MAX_ANTIGRAVITY_TOKEN_BUDGET = 100_000

_GEMMA_SHADOW_FLAG = "SPORTABASE_GEMMA_SHADOW_ENABLED"
_HOSTED_EMBEDDING_FLAG = "SPORTABASE_EMBEDDING_RUNTIME_ENABLED"
_LOCAL_EMBEDDING_FLAG = "SPORTABASE_LOCAL_EMBEDDING_RUNTIME_ENABLED"
_PROVENANCE_AGENT_FLAG = "SPORTABASE_PROVENANCE_AGENTS_ENABLED"

_EMBEDDING_TASK_TYPES = {
    "RETRIEVAL_QUERY",
    "RETRIEVAL_DOCUMENT",
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
    "QUESTION_ANSWERING",
    "FACT_VERIFICATION",
    "CODE_RETRIEVAL_QUERY",
}

_SHADOW_TASKS = {
    CLAIM_SHADOW_REVIEW,
    CLAIM_DEEP_SHADOW_REVIEW,
}

_MANAGED_AGENT_TASKS = {
    PROVENANCE_RESEARCH,
    PROVENANCE_RESEARCH_MAX,
    AGENTIC_PROVENANCE_INSPECTION,
}


class SpecializedAIInputError(ValueError):
    pass


class SpecializedAIConfigurationError(RuntimeError):
    pass


def _enabled(
    name: str,
    *,
    env_getter: Callable[[str, str], Any] = os.getenv,
) -> bool:
    return str(
        env_getter(name, "") or ""
    ).strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def specialized_resource_enable_key(
    resource_id: str,
) -> str:
    suffix = re.sub(
        r"[^A-Z0-9]+",
        "_",
        str(resource_id or "").strip().upper(),
    ).strip("_")

    if not suffix:
        raise SpecializedAIInputError(
            "AI resource ID is required."
        )

    return "SPORTABASE_AI_RESOURCE_" + suffix + "_ENABLED"


def _resource_explicitly_enabled(
    resource_id: str,
    *,
    env_getter: Callable[[str, str], Any],
) -> bool:
    return _enabled(
        specialized_resource_enable_key(
            resource_id
        ),
        env_getter=env_getter,
    )


def _require_runtime_enabled(
    *,
    flag_name: str,
    resource_id: str,
    env_getter: Callable[[str, str], Any],
) -> None:
    if not _enabled(
        flag_name,
        env_getter=env_getter,
    ):
        raise SpecializedAIConfigurationError(
            "Specialized AI runtime is disabled: "
            + flag_name
        )

    spec = resource_spec(
        resource_id
    )

    if (
        spec.requires_project_capacity_config
        and not _resource_explicitly_enabled(
            spec.resource_id,
            env_getter=env_getter,
        )
    ):
        raise SpecializedAIConfigurationError(
            "Specialized AI resource requires explicit enablement: "
            + specialized_resource_enable_key(
                spec.resource_id
            )
        )


def _bounded_nonempty_text(
    value: Any,
    *,
    field_name: str,
    max_chars: int,
) -> str:
    text = str(
        value or ""
    ).strip()

    if not text:
        raise SpecializedAIInputError(
            field_name + " is required."
        )

    if len(text) > int(max_chars):
        raise SpecializedAIInputError(
            field_name
            + " exceeds the configured size limit."
        )

    return text


def _normalize_embedding_texts(
    texts: Iterable[Any],
) -> list[str]:
    if isinstance(
        texts,
        (str, bytes),
    ):
        raw_items = [texts]
    else:
        raw_items = list(
            texts or []
        )

    if not raw_items:
        raise SpecializedAIInputError(
            "At least one embedding input is required."
        )

    if len(raw_items) > MAX_EMBEDDING_ITEMS:
        raise SpecializedAIInputError(
            "Embedding batch exceeds the configured item limit."
        )

    normalized = [
        _bounded_nonempty_text(
            item,
            field_name="Embedding input",
            max_chars=MAX_EMBEDDING_ITEM_CHARS,
        )
        for item in raw_items
    ]

    if sum(
        len(item)
        for item in normalized
    ) > MAX_EMBEDDING_TOTAL_CHARS:
        raise SpecializedAIInputError(
            "Embedding batch exceeds the configured character budget."
        )

    return normalized


def _embedding_dimension(
    value: Any,
) -> int:
    try:
        dimension = int(
            value
        )
    except (TypeError, ValueError) as error:
        raise SpecializedAIInputError(
            "Embedding output dimension must be an integer."
        ) from error

    if not (
        MIN_EMBEDDING_DIMENSION
        <= dimension
        <= MAX_EMBEDDING_DIMENSION
    ):
        raise SpecializedAIInputError(
            "Embedding output dimension is outside the supported range."
        )

    return dimension


def _vector_values(
    embedding: Any,
) -> list[float]:
    raw_values = (
        embedding.get("values")
        if isinstance(embedding, Mapping)
        else getattr(
            embedding,
            "values",
            None,
        )
    )

    if raw_values is None:
        raise SpecializedAIConfigurationError(
            "Embedding response did not contain vector values."
        )

    return [
        float(value)
        for value in raw_values
    ]


def run_hosted_retrieval_embedding(
    *,
    client: Any,
    texts: Iterable[Any],
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = DEFAULT_EMBEDDING_DIMENSION,
    requested_resource_id: str | None = None,
    env_getter: Callable[[str, str], Any] = os.getenv,
) -> dict[str, Any]:
    route = route_task(
        RETRIEVAL_EMBEDDING,
        requested_resource_id=(
            requested_resource_id
        ),
    )

    if route.resource_kind != EMBEDDING:
        raise SpecializedAIConfigurationError(
            "Retrieval embedding task did not resolve to an embedding resource."
        )

    _require_runtime_enabled(
        flag_name=_HOSTED_EMBEDDING_FLAG,
        resource_id=route.resource_id,
        env_getter=env_getter,
    )

    normalized_texts = _normalize_embedding_texts(
        texts
    )
    normalized_task_type = str(
        task_type or ""
    ).strip().upper()

    if normalized_task_type not in _EMBEDDING_TASK_TYPES:
        raise SpecializedAIInputError(
            "Unsupported embedding task type."
        )

    dimension = _embedding_dimension(
        output_dimensionality
    )

    models = getattr(
        client,
        "models",
        None,
    )
    embed_content = getattr(
        models,
        "embed_content",
        None,
    )

    if not callable(embed_content):
        raise SpecializedAIConfigurationError(
            "Gemini embedding client is unavailable."
        )

    try:
        from google.genai import types

        config = types.EmbedContentConfig(
            task_type=normalized_task_type,
            output_dimensionality=dimension,
        )
    except Exception:
        config = {
            "task_type": normalized_task_type,
            "output_dimensionality": dimension,
        }

    response = embed_content(
        model=route.resource_id,
        contents=normalized_texts,
        config=config,
    )

    raw_embeddings = getattr(
        response,
        "embeddings",
        None,
    )

    if raw_embeddings is None and isinstance(
        response,
        Mapping,
    ):
        raw_embeddings = response.get(
            "embeddings"
        )

    vectors = [
        _vector_values(embedding)
        for embedding in list(
            raw_embeddings or []
        )
    ]

    if len(vectors) != len(normalized_texts):
        raise SpecializedAIConfigurationError(
            "Embedding response count did not match the request."
        )

    return {
        "version": SPECIALIZED_AI_RUNTIME_VERSION,
        "status": "completed",
        "task_id": RETRIEVAL_EMBEDDING,
        "resource_id": route.resource_id,
        "count": len(vectors),
        "dimension": (
            len(vectors[0])
            if vectors
            else dimension
        ),
        "vectors": vectors,
        "policy": {
            "input_text_returned": False,
            "bounded_batch": True,
            "affects_live_merit": False,
            "embedding_is_not_truth": True,
        },
    }


def _default_local_encoder_factory(
    resource_id: str,
):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise SpecializedAIConfigurationError(
            "Local EmbeddingGemma requires the optional sentence-transformers dependency."
        ) from error

    return SentenceTransformer(
        resource_id
    )


def run_local_retrieval_embedding(
    *,
    texts: Iterable[Any],
    encoder: Any = None,
    encoder_factory: Callable[[str], Any] | None = None,
    env_getter: Callable[[str, str], Any] = os.getenv,
) -> dict[str, Any]:
    route = route_task(
        LOCAL_RETRIEVAL_EMBEDDING
    )

    if route.resource_kind != LOCAL_EMBEDDING:
        raise SpecializedAIConfigurationError(
            "Local retrieval task did not resolve to a local embedding resource."
        )

    if not _enabled(
        _LOCAL_EMBEDDING_FLAG,
        env_getter=env_getter,
    ):
        raise SpecializedAIConfigurationError(
            "Local embedding runtime is disabled: "
            + _LOCAL_EMBEDDING_FLAG
        )

    normalized_texts = _normalize_embedding_texts(
        texts
    )

    if encoder is None:
        factory = (
            encoder_factory
            or _default_local_encoder_factory
        )
        encoder = factory(
            route.resource_id
        )

    encode = getattr(
        encoder,
        "encode",
        None,
    )

    if not callable(encode):
        raise SpecializedAIConfigurationError(
            "Local embedding encoder is unavailable."
        )

    raw_vectors = encode(
        normalized_texts,
        normalize_embeddings=True,
    )

    vectors = [
        [
            float(value)
            for value in vector
        ]
        for vector in list(
            raw_vectors
        )
    ]

    if len(vectors) != len(normalized_texts):
        raise SpecializedAIConfigurationError(
            "Local embedding response count did not match the request."
        )

    return {
        "version": SPECIALIZED_AI_RUNTIME_VERSION,
        "status": "completed",
        "task_id": LOCAL_RETRIEVAL_EMBEDDING,
        "resource_id": route.resource_id,
        "count": len(vectors),
        "dimension": (
            len(vectors[0])
            if vectors
            else 0
        ),
        "vectors": vectors,
        "policy": {
            "hosted_provider_call": False,
            "input_text_returned": False,
            "bounded_batch": True,
            "affects_live_merit": False,
            "embedding_is_not_truth": True,
        },
    }


def run_gemma_shadow_review(
    *,
    prompt: Any,
    generation_executor: Callable[..., Any],
    task_id: str = CLAIM_SHADOW_REVIEW,
    requested_resource_id: str | None = None,
    env_getter: Callable[[str, str], Any] = os.getenv,
    executor_kwargs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if task_id not in _SHADOW_TASKS:
        raise SpecializedAIInputError(
            "Unsupported Gemma shadow task."
        )

    route = route_task(
        task_id,
        requested_resource_id=(
            requested_resource_id
        ),
    )
    spec = resource_spec(
        route.resource_id
    )

    if (
        route.resource_kind != GENERATION
        or spec.family != "gemma"
    ):
        raise SpecializedAIConfigurationError(
            "Gemma shadow task did not resolve to Gemma generation."
        )

    _require_runtime_enabled(
        flag_name=_GEMMA_SHADOW_FLAG,
        resource_id=route.resource_id,
        env_getter=env_getter,
    )

    bounded_prompt = _bounded_nonempty_text(
        prompt,
        field_name="Gemma shadow prompt",
        max_chars=MAX_SHADOW_PROMPT_CHARS,
    )

    if not callable(generation_executor):
        raise SpecializedAIConfigurationError(
            "Gemma shadow generation executor is unavailable."
        )

    call_kwargs = dict(
        executor_kwargs or {}
    )
    call_kwargs.update(
        {
            "mode": task_id,
            "model": route.resource_id,
            "contents": bounded_prompt,
        }
    )

    response = generation_executor(
        **call_kwargs
    )
    output_text = str(
        getattr(
            response,
            "text",
            "",
        )
        or ""
    ).strip()[:MAX_SHADOW_OUTPUT_CHARS]

    return {
        "version": SPECIALIZED_AI_RUNTIME_VERSION,
        "status": "completed",
        "task_id": task_id,
        "resource_id": route.resource_id,
        "output_text": output_text,
        "policy": {
            "shadow_only": True,
            "affects_live_merit": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "independence_not_inferred_from_model_family": True,
        },
    }


def _managed_agent_config(
    *,
    task_id: str,
    max_total_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if task_id == AGENTIC_PROVENANCE_INSPECTION:
        budget = max(
            1_000,
            min(
                int(max_total_tokens),
                MAX_ANTIGRAVITY_TOKEN_BUDGET,
            ),
        )
        return (
            {
                "type": "antigravity",
                "max_total_tokens": budget,
            },
            {
                "environment": "remote",
            },
        )

    if task_id in {
        PROVENANCE_RESEARCH,
        PROVENANCE_RESEARCH_MAX,
    }:
        return (
            {
                "type": "deep-research",
                "thinking_summaries": "auto",
                "collaborative_planning": False,
            },
            {},
        )

    raise SpecializedAIInputError(
        "Unsupported managed-agent task."
    )


def start_provenance_research(
    *,
    client: Any,
    prompt: Any,
    task_id: str = PROVENANCE_RESEARCH,
    requested_resource_id: str | None = None,
    max_total_tokens: int = DEFAULT_ANTIGRAVITY_TOKEN_BUDGET,
    env_getter: Callable[[str, str], Any] = os.getenv,
) -> dict[str, Any]:
    if task_id not in _MANAGED_AGENT_TASKS:
        raise SpecializedAIInputError(
            "Unsupported provenance agent task."
        )

    route = route_task(
        task_id,
        requested_resource_id=(
            requested_resource_id
        ),
    )

    if route.resource_kind != MANAGED_AGENT:
        raise SpecializedAIConfigurationError(
            "Provenance task did not resolve to a managed agent."
        )

    _require_runtime_enabled(
        flag_name=_PROVENANCE_AGENT_FLAG,
        resource_id=route.resource_id,
        env_getter=env_getter,
    )

    bounded_prompt = _bounded_nonempty_text(
        prompt,
        field_name="Provenance research prompt",
        max_chars=MAX_PROVENANCE_PROMPT_CHARS,
    )

    interactions = getattr(
        client,
        "interactions",
        None,
    )
    create = getattr(
        interactions,
        "create",
        None,
    )

    if not callable(create):
        raise SpecializedAIConfigurationError(
            "Gemini Interactions API client is unavailable."
        )

    agent_config, extra = _managed_agent_config(
        task_id=task_id,
        max_total_tokens=max_total_tokens,
    )

    interaction = create(
        agent=route.resource_id,
        input=bounded_prompt,
        agent_config=agent_config,
        tools=[
            {"type": "google_search"},
            {"type": "url_context"},
        ],
        background=True,
        store=True,
        **extra,
    )

    interaction_id = str(
        getattr(
            interaction,
            "id",
            "",
        )
        or ""
    ).strip()

    if not interaction_id:
        raise SpecializedAIConfigurationError(
            "Managed agent did not return an interaction ID."
        )

    return {
        "version": SPECIALIZED_AI_RUNTIME_VERSION,
        "status": str(
            getattr(
                interaction,
                "status",
                "submitted",
            )
            or "submitted"
        ),
        "task_id": task_id,
        "resource_id": route.resource_id,
        "interaction_id": interaction_id,
        "policy": {
            "background_only": True,
            "stored_interaction": True,
            "public_request_does_not_wait": True,
            "affects_live_merit": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "google_search_enabled": True,
            "url_context_enabled": True,
        },
    }


def get_provenance_research_status(
    *,
    client: Any,
    interaction_id: Any,
) -> dict[str, Any]:
    normalized_id = _bounded_nonempty_text(
        interaction_id,
        field_name="Interaction ID",
        max_chars=256,
    )

    interactions = getattr(
        client,
        "interactions",
        None,
    )
    get_interaction = getattr(
        interactions,
        "get",
        None,
    )

    if not callable(get_interaction):
        raise SpecializedAIConfigurationError(
            "Gemini Interactions API status client is unavailable."
        )

    result = get_interaction(
        id=normalized_id
    )

    return {
        "version": SPECIALIZED_AI_RUNTIME_VERSION,
        "status": str(
            getattr(
                result,
                "status",
                "unknown",
            )
            or "unknown"
        ),
        "interaction_id": normalized_id,
        "output_text": _interaction_output_text(
            result
        ),
        "policy": {
            "affects_live_merit": False,
            "establishes_truth": False,
            "establishes_authority": False,
        },
    }


def _interaction_output_text(
    interaction: Any,
) -> str:
    direct = str(
        getattr(
            interaction,
            "output_text",
            "",
        )
        or ""
    ).strip()

    if direct:
        return direct[:MAX_SHADOW_OUTPUT_CHARS]

    pieces: list[str] = []

    for step in list(
        getattr(
            interaction,
            "steps",
            None,
        )
        or []
    ):
        if str(
            getattr(
                step,
                "type",
                "",
            )
            or ""
        ) != "model_output":
            continue

        for item in list(
            getattr(
                step,
                "content",
                None,
            )
            or []
        ):
            text = str(
                getattr(
                    item,
                    "text",
                    "",
                )
                or ""
            ).strip()
            if text:
                pieces.append(
                    text
                )

    return "\n\n".join(
        pieces
    )[:MAX_SHADOW_OUTPUT_CHARS]


def cancel_provenance_research(
    *,
    client: Any,
    interaction_id: Any,
) -> dict[str, Any]:
    normalized_id = _bounded_nonempty_text(
        interaction_id,
        field_name="Interaction ID",
        max_chars=256,
    )

    interactions = getattr(
        client,
        "interactions",
        None,
    )
    cancel = getattr(
        interactions,
        "cancel",
        None,
    )

    if not callable(cancel):
        raise SpecializedAIConfigurationError(
            "Gemini Interactions API cancellation client is unavailable."
        )

    cancel(
        id=normalized_id
    )

    return {
        "version": SPECIALIZED_AI_RUNTIME_VERSION,
        "status": "cancel_requested",
        "interaction_id": normalized_id,
        "policy": {
            "affects_live_merit": False,
        },
    }


__all__ = [
    "SPECIALIZED_AI_RUNTIME_VERSION",
    "SpecializedAIInputError",
    "SpecializedAIConfigurationError",
    "specialized_resource_enable_key",
    "run_hosted_retrieval_embedding",
    "run_local_retrieval_embedding",
    "run_gemma_shadow_review",
    "start_provenance_research",
    "get_provenance_research_status",
    "cancel_provenance_research",
]
