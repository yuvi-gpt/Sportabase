from __future__ import annotations

import copy
import math

from typing import Any, Dict, Mapping

from app.analysis import corroboration as corroboration_analysis
from app.analysis import merit as merit_analysis
from app.services import multimodal_corroboration_runtime


MULTIMODAL_LIVE_MERIT_SHADOW_VERSION = (
    "multimodal-live-merit-shadow-v1"
)


class MultimodalLiveMeritShadowError(RuntimeError):
    pass


class ShadowInputError(
    MultimodalLiveMeritShadowError
):
    pass


class ShadowIntegrityError(
    MultimodalLiveMeritShadowError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _finite_number(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(value, bool):
        raise ShadowInputError(
            label + " must be numeric."
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ShadowInputError(
            label + " must be numeric."
        ) from exc

    if not math.isfinite(result):
        raise ShadowInputError(
            label + " must be finite."
        )

    return result


def _require_legacy_score(
    raw: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ShadowInputError(
            "Legacy Merit score must be a mapping."
        )

    score = copy.deepcopy(
        dict(raw)
    )

    total = _finite_number(
        score.get("total"),
        label="Legacy Merit total",
    )

    if total < 0.0 or total > 100.0:
        raise ShadowInputError(
            "Legacy Merit total must be between 0 and 100."
        )

    return score


def _require_corroboration_result(
    raw: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ShadowInputError(
            "#18 corroboration result must be a mapping."
        )

    result = copy.deepcopy(
        dict(raw)
    )

    if (
        _clean(
            result.get("version")
        )
        != (
            multimodal_corroboration_runtime
            .MULTIMODAL_CORROBORATION_RUNTIME_VERSION
        )
    ):
        raise ShadowInputError(
            "#18 corroboration runtime version is unsupported."
        )

    claim_id = _clean(
        result.get("claim_id")
    )

    if not claim_id:
        raise ShadowInputError(
            "#18 corroboration result requires a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise ShadowInputError(
            "#18 corroboration policy is required."
        )

    required_true = (
        "model_stance_materializes_historical_support_only",
        "support_edge_does_not_establish_truth",
        "support_edge_does_not_establish_independence",
        "independence_requires_existing_direct_stakeholder_verifier",
        "requires_two_distinct_sources",
        "requires_two_distinct_verified_direct_stakeholders",
        "requires_origin_destination_role_pair",
        "recorded_cross_dependency_fails_closed",
        "source_domain_diversity_alone_is_not_independence",
        "model_output_is_not_independence_proof",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise ShadowInputError(
                "#18 safety boundary missing: "
                + field
            )

    for field in (
        "establishes_truth",
        "live_merit_evaluated",
        "affects_live_merit",
    ):
        if bool(policy.get(field)):
            raise ShadowInputError(
                "#18 result may not enable "
                + field
                + "."
            )

    state = result.get(
        "corroboration_state"
    )

    if not isinstance(state, Mapping):
        raise ShadowInputError(
            "#18 canonical corroboration state is required."
        )

    if (
        _clean(
            state.get("version")
        )
        != (
            corroboration_analysis
            .CLAIM_CORROBORATION_POLICY_VERSION
        )
    ):
        raise ShadowInputError(
            "Canonical corroboration state version is unsupported."
        )

    state_policy = state.get("policy")

    if not isinstance(
        state_policy,
        Mapping,
    ):
        raise ShadowInputError(
            "Canonical corroboration policy is required."
        )

    for field in (
        "corroboration_requires_explicit_support",
        "corroboration_requires_established_independent_support",
        "source_diversity_alone_does_not_establish_corroboration",
        "absence_of_dependency_does_not_establish_corroboration",
        "evidence_only_support_does_not_establish_corroboration",
        "contradiction_does_not_erase_recorded_support",
        "corroboration_does_not_establish_truth",
    ):
        if state_policy.get(field) is not True:
            raise ShadowInputError(
                "Canonical corroboration policy missing: "
                + field
            )

    claims = state.get("claims")

    if not isinstance(claims, list):
        raise ShadowInputError(
            "Canonical corroboration claims must be a list."
        )

    matches = [
        dict(row)
        for row in claims
        if (
            isinstance(row, Mapping)
            and _clean(
                row.get("claim_id")
            )
            == claim_id
        )
    ]

    if len(matches) != 1:
        raise ShadowInputError(
            "#18 must contain exactly one canonical row "
            "for its claim."
        )

    row = matches[0]

    status = _key(
        row.get("status")
    )

    established = bool(
        row.get(
            "corroboration_established"
        )
    )

    independent = bool(
        row.get(
            "independent_support_established"
        )
    )

    contested = bool(
        row.get("contested")
    )

    contradiction_present = bool(
        row.get(
            "contradiction_present"
        )
    )

    if (
        established
        != (
            status
            == "corroboration_established"
        )
    ):
        raise ShadowIntegrityError(
            "Canonical corroboration status and "
            "established flag disagree."
        )

    if established and not independent:
        raise ShadowIntegrityError(
            "Canonical corroboration cannot be established "
            "without independent support."
        )

    if (
        contested
        != contradiction_present
    ):
        raise ShadowIntegrityError(
            "Canonical contested and contradiction flags disagree."
        )

    if (
        bool(
            result.get(
                "corroboration_established"
            )
        )
        != established
    ):
        raise ShadowIntegrityError(
            "#18 top-level corroboration flag does not match "
            "its canonical claim row."
        )

    if (
        bool(
            result.get(
                "independent_support_established"
            )
        )
        != independent
    ):
        raise ShadowIntegrityError(
            "#18 top-level independence flag does not match "
            "its canonical claim row."
        )

    if (
        bool(
            result.get("contested")
        )
        != contested
    ):
        raise ShadowIntegrityError(
            "#18 top-level contested flag does not match "
            "its canonical claim row."
        )

    scoped_state = copy.deepcopy(
        dict(state)
    )

    scoped_state["claims"] = [
        copy.deepcopy(row)
    ]

    result["claim_id"] = claim_id
    result["corroboration_state"] = (
        scoped_state
    )
    result["_canonical_claim_row"] = (
        copy.deepcopy(row)
    )

    return result


def _validate_overlay(
    *,
    overlay: Mapping[str, Any],
    legacy_score: Mapping[str, Any],
    canonical_row: Mapping[str, Any],
) -> Dict[str, Any]:
    if not isinstance(overlay, Mapping):
        raise ShadowIntegrityError(
            "Merit overlay must be a mapping."
        )

    normalized = copy.deepcopy(
        dict(overlay)
    )

    if (
        _clean(
            normalized.get("version")
        )
        != (
            merit_analysis
            .MERIT_CORROBORATION_OVERLAY_VERSION
        )
    ):
        raise ShadowIntegrityError(
            "Merit shadow overlay version mismatch."
        )

    if _key(
        normalized.get("mode")
    ) != "shadow":
        raise ShadowIntegrityError(
            "Merit overlay escaped shadow mode."
        )

    claim_id = _clean(
        canonical_row.get("claim_id")
    )

    if (
        not claim_id
        or _clean(
            normalized.get("claim_id")
        )
        != claim_id
    ):
        raise ShadowIntegrityError(
            "Merit overlay claim scope changed."
        )

    legacy = normalized.get("legacy")
    live = normalized.get("live")

    if (
        not isinstance(legacy, Mapping)
        or not isinstance(live, Mapping)
    ):
        raise ShadowIntegrityError(
            "Merit overlay legacy/live state is malformed."
        )

    legacy_total = _finite_number(
        legacy_score.get("total"),
        label="Legacy Merit total",
    )

    if (
        _finite_number(
            legacy.get("total"),
            label="Overlay legacy total",
        )
        != legacy_total
    ):
        raise ShadowIntegrityError(
            "Merit shadow overlay changed the legacy score."
        )

    if (
        live.get("score_effect_enabled")
        is not False
        or _finite_number(
            live.get("total"),
            label="Overlay live total",
        )
        != legacy_total
    ):
        raise ShadowIntegrityError(
            "Merit shadow overlay changed or enabled the live score."
        )

    policy = normalized.get("policy")

    if not isinstance(policy, Mapping):
        raise ShadowIntegrityError(
            "Merit overlay policy is required."
        )

    required_policy = (
        "verified_corroboration_is_required_for_positive_effect",
        "verified_independence_is_required",
        "distinct_source_count_is_not_weighted",
        "additional_sources_do_not_increase_adjustment",
        "contested_corroboration_does_not_receive_boost",
        "absence_of_corroboration_does_not_reduce_score",
        "dependency_does_not_create_negative_score",
        "overlay_does_not_establish_truth",
        "legacy_corroboration_component_is_not_replaced_yet",
        "live_merit_effect_is_disabled",
        "machine_score_release_certificate_is_required_before_enablement",
    )

    for field in required_policy:
        if policy.get(field) is not True:
            raise ShadowIntegrityError(
                "Merit shadow overlay policy contract is incomplete: "
                + field
            )

    proposed = normalized.get("proposed")

    if not isinstance(proposed, Mapping):
        raise ShadowIntegrityError(
            "Merit shadow proposal is required."
        )

    adjustment = _finite_number(
        proposed.get("adjustment"),
        label="Shadow proposed adjustment",
    )

    max_boost = (
        merit_analysis
        .MERIT_CORROBORATION_SHADOW_MAX_BOOST
    )

    if (
        _finite_number(
            proposed.get("max_adjustment"),
            label="Shadow max adjustment",
        )
        != float(max_boost)
    ):
        raise ShadowIntegrityError(
            "Merit shadow overlay changed the locked boost cap."
        )

    if adjustment not in {
        0.0,
        float(max_boost),
    }:
        raise ShadowIntegrityError(
            "Claim-scoped shadow adjustment must be 0 or the "
            "locked maximum boost."
        )

    expected_qualifies = bool(
        canonical_row.get(
            "corroboration_established"
        )
        and canonical_row.get(
            "independent_support_established"
        )
        and not canonical_row.get(
            "contested"
        )
    )

    expected_adjustment = (
        float(max_boost)
        if expected_qualifies
        else 0.0
    )

    if adjustment != expected_adjustment:
        raise ShadowIntegrityError(
            "Shadow adjustment does not match canonical "
            "corroboration state."
        )

    proposed_total = _finite_number(
        proposed.get("shadow_total"),
        label="Shadow proposed total",
    )

    expected_total = round(
        min(
            100.0,
            legacy_total
            + expected_adjustment,
        ),
        2,
    )

    if (
        round(
            proposed_total,
            2,
        )
        != expected_total
    ):
        raise ShadowIntegrityError(
            "Shadow proposed total does not match "
            "the locked overlay calculation."
        )

    return normalized


def evaluate_multimodal_live_merit_shadow(
    *,
    corroboration_result: Mapping[str, Any],
    legacy_score: Mapping[str, Any],
) -> Dict[str, Any]:
    """Evaluate #18 corroboration through the locked Merit overlay.

    This runtime is observational only. It does not consume a release
    certificate, call the live release service, persist state, or alter
    the supplied legacy score.
    """

    original_corroboration = copy.deepcopy(
        corroboration_result
    )
    original_legacy = copy.deepcopy(
        legacy_score
    )

    score = _require_legacy_score(
        legacy_score
    )

    corroboration = (
        _require_corroboration_result(
            corroboration_result
        )
    )

    overlay = (
        merit_analysis
        .build_merit_corroboration_overlay(
            corroboration_state=(
                corroboration[
                    "corroboration_state"
                ]
            ),
            legacy_score=score,
            claim_id=(
                corroboration[
                    "claim_id"
                ]
            ),
        )
    )

    validated_overlay = (
        _validate_overlay(
            overlay=overlay,
            legacy_score=score,
            canonical_row=(
                corroboration[
                    "_canonical_claim_row"
                ]
            ),
        )
    )

    if (
        corroboration_result
        != original_corroboration
        or legacy_score
        != original_legacy
    ):
        raise ShadowIntegrityError(
            "Shadow evaluation mutated caller input."
        )

    proposed = validated_overlay[
        "proposed"
    ]

    adjustment = float(
        proposed[
            "adjustment"
        ]
    )

    return {
        "version": (
            MULTIMODAL_LIVE_MERIT_SHADOW_VERSION
        ),
        "status": "evaluated_shadow",
        "claim_id": (
            corroboration[
                "claim_id"
            ]
        ),
        "corroboration_runtime_version": (
            multimodal_corroboration_runtime
            .MULTIMODAL_CORROBORATION_RUNTIME_VERSION
        ),
        "overlay_version": (
            merit_analysis
            .MERIT_CORROBORATION_OVERLAY_VERSION
        ),
        "legacy_score": copy.deepcopy(
            score
        ),
        "live_score": copy.deepcopy(
            score
        ),
        "shadow": copy.deepcopy(
            proposed
        ),
        "proposed_adjustment": (
            adjustment
        ),
        "proposed_shadow_total": (
            proposed[
                "shadow_total"
            ]
        ),
        "shadow_boost_eligible_under_overlay": (
            adjustment
            == (
                merit_analysis
                .MERIT_CORROBORATION_SHADOW_MAX_BOOST
            )
        ),
        "overlay": (
            validated_overlay
        ),
        "policy": {
            "shadow_only": True,
            "existing_merit_overlay_used": True,
            "claim_scoped_evaluation": True,
            "no_live_release_invocation": True,
            "no_certificate_consumption": True,
            "live_enablement_authorized": False,
            "score_effect_applied": False,
            "legacy_score_unchanged": True,
            "multimodal_evidence_status_unchanged": True,
            "truth_not_established_by_shadow_score": True,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }
