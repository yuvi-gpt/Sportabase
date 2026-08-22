from __future__ import annotations

import os
import re
import time

from typing import Any

from app.ai import generation as _generation
from app.ai.models import DEFAULT_GEMINI_MODEL
from app.ai.resources import (
    GENERATION,
    resource_spec,
)
from app.ai.router import route_task
from app.ai.tasks import task_policy


ROUTED_GENERATION_VERSION = "google-model-router-wiring-v2"

_REQUIRED_MODEL_CAPACITY_KEYS = (
    "PROVIDER_RPM",
    "DISPATCH_RPM",
    "PROVIDER_TPM",
    "USABLE_TPM",
    "PROVIDER_RPD",
    "RPD_RESERVE",
    "MAX_ESTIMATED_INPUT_TOKENS",
    "MAX_PACING_WAIT_SECONDS",
)


class AIResourceCapacityConfigurationError(
    RuntimeError
):
    pass


def _normalized_resource_id(
    resource_id: Any,
) -> str:
    return str(
        resource_id or ""
    ).strip().lower()


def _capacity_env_suffix(
    resource_id: Any,
) -> str:
    normalized = _normalized_resource_id(
        resource_id
    )

    return re.sub(
        r"[^A-Z0-9]+",
        "_",
        normalized.upper(),
    ).strip("_")


def model_capacity_env_keys(
    resource_id: Any,
) -> tuple[str, ...]:
    suffix = _capacity_env_suffix(
        resource_id
    )

    if not suffix:
        return ()

    return tuple(
        "SPORTABASE_GEMINI_MODEL_"
        + suffix
        + "_"
        + key
        for key in _REQUIRED_MODEL_CAPACITY_KEYS
    )


def project_capacity_configured(
    resource_id: Any,
) -> bool:
    keys = model_capacity_env_keys(
        resource_id
    )

    return bool(
        keys
        and all(
            str(
                os.getenv(
                    key,
                    "",
                )
            ).strip()
            for key in keys
        )
    )


def _resource_capacity_ready(
    resource_id: str,
) -> bool:
    spec = resource_spec(
        resource_id
    )

    return bool(
        not spec.requires_project_capacity_config
        or project_capacity_configured(
            spec.resource_id
        )
    )


def _missing_capacity_keys(
    resource_id: str,
) -> list[str]:
    return [
        key
        for key in model_capacity_env_keys(
            resource_id
        )
        if not str(
            os.getenv(
                key,
                "",
            )
        ).strip()
    ]


def resolve_routed_generation_model(
    *,
    mode: str,
    model: str,
) -> str:
    try:
        policy = task_policy(
            mode
        )
    except KeyError:
        # Compatibility path for legacy/internal modes that have not
        # been registered as Sportabase AI tasks yet.
        return model

    requested = _normalized_resource_id(
        model
    )

    uses_task_primary = bool(
        not requested
        or requested
        == DEFAULT_GEMINI_MODEL
    )

    requested_resource_id = (
        None
        if uses_task_primary
        else requested
    )

    route = route_task(
        policy.task_id,
        requested_resource_id=(
            requested_resource_id
        ),
    )

    if route.resource_kind != GENERATION:
        raise RuntimeError(
            "AI task cannot execute through the generation backend: "
            + route.task_id
        )

    if _resource_capacity_ready(
        route.resource_id
    ):
        return route.resource_id

    # A task's compatibility fallback is used only when the caller requested
    # the task primary implicitly and the preferred production model lacks an
    # explicit project-capacity envelope. This is not a provider-error retry,
    # quota spillover, or silent downgrade after a 429/503. Explicit model
    # overrides always fail closed when their capacity configuration is absent.
    if (
        uses_task_primary
        and route.automatic_fallback_enabled
    ):
        for fallback_resource_id in (
            route.fallback_resource_ids
        ):
            fallback = resource_spec(
                fallback_resource_id
            )

            if fallback.resource_kind != GENERATION:
                continue

            if _resource_capacity_ready(
                fallback.resource_id
            ):
                return fallback.resource_id

    missing_keys = _missing_capacity_keys(
        route.resource_id
    )

    raise AIResourceCapacityConfigurationError(
        "AI resource requires explicit project capacity "
        "configuration before execution: "
        + route.resource_id
        + ". Missing: "
        + ", ".join(
            missing_keys
        )
    )


# Preserve the existing execution-platform public surface. Only generation
# dispatch is wrapped; all quota, telemetry, failure, and cache helpers remain
# the exact canonical implementations from app.ai.generation.
request_client_key = _generation.request_client_key
expire_stale_gemini_reservations = (
    _generation.expire_stale_gemini_reservations
)
reserve_gemini_call = _generation.reserve_gemini_call
usage_metadata_counts = _generation.usage_metadata_counts
classify_gemini_failure = _generation.classify_gemini_failure
finish_gemini_call = _generation.finish_gemini_call
record_inflight_gemini_join = (
    _generation.record_inflight_gemini_join
)
gemini_request_fingerprint = (
    _generation.gemini_request_fingerprint
)
record_analysis_cache_hit = (
    _generation.record_analysis_cache_hit
)


def generate_gemini_content(
    *,
    client: Any,
    client_key: str,
    mode: str,
    model: str,
    contents: Any,
    inflight_lock,
    inflight_calls,
    fingerprint_resolver,
    reserve_call,
    finish_call,
    classify_failure,
    record_join,
    sleep_func=time.sleep,
) -> Any:
    resolved_model = (
        resolve_routed_generation_model(
            mode=mode,
            model=model,
        )
    )

    return _generation.generate_gemini_content(
        client=client,
        client_key=client_key,
        mode=mode,
        model=resolved_model,
        contents=contents,
        inflight_lock=inflight_lock,
        inflight_calls=inflight_calls,
        fingerprint_resolver=(
            fingerprint_resolver
        ),
        reserve_call=reserve_call,
        finish_call=finish_call,
        classify_failure=classify_failure,
        record_join=record_join,
        sleep_func=sleep_func,
    )


def __getattr__(name: str):
    # Keep incidental historical module attributes available while callers
    # migrate to explicit app.ai imports.
    return getattr(
        _generation,
        name,
    )
