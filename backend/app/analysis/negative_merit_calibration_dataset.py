import json
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

from app.services.canonical_outcome_resolution_verifier import (
    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
)


NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION = (
    "negative-merit-calibration-dataset-v2"
)

NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION = (
    "negative-merit-calibration-observation-v2"
)

NEGATIVE_MERIT_CALIBRATION_ORIGIN = (
    "real_world"
)

NEGATIVE_MERIT_CALIBRATION_OBSERVATION_CLASSES = {
    "resolved_against_claim_observation",
    "two_gate_observation",
    "authority_only_control",
    "semantic_only_control",
    "no_negative_evidence_control",
    "exclusive_no_corroboration_control",
}

NEGATIVE_MERIT_CALIBRATION_RESOLUTION_STATUSES = {
    "unresolved",
    "resolved_against_claim",
}

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


def _decode_metadata(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(
                value or "{}"
            )
        )

    except Exception as exc:
        raise ValueError(
            f"{label} contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            f"{label} must be a dictionary."
        )

    return parsed


def _validate_resolution_verification(
    *,
    value: Any,
    claim_id: str,
    captures: List[
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Resolved-against-claim calibration "
            "observation requires the persisted "
            "canonical outcome verifier result."
        )

    if (
        _clean(
            value.get(
                "version"
            )
        )
        != (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        )
    ):
        raise ValueError(
            "Resolved calibration verification "
            "version is unsupported."
        )

    if (
        value.get(
            "status"
        )
        not in {
            (
                "persisted_verified_"
                "canonical_outcome_resolution"
            ),
            "verification_already_present",
        }
        or value.get(
            "persisted"
        )
        is not True
    ):
        raise ValueError(
            "Resolved calibration case requires "
            "a persisted verified canonical "
            "outcome resolution."
        )

    policy = value.get(
        "policy"
    )

    if not isinstance(
        policy,
        dict,
    ):
        raise ValueError(
            "Resolved calibration verification "
            "policy is missing."
        )

    required_true = {
        "canonical_resolution_machine_verified",
        "resolved_against_claim",
        "does_not_change_live_merit",
    }

    for field in required_true:
        if policy.get(
            field
        ) is not True:
            raise ValueError(
                "Resolved calibration verification "
                f"policy field {field} must be true."
            )

    if (
        _key(
            policy.get(
                "machine_stance"
            )
        )
        != "contradicts"
        or _key(
            policy.get(
                "machine_basis_class"
            )
        )
        != "canonical_resolution"
    ):
        raise ValueError(
            "Resolved calibration verification "
            "must contain the machine-verified "
            "canonical-resolution contradiction."
        )

    if (
        policy.get(
            "claim_truth_established"
        )
        is not False
        or policy.get(
            "numeric_negative_penalty_authorized"
        )
        is not False
        or policy.get(
            "live_negative_merit_authorized"
        )
        is not False
    ):
        raise ValueError(
            "Resolved calibration verification "
            "violates the truth or live-Merit "
            "safety boundary."
        )

    candidate_result = value.get(
        "candidate"
    )

    if not isinstance(
        candidate_result,
        dict,
    ):
        raise ValueError(
            "Resolved calibration canonical "
            "candidate is missing."
        )

    if (
        _clean(
            candidate_result.get(
                "version"
            )
        )
        != (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        )
        or candidate_result.get(
            "status"
        )
        != (
            "verified_canonical_outcome_"
            "against_claim"
        )
    ):
        raise ValueError(
            "Resolved calibration canonical "
            "candidate is not verifier-certified."
        )

    if (
        _clean(
            candidate_result.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Resolved calibration verification "
            "belongs to another claim."
        )

    source_id = _clean(
        candidate_result.get(
            "source_id"
        )
    )

    proof_evidence_id = _clean(
        candidate_result.get(
            "proof_evidence_id"
        )
    )

    if (
        not source_id
        or not proof_evidence_id
    ):
        raise ValueError(
            "Resolved calibration verification "
            "source or proof identity is missing."
        )

    candidate = candidate_result.get(
        "candidate"
    )

    if not isinstance(
        candidate,
        dict,
    ):
        raise ValueError(
            "Resolved calibration verified "
            "candidate payload is missing."
        )

    resolution = candidate.get(
        "canonical_resolution"
    )

    if (
        not isinstance(
            resolution,
            dict,
        )
        or resolution.get(
            "status"
        )
        != (
            "resolution_against_claim_candidate"
        )
        or _key(
            resolution.get(
                "direction"
            )
        )
        != "against_claim"
    ):
        raise ValueError(
            "Resolved calibration verification "
            "does not contain an against-claim "
            "canonical resolution."
        )

    rule_id = _clean(
        candidate.get(
            "rule_id"
        )
    )

    if (
        not rule_id
        or rule_id
        != _clean(
            resolution.get(
                "rule_id"
            )
        )
    ):
        raise ValueError(
            "Resolved calibration canonical "
            "resolution rule identity is invalid."
        )

    canonical_url = _clean(
        candidate.get(
            "canonical_url"
        )
    )

    content_sha256 = _key(
        candidate.get(
            "content_sha256"
        )
    )

    if (
        not canonical_url
        or not _SHA256_RE.fullmatch(
            content_sha256
        )
    ):
        raise ValueError(
            "Resolved calibration canonical "
            "source capture identity is invalid."
        )

    matching_capture = any(
        (
            capture[
                "source_id"
            ]
            == source_id
            and capture[
                "url"
            ]
            == canonical_url
            and capture[
                "content_sha256"
            ]
            == content_sha256
        )
        for capture in captures
    )

    if not matching_capture:
        raise ValueError(
            "Resolved calibration verifier "
            "result is not bound to an immutable "
            "source capture in this case."
        )

    resolution_evidence_id = _clean(
        value.get(
            "resolution_evidence_id"
        )
    )

    if not resolution_evidence_id:
        raise ValueError(
            "Resolved calibration machine "
            "resolution evidence ID is required."
        )

    runtime = value.get(
        "revision_runtime"
    )

    if (
        not isinstance(
            runtime,
            dict,
        )
        or _clean(
            runtime.get(
                "version"
            )
        )
        != (
            MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
        )
    ):
        raise ValueError(
            "Resolved calibration machine "
            "revision runtime is invalid."
        )

    evidence = runtime.get(
        "evidence"
    )

    if (
        not isinstance(
            evidence,
            dict,
        )
        or _clean(
            evidence.get(
                "id"
            )
        )
        != resolution_evidence_id
        or _key(
            evidence.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        raise ValueError(
            "Resolved calibration machine "
            "evidence is not persisted as verified."
        )

    if (
        _clean(
            evidence.get(
                "canonical_url"
            )
        )
        != canonical_url
    ):
        raise ValueError(
            "Resolved calibration machine "
            "evidence URL does not match the "
            "captured canonical outcome."
        )

    metadata = _decode_metadata(
        evidence.get(
            "metadata_json"
        ),
        label=(
            "Resolved calibration machine "
            "evidence metadata"
        ),
    )

    if (
        metadata.get(
            "canonical_outcome_resolution_verifier_version"
        )
        != (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        )
        or metadata.get(
            "canonical_outcome_resolution_verified"
        )
        is not True
        or metadata.get(
            "resolved_against_claim"
        )
        is not True
        or metadata.get(
            "claim_truth_established"
        )
        is not False
        or metadata.get(
            "live_merit_changed"
        )
        is not False
    ):
        raise ValueError(
            "Resolved calibration machine "
            "evidence metadata violates the "
            "verified-resolution contract."
        )

    machine_runs = runtime.get(
        "machine_evaluator_runs"
    )

    if not isinstance(
        machine_runs,
        list,
    ):
        raise ValueError(
            "Resolved calibration machine "
            "evaluator history is invalid."
        )

    stance_judgments = []

    for run in machine_runs:
        if (
            not isinstance(
                run,
                dict,
            )
            or _key(
                run.get(
                    "derivation_mode"
                )
            )
            != "machine_verified"
        ):
            raise ValueError(
                "Resolved calibration resolution "
                "must come only from a "
                "machine-verified evaluator run."
            )

        judgments = run.get(
            "judgments",
            [],
        )

        if not isinstance(
            judgments,
            list,
        ):
            raise ValueError(
                "Resolved calibration machine "
                "judgments are invalid."
            )

        for judgment in judgments:
            if not isinstance(
                judgment,
                dict,
            ):
                raise ValueError(
                    "Resolved calibration machine "
                    "judgment is invalid."
                )

            if (
                _key(
                    judgment.get(
                        "field"
                    )
                )
                == "stance"
            ):
                stance_judgments.append(
                    judgment
                )

    if len(
        stance_judgments
    ) != 1:
        raise ValueError(
            "Resolved calibration verification "
            "requires exactly one machine "
            "stance judgment."
        )

    stance = stance_judgments[0]

    if (
        _key(
            stance.get(
                "value"
            )
        )
        != "contradicts"
        or _key(
            stance.get(
                "basis_class"
            )
        )
        != "canonical_resolution"
    ):
        raise ValueError(
            "Resolved calibration machine "
            "stance is not a canonical "
            "resolution contradiction."
        )

    return {
        "version": (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        ),
        "status": (
            "resolved_against_claim"
        ),
        "claim_id": claim_id,
        "source_id": source_id,
        "proof_evidence_id": (
            proof_evidence_id
        ),
        "resolution_evidence_id": (
            resolution_evidence_id
        ),
        "rule_id": rule_id,
        "canonical_url": (
            canonical_url
        ),
        "content_sha256": (
            content_sha256
        ),
        "machine_verified": True,
        "claim_truth_established": False,
        "live_merit_effect_enabled": False,
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

    if observation_class in {
        "resolved_against_claim_observation",
        "two_gate_observation",
    }:
        if not (
            authority_gate
            and semantic_gate
            and eligible
        ):
            raise ValueError(
                "Resolved or two-gate calibration "
                "observation must satisfy both "
                "evidence gates and be "
                "calibration-eligible."
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
    resolved_scores = []
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
            not in (
                NEGATIVE_MERIT_CALIBRATION_RESOLUTION_STATUSES
            )
        ):
            raise ValueError(
                "Unsupported Negative Merit "
                "calibration resolution status."
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

        resolution_verification = (
            raw_case.get(
                "resolution_verification"
            )
        )

        resolution_summary = None

        if (
            resolution_status
            == "resolved_against_claim"
        ):
            if (
                observation_class
                != (
                    "resolved_against_claim_observation"
                )
            ):
                raise ValueError(
                    "Resolved-against-claim status "
                    "requires the dedicated resolved "
                    "observation class."
                )

            resolution_summary = (
                _validate_resolution_verification(
                    value=(
                        resolution_verification
                    ),
                    claim_id=(
                        claim_id
                    ),
                    captures=(
                        captures
                    ),
                )
            )

        else:
            if (
                observation_class
                == (
                    "resolved_against_claim_observation"
                )
            ):
                raise ValueError(
                    "Resolved observation class "
                    "requires resolved-against-claim "
                    "status."
                )

            if (
                resolution_verification
                is not None
            ):
                raise ValueError(
                    "Unresolved calibration "
                    "observation must not carry "
                    "resolved-outcome verification."
                )

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
            == (
                "resolved_against_claim_observation"
            )
        ):
            resolved_scores.append(
                legacy_total
            )

        elif (
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
                "resolution_verification": (
                    resolution_summary
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

    blockers = [
        "numeric_penalty_not_calibrated",
    ]

    if not resolved_scores:
        blockers.insert(
            0,
            "resolved_outcome_labels_not_present",
        )

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
            "resolved_against_claim": (
                _distribution(
                    resolved_scores
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
            "canonical_outcome_verifier_available": True,
            "canonical_outcome_labels_available": bool(
                resolved_scores
            ),
            "resolved_against_claim_case_count": len(
                resolved_scores
            ),
            "blockers": blockers,
        },
        "policy": {
            "real_world_observations_required": True,
            "machine_verified_lineage_required": True,
            "immutable_https_source_captures_required": True,
            "two_gate_observation_is_not_a_falsehood_label": True,
            "case_machine_verified_does_not_mean_claim_truth": True,
            "resolved_labels_require_exact_verified_canonical_outcome_result": True,
            "resolved_label_must_match_case_claim": True,
            "resolved_label_must_match_immutable_source_capture": True,
            "resolved_label_requires_machine_verified_canonical_resolution_stance": True,
            "resolved_label_is_not_permanent_objective_truth": True,
            "score_distribution_must_be_measured_before_weight_selection": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "early_exclusives_are_controls_not_falsehoods": True,
            "numeric_negative_adjustments_are_forbidden": True,
            "live_negative_merit_is_forbidden": True,
            "dataset_does_not_authorize_release": True,
        },
    }
