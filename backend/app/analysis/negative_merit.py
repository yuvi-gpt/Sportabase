import json

from typing import Any, Dict

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE,
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)


NEGATIVE_MERIT_SHADOW_VERSION = (
    "negative-merit-shadow-v1"
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
            str(value or "{}")
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


def build_negative_merit_shadow(
    *,
    legacy_score: Dict[str, Any],
    claim_id: str,
    contradiction_verification: (
        Dict[str, Any] | None
    ),
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

    verification = (
        contradiction_verification
        if isinstance(
            contradiction_verification,
            dict,
        )
        else {}
    )

    evidence = verification.get(
        "evidence"
    )

    qualifies = False

    if (
        verification.get(
            "version"
        )
        == DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
        and verification.get(
            "status"
        )
        == (
            "persisted_verified_direct_stakeholder_"
            "contradiction_lineage"
        )
        and verification.get(
            "persisted"
        )
        is True
        and isinstance(
            evidence,
            dict,
        )
    ):
        metadata = _metadata(
            evidence.get(
                "metadata_json"
            )
        )

        qualifies = (
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
                + normalized_claim_id
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

    if qualifies:
        signal = (
            "verified_authority_"
            "contradiction_recorded"
        )
        severity_class = (
            "strong_negative_evidence_candidate"
        )
        calibration_eligible = True
        reason = (
            "A persisted contradiction is tied "
            "to a machine-verified direct "
            "stakeholder. This is eligible for "
            "negative-Merit calibration but does "
            "not yet authorize a live penalty."
        )

    else:
        signal = (
            "no_certified_negative_evidence"
        )
        severity_class = "none"
        calibration_eligible = False
        reason = (
            "No qualifying machine-verified "
            "direct-stakeholder contradiction "
            "lineage is available."
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
        "legacy": {
            "total": legacy_total,
        },
        "proposed": {
            "adjustment": 0.0,
            "shadow_total": (
                legacy_total
            ),
            "eligible_for_penalty_calibration": (
                calibration_eligible
            ),
        },
        "live": {
            "score_effect_enabled": False,
            "total": legacy_total,
        },
        "policy": {
            "absence_of_corroboration_is_not_negative_evidence": True,
            "single_source_exclusive_is_not_penalized": True,
            "publisher_or_aggregator_contradiction_is_not_certified_here": True,
            "model_only_contradiction_never_changes_merit": True,
            "verified_direct_authority_lineage_is_required": True,
            "recorded_contradiction_is_not_permanent_truth": True,
            "numeric_negative_weight_requires_calibration": True,
            "live_negative_merit_is_disabled": True,
        },
    }
