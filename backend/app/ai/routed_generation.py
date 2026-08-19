from __future__ import annotations

import os
import re
import time

from typing import Any

from app.ai import generation as _generation
from app.ai.models import DEFAULT_GEMINI_MODEL
from app.ai.resources import GENERATION
from app.ai.router import route_task
from app.ai.tasks import task_policy


ROUTED_GENERATION_VERSION = "google-model-router-wiring-v1"

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

    requested_resource_id = (
        None
        if (
            not requested
            or requested
            == DEFAULT_GEMINI_MODEL
        )
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

    if (
        route.requires_project_capacity_config
        and not project_capacity_configured(
            route.resource_id
        )
    ):
        missing_keys = [
            key
            for key in model_capacity_env_keys(
                route.resource_id
            )
            if not str(
                os.getenv(
                    key,
                    "",
                )
            ).strip()
        ]

        raise AIResourceCapacityConfigurationError(
            "AI resource requires explicit project capacity "
            "configuration before execution: "
            + route.resource_id
            + ". Missing: "
            + ", ".join(
                missing_keys
            )
        )

    return route.resource_id


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
