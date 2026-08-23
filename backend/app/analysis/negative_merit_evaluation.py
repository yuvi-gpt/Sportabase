from typing import (
    Any,
    Dict,
    List,
)


from app.analysis.negative_merit import (
    NEGATIVE_MERIT_SHADOW_VERSION,
    build_negative_merit_shadow,
)


NEGATIVE_MERIT_EVALUATION_VERSION = (
    "negative-merit-evaluation-v1"
)

NEGATIVE_MERIT_EVALUATION_CASE_VERSION = (
    "negative-merit-evaluation-case-v1"
)

NEGATIVE_MERIT_EVALUATION_ORIGIN = (
    "synthetic_policy_fixture"
)

NEGATIVE_MERIT_EVALUATION_CONTROL_CLASSES = {
    "two_gate_candidate",
    "authority_only_control",
    "semantic_only_control",
    "no_negative_evidence_control",
    "exclusive_no_corroboration_control",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _number(
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

    return result


def _boolean(
    value: Any,
    *,
    label: str,
) -> bool:
    if not isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{label} must be boolean."
        )

    return value


def _same_number(
    left: Any,
    right: Any,
) -> bool:
    return (
        abs(
            _number(
                left,
                label="Observed numeric value",
            )
            - _number(
                right,
                label="Expected numeric value",
            )
        )
        <= 1e-9
    )


def _expectations(
    value: Any,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Negative Merit evaluation "
            "expectations must be a dictionary."
        )

    required = {
        "signal",
        "severity_class",
        "calibration_eligible",
        "adjustment",
        "live_total",
        "shadow_total",
        "authority_gate",
        "semantic_gate",
    }

    missing = sorted(
        required
        - set(
            value.keys()
        )
    )

    if missing:
        raise ValueError(
            "Negative Merit evaluation "
            "expectations are missing fields: "
            + ", ".join(
                missing
            )
        )

    _boolean(
        value.get(
            "calibration_eligible"
        ),
        label=(
            "Expected calibration eligibility"
        ),
    )

    _boolean(
        value.get(
            "authority_gate"
        ),
        label=(
            "Expected authority gate"
        ),
    )

    _boolean(
        value.get(
            "semantic_gate"
        ),
        label=(
            "Expected semantic gate"
        ),
    )

    return value


def evaluate_negative_merit_cases(
    *,
    cases: List[
        Dict[str, Any]
    ],
    shadow_builder=(
        build_negative_merit_shadow
    ),
) -> Dict[str, Any]:
    if not isinstance(
        cases,
        list,
    ):
        raise ValueError(
            "Negative Merit evaluation "
            "cases must be a list."
        )

    if not cases:
        raise ValueError(
            "Negative Merit evaluation "
            "requires at least one case."
        )

    seen_case_ids = set()
    results = []

    metrics = {
        "cases": 0,
        "expectations_passed": 0,
        "expectations_failed": 0,
        "safety_violations": 0,
        "two_gate_candidates": 0,
        "calibration_candidates": 0,
        "live_score_changes": 0,
        "numeric_adjustments_before_calibration": 0,
        "false_positive_calibration_candidates": 0,
        "claim_truth_boundary_violations": 0,
    }

    for raw_case in cases:
        if not isinstance(
            raw_case,
            dict,
        ):
            raise ValueError(
                "Each Negative Merit evaluation "
                "case must be a dictionary."
            )

        if (
            _clean(
                raw_case.get(
                    "version"
                )
            )
            != (
                NEGATIVE_MERIT_EVALUATION_CASE_VERSION
            )
        ):
            raise ValueError(
                "Unsupported Negative Merit "
                "evaluation case version."
            )

        if (
            _key(
                raw_case.get(
                    "origin"
                )
            )
            != (
                NEGATIVE_MERIT_EVALUATION_ORIGIN
            )
        ):
            raise ValueError(
                "Negative Merit policy evaluation "
                "accepts synthetic policy fixtures "
                "only. Real-world calibration must "
                "use a separate release path."
            )

        case_id = _clean(
            raw_case.get(
                "id"
            )
        )

        claim_id = _clean(
            raw_case.get(
                "claim_id"
            )
        )

        control_class = _key(
            raw_case.get(
                "control_class"
            )
        )

        if not case_id:
            raise ValueError(
                "Negative Merit evaluation "
                "case ID is required."
            )

        if case_id in seen_case_ids:
            raise ValueError(
                "Negative Merit evaluation "
                "case IDs must be unique."
            )

        seen_case_ids.add(
            case_id
        )

        if not claim_id:
            raise ValueError(
                "Negative Merit evaluation "
                "claim ID is required."
            )

        if (
            control_class
            not in (
                NEGATIVE_MERIT_EVALUATION_CONTROL_CLASSES
            )
        ):
            raise ValueError(
                "Unsupported Negative Merit "
                "evaluation control class."
            )

        legacy_score = raw_case.get(
            "legacy_score"
        )

        if not isinstance(
            legacy_score,
            dict,
        ):
            raise ValueError(
                "Negative Merit evaluation "
                "legacy score must be a dictionary."
            )

        expected = _expectations(
            raw_case.get(
                "expectations"
            )
        )

        shadow = shadow_builder(
            legacy_score=(
                legacy_score
            ),
            claim_id=(
                claim_id
            ),
            contradiction_verification=(
                raw_case.get(
                    "contradiction_verification"
                )
            ),
            semantic_verification=(
                raw_case.get(
                    "semantic_verification"
                )
            ),
        )

        if not isinstance(
            shadow,
            dict,
        ):
            raise ValueError(
                "Negative Merit shadow builder "
                "must return a dictionary."
            )

        if (
            _clean(
                shadow.get(
                    "version"
                )
            )
            != (
                NEGATIVE_MERIT_SHADOW_VERSION
            )
        ):
            raise ValueError(
                "Negative Merit evaluation "
                "received an unsupported shadow."
            )

        proposed = shadow.get(
            "proposed"
        )

        live = shadow.get(
            "live"
        )

        gates = shadow.get(
            "evidence_gates"
        )

        if (
            not isinstance(
                proposed,
                dict,
            )
            or not isinstance(
                live,
                dict,
            )
            or not isinstance(
                gates,
                dict,
            )
        ):
            raise ValueError(
                "Negative Merit shadow is "
                "missing score or gate sections."
            )

        legacy_total = _number(
            legacy_score.get(
                "total"
            ),
            label=(
                "Legacy Merit total"
            ),
        )

        adjustment = _number(
            proposed.get(
                "adjustment"
            ),
            label=(
                "Negative Merit adjustment"
            ),
        )

        shadow_total = _number(
            proposed.get(
                "shadow_total"
            ),
            label=(
                "Negative Merit shadow total"
            ),
        )

        live_total = _number(
            live.get(
                "total"
            ),
            label=(
                "Negative Merit live total"
            ),
        )

        calibration_eligible = (
            _boolean(
                proposed.get(
                    "eligible_for_penalty_calibration"
                ),
                label=(
                    "Negative Merit calibration eligibility"
                ),
            )
        )

        live_effect_enabled = (
            _boolean(
                live.get(
                    "score_effect_enabled"
                ),
                label=(
                    "Negative Merit live effect state"
                ),
            )
        )

        authority_gate = (
            _boolean(
                gates.get(
                    "direct_authority_contradiction_lineage"
                ),
                label=(
                    "Negative Merit authority gate"
                ),
            )
        )

        semantic_gate = (
            _boolean(
                gates.get(
                    "machine_verified_contradiction_semantics"
                ),
                label=(
                    "Negative Merit semantic gate"
                ),
            )
        )

        both_required = (
            _boolean(
                gates.get(
                    "both_required"
                ),
                label=(
                    "Negative Merit two-gate policy"
                ),
            )
        )

        claim_truth_established = (
            _boolean(
                gates.get(
                    "claim_truth_established"
                ),
                label=(
                    "Negative Merit claim-truth boundary"
                ),
            )
        )

        signal = _clean(
            shadow.get(
                "signal"
            )
        )

        severity_class = _clean(
            shadow.get(
                "severity_class"
            )
        )

        checks = {
            "signal": (
                signal
                == _clean(
                    expected.get(
                        "signal"
                    )
                )
            ),
            "severity_class": (
                severity_class
                == _clean(
                    expected.get(
                        "severity_class"
                    )
                )
            ),
            "calibration_eligible": (
                calibration_eligible
                is expected.get(
                    "calibration_eligible"
                )
            ),
            "adjustment": (
                _same_number(
                    adjustment,
                    expected.get(
                        "adjustment"
                    ),
                )
            ),
            "live_total": (
                _same_number(
                    live_total,
                    expected.get(
                        "live_total"
                    ),
                )
            ),
            "shadow_total": (
                _same_number(
                    shadow_total,
                    expected.get(
                        "shadow_total"
                    ),
                )
            ),
            "authority_gate": (
                authority_gate
                is expected.get(
                    "authority_gate"
                )
            ),
            "semantic_gate": (
                semantic_gate
                is expected.get(
                    "semantic_gate"
                )
            ),
        }

        safety = []

        if not _same_number(
            live_total,
            legacy_total,
        ):
            safety.append(
                "live_score_changed"
            )

            metrics[
                "live_score_changes"
            ] += 1

        if live_effect_enabled:
            safety.append(
                "live_negative_merit_enabled"
            )

        if abs(
            adjustment
        ) > 1e-9:
            safety.append(
                "numeric_adjustment_before_calibration"
            )

            metrics[
                "numeric_adjustments_before_calibration"
            ] += 1

        if not _same_number(
            shadow_total,
            legacy_total,
        ):
            safety.append(
                "shadow_total_changed_before_calibration"
            )

        if not both_required:
            safety.append(
                "two_gate_requirement_disabled"
            )

        if claim_truth_established:
            safety.append(
                "claim_truth_boundary_violated"
            )

            metrics[
                "claim_truth_boundary_violations"
            ] += 1

        both_gates = bool(
            authority_gate
            and semantic_gate
        )

        if (
            calibration_eligible
            and not both_gates
        ):
            safety.append(
                "calibration_eligible_without_both_gates"
            )

            metrics[
                "false_positive_calibration_candidates"
            ] += 1

        if (
            control_class
            != "two_gate_candidate"
            and calibration_eligible
        ):
            safety.append(
                "negative_control_became_calibration_eligible"
            )

            metrics[
                "false_positive_calibration_candidates"
            ] += 1

        if (
            control_class
            == "two_gate_candidate"
        ):
            metrics[
                "two_gate_candidates"
            ] += 1

        if calibration_eligible:
            metrics[
                "calibration_candidates"
            ] += 1

        expectations_passed = all(
            checks.values()
        )

        if expectations_passed:
            metrics[
                "expectations_passed"
            ] += 1

        else:
            metrics[
                "expectations_failed"
            ] += 1

        metrics[
            "safety_violations"
        ] += len(
            safety
        )

        metrics[
            "cases"
        ] += 1

        results.append(
            {
                "case_id": (
                    case_id
                ),
                "claim_id": (
                    claim_id
                ),
                "control_class": (
                    control_class
                ),
                "expectations_passed": (
                    expectations_passed
                ),
                "checks": (
                    checks
                ),
                "safety_violations": (
                    safety
                ),
                "observed": {
                    "signal": (
                        signal
                    ),
                    "severity_class": (
                        severity_class
                    ),
                    "calibration_eligible": (
                        calibration_eligible
                    ),
                    "adjustment": (
                        adjustment
                    ),
                    "live_total": (
                        live_total
                    ),
                    "shadow_total": (
                        shadow_total
                    ),
                    "authority_gate": (
                        authority_gate
                    ),
                    "semantic_gate": (
                        semantic_gate
                    ),
                },
            }
        )

    passed = bool(
        metrics[
            "expectations_failed"
        ]
        == 0
        and metrics[
            "safety_violations"
        ]
        == 0
    )

    return {
        "version": (
            NEGATIVE_MERIT_EVALUATION_VERSION
        ),
        "status": (
            "passed"
            if passed
            else "failed"
        ),
        "metrics": (
            metrics
        ),
        "cases": (
            results
        ),
        "enablement": {
            "live_negative_merit_authorized": False,
            "numeric_penalty_authorized": False,
            "recommendation": (
                "real_world_negative_calibration_"
                "certificate_required"
            ),
            "reason": (
                "Synthetic policy fixtures can "
                "validate the two-gate safety "
                "boundary but cannot calibrate "
                "or authorize a live negative "
                "Merit weight."
            ),
        },
        "policy": {
            "synthetic_cases_are_not_real_world_validation": True,
            "two_verified_gates_required_for_candidate_status": True,
            "single_gate_controls_must_not_become_candidates": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "exclusive_reporting_is_not_negative_evidence": True,
            "model_only_contradiction_is_not_negative_evidence": True,
            "numeric_negative_adjustments_are_forbidden_during_policy_evaluation": True,
            "claim_truth_is_not_established_by_semantic_contradiction": True,
            "evaluation_does_not_enable_live_scoring": True,
            "real_world_calibration_is_required_before_weight_selection": True,
        },
    }
