from __future__ import annotations

import copy
import hashlib
import json

from typing import (
    Any,
    Dict,
)


NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION = (
    "negative-merit-score-release-certificate-v1"
)

NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_REPORT_VERSION = (
    "negative-merit-real-world-resolved-release-gate-v1"
)

NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_REPORT_DIGEST = (
    "abdec795c72cab03231322b4ad13dacdb2edfd44465d53a427a900e75840032f"
)

NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT = (
    -15.0
)

NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CASE_COUNT = (
    7
)

NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_RESOLVED_COUNT = (
    1
)

NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_TWO_GATE_COUNT = (
    3
)

NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CONTROL_COUNT = (
    3
)


_FORBIDDEN_HUMAN_KEYS = {
    "reviewer",
    "review_status",
    "reviewed_at",
    "human_review",
    "human_reviewer",
    "manual_approval",
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


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )


def _sha256(
    value: Any,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


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


def _assert_no_human_review_keys(
    value: Any,
    *,
    path: str = "root",
) -> None:
    if isinstance(
        value,
        dict,
    ):
        for key, nested in (
            value.items()
        ):
            if (
                _key(
                    key
                )
                in _FORBIDDEN_HUMAN_KEYS
            ):
                raise ValueError(
                    "Negative Merit release data "
                    "cannot contain human-review key "
                    f"{path}.{key}."
                )

            _assert_no_human_review_keys(
                nested,
                path=(
                    f"{path}.{key}"
                ),
            )

    elif isinstance(
        value,
        list,
    ):
        for index, nested in enumerate(
            value
        ):
            _assert_no_human_review_keys(
                nested,
                path=(
                    f"{path}[{index}]"
                ),
            )


def _validate_release_gate_report(
    report: Any,
) -> Dict[str, Any]:
    if not isinstance(
        report,
        dict,
    ):
        raise ValueError(
            "Negative Merit release-gate "
            "report must be a dictionary."
        )

    _assert_no_human_review_keys(
        report
    )

    if (
        _clean(
            report.get(
                "version"
            )
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_REPORT_VERSION
        )
    ):
        raise ValueError(
            "Unsupported Negative Merit "
            "release-gate report version."
        )

    report_digest = _key(
        report.get(
            "manifest_digest"
        )
    )

    core = {
        key: value
        for key, value
        in report.items()
        if key
        != "manifest_digest"
    }

    rebuilt_digest = _sha256(
        core
    )

    if (
        report_digest
        != rebuilt_digest
    ):
        raise ValueError(
            "Negative Merit release-gate "
            "manifest digest is invalid."
        )

    if (
        report_digest
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_REPORT_DIGEST
        )
    ):
        raise ValueError(
            "Negative Merit release-gate "
            "identity does not match the "
            "pinned calibration report."
        )

    dataset = report.get(
        "calibration_dataset"
    )

    if not isinstance(
        dataset,
        dict,
    ):
        raise ValueError(
            "Negative Merit calibration "
            "dataset is missing."
        )

    if (
        int(
            dataset.get(
                "case_count",
                -1,
            )
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CASE_COUNT
        )
    ):
        raise ValueError(
            "Negative Merit release requires "
            "the exact certified calibration "
            "case count."
        )

    calibration = dataset.get(
        "calibration"
    )

    if not isinstance(
        calibration,
        dict,
    ):
        raise ValueError(
            "Negative Merit calibration "
            "summary is missing."
        )

    if (
        calibration.get(
            "blockers"
        )
        != [
            "numeric_penalty_not_calibrated"
        ]
    ):
        raise ValueError(
            "Negative Merit release certificate "
            "may only clear the final numeric "
            "calibration blocker."
        )

    if (
        calibration.get(
            "canonical_outcome_labels_available"
        )
        is not True
        or calibration.get(
            "canonical_outcome_verifier_available"
        )
        is not True
        or calibration.get(
            "resolved_against_claim_case_count"
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_RESOLVED_COUNT
        )
        or calibration.get(
            "numeric_penalty_authorized"
        )
        is not False
        or calibration.get(
            "live_negative_merit_authorized"
        )
        is not False
        or calibration.get(
            "penalty_weight_selected"
        )
        is not False
    ):
        raise ValueError(
            "Negative Merit calibration "
            "pre-release state is invalid."
        )

    observations = dataset.get(
        "observations"
    )

    if not isinstance(
        observations,
        list,
    ):
        raise ValueError(
            "Negative Merit calibration "
            "observations are missing."
        )

    classes = [
        _key(
            row.get(
                "observation_class"
            )
        )
        for row
        in observations
        if isinstance(
            row,
            dict,
        )
    ]

    if (
        classes.count(
            "resolved_against_claim_observation"
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_RESOLVED_COUNT
        )
        or classes.count(
            "two_gate_observation"
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_TWO_GATE_COUNT
        )
        or classes.count(
            "no_negative_evidence_control"
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CONTROL_COUNT
        )
    ):
        raise ValueError(
            "Negative Merit calibration "
            "population contract changed."
        )

    penalty = report.get(
        "penalty_selection"
    )

    if not isinstance(
        penalty,
        dict,
    ):
        raise ValueError(
            "Negative Merit provisional "
            "penalty selection is missing."
        )

    adjustment = _number(
        penalty.get(
            "provisional_adjustment"
        ),
        label=(
            "Negative Merit provisional adjustment"
        ),
    )

    if (
        abs(
            adjustment
            - (
                NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT
            )
        )
        > 1e-9
        or _key(
            penalty.get(
                "status"
            )
        )
        != "provisional_penalty_selected"
        or penalty.get(
            "release_authorized"
        )
        is not False
        or penalty.get(
            "requires_separate_release_certificate"
        )
        is not True
        or int(
            penalty.get(
                "cap",
                -1,
            )
        )
        != 15
        or int(
            penalty.get(
                "floor",
                -1,
            )
        )
        != 5
        or _clean(
            penalty.get(
                "selection_rule"
            )
        )
        != (
            "negative_half_of_median_two_gate_"
            "control_separation_rounded_up_and_capped"
        )
    ):
        raise ValueError(
            "Negative Merit provisional "
            "penalty contract changed."
        )

    if (
        [int(value) for value in penalty.get(
            "two_gate_scores",
            [],
        )]
        != [
            34,
            35,
            46,
        ]
        or [int(value) for value in penalty.get(
            "control_scores",
            [],
        )]
        != [
            64,
            64,
            56,
        ]
        or float(
            penalty.get(
                "median_separation",
                -1,
            )
        )
        != 29.0
    ):
        raise ValueError(
            "Negative Merit measured score "
            "distribution changed."
        )

    resolved = report.get(
        "resolved_case"
    )

    if not isinstance(
        resolved,
        dict,
    ):
        raise ValueError(
            "Negative Merit resolved "
            "case is missing."
        )

    if (
        resolved.get(
            "calibration_eligible"
        )
        is not True
        or _key(
            resolved.get(
                "canonical_resolution_status"
            )
        )
        != (
            "persisted_verified_"
            "canonical_outcome_resolution"
        )
        or _key(
            resolved.get(
                "direct_contradiction_status"
            )
        )
        != (
            "persisted_verified_direct_"
            "stakeholder_contradiction_lineage"
        )
        or _key(
            resolved.get(
                "semantic_status"
            )
        )
        != (
            "persisted_verified_machine_"
            "contradiction_semantics"
        )
        or _key(
            resolved.get(
                "negative_merit_signal"
            )
        )
        != (
            "verified_authority_machine_"
            "semantic_contradiction"
        )
        or resolved.get(
            "claim_truth_established"
        )
        is not False
        or resolved.get(
            "live_merit_changed"
        )
        is not False
    ):
        raise ValueError(
            "Negative Merit resolved case "
            "verification lineage is invalid."
        )

    temporal = report.get(
        "temporal_false_positive_control"
    )

    if not isinstance(
        temporal,
        dict,
    ):
        raise ValueError(
            "Negative Merit temporal "
            "false-positive control is missing."
        )

    denial = temporal.get(
        "denial_comparison"
    )

    completion = temporal.get(
        "completion_comparison"
    )

    if (
        not isinstance(
            denial,
            dict,
        )
        or not isinstance(
            completion,
            dict,
        )
        or _key(
            denial.get(
                "direction"
            )
        )
        != "indeterminate"
        or _key(
            denial.get(
                "status"
            )
        )
        != "state_transition_not_decisive"
        or _key(
            completion.get(
                "direction"
            )
        )
        == "against_claim"
        or temporal.get(
            "penalty_authorized"
        )
        is not False
        or temporal.get(
            "claim_truth_established"
        )
        is not False
        or _clean(
            temporal.get(
                "safety_rule"
            )
        )
        != (
            "club_denial_does_not_make_"
            "agreement_claim_permanently_false"
        )
    ):
        raise ValueError(
            "Negative Merit temporal "
            "false-positive protection failed."
        )

    two_gate_cases = report.get(
        "two_gate_cases"
    )

    if (
        not isinstance(
            two_gate_cases,
            list,
        )
        or len(
            two_gate_cases
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_TWO_GATE_COUNT
        )
    ):
        raise ValueError(
            "Negative Merit two-gate "
            "real-world case population changed."
        )

    for row in two_gate_cases:
        if (
            not isinstance(
                row,
                dict,
            )
            or row.get(
                "calibration_eligible"
            )
            is not True
            or _key(
                row.get(
                    "negative_merit_signal"
                )
            )
            != (
                "verified_authority_machine_"
                "semantic_contradiction"
            )
            or row.get(
                "claim_truth_established"
            )
            is not False
            or row.get(
                "live_merit_changed"
            )
            is not False
        ):
            raise ValueError(
                "Negative Merit two-gate "
                "case contract is invalid."
            )

    controls = report.get(
        "controls"
    )

    if (
        not isinstance(
            controls,
            list,
        )
        or len(
            controls
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CONTROL_COUNT
        )
    ):
        raise ValueError(
            "Negative Merit no-evidence "
            "control population changed."
        )

    policy = report.get(
        "policy"
    )

    if not isinstance(
        policy,
        dict,
    ):
        raise ValueError(
            "Negative Merit release-gate "
            "policy is missing."
        )

    required_true = {
        "real_world_sources_only",
        "production_verifier_logic_used",
        "temporary_evaluation_database_only",
        "resolved_case_is_temporal_not_permanent_truth",
        "club_denial_alone_never_authorizes_negative_merit",
        "absence_of_corroboration_is_not_negative_evidence",
        "separate_release_certificate_still_required",
    }

    for field in required_true:
        if (
            policy.get(
                field
            )
            is not True
        ):
            raise ValueError(
                "Negative Merit release-gate "
                f"policy field {field} "
                "must be true."
            )

    required_false = {
        "production_database_written",
        "provider_call_performed",
        "claim_truth_established",
        "numeric_penalty_live",
        "live_negative_merit_authorized",
    }

    for field in required_false:
        if (
            policy.get(
                field
            )
            is not False
        ):
            raise ValueError(
                "Negative Merit release-gate "
                f"policy field {field} "
                "must be false."
            )

    return {
        "report_digest": (
            report_digest
        ),
        "case_count": (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CASE_COUNT
        ),
        "resolved_case_count": (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_RESOLVED_COUNT
        ),
        "two_gate_case_count": (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_TWO_GATE_COUNT
        ),
        "control_case_count": (
            NEGATIVE_MERIT_SCORE_RELEASE_REQUIRED_CONTROL_COUNT
        ),
        "temporal_false_positive_control_count": 1,
        "certified_adjustment": (
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT
        ),
    }


def build_negative_merit_score_release_certificate(
    *,
    release_gate_report: Dict[str, Any],
) -> Dict[str, Any]:
    validated = (
        _validate_release_gate_report(
            release_gate_report
        )
    )

    payload = {
        "version": (
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION
        ),
        "status": "authorized",
        "live_enablement_authorized": True,
        "blockers": [],
        "certified_adjustment": (
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT
        ),
        "release_gate": (
            validated
        ),
        "release_gate_report": copy.deepcopy(
            release_gate_report
        ),
        "policy": {
            "real_world_calibration_required": True,
            "resolved_outcome_required": True,
            "two_gate_negative_evidence_required": True,
            "temporal_false_positive_control_required": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "club_denial_alone_never_authorizes_negative_merit": True,
            "model_output_alone_never_authorizes_negative_merit": True,
            "claim_truth_is_not_established_by_release": True,
            "human_review_not_part_of_release_path": True,
            "certificate_does_not_itself_activate_live_negative_merit": True,
            "runtime_must_fail_closed": True,
            "runtime_must_preserve_positive_merit_composition": True,
            "runtime_must_clamp_score_to_zero_one_hundred": True,
        },
    }

    payload[
        "certificate_sha256"
    ] = _sha256(
        payload
    )

    return payload


def validate_negative_merit_score_release_certificate(
    certificate: Any,
) -> Dict[str, Any]:
    if not isinstance(
        certificate,
        dict,
    ):
        raise ValueError(
            "Negative Merit score-release "
            "certificate must be a dictionary."
        )

    _assert_no_human_review_keys(
        certificate
    )

    if (
        _clean(
            certificate.get(
                "version"
            )
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION
        )
    ):
        raise ValueError(
            "Unsupported Negative Merit "
            "score-release certificate."
        )

    report = certificate.get(
        "release_gate_report"
    )

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError(
            "Negative Merit score-release "
            "certificate is missing its "
            "release-gate report."
        )

    rebuilt = (
        build_negative_merit_score_release_certificate(
            release_gate_report=report
        )
    )

    if (
        _canonical_json(
            rebuilt
        )
        != _canonical_json(
            certificate
        )
    ):
        raise ValueError(
            "Negative Merit score-release "
            "certificate content or identity "
            "has been tampered with."
        )

    return rebuilt
