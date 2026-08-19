from __future__ import annotations

from app.ai.resources import (
    GENERATION,
    AIResourceSpec,
    resource_spec,
    resources_by_kind,
)


MODEL_REGISTRY_VERSION = "google-generation-model-registry-v2"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def _generation_ids(
    *,
    family: str | None = None,
) -> tuple[str, ...]:
    normalized_family = (
        str(family).strip().lower()
        if family is not None
        else None
    )

    return tuple(
        spec.resource_id
        for spec in resources_by_kind(
            GENERATION
        )
        if (
            normalized_family is None
            or spec.family == normalized_family
        )
    )


HOSTED_GENERATION_MODEL_IDS = (
    _generation_ids()
)
GEMINI_GENERATION_MODEL_IDS = (
    _generation_ids(
        family="gemini"
    )
)
GEMMA_HOSTED_MODEL_IDS = (
    _generation_ids(
        family="gemma"
    )
)


if DEFAULT_GEMINI_MODEL not in HOSTED_GENERATION_MODEL_IDS:
    raise RuntimeError(
        "Default Gemini model is missing from the generation registry."
    )


def registered_model_ids() -> tuple[str, ...]:
    return HOSTED_GENERATION_MODEL_IDS


def model_spec(
    model_id: str,
) -> AIResourceSpec:
    spec = resource_spec(
        model_id
    )

    if spec.resource_kind != GENERATION:
        raise KeyError(
            "AI resource is not a generation model: "
            + spec.resource_id
        )

    return spec


def is_registered_model(
    model_id: str,
) -> bool:
    try:
        model_spec(
            model_id
        )
    except KeyError:
        return False

    return True
