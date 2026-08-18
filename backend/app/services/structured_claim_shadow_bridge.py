from __future__ import annotations

import re

from typing import Any, Dict, Mapping, Sequence

from app.intelligence import claim_semantic_protocol_ownership as ownership
from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import multimodal_intelligence_bridge as production_bridge


STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION = (
    "structured-claim-shadow-bridge-v1"
)

SHADOW_STATUS_DISABLED = "disabled"
SHADOW_STATUS_ACTIVE = "active"
SHADOW_STATUS_NOT_PROVIDED = "not_provided"
SHADOW_STATUS_EVALUATED = "evaluated"
SHADOW_STATUS_ERROR = "error"


STRUCTURED_CLAIM_SHADOW_POLICY = {
    "shadow_is_opt_in": True,
    "shadow_default_enabled": False,
    "production_bridge_runs_first": True,
    "production_bridge_result_is_not_modified": True,
    "shadow_failure_can_break_production_bridge": False,
    "shadow_outputs_are_keyed_by_existing_candidate_id": True,
    "unbound_shadow_outputs_are_ignored": True,
    "protocol_ownership_is_product35g": True,
    "three_way_router_is_product35e": True,
    "partial_semantics_validator_is_product35d": True,
    "full_identity_authority_is_product35a": True,
    "shadow_can_replace_production_identity": False,
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
    "provider_calls_expected": 0,
    "provider_tokens_expected": 0,
    "database_writes_expected": 0,
}


class StructuredClaimShadowBridgeError(ValueError):
    pass


class StructuredClaimShadowBridgeInputError(
    StructuredClaimShadowBridgeError
):
    pass


def _clean(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _candidate_claim_id(candidate: Any) -> str:
    proposal = getattr(
        candidate,
        "claim",
        None,
    )

    return _clean(
        getattr(
            proposal,
            "deterministic_id",
            "",
        )
    )


def _shadow_row_base(
    *,
    candidate_id: str,
    production_claim_id: str,
) -> Dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "production_claim_id": production_claim_id,
        "shadow_status": SHADOW_STATUS_NOT_PROVIDED,
        "router_status": "",
        "route": "",
        "reason": "",
        "candidate": None,
        "identity_complete": False,
        "missing_identity_fields": [],
        "core_key": "",
        "core_fingerprint": "",
        "specific_fingerprint": "",
        "safe_acceptance": False,
        "safe_exclusion": False,
        "protocol_ownership": None,
        "error_type": "",
        "error": "",
        "raw_model_output_stored": False,
        "persistence_allowed": False,
        "replaces_production_identity": False,
        "story_membership_allowed": False,
        "corroboration_allowed": False,
        "live_merit_effect": False,
    }


def _shadow_row_from_parsed(
    *,
    candidate_id: str,
    production_claim_id: str,
    parsed: Mapping[str, Any],
) -> Dict[str, Any]:
    row = _shadow_row_base(
        candidate_id=candidate_id,
        production_claim_id=production_claim_id,
    )

    candidate = parsed.get(
        "candidate"
    )

    protocol = parsed.get(
        "protocol_ownership"
    )

    row.update(
        {
            "shadow_status": SHADOW_STATUS_EVALUATED,
            "router_status": _clean(
                parsed.get("status")
            ),
            "route": _clean(
                parsed.get("route")
            ),
            "reason": _clean(
                parsed.get("reason")
            )[:500],
            "candidate": (
                dict(candidate)
                if isinstance(
                    candidate,
                    Mapping,
                )
                else None
            ),
            "identity_complete": bool(
                parsed.get(
                    "identity_complete",
                    False,
                )
            ),
            "missing_identity_fields": list(
                parsed.get(
                    "missing_identity_fields",
                    [],
                )
                or []
            ),
            "core_key": _clean(
                parsed.get("core_key")
            ),
            "core_fingerprint": _clean(
                parsed.get(
                    "core_fingerprint"
                )
            ),
            "specific_fingerprint": _clean(
                parsed.get(
                    "specific_fingerprint"
                )
            ),
            "safe_acceptance": bool(
                parsed.get(
                    "safe_acceptance",
                    False,
                )
            ),
            "safe_exclusion": bool(
                parsed.get(
                    "safe_exclusion",
                    False,
                )
            ),
            "protocol_ownership": (
                dict(protocol)
                if isinstance(
                    protocol,
                    Mapping,
                )
                else None
            ),
        }
    )

    return row


def _shadow_error_row(
    *,
    candidate_id: str,
    production_claim_id: str,
    error: Exception,
) -> Dict[str, Any]:
    row = _shadow_row_base(
        candidate_id=candidate_id,
        production_claim_id=production_claim_id,
    )

    row.update(
        {
            "shadow_status": SHADOW_STATUS_ERROR,
            "error_type": type(error).__name__,
            "error": _clean(error)[:500],
        }
    )

    return row


def structured_claim_shadow_descriptor() -> Dict[str, Any]:
    return {
        "version": STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION,
        "shadow_default_enabled": False,
        "provider_call_performed": False,
        "provider_calls_expected": 0,
        "provider_tokens_expected": 0,
        "database_writes_expected": 0,
        "production_bridge_changed": False,
        "production_identity_replaced": False,
        "live_merit_effect": False,
        "policy": dict(
            STRUCTURED_CLAIM_SHADOW_POLICY
        ),
    }


def build_item_intelligence_bridge_with_structured_shadow(
    *,
    item: content.UnifiedContentItem,
    manifest: artifact_models.ItemArtifactManifest,
    bindings: bridge_models.BridgeBindings | None = None,
    relationships: Sequence[
        content.ContentRelationship
    ] = (),
    shadow_enabled: bool = False,
    structured_outputs_by_candidate_id: Mapping[
        str,
        Any,
    ] | None = None,
    allowed_entity_keys: Sequence[str] = (),
) -> Dict[str, Any]:
    """
    Build the existing production bridge plan first, then optionally evaluate
    precomputed structured model outputs in an isolated read-only shadow path.

    The shadow path performs no provider calls and no persistence. It cannot
    replace or mutate any identity, proposal, observation, story membership,
    corroboration, authority, or Merit behavior from the production bridge.
    """

    production_plan = (
        production_bridge
        .build_item_intelligence_bridge(
            item=item,
            manifest=manifest,
            bindings=bindings,
            relationships=relationships,
        )
    )

    report: Dict[str, Any] = {
        "version": STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION,
        "enabled": bool(
            shadow_enabled
        ),
        "status": (
            SHADOW_STATUS_ACTIVE
            if shadow_enabled
            else SHADOW_STATUS_DISABLED
        ),
        "subject_key": _clean(
            production_plan.subject_key
        ),
        "candidate_rows": [],
        "unbound_output_candidate_ids": [],
        "report_errors": [],
        "raw_model_outputs_stored": False,
        "persistence_allowed": False,
        "replaces_production_identity": False,
        "story_membership_allowed": False,
        "corroboration_allowed": False,
        "live_merit_effect": False,
        "policy": dict(
            STRUCTURED_CLAIM_SHADOW_POLICY
        ),
    }

    if not shadow_enabled:
        return {
            "version": STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION,
            "production_plan": production_plan,
            "structured_shadow": report,
        }

    if structured_outputs_by_candidate_id is None:
        outputs: Mapping[
            str,
            Any,
        ] = {}
    elif isinstance(
        structured_outputs_by_candidate_id,
        Mapping,
    ):
        outputs = (
            structured_outputs_by_candidate_id
        )
    else:
        report[
            "report_errors"
        ].append(
            "structured_outputs_by_candidate_id_not_mapping"
        )
        return {
            "version": STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION,
            "production_plan": production_plan,
            "structured_shadow": report,
        }

    normalized_outputs: Dict[
        str,
        Any,
    ] = {}

    duplicate_ids = []

    for raw_id, raw_output in (
        outputs.items()
    ):
        candidate_id = _clean(
            raw_id
        )

        if not candidate_id:
            report[
                "report_errors"
            ].append(
                "empty_shadow_candidate_id"
            )
            continue

        if candidate_id in normalized_outputs:
            duplicate_ids.append(
                candidate_id
            )
            continue

        normalized_outputs[
            candidate_id
        ] = raw_output

    for candidate_id in sorted(
        set(duplicate_ids)
    ):
        report[
            "report_errors"
        ].append(
            "duplicate_shadow_candidate_id:"
            + candidate_id
        )

    production_candidate_ids = []

    for production_candidate in (
        production_plan.candidates
    ):
        candidate_id = _clean(
            production_candidate.candidate_id
        )

        production_claim_id = (
            _candidate_claim_id(
                production_candidate
            )
        )

        if candidate_id:
            production_candidate_ids.append(
                candidate_id
            )

        row = _shadow_row_base(
            candidate_id=candidate_id,
            production_claim_id=(
                production_claim_id
            ),
        )

        if (
            not candidate_id
            or candidate_id
            not in normalized_outputs
        ):
            report[
                "candidate_rows"
            ].append(row)
            continue

        if not _clean(
            production_plan.subject_key
        ):
            report[
                "candidate_rows"
            ].append(
                _shadow_error_row(
                    candidate_id=candidate_id,
                    production_claim_id=(
                        production_claim_id
                    ),
                    error=(
                        StructuredClaimShadowBridgeInputError(
                            "Production bridge subject is unresolved."
                        )
                    ),
                )
            )
            continue

        try:
            parsed = (
                ownership
                .parse_protocol_owned_claim_semantic_output(
                    normalized_outputs[
                        candidate_id
                    ],
                    expected_subject_key=(
                        production_plan.subject_key
                    ),
                    allowed_entity_keys=(
                        allowed_entity_keys
                    ),
                )
            )
        except Exception as error:
            # Shadow failures are observational only. The already-built
            # production plan remains the authoritative return artifact.
            report[
                "candidate_rows"
            ].append(
                _shadow_error_row(
                    candidate_id=candidate_id,
                    production_claim_id=(
                        production_claim_id
                    ),
                    error=error,
                )
            )
            continue

        report[
            "candidate_rows"
        ].append(
            _shadow_row_from_parsed(
                candidate_id=candidate_id,
                production_claim_id=(
                    production_claim_id
                ),
                parsed=parsed,
            )
        )

    production_ids = set(
        production_candidate_ids
    )

    report[
        "unbound_output_candidate_ids"
    ] = sorted(
        candidate_id
        for candidate_id
        in normalized_outputs
        if candidate_id
        not in production_ids
    )

    return {
        "version": STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION,
        "production_plan": production_plan,
        "structured_shadow": report,
    }


__all__ = [
    "STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION",
    "SHADOW_STATUS_DISABLED",
    "SHADOW_STATUS_ACTIVE",
    "SHADOW_STATUS_NOT_PROVIDED",
    "SHADOW_STATUS_EVALUATED",
    "SHADOW_STATUS_ERROR",
    "STRUCTURED_CLAIM_SHADOW_POLICY",
    "StructuredClaimShadowBridgeError",
    "StructuredClaimShadowBridgeInputError",
    "structured_claim_shadow_descriptor",
    "build_item_intelligence_bridge_with_structured_shadow",
]
