from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Sequence

from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import multimodal_intelligence_bridge
from app.services import structured_claim_input
from app.services import structured_claim_shadow_bridge


MULTIMODAL_STRUCTURED_SHADOW_CALLER_VERSION = (
    "multimodal-structured-shadow-caller-v1"
)


MULTIMODAL_STRUCTURED_SHADOW_CALLER_POLICY = {
    "shadow_default_enabled": False,
    "disabled_path_uses_existing_bridge_builder_directly": True,
    "enabled_path_uses_product35i_wrapper": True,
    "shadow_failure_falls_back_to_existing_bridge_builder": True,
    "shadow_sink_failure_can_break_runtime": False,
    "manifest_structured_input_autowiring": True,
    "explicit_structured_input_overrides_manifest": True,
    "manifest_input_collection_can_establish_identity": False,
    "shadow_output_can_select_claim": False,
    "shadow_output_can_filter_candidate": False,
    "shadow_output_can_persist_claim": False,
    "shadow_output_can_persist_evidence": False,
    "shadow_output_can_persist_observation": False,
    "shadow_output_can_create_story_membership": False,
    "shadow_output_can_establish_corroboration": False,
    "shadow_output_can_establish_authority": False,
    "shadow_output_can_establish_reliability": False,
    "shadow_output_can_establish_independence": False,
    "shadow_output_can_establish_truth": False,
    "shadow_output_can_affect_live_merit": False,
    "provider_calls_expected": 0,
    "provider_tokens_expected": 0,
    "database_writes_expected": 0,
}


def _disabled_shadow_report() -> Dict[str, Any]:
    return {
        "version": (
            structured_claim_shadow_bridge
            .STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION
        ),
        "status": "disabled",
        "candidate_rows": [],
        "unbound_output_candidate_ids": [],
        "raw_model_outputs_stored": False,
        "persistence_allowed": False,
        "replaces_production_identity": False,
        "story_membership_allowed": False,
        "corroboration_allowed": False,
        "live_merit_effect": False,
        "policy": dict(
            structured_claim_shadow_bridge
            .STRUCTURED_CLAIM_SHADOW_POLICY
        ),
    }


def _shadow_error_report(error: Exception) -> Dict[str, Any]:
    return {
        "version": (
            structured_claim_shadow_bridge
            .STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION
        ),
        "status": "error",
        "candidate_rows": [],
        "unbound_output_candidate_ids": [],
        "raw_model_outputs_stored": False,
        "persistence_allowed": False,
        "replaces_production_identity": False,
        "story_membership_allowed": False,
        "corroboration_allowed": False,
        "live_merit_effect": False,
        "error_type": type(error).__name__,
        "error": " ".join(str(error or "").split())[:320],
        "policy": {
            **dict(
                structured_claim_shadow_bridge
                .STRUCTURED_CLAIM_SHADOW_POLICY
            ),
            "shadow_failure_fell_back_to_existing_bridge_builder": True,
        },
    }


def _validate_result(
    raw: Any,
    *,
    item_id: str,
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError(
            "Structured shadow bridge result must be a mapping."
        )

    result = dict(raw)
    plan = result.get("production_plan")
    report = result.get("structured_shadow")

    if not isinstance(
        plan,
        bridge_models.ItemIntelligenceBridgePlan,
    ):
        raise ValueError(
            "Structured shadow bridge did not return a production plan."
        )

    if plan.item_id != item_id:
        raise ValueError(
            "Structured shadow bridge changed the production plan item ID."
        )

    if not isinstance(report, Mapping):
        raise ValueError(
            "Structured shadow bridge did not return a shadow report."
        )

    report = dict(report)

    for field in (
        "persistence_allowed",
        "replaces_production_identity",
        "story_membership_allowed",
        "corroboration_allowed",
        "live_merit_effect",
    ):
        if bool(report.get(field)):
            raise ValueError(
                "Structured shadow report enabled forbidden authority: "
                + field
            )

    return {
        "production_plan": plan,
        "structured_shadow": report,
    }


def _bounded_string_list(
    value: Any,
) -> list[str]:
    if not isinstance(
        value,
        (list, tuple),
    ):
        return []

    output = []

    for raw in value:
        text = " ".join(
            str(raw or "").split()
        )[:320]

        if (
            text
            and text not in output
        ):
            output.append(text)

    return output


def _manifest_structured_input(
    raw: Any,
) -> tuple[
    Mapping[str, Any],
    Dict[str, Any],
]:
    if not isinstance(
        raw,
        Mapping,
    ):
        raise ValueError(
            "Structured Claim Input collector "
            "must return a mapping."
        )

    result = dict(raw)

    if (
        " ".join(
            str(
                result.get(
                    "version",
                    "",
                )
                or ""
            ).split()
        )
        != (
            structured_claim_input
            .STRUCTURED_CLAIM_INPUT_VERSION
        )
    ):
        raise ValueError(
            "Structured Claim Input collector "
            "version is unsupported."
        )

    outputs = result.get(
        "outputs_by_candidate_id"
    )

    if not isinstance(
        outputs,
        Mapping,
    ):
        raise ValueError(
            "Structured Claim Input collector "
            "outputs must be a mapping."
        )

    summary = {
        "version": (
            structured_claim_input
            .STRUCTURED_CLAIM_INPUT_VERSION
        ),
        "source": (
            "semantic_manifest_sidecar"
        ),
        "candidate_count": int(
            result.get(
                "candidate_count",
                0,
            )
            or 0
        ),
        "provided_count": int(
            result.get(
                "provided_count",
                0,
            )
            or 0
        ),
        "duplicate_candidate_ids": (
            _bounded_string_list(
                result.get(
                    "duplicate_candidate_ids"
                )
            )
        ),
        "unbound_output_candidate_ids": (
            _bounded_string_list(
                result.get(
                    "unbound_output_candidate_ids"
                )
            )
        ),
        "report_errors": (
            _bounded_string_list(
                result.get(
                    "report_errors"
                )
            )
        ),
        "raw_provider_response_stored": False,
    }

    return (
        dict(outputs),
        summary,
    )


def _explicit_structured_input_summary(
    outputs: Any,
) -> Dict[str, Any]:
    return {
        "version": (
            structured_claim_input
            .STRUCTURED_CLAIM_INPUT_VERSION
        ),
        "source": (
            "explicit_runtime_mapping"
        ),
        "candidate_count": None,
        "provided_count": (
            len(outputs)
            if isinstance(
                outputs,
                Mapping,
            )
            else 0
        ),
        "duplicate_candidate_ids": [],
        "unbound_output_candidate_ids": [],
        "report_errors": (
            []
            if isinstance(
                outputs,
                Mapping,
            )
            else [
                "explicit_structured_outputs_not_mapping"
            ]
        ),
        "raw_provider_response_stored": False,
    }


def build_runtime_bridge_plan(
    *,
    item: content.UnifiedContentItem,
    manifest: artifact_models.ItemArtifactManifest,
    bindings: bridge_models.BridgeBindings,
    relationships: Sequence[
        content.ContentRelationship
    ] = (),
    shadow_enabled: bool = False,
    structured_outputs_by_candidate_id: Mapping[
        str,
        Any,
    ] | None = None,
    allowed_entity_keys: Sequence[str] = (),
    production_bridge_builder=(
        multimodal_intelligence_bridge
        .build_item_intelligence_bridge
    ),
    shadow_bridge_builder=(
        structured_claim_shadow_bridge
        .build_item_intelligence_bridge_with_structured_shadow
    ),
    structured_input_collector=(
        structured_claim_input
        .collect_structured_claim_outputs
    ),
) -> Dict[str, Any]:
    """Build the runtime bridge plan with an optional isolated #35I shadow path."""

    if not shadow_enabled:
        plan = production_bridge_builder(
            item=item,
            manifest=manifest,
            bindings=bindings,
            relationships=tuple(relationships),
        )

        return {
            "production_plan": plan,
            "structured_shadow": _disabled_shadow_report(),
        }

    try:
        if (
            structured_outputs_by_candidate_id
            is None
        ):
            (
                resolved_outputs,
                structured_input_summary,
            ) = _manifest_structured_input(
                structured_input_collector(
                    manifest
                )
            )

        else:
            resolved_outputs = (
                structured_outputs_by_candidate_id
            )

            structured_input_summary = (
                _explicit_structured_input_summary(
                    resolved_outputs
                )
            )

        raw = shadow_bridge_builder(
            item=item,
            manifest=manifest,
            bindings=bindings,
            relationships=tuple(relationships),
            shadow_enabled=True,
            structured_outputs_by_candidate_id=(
                resolved_outputs
            ),
            allowed_entity_keys=tuple(
                allowed_entity_keys
            ),
        )

        validated = _validate_result(
            raw,
            item_id=item.item_id,
        )

        report = dict(
            validated[
                "structured_shadow"
            ]
        )

        report[
            "structured_input"
        ] = structured_input_summary

        return {
            "production_plan": (
                validated[
                    "production_plan"
                ]
            ),
            "structured_shadow": report,
        }

    except Exception as error:
        plan = production_bridge_builder(
            item=item,
            manifest=manifest,
            bindings=bindings,
            relationships=tuple(relationships),
        )

        return {
            "production_plan": plan,
            "structured_shadow": _shadow_error_report(
                error
            ),
        }


def emit_structured_shadow_diagnostic(
    *,
    sink: Callable[[Mapping[str, Any]], Any] | None,
    side: str,
    report: Mapping[str, Any],
) -> bool:
    """Best-effort diagnostic emission. Sink failures never escape."""

    if sink is None:
        return False

    payload = {
        "version": MULTIMODAL_STRUCTURED_SHADOW_CALLER_VERSION,
        "side": " ".join(str(side or "").split()).lower(),
        "structured_shadow": dict(report),
        "policy": {
            "diagnostic_only": True,
            "raw_model_output_stored": False,
            "can_select_claim": False,
            "can_filter_candidate": False,
            "can_persist": False,
            "can_affect_live_merit": False,
        },
    }

    try:
        sink(payload)
    except Exception:
        return False

    return True


def structured_shadow_caller_descriptor() -> Dict[str, Any]:
    return {
        "version": MULTIMODAL_STRUCTURED_SHADOW_CALLER_VERSION,
        "shadow_default_enabled": False,
        "provider_call_performed": False,
        "provider_calls_expected": 0,
        "provider_tokens_expected": 0,
        "database_writes_expected": 0,
        "production_identity_replaced": False,
        "live_merit_effect": False,
        "policy": dict(
            MULTIMODAL_STRUCTURED_SHADOW_CALLER_POLICY
        ),
    }
