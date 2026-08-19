from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


MODEL_REGISTRY_VERSION = "google-model-registry-v1"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    provider: str
    model_family: str
    model_class: str
    stable: bool
    free_pool: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "model_family": self.model_family,
            "model_class": self.model_class,
            "stable": self.stable,
            "free_pool": self.free_pool,
        }


_MODEL_SPECS = (
    ModelSpec(
        model_id="gemini-3.6-flash",
        provider="google",
        model_family="gemini",
        model_class="flash",
        stable=True,
        free_pool=True,
    ),
    ModelSpec(
        model_id="gemini-3.5-flash",
        provider="google",
        model_family="gemini",
        model_class="flash",
        stable=True,
        free_pool=True,
    ),
    ModelSpec(
        model_id="gemini-3.5-flash-lite",
        provider="google",
        model_family="gemini",
        model_class="flash_lite",
        stable=True,
        free_pool=True,
    ),
    ModelSpec(
        model_id="gemini-3.1-flash-lite",
        provider="google",
        model_family="gemini",
        model_class="flash_lite",
        stable=True,
        free_pool=True,
    ),
    ModelSpec(
        model_id="gemini-2.5-flash",
        provider="google",
        model_family="gemini",
        model_class="flash",
        stable=True,
        free_pool=True,
    ),
    ModelSpec(
        model_id="gemini-2.5-flash-lite",
        provider="google",
        model_family="gemini",
        model_class="flash_lite",
        stable=True,
        free_pool=True,
    ),
)

_MODEL_REGISTRY: Mapping[str, ModelSpec] = MappingProxyType(
    {
        spec.model_id: spec
        for spec in _MODEL_SPECS
    }
)

FREE_GEMINI_MODEL_IDS = tuple(
    spec.model_id
    for spec in _MODEL_SPECS
    if spec.free_pool
)


if DEFAULT_GEMINI_MODEL not in _MODEL_REGISTRY:
    raise RuntimeError(
        "Default Gemini model is missing from the model registry."
    )


def registered_model_ids() -> tuple[str, ...]:
    return tuple(
        _MODEL_REGISTRY.keys()
    )


def model_spec(
    model_id: str,
) -> ModelSpec:
    normalized = str(
        model_id or ""
    ).strip().lower()

    if not normalized:
        raise KeyError(
            "Gemini model ID is required."
        )

    try:
        return _MODEL_REGISTRY[
            normalized
        ]
    except KeyError as error:
        raise KeyError(
            "Unregistered Gemini model: "
            + normalized
        ) from error


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
