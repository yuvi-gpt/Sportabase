import math
import re
import statistics

from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
)
from urllib.parse import (
    urlparse,
)


from app.analysis.negative_merit import (
    NEGATIVE_MERIT_SHADOW_VERSION,
    build_negative_merit_shadow,
)


NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION = (
    "negative-merit-calibration-dataset-v1"
)

NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION = (
    "negative-merit-calibration-observation-v1"
)

NEGATIVE_MERIT_CALIBRATION_ORIGIN = (
    "real_world"
)

NEGATIVE_MERIT_CALIBRATION_OBSERVATION_CLASSES = {
    "two_gate_observation",
    "authority_only_control",
    "semantic_only_control",
    "no_negative_evidence_control",
    "exclusive_no_corroboration_control",
}

NEGATIVE_MERIT_CALIBRATION_RESOLUTION_STATUS = (
    "unresolved"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


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

    if not (
        0.0
        <= result
        <= 100.0
    ):
        raise ValueError(
            f"{label} must be between 0 and 100."
        )

    return result


def _signed_number(
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

    if not math.isfinite(
        result
    ):
        raise ValueError(
            f"{label} must be finite."
        )

    return result


def _timestamp(
    value: Any,
    *,
    label: str,
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    candidate = text

    if candidate.endswith(
        "Z"
    ):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = (
            datetime.fromisoformat(
                candidate
            )
        )

    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed.isoformat()


def _capture(
    value: Any,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Calibration source capture "
            "must be a dictionary."
        )

    url = _clean(
        value.get(
            "url"
        )
    )

    source_id = _clean(
        value.get(
            "source_id"
        )
    )

    content_sha256 = _key(
        value.get(
            "content_sha256"
        )
    )

    captured_at = _timestamp(
        value.get(
            "captured_at"
        ),
        label=(
            "Calibration capture captured_at"
        ),
    )

    parsed = urlparse(
        url
    )

    if (
        not url
        or parsed.scheme.lower()
        != "https"
        or not parsed.netloc
    ):
        raise ValueError(
            "Calibration source captures "
            "must use HTTPS."
        )

    if not source_id:
        raise ValueError(
            "Calibration source capture "
            "requires source identity."
        )

    if not _SHA256_RE.fullmatch(
        content_sha256
    ):
        raise ValueError(
            "Calibration source capture "
            "requires a SHA256 content hash."
        )

    return {
        "url": url,
        "source_id": source_id,
        "content_sha256": (
            content_sha256
        ),
        "captured_at": (
            captured_at
        ),
    }


def _bucket(
    value: float,
) -> str:
    if value < 20:
        return "00_19"

    if value < 40:
        return "20_39"

    if value < 60:
        return "40_59"

    if value < 80:
        return "60_79"

    return "80_100"


def _distribution(
    values: List[float],
) -> Dict[str, Any]:
    buckets = {
        "00_19": 0,
        "20_39": 0,
        "40_59": 0,
        "60_79": 0,
        "80_100": 0,
    }

    if not values:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "mean": None,
            "median": None,
            "buckets": buckets,
        }

    normalized = [
        float(
            value
        )
        for value
        in values
    ]

    for value in normalized:
        buckets[
            _bucket(
                value
            )
        ] += 1

    return {
        "count": len(
            normalized
        ),
        "minimum": min(
            normalized
        ),
        "maximum": max(
            normalized
        ),
        "mean": float(
            statistics.fmean(
                normalized
            )
        ),
        "median": float(
            statistics.median(
                normalized
            )
        ),
        "buckets": buckets,
    }


def _validate_shadow_safety(
    *,
    shadow: Dict[str, Any],
    legacy_total: float,
) -> Dict[str, Any]:
    if not isinstance(
        shadow,
        dict,
    ):
        raise ValueError(
            "Calibration shadow result "
            "must be a dictionary."
        )

    if (
        _clean(
            shadow.get(
                "version"
            )
        )
        != NEGATIVE_MERIT_SHADOW_VERSION
    ):
        raise ValueError(
            "Calibration observation received "
            "an unsupported Negative Merit shadow."
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
            "Calibration observation shadow "
            "is missing required score or "
            "evidence-gate sections."
        )

    adjustment = _signed_number(
        proposed.get(
            "adjustment"
        ),
        label=(
            "Calibration observation adjustment"
        ),
    )

    shadow_total = _number(
        proposed.get(
            "shadow_total"
        ),
        label=(
            "Calibration observation shadow total"
        ),
    )

    live_total = _number(
        live.get(
            "total"
        ),
        label=(
            "Calibration observation live total"
        ),
    )

    eligible = proposed.get(
        "eligible_for_penalty_calibration"
    )

    authority_gate = gates.get(
        "direct_authority_contradiction_lineage"
    )

    semantic_gate = gates.get(
        "machine_verified_contradiction_semantics"
    )

    both_required = gates.get(
        "both_required"
    )

    claim_truth_established = gates.get(
        "claim_truth_established"
    )

    live_effect_enabled = live.get(
        "score_effect_enabled"
    )

    for label, value in (
        (
            "Calibration eligibility",
            eligible,
        ),
        (
            "Direct-authority gate",
            authority_gate,
        ),
        (
            "Semantic gate",
            semantic_gate,
        ),
        (
            "Two-gate requirement",
            both_required,
        ),
        (
            "Claim-truth boundary",
            claim_truth_established,
        ),
        (
            "Live score effect state",
            live_effect_enabled,
        ),
    ):
        if not isinstance(
            value,
            bool,
        ):
            raise ValueError(
                f"{label} must be boolean."
            )

    if abs(
        adjustment
    ) > 1e-9:
        raise ValueError(
            "Calibration observation collection "
            "cannot contain a numeric negative "
            "Merit adjustment."
        )

    if (
        abs(
            shadow_total
            - legacy_total
        )
        > 1e-9
    ):
        raise ValueError(
            "Calibration observation collection "
            "cannot change the shadow score."
        )

    if (
        abs(
            live_total
            - legacy_total
        )
        > 1e-9
    ):
        raise ValueError(
            "Calibration observation collection "
            "cannot change the live score."
        )

    if live_effect_enabled:
        raise ValueError(
            "Calibration observation collection "
            "cannot enable live negative Merit."
        )

    if not both_required:
        raise ValueError(
            "Calibration observation requires "
            "the two-gate safety boundary."
        )

    if claim_truth_established:
        raise ValueError(
            "Calibration observation cannot "
            "establish objective claim truth."
        )

    return {
        "eligible": (
            eligible
        ),
        "authority_gate": (
            authority_gate
        ),
        "semantic_gate": (
            semantic_gate
        ),
        "signal": _clean(
            shadow.get(
                "signal"
            )
        ),
        "severity_class": _clean(
            shadow.get(
                "severity_class"
            )
        ),
    }


def _validate_class(
    *,
    observation_class: str,
    shadow_state: Dict[str, Any],
) -> None:
    authority_gate = (
        shadow_state[
            "authority_gate"
        ]
    )

    semantic_gate = (
        shadow_state[
            "semantic_gate"
        ]
    )

    eligible = (
        shadow_state[
            "eligible"
        ]
    )

    if (
        observation_class
        == "two_gate_observation"
    ):
        if not (
            authority_gate
            and semantic_gate
            and eligible
        ):
            raise ValueError(
                "Two-gate calibration observation "
                "must satisfy both evidence gates "
                "and be calibration-eligible."
            )

        return

    if (
        observation_class
        == "authority_only_control"
    ):
        if not (
            authority_gate
            and not semantic_gate
            and not eligible
        ):
            raise ValueError(
                "Authority-only calibration "
                "control has inconsistent gates."
            )

        return

    if (
        observation_class
        == "semantic_only_control"
    ):
        if not (
            not authority_gate
            and semantic_gate
            and not eligible
        ):
            raise ValueError(
                "Semantic-only calibration "
                "control has inconsistent gates."
            )

        return

    if observation_class in {
        "no_negative_evidence_control",
        "exclusive_no_corroboration_control",
    }:
        if (
            authority_gate
            or semantic_gate
            or eligible
        ):
            raise ValueError(
                "Negative-evidence control "
                "unexpectedly satisfies a "
                "negative Merit gate."
            )

        return

    raise ValueError(
        "Unsupported Negative Merit "
        "calibration observation class."
    )


def build_negative_merit_calibration_dataset(
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
            "Negative Merit calibration "
            "cases must be a list."
        )

    if not cases:
        raise ValueError(
            "Negative Merit calibration "
            "dataset requires at least one "
            "real-world observation."
        )

    seen_ids = set()
    observations = []

    all_scores = []
    two_gate_scores = []
    control_scores = []

    per_class_scores = {
        observation_class: []
        for observation_class
        in sorted(
            NEGATIVE_MERIT_CALIBRATION_OBSERVATION_CLASSES
        )
    }

    source_ids = set()
    capture_hashes = set()

    for raw_case in cases:
        if not isinstance(
            raw_case,
            dict,
        ):
            raise ValueError(
                "Each calibration observation "
                "must be a dictionary."
            )

        if (
            _clean(
                raw_case.get(
                    "version"
                )
            )
            != (
                NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
            )
        ):
            raise ValueError(
                "Unsupported Negative Merit "
                "calibration observation version."
            )

        if (
            _key(
                raw_case.get(
                    "origin"
                )
            )
            != NEGATIVE_MERIT_CALIBRATION_ORIGIN
        ):
            raise ValueError(
                "Negative Merit calibration "
                "observations must be marked "
                "real_world."
            )

        if (
            raw_case.get(
                "machine_verified"
            )
            is not True
        ):
            raise ValueError(
                "Negative Merit calibration "
                "observation lineage must be "
                "machine-verified."
            )

        observation_id = _clean(
            raw_case.get(
                "id"
            )
        )

        claim_id = _clean(
            raw_case.get(
                "claim_id"
            )
        )

        observation_class = _key(
            raw_case.get(
                "observation_class"
            )
        )

        if not observation_id:
            raise ValueError(
                "Calibration observation ID "
                "is required."
            )

        if observation_id in seen_ids:
            raise ValueError(
                "Calibration observation IDs "
                "must be unique."
            )

        seen_ids.add(
            observation_id
        )

        if not claim_id:
            raise ValueError(
                "Calibration observation claim "
                "ID is required."
            )

        if (
            observation_class
            not in (
                NEGATIVE_MERIT_CALIBRATION_OBSERVATION_CLASSES
            )
        ):
            raise ValueError(
                "Unsupported Negative Merit "
                "calibration observation class."
            )

        observed_at = _timestamp(
            raw_case.get(
                "observed_at"
            ),
            label=(
                "Calibration observation observed_at"
            ),
        )

        resolution_status = _key(
            raw_case.get(
                "resolution_status"
            )
        )

        if (
            resolution_status
            != (
                NEGATIVE_MERIT_CALIBRATION_RESOLUTION_STATUS
            )
        ):
            raise ValueError(
                "Resolved claim-outcome labels "
                "are not accepted by calibration "
                "dataset v1. A dedicated "
                "machine-verified canonical-outcome "
                "verifier is required first."
            )

        captures_raw = raw_case.get(
            "source_captures"
        )

        if (
            not isinstance(
                captures_raw,
                list,
            )
            or not captures_raw
        ):
            raise ValueError(
                "Calibration observation requires "
                "at least one immutable source capture."
            )

        captures = [
            _capture(
                capture
            )
            for capture
            in captures_raw
        ]

        legacy_score = raw_case.get(
            "legacy_score"
        )

        if not isinstance(
            legacy_score,
            dict,
        ):
            raise ValueError(
                "Calibration observation legacy "
                "score must be a dictionary."
            )

        legacy_total = _number(
            legacy_score.get(
                "total"
            ),
            label=(
                "Calibration legacy Merit total"
            ),
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

        shadow_state = (
            _validate_shadow_safety(
                shadow=(
                    shadow
                ),
                legacy_total=(
                    legacy_total
                ),
            )
        )

        _validate_class(
            observation_class=(
                observation_class
            ),
            shadow_state=(
                shadow_state
            ),
        )

        all_scores.append(
            legacy_total
        )

        per_class_scores[
            observation_class
        ].append(
            legacy_total
        )

        if (
            observation_class
            == "two_gate_observation"
        ):
            two_gate_scores.append(
                legacy_total
            )

        else:
            control_scores.append(
                legacy_total
            )

        for capture in captures:
            source_ids.add(
                capture[
                    "source_id"
                ]
            )

            capture_hashes.add(
                capture[
                    "content_sha256"
                ]
            )

        observations.append(
            {
                "id": (
                    observation_id
                ),
                "claim_id": (
                    claim_id
                ),
                "observation_class": (
                    observation_class
                ),
                "observed_at": (
                    observed_at
                ),
                "resolution_status": (
                    resolution_status
                ),
                "legacy_total": (
                    legacy_total
                ),
                "source_captures": (
                    captures
                ),
                "negative_merit": {
                    "signal": (
                        shadow_state[
                            "signal"
                        ]
                    ),
                    "severity_class": (
                        shadow_state[
                            "severity_class"
                        ]
                    ),
                    "calibration_eligible": (
                        shadow_state[
                            "eligible"
                        ]
                    ),
                    "authority_gate": (
                        shadow_state[
                            "authority_gate"
                        ]
                    ),
                    "semantic_gate": (
                        shadow_state[
                            "semantic_gate"
                        ]
                    ),
                    "adjustment": 0.0,
                    "live_effect_enabled": False,
                    "claim_truth_established": False,
                },
            }
        )

    per_class = {
        observation_class: (
            _distribution(
                per_class_scores[
                    observation_class
                ]
            )
        )
        for observation_class
        in sorted(
            per_class_scores
        )
    }

    return {
        "version": (
            NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION
        ),
        "status": (
            "measurement_ready"
        ),
        "case_count": len(
            observations
        ),
        "source_count": len(
            source_ids
        ),
        "capture_hash_count": len(
            capture_hashes
        ),
        "observations": (
            observations
        ),
        "score_distribution": {
            "overall": (
                _distribution(
                    all_scores
                )
            ),
            "two_gate_observations": (
                _distribution(
                    two_gate_scores
                )
            ),
            "controls": (
                _distribution(
                    control_scores
                )
            ),
            "by_class": (
                per_class
            ),
        },
        "calibration": {
            "penalty_weight_selected": False,
            "numeric_penalty_authorized": False,
            "live_negative_merit_authorized": False,
            "canonical_outcome_labels_available": False,
            "blockers": [
                (
                    "canonical_outcome_verifier_"
                    "not_implemented"
                ),
                (
                    "resolved_outcome_labels_"
                    "not_available"
                ),
                (
                    "numeric_penalty_not_calibrated"
                ),
            ],
        },
        "policy": {
            "real_world_observations_required": True,
            "machine_verified_lineage_required": True,
            "immutable_https_source_captures_required": True,
            "two_gate_observation_is_not_a_falsehood_label": True,
            "case_machine_verified_does_not_mean_claim_truth": True,
            "unresolved_outcomes_only_in_v1": True,
            "resolved_labels_require_dedicated_canonical_outcome_verifier": True,
            "score_distribution_must_be_measured_before_weight_selection": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "early_exclusives_are_controls_not_falsehoods": True,
            "numeric_negative_adjustments_are_forbidden": True,
            "live_negative_merit_is_forbidden": True,
            "dataset_does_not_authorize_release": True,
        },
    }
