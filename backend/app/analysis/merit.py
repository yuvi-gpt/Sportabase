from typing import Any, Dict

from app.analysis.corroboration import (
    CLAIM_CORROBORATION_POLICY_VERSION,
)


MERIT_CORROBORATION_OVERLAY_VERSION = (
    "merit-corroboration-overlay-v2"
)

MERIT_CORROBORATION_SHADOW_MAX_BOOST = 6.0


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _score_value(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{label} must be numeric."
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
            f"{label} must be numeric."
        ) from exc

    if not 0.0 <= result <= 100.0:
        raise ValueError(
            f"{label} must be between "
            "0 and 100."
        )

    return result


def _claim_rows(
    corroboration_state: Dict[str, Any],
    claim_id: str,
):
    claims = corroboration_state.get(
        "claims",
        [],
    )

    if not isinstance(
        claims,
        list,
    ):
        raise ValueError(
            "Merit corroboration state "
            "claims must be a list."
        )

    return [
        row
        for row in claims
        if (
            isinstance(
                row,
                dict,
            )
            and _clean(
                row.get(
                    "claim_id"
                )
            )
            == claim_id
        )
    ]


def build_merit_corroboration_overlay(
    *,
    legacy_score: Dict[str, Any],
    corroboration_state: Dict[str, Any],
    claim_id: str,
) -> Dict[str, Any]:
    if not isinstance(
        legacy_score,
        dict,
    ):
        raise ValueError(
            "Legacy Merit score must "
            "be a dictionary."
        )

    if not isinstance(
        corroboration_state,
        dict,
    ):
        raise ValueError(
            "Merit corroboration state "
            "must be a dictionary."
        )

    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Merit corroboration claim "
            "ID is required."
        )

    if (
        _clean(
            corroboration_state.get(
                "version"
            )
        )
        != CLAIM_CORROBORATION_POLICY_VERSION
    ):
        raise ValueError(
            "Unsupported claim "
            "corroboration version."
        )

    legacy_total = _score_value(
        legacy_score.get(
            "total"
        ),
        label=(
            "Legacy Merit total"
        ),
    )

    components = legacy_score.get(
        "components",
        {},
    )

    if not isinstance(
        components,
        dict,
    ):
        raise ValueError(
            "Legacy Merit components "
            "must be a dictionary."
        )

    legacy_corroboration_component = (
        components.get(
            "corroboration"
        )
    )

    if (
        legacy_corroboration_component
        is not None
    ):
        legacy_corroboration_component = (
            _score_value(
                legacy_corroboration_component,
                label=(
                    "Legacy corroboration "
                    "component"
                ),
            )
        )

    rows = _claim_rows(
        corroboration_state,
        normalized_claim_id,
    )

    if len(rows) != 1:
        raise ValueError(
            "Merit corroboration overlay "
            "requires exactly one target "
            "claim result."
        )

    claim = rows[0]

    status = _clean(
        claim.get(
            "status"
        )
    ).lower()

    corroboration_established = bool(
        claim.get(
            "corroboration_established",
            False,
        )
    )

    contested = bool(
        claim.get(
            "contested",
            False,
        )
    )

    contradiction_present = bool(
        claim.get(
            "contradiction_present",
            False,
        )
    )

    independent_support_established = bool(
        claim.get(
            "independent_support_established",
            False,
        )
    )

    if (
        corroboration_established
        != (
            status
            == "corroboration_established"
        )
    ):
        raise ValueError(
            "Corroboration status and "
            "established flag disagree."
        )

    if (
        contested
        != contradiction_present
    ):
        raise ValueError(
            "Corroboration contested and "
            "contradiction flags disagree."
        )

    if (
        corroboration_established
        and not independent_support_established
    ):
        raise ValueError(
            "Established corroboration "
            "requires established independent "
            "support."
        )

    supporting_source_ids = sorted(
        {
            _clean(
                value
            )
            for value in claim.get(
                "supporting_source_ids",
                [],
            )
            if _clean(
                value
            )
        }
    )

    if (
        corroboration_established
        and not contested
    ):
        signal = (
            "verified_corroboration"
        )

        proposed_adjustment = (
            MERIT_CORROBORATION_SHADOW_MAX_BOOST
        )

        reason = (
            "Verified independent support "
            "establishes uncontested "
            "corroboration."
        )

    elif (
        corroboration_established
        and contested
    ):
        signal = (
            "verified_corroboration_contested"
        )

        proposed_adjustment = 0.0

        reason = (
            "Corroboration is established "
            "but explicit contradiction is "
            "also recorded, so no Merit "
            "boost is proposed."
        )

    elif status == (
        "recorded_support_dependency_present"
    ):
        signal = (
            "support_dependency_present"
        )

        proposed_adjustment = 0.0

        reason = (
            "Recorded support dependency "
            "prevents a corroboration boost."
        )

    elif status == (
        "support_independence_unknown"
    ):
        signal = (
            "support_independence_unknown"
        )

        proposed_adjustment = 0.0

        reason = (
            "Multiple supporting sources "
            "without verified independence "
            "do not earn a Merit boost."
        )

    else:
        signal = (
            "no_verified_corroboration_boost"
        )

        proposed_adjustment = 0.0

        reason = (
            "No qualifying uncontested "
            "verified corroboration is "
            "available for a Merit boost."
        )

    proposed_adjustment = min(
        max(
            float(
                proposed_adjustment
            ),
            0.0,
        ),
        MERIT_CORROBORATION_SHADOW_MAX_BOOST,
    )

    shadow_total = min(
        100.0,
        legacy_total
        + proposed_adjustment,
    )

    live_total = legacy_total

    return {
        "version": (
            MERIT_CORROBORATION_OVERLAY_VERSION
        ),
        "mode": "shadow",
        "claim_id": (
            normalized_claim_id
        ),
        "signal": (
            signal
        ),
        "reason": (
            reason
        ),
        "corroboration_status": (
            status
        ),
        "corroboration_established": (
            corroboration_established
        ),
        "contested": (
            contested
        ),
        "independent_support_established": (
            independent_support_established
        ),
        "supporting_source_ids": (
            supporting_source_ids
        ),
        "legacy": {
            "total": (
                legacy_total
            ),
            (
                "legacy_corroboration_"
                "component"
            ): (
                legacy_corroboration_component
            ),
        },
        "proposed": {
            "adjustment": (
                proposed_adjustment
            ),
            "max_adjustment": (
                MERIT_CORROBORATION_SHADOW_MAX_BOOST
            ),
            "shadow_total": (
                shadow_total
            ),
        },
        "live": {
            "score_effect_enabled": (
                False
            ),
            "total": (
                live_total
            ),
        },
        "policy": {
            (
                "verified_corroboration_is_"
                "required_for_positive_effect"
            ): True,
            (
                "verified_independence_is_"
                "required"
            ): True,
            (
                "distinct_source_count_is_"
                "not_weighted"
            ): True,
            (
                "additional_sources_do_not_"
                "increase_adjustment"
            ): True,
            (
                "contested_corroboration_"
                "does_not_receive_boost"
            ): True,
            (
                "absence_of_corroboration_"
                "does_not_reduce_score"
            ): True,
            (
                "dependency_does_not_create_"
                "negative_score"
            ): True,
            (
                "overlay_does_not_establish_"
                "truth"
            ): True,
            (
                "legacy_corroboration_component_"
                "is_not_replaced_yet"
            ): True,
            (
                "live_merit_effect_is_disabled"
            ): True,
            (
                "machine_score_release_certificate_is_"
                "required_before_enablement"
            ): True,
        },
    }
