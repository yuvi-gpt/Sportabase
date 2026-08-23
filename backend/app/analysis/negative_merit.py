import json

from typing import Any, Dict

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE,
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
)


NEGATIVE_MERIT_SHADOW_VERSION = (
    "negative-merit-shadow-v2"
)


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _score(value: Any) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Legacy Merit total must be numeric."
        )

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Legacy Merit total must be numeric."
        ) from exc

    if not (
        0.0
        <= result
        <= 100.0
    ):
        raise ValueError(
            "Legacy Merit total must be "
            "between 0 and 100."
        )

    return result


def _metadata(
    value: Any,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(
                value or "{}"
            )
        )

    except Exception:
        return {}

    return (
        parsed
        if isinstance(
            parsed,
            dict,
        )
        else {}
    )


def _authority_gate(
    *,
    claim_id: str,
    verification: Dict[str, Any] | None,
) -> bool:
    result = (
        verification
        if isinstance(
            verification,
            dict,
        )
        else {}
    )

    evidence = result.get(
        "evidence"
    )

    if (
        result.get(
            "version"
        )
        != DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
        or result.get(
            "status"
        )
        != (
            "persisted_verified_direct_stakeholder_"
            "contradiction_lineage"
        )
        or result.get(
            "persisted"
        )
        is not True
        or not isinstance(
            evidence,
            dict,
        )
    ):
        return False

    metadata = _metadata(
        evidence.get(
            "metadata_json"
        )
    )

    return bool(
        _key(
            evidence.get(
                "evidence_type"
            )
        )
        == (
            DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE
        )
        and _key(
            evidence.get(
                "verification_status"
            )
        )
        == "verified"
        and _clean(
            evidence.get(
                "subject_key"
            )
        )
        == (
            "merit-negative-evidence|"
            + claim_id
        )
        and metadata.get(
            "verifier_version"
        )
        == (
            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
        )
        and metadata.get(
            "machine_verified_authority"
        )
        is True
        and metadata.get(
            "recorded_contradiction_relationship"
        )
        is True
        and metadata.get(
            "contradiction_semantics_verified"
        )
        is False
        and metadata.get(
            "claim_truth_established"
        )
        is False
        and metadata.get(
            "live_merit_changed"
        )
        is False
    )


def _semantic_gate(
    *,
    claim_id: str,
    verification: Dict[str, Any] | None,
) -> bool:
    result = (
        verification
        if isinstance(
            verification,
            dict,
        )
        else {}
    )

    evidence = result.get(
        "evidence"
    )

    if (
        result.get(
            "version"
        )
        != (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        )
        or result.get(
            "status"
        )
        != (
            "persisted_verified_machine_"
            "contradiction_semantics"
        )
        or result.get(
            "persisted"
        )
        is not True
        or not isinstance(
            evidence,
            dict,
        )
    ):
        return False

    metadata = _metadata(
        evidence.get(
            "metadata_json"
        )
    )

    return bool(
        _key(
            evidence.get(
                "evidence_type"
            )
        )
        == (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE
        )
        and _key(
            evidence.get(
                "verification_status"
            )
        )
        == "verified"
        and _clean(
            evidence.get(
                "subject_key"
            )
        )
        == (
            "merit-negative-semantic-evidence|"
            + claim_id
        )
        and metadata.get(
            "verifier_version"
        )
        == (
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
        )
        and _clean(
            metadata.get(
                "claim_id"
            )
        )
        == claim_id
        and _key(
            metadata.get(
                "stance"
            )
        )
        == "contradicts"
        and metadata.get(
            "contradiction_semantics_verified"
        )
        is True
        and metadata.get(
            "contradiction_semantics_are_source_semantics"
        )
        is True
        and metadata.get(
            "claim_truth_established"
        )
        is False
        and metadata.get(
            "live_merit_changed"
        )
        is False
    )


def build_negative_merit_shadow(
    *,
    legacy_score: Dict[str, Any],
    claim_id: str,
    contradiction_verification: (
        Dict[str, Any] | None
    ),
    semantic_verification: (
        Dict[str, Any] | None
    ) = None,
) -> Dict[str, Any]:
    if not isinstance(
        legacy_score,
        dict,
    ):
        raise ValueError(
            "Negative Merit shadow requires "
            "a legacy score."
        )

    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Negative Merit shadow claim ID "
            "is required."
        )

    legacy_total = _score(
        legacy_score.get(
            "total"
        )
    )

    authority_verified = (
        _authority_gate(
            claim_id=(
                normalized_claim_id
            ),
            verification=(
                contradiction_verification
            ),
        )
    )

    semantics_verified = (
        _semantic_gate(
            claim_id=(
                normalized_claim_id
            ),
            verification=(
                semantic_verification
            ),
        )
    )

    calibration_eligible = bool(
        authority_verified
        and semantics_verified
    )

    if calibration_eligible:
        signal = (
            "verified_authority_machine_"
            "semantic_contradiction"
        )

        severity_class = (
            "two_gate_negative_evidence_candidate"
        )

        reason = (
            "A persisted contradiction is tied "
            "to machine-verified direct authority "
            "and the claim also has persisted "
            "machine-verified contradiction "
            "semantics. This qualifies for "
            "negative-Merit calibration only; "
            "it does not establish objective "
            "claim falsity or authorize a live "
            "score penalty."
        )

    elif authority_verified:
        signal = (
            "verified_authority_contradiction_"
            "semantics_unverified"
        )

        severity_class = (
            "authority_only_negative_evidence_candidate"
        )

        reason = (
            "Direct-authority contradiction "
            "lineage is verified, but the "
            "machine semantic contradiction "
            "gate has not been satisfied."
        )

    elif semantics_verified:
        signal = (
            "machine_semantic_contradiction_"
            "without_verified_direct_authority"
        )

        severity_class = (
            "semantic_only_negative_evidence_candidate"
        )

        reason = (
            "Machine-verified contradiction "
            "semantics exist, but verified "
            "direct-authority contradiction "
            "lineage is unavailable."
        )

    else:
        signal = (
            "no_certified_negative_evidence"
        )

        severity_class = "none"

        reason = (
            "The two required negative-evidence "
            "gates are not both satisfied."
        )

    return {
        "version": (
            NEGATIVE_MERIT_SHADOW_VERSION
        ),
        "mode": "shadow",
        "claim_id": (
            normalized_claim_id
        ),
        "signal": signal,
        "severity_class": (
            severity_class
        ),
        "reason": reason,
        "evidence_gates": {
            (
                "direct_authority_"
                "contradiction_lineage"
            ): (
                authority_verified
            ),
            (
                "machine_verified_"
                "contradiction_semantics"
            ): (
                semantics_verified
            ),
            "both_required": True,
            "claim_truth_established": False,
        },
        "legacy": {
            "total": legacy_total,
        },
        "proposed": {
            "adjustment": 0.0,
            "shadow_total": (
                legacy_total
            ),
            (
                "eligible_for_"
                "penalty_calibration"
            ): (
                calibration_eligible
            ),
        },
        "live": {
            "score_effect_enabled": False,
            "total": legacy_total,
        },
        "policy": {
            (
                "absence_of_corroboration_"
                "is_not_negative_evidence"
            ): True,
            (
                "single_source_exclusive_"
                "is_not_penalized"
            ): True,
            (
                "publisher_or_aggregator_"
                "contradiction_is_not_"
                "certified_here"
            ): True,
            (
                "model_only_contradiction_"
                "never_changes_merit"
            ): True,
            (
                "verified_direct_authority_"
                "lineage_is_required"
            ): True,
            (
                "machine_verified_"
                "contradiction_semantics_"
                "required_for_calibration"
            ): True,
            (
                "authority_lineage_alone_"
                "is_not_calibration_eligible"
            ): True,
            (
                "semantic_verification_alone_"
                "is_not_calibration_eligible"
            ): True,
            (
                "recorded_contradiction_"
                "is_not_permanent_truth"
            ): True,
            (
                "semantic_contradiction_"
                "is_not_objective_falsity"
            ): True,
            (
                "numeric_negative_weight_"
                "requires_calibration"
            ): True,
            (
                "live_negative_merit_"
                "is_disabled"
            ): True,
        },
    }
