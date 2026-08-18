from __future__ import annotations

import copy
import re

from typing import Any, Callable, Dict, Mapping, Sequence

from app.models import intelligence_bridge as bridge_models
from app.services import multimodal_intelligence_bridge as production_bridge
from app.services import multimodal_intelligence_runtime as production_runtime
from app.services import structured_claim_shadow_bridge as shadow_bridge


STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION = (
    "structured-claim-shadow-runtime-v1"
)

SHADOW_RUNTIME_STATUS_ACTIVE = "active"
SHADOW_RUNTIME_STATUS_ERROR = "error"
SHADOW_RUNTIME_STATUS_NOT_OBSERVED = "not_observed"


STRUCTURED_CLAIM_SHADOW_RUNTIME_POLICY = {
    "shadow_is_opt_in": True,
    "shadow_default_enabled": False,
    "disabled_path_delegates_without_shadow_validation": True,
    "existing_runtime_is_authoritative": True,
    "existing_runtime_result_is_not_modified": True,
    "existing_runtime_bridge_builder_seam_is_used": True,
    "existing_shadow_api_runtime_runner_seam_is_compatible": True,
    "product35i_shadow_bridge_is_reused": True,
    "shadow_failure_can_break_runtime": False,
    "shadow_additional_provider_calls_expected": 0,
    "shadow_additional_provider_tokens_expected": 0,
    "shadow_database_writes_expected": 0,
    "structured_outputs_are_precomputed_inputs": True,
    "raw_model_outputs_are_not_copied_to_runtime_result": True,
    "shadow_can_replace_production_identity": False,
    "shadow_can_filter_production_candidates": False,
    "shadow_can_change_persistence_scope": False,
    "shadow_can_persist_claims": False,
    "shadow_can_persist_evidence": False,
    "shadow_can_persist_observations": False,
    "shadow_can_create_story_membership": False,
    "shadow_can_establish_corroboration": False,
    "shadow_can_establish_authority": False,
    "shadow_can_establish_reliability": False,
    "shadow_can_establish_independence": False,
    "shadow_can_establish_truth": False,
    "shadow_can_affect_live_merit": False,
    "shadow_can_create_training_labels": False,
}


class StructuredClaimShadowRuntimeError(RuntimeError):
    pass


class StructuredClaimShadowRuntimeInputError(
    StructuredClaimShadowRuntimeError
):
    pass


class StructuredClaimShadowRuntimeIntegrityError(
    StructuredClaimShadowRuntimeError
):
    pass


def _clean(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _binding_media_id(value: Any) -> str:
    return _clean(
        getattr(
            value,
            "media_item_id",
            "",
        )
    )


def _normalize_outputs(
    value: Any,
    *,
    label: str,
) -> Mapping[str, Any]:
    if value is None:
        return {}

    if not isinstance(
        value,
        Mapping,
    ):
        raise StructuredClaimShadowRuntimeInputError(
            label
            + " structured outputs must be a mapping."
        )

    return value


def _normalize_entity_keys(
    values: Sequence[str],
) -> tuple[str, ...]:
    if isinstance(
        values,
        (str, bytes),
    ):
        raise StructuredClaimShadowRuntimeInputError(
            "Structured entity allowlist must be a sequence of keys."
        )

    output = []

    for raw in values:
        key = _clean(raw)

        if key and key not in output:
            output.append(key)

    return tuple(output)


def _side_for_bridge_call(
    *,
    bindings: Any,
    left_media_item_id: str,
    right_media_item_id: str,
) -> str:
    media_item_id = _binding_media_id(
        bindings
    )

    if (
        media_item_id
        and media_item_id
        == left_media_item_id
    ):
        return "left"

    if (
        media_item_id
        and media_item_id
        == right_media_item_id
    ):
        return "right"

    raise StructuredClaimShadowRuntimeIntegrityError(
        "Structured shadow bridge call could not be bound "
        "to the left or right verified media item."
    )


def _error_report(
    *,
    side: str,
    item_id: str,
    error: Exception,
) -> Dict[str, Any]:
    return {
        "version": (
            STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION
        ),
        "side": side,
        "item_id": _clean(item_id),
        "status": SHADOW_RUNTIME_STATUS_ERROR,
        "error_type": type(error).__name__,
        "error": _clean(error)[:500],
        "structured_shadow": None,
        "raw_model_output_stored": False,
        "production_plan_replaced": False,
        "production_candidate_filter_applied": False,
        "persistence_scope_changed": False,
        "additional_provider_calls": 0,
        "additional_provider_tokens": 0,
        "database_writes": 0,
        "live_merit_effect": False,
    }


def _observed_report(
    *,
    side: str,
    item_id: str,
    report: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "version": (
            STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION
        ),
        "side": side,
        "item_id": _clean(item_id),
        "status": SHADOW_RUNTIME_STATUS_ACTIVE,
        "error_type": "",
        "error": "",
        "structured_shadow": copy.deepcopy(
            dict(report)
        ),
        "raw_model_output_stored": False,
        "production_plan_replaced": False,
        "production_candidate_filter_applied": False,
        "persistence_scope_changed": False,
        "additional_provider_calls": 0,
        "additional_provider_tokens": 0,
        "database_writes": 0,
        "live_merit_effect": False,
    }


def _not_observed_report(
    *,
    side: str,
) -> Dict[str, Any]:
    return {
        "version": (
            STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION
        ),
        "side": side,
        "item_id": "",
        "status": SHADOW_RUNTIME_STATUS_NOT_OBSERVED,
        "error_type": "",
        "error": "",
        "structured_shadow": None,
        "raw_model_output_stored": False,
        "production_plan_replaced": False,
        "production_candidate_filter_applied": False,
        "persistence_scope_changed": False,
        "additional_provider_calls": 0,
        "additional_provider_tokens": 0,
        "database_writes": 0,
        "live_merit_effect": False,
    }


def structured_claim_shadow_runtime_descriptor() -> Dict[str, Any]:
    return {
        "version": (
            STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION
        ),
        "shadow_default_enabled": False,
        "checkpoint_provider_call_performed": False,
        "shadow_additional_provider_calls_expected": 0,
        "shadow_additional_provider_tokens_expected": 0,
        "shadow_database_writes_expected": 0,
        "production_runtime_changed": False,
        "production_shadow_api_changed": False,
        "production_bridge_changed": False,
        "production_identity_replaced": False,
        "live_merit_effect": False,
        "policy": dict(
            STRUCTURED_CLAIM_SHADOW_RUNTIME_POLICY
        ),
    }


def run_multimodal_intelligence_runtime_with_structured_shadow(
    *,
    structured_claim_shadow_enabled: bool = False,
    left_structured_outputs_by_candidate_id: Mapping[
        str,
        Any,
    ] | None = None,
    right_structured_outputs_by_candidate_id: Mapping[
        str,
        Any,
    ] | None = None,
    structured_allowed_entity_keys: Sequence[str] = (),
    runtime_runner: Callable[..., Mapping[str, Any]] = (
        production_runtime
        .run_multimodal_intelligence_runtime
    ),
    structured_shadow_bridge_builder: Callable[..., Mapping[str, Any]] = (
        shadow_bridge
        .build_item_intelligence_bridge_with_structured_shadow
    ),
    production_bridge_builder: Callable[..., Any] = (
        production_bridge
        .build_item_intelligence_bridge
    ),
    **runtime_kwargs: Any,
) -> Dict[str, Any]:
    """Run the existing multimodal runtime with optional #35I diagnostics.

    Disabled mode delegates directly and does not inspect structured inputs.
    Enabled mode replaces only the runtime's injected bridge-builder dependency.
    The injected bridge-builder returns the ordinary production bridge plan to
    the existing runtime and keeps the structured report on a separate path.
    """

    if not isinstance(
        structured_claim_shadow_enabled,
        bool,
    ):
        raise StructuredClaimShadowRuntimeInputError(
            "Structured claim shadow flag must be boolean."
        )

    if not callable(runtime_runner):
        raise StructuredClaimShadowRuntimeInputError(
            "Runtime runner must be callable."
        )

    if not structured_claim_shadow_enabled:
        # Deliberately do not validate, normalize, copy, or otherwise inspect
        # structured shadow inputs while disabled. The caller receives exactly
        # the existing runtime result from exactly the existing runtime kwargs.
        return runtime_runner(
            **runtime_kwargs
        )

    if "bridge_builder" in runtime_kwargs:
        raise StructuredClaimShadowRuntimeInputError(
            "Enabled structured shadow cannot be combined with a caller-"
            "supplied bridge_builder; the locked production bridge must remain "
            "the authoritative bridge implementation."
        )

    if not callable(
        structured_shadow_bridge_builder
    ):
        raise StructuredClaimShadowRuntimeInputError(
            "Structured shadow bridge builder must be callable."
        )

    if not callable(
        production_bridge_builder
    ):
        raise StructuredClaimShadowRuntimeInputError(
            "Production bridge fallback must be callable."
        )

    left_outputs = _normalize_outputs(
        left_structured_outputs_by_candidate_id,
        label="Left",
    )

    right_outputs = _normalize_outputs(
        right_structured_outputs_by_candidate_id,
        label="Right",
    )

    entity_keys = _normalize_entity_keys(
        structured_allowed_entity_keys
    )

    left_bindings = runtime_kwargs.get(
        "left_bindings"
    )
    right_bindings = runtime_kwargs.get(
        "right_bindings"
    )

    if not isinstance(
        left_bindings,
        bridge_models.BridgeBindings,
    ) or not isinstance(
        right_bindings,
        bridge_models.BridgeBindings,
    ):
        raise StructuredClaimShadowRuntimeInputError(
            "Enabled structured shadow requires the runtime's left and right "
            "BridgeBindings."
        )

    left_media_item_id = _binding_media_id(
        left_bindings
    )
    right_media_item_id = _binding_media_id(
        right_bindings
    )

    if (
        not left_media_item_id
        or not right_media_item_id
        or left_media_item_id
        == right_media_item_id
    ):
        raise StructuredClaimShadowRuntimeInputError(
            "Enabled structured shadow requires two distinct non-empty media "
            "item bindings."
        )

    side_reports: Dict[
        str,
        Dict[str, Any],
    ] = {}

    def runtime_bridge_builder(
        *,
        item,
        manifest,
        bindings,
        relationships=(),
    ):
        side = _side_for_bridge_call(
            bindings=bindings,
            left_media_item_id=(
                left_media_item_id
            ),
            right_media_item_id=(
                right_media_item_id
            ),
        )

        outputs = (
            left_outputs
            if side == "left"
            else right_outputs
        )

        try:
            wrapped = (
                structured_shadow_bridge_builder(
                    item=item,
                    manifest=manifest,
                    bindings=bindings,
                    relationships=relationships,
                    shadow_enabled=True,
                    structured_outputs_by_candidate_id=(
                        outputs
                    ),
                    allowed_entity_keys=(
                        entity_keys
                    ),
                )
            )

            if not isinstance(
                wrapped,
                Mapping,
            ):
                raise StructuredClaimShadowRuntimeIntegrityError(
                    "#35I structured shadow wrapper did not return a mapping."
                )

            production_plan = wrapped.get(
                "production_plan"
            )
            report = wrapped.get(
                "structured_shadow"
            )

            if not isinstance(
                production_plan,
                bridge_models.ItemIntelligenceBridgePlan,
            ):
                raise StructuredClaimShadowRuntimeIntegrityError(
                    "#35I structured shadow wrapper did not expose a production "
                    "bridge plan."
                )

            if not isinstance(
                report,
                Mapping,
            ):
                raise StructuredClaimShadowRuntimeIntegrityError(
                    "#35I structured shadow wrapper did not expose a bounded "
                    "shadow report."
                )

            side_reports[side] = (
                _observed_report(
                    side=side,
                    item_id=getattr(
                        item,
                        "item_id",
                        "",
                    ),
                    report=report,
                )
            )

            # Only the production plan is returned to the existing runtime.
            return production_plan

        except Exception as error:
            # A shadow-layer failure may never break the existing runtime. The
            # locked production bridge is recomputed directly and returned.
            production_plan = (
                production_bridge_builder(
                    item=item,
                    manifest=manifest,
                    bindings=bindings,
                    relationships=relationships,
                )
            )

            side_reports[side] = (
                _error_report(
                    side=side,
                    item_id=getattr(
                        item,
                        "item_id",
                        "",
                    ),
                    error=error,
                )
            )

            return production_plan

    runtime_result = runtime_runner(
        **runtime_kwargs,
        bridge_builder=(
            runtime_bridge_builder
        ),
    )

    if not isinstance(
        runtime_result,
        Mapping,
    ):
        raise StructuredClaimShadowRuntimeIntegrityError(
            "Existing multimodal runtime did not return a mapping."
        )

    # Never mutate the result returned by the existing runtime.
    output = copy.deepcopy(
        dict(runtime_result)
    )

    output[
        "structured_claim_shadow"
    ] = {
        "version": (
            STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION
        ),
        "enabled": True,
        "status": SHADOW_RUNTIME_STATUS_ACTIVE,
        "left": copy.deepcopy(
            side_reports.get(
                "left",
                _not_observed_report(
                    side="left"
                ),
            )
        ),
        "right": copy.deepcopy(
            side_reports.get(
                "right",
                _not_observed_report(
                    side="right"
                ),
            )
        ),
        "raw_model_outputs_stored": False,
        "production_result_mutated": False,
        "production_identity_replaced": False,
        "production_candidate_filter_applied": False,
        "persistence_scope_changed": False,
        "additional_provider_calls": 0,
        "additional_provider_tokens": 0,
        "database_writes": 0,
        "story_membership_created": False,
        "corroboration_established": False,
        "authority_established": False,
        "reliability_established": False,
        "independence_established": False,
        "truth_established": False,
        "live_merit_effect": False,
        "policy": dict(
            STRUCTURED_CLAIM_SHADOW_RUNTIME_POLICY
        ),
    }

    return output


def make_structured_claim_shadow_runtime_runner(
    *,
    structured_claim_shadow_enabled: bool = False,
    left_structured_outputs_by_candidate_id: Mapping[
        str,
        Any,
    ] | None = None,
    right_structured_outputs_by_candidate_id: Mapping[
        str,
        Any,
    ] | None = None,
    structured_allowed_entity_keys: Sequence[str] = (),
    runtime_runner: Callable[..., Mapping[str, Any]] = (
        production_runtime
        .run_multimodal_intelligence_runtime
    ),
    structured_shadow_bridge_builder: Callable[..., Mapping[str, Any]] = (
        shadow_bridge
        .build_item_intelligence_bridge_with_structured_shadow
    ),
    production_bridge_builder: Callable[..., Any] = (
        production_bridge
        .build_item_intelligence_bridge
    ),
) -> Callable[..., Dict[str, Any]]:
    """Create a runtime_runner compatible with multimodal_shadow_api."""

    def runner(**runtime_kwargs: Any) -> Dict[str, Any]:
        return (
            run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=(
                    structured_claim_shadow_enabled
                ),
                left_structured_outputs_by_candidate_id=(
                    left_structured_outputs_by_candidate_id
                ),
                right_structured_outputs_by_candidate_id=(
                    right_structured_outputs_by_candidate_id
                ),
                structured_allowed_entity_keys=(
                    structured_allowed_entity_keys
                ),
                runtime_runner=runtime_runner,
                structured_shadow_bridge_builder=(
                    structured_shadow_bridge_builder
                ),
                production_bridge_builder=(
                    production_bridge_builder
                ),
                **runtime_kwargs,
            )
        )

    return runner


__all__ = [
    "STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION",
    "SHADOW_RUNTIME_STATUS_ACTIVE",
    "SHADOW_RUNTIME_STATUS_ERROR",
    "SHADOW_RUNTIME_STATUS_NOT_OBSERVED",
    "STRUCTURED_CLAIM_SHADOW_RUNTIME_POLICY",
    "StructuredClaimShadowRuntimeError",
    "StructuredClaimShadowRuntimeInputError",
    "StructuredClaimShadowRuntimeIntegrityError",
    "structured_claim_shadow_runtime_descriptor",
    "run_multimodal_intelligence_runtime_with_structured_shadow",
    "make_structured_claim_shadow_runtime_runner",
]
