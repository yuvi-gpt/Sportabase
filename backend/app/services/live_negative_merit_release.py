from __future__ import annotations

import copy
import hashlib
import json

from pathlib import Path
from typing import (
    Any,
    Dict,
)


from app.analysis.negative_merit import (
    NEGATIVE_MERIT_SHADOW_VERSION,
)

from app.analysis.negative_merit_score_release import (
    NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
    NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT,
    validate_negative_merit_score_release_certificate,
)

from app.services.negative_merit_runtime import (
    NEGATIVE_MERIT_RUNTIME_VERSION,
)


LIVE_NEGATIVE_MERIT_RELEASE_RUNTIME_VERSION = (
    "live-negative-merit-release-runtime-v1"
)

LIVE_NEGATIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT = (
    -15.0
)

LIVE_NEGATIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256 = (
    "28c6ee7870ba8a86dc7f531dc5494718c90b031480085607deadd3341411ef7a"
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


def _read_certificate(
    certificate_path: Path,
    *,
    raw: bytes | None = None,
) -> Dict[str, Any]:
    path = Path(
        certificate_path
    )

    if raw is None:
        raw = path.read_bytes()

    if not isinstance(
        raw,
        (
            bytes,
            bytearray,
        ),
    ):
        raise ValueError(
            "Negative Merit certificate "
            "bytes must be bytes."
        )

    raw = bytes(
        raw
    )

    raw_file_sha256 = (
        hashlib.sha256(
            raw
        ).hexdigest()
    )

    payload = json.loads(
        raw.decode(
            "utf-8"
        )
    )

    validated = (
        validate_negative_merit_score_release_certificate(
            payload
        )
    )

    if (
        _clean(
            validated.get(
                "version"
            )
        )
        != (
            NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_VERSION
        )
    ):
        raise ValueError(
            "Negative Merit certificate "
            "version is unsupported."
        )

    certificate_sha256 = _clean(
        validated.get(
            "certificate_sha256"
        )
    )

    if (
        certificate_sha256
        != (
            LIVE_NEGATIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
        )
    ):
        raise ValueError(
            "Negative Merit certificate "
            "identity does not match the "
            "pinned release."
        )

    if (
        _key(
            validated.get(
                "status"
            )
        )
        != "authorized"
        or validated.get(
            "live_enablement_authorized"
        )
        is not True
        or validated.get(
            "blockers"
        )
        != []
    ):
        raise ValueError(
            "Negative Merit certificate "
            "is not authorized."
        )

    adjustment = float(
        validated.get(
            "certified_adjustment"
        )
    )

    if (
        abs(
            adjustment
            - (
                LIVE_NEGATIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT
            )
        )
        > 1e-9
        or abs(
            adjustment
            - (
                NEGATIVE_MERIT_SCORE_RELEASE_CERTIFIED_ADJUSTMENT
            )
        )
        > 1e-9
    ):
        raise ValueError(
            "Negative Merit certificate "
            "adjustment does not match "
            "the pinned runtime."
        )

    policy = validated.get(
        "policy"
    )

    if (
        not isinstance(
            policy,
            dict,
        )
        or policy.get(
            "certificate_does_not_itself_activate_live_negative_merit"
        )
        is not True
        or policy.get(
            "runtime_must_fail_closed"
        )
        is not True
        or policy.get(
            "runtime_must_preserve_positive_merit_composition"
        )
        is not True
        or policy.get(
            "absence_of_corroboration_is_not_negative_evidence"
        )
        is not True
        or policy.get(
            "club_denial_alone_never_authorizes_negative_merit"
        )
        is not True
    ):
        raise ValueError(
            "Negative Merit certificate "
            "policy contract is incomplete."
        )

    return {
        "certificate": validated,
        "certificate_sha256": (
            certificate_sha256
        ),
        "raw_file_sha256": (
            raw_file_sha256
        ),
    }


def live_negative_merit_release_cache_token(
    *,
    enabled: bool,
    certificate_path: Path,
) -> str:
    path = Path(
        certificate_path
    )

    raw_sha256 = "missing"
    state = "disabled"

    if enabled:
        state = "invalid"

        try:
            raw = path.read_bytes()

            raw_sha256 = (
                hashlib.sha256(
                    raw
                ).hexdigest()
            )

        except Exception:
            raw = None

        if raw is not None:
            try:
                _read_certificate(
                    path,
                    raw=raw,
                )

                state = "authorized"

            except Exception:
                state = "invalid"

    token_payload = "|".join(
        [
            LIVE_NEGATIVE_MERIT_RELEASE_RUNTIME_VERSION,
            str(
                int(
                    bool(
                        enabled
                    )
                )
            ),
            state,
            raw_sha256,
            (
                LIVE_NEGATIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
            ),
        ]
    )

    return hashlib.sha256(
        token_payload.encode(
            "utf-8"
        )
    ).hexdigest()


def _fallback(
    *,
    score: Dict[str, Any],
    enabled: bool,
    reason: str,
    certificate: Dict[str, Any] | None = None,
    claim_id: str = "",
    signal: str = "",
) -> Dict[str, Any]:
    certificate_state = (
        certificate
        if isinstance(
            certificate,
            dict,
        )
        else {}
    )

    total = (
        score.get(
            "total"
        )
        if isinstance(
            score,
            dict,
        )
        else None
    )

    return {
        "version": (
            LIVE_NEGATIVE_MERIT_RELEASE_RUNTIME_VERSION
        ),
        "status": (
            "score_preserved"
        ),
        "enabled": bool(
            enabled
        ),
        "score_effect_applied": False,
        "reason": _clean(
            reason
        ),
        "claim_id": _clean(
            claim_id
        ),
        "signal": _clean(
            signal
        ),
        "adjustment": 0.0,
        "input_total": total,
        "live_total": total,
        "certificate": {
            "valid": bool(
                certificate_state
            ),
            "certificate_sha256": (
                certificate_state.get(
                    "certificate_sha256",
                    "",
                )
            ),
            "raw_file_sha256": (
                certificate_state.get(
                    "raw_file_sha256",
                    "",
                )
            ),
            "required_certificate_sha256": (
                LIVE_NEGATIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
            ),
        },
        "score": copy.deepcopy(
            score
        ),
        "policy": {
            "certificate_required": True,
            "strict_two_gate_result_required": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "club_denial_alone_is_not_negative_evidence": True,
            "model_only_contradiction_never_changes_merit": True,
            "failure_preserves_exact_input_score": True,
            "positive_merit_composition_is_preserved": True,
            "claim_truth_established": False,
            "no_network_calls": True,
            "no_gemini_calls": True,
        },
    }


def _validate_negative_runtime_result(
    value: Any,
) -> Dict[str, str]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Negative Merit runtime result "
            "must be a dictionary."
        )

    if (
        _clean(
            value.get(
                "version"
            )
        )
        != (
            NEGATIVE_MERIT_RUNTIME_VERSION
        )
        or _key(
            value.get(
                "status"
            )
        )
        != (
            "negative_evidence_"
            "calibration_eligible"
        )
        or _key(
            value.get(
                "mode"
            )
        )
        != "shadow"
        or value.get(
            "provider_call_performed"
        )
        is not False
        or value.get(
            "live_merit_effect_enabled"
        )
        is not False
        or value.get(
            "claim_truth_established"
        )
        is not False
    ):
        raise ValueError(
            "Negative Merit runtime "
            "is not strict two-gate eligible."
        )

    claim_id = _clean(
        value.get(
            "claim_id"
        )
    )

    if not claim_id:
        raise ValueError(
            "Negative Merit runtime "
            "claim ID is missing."
        )

    policy = value.get(
        "policy"
    )

    if (
        not isinstance(
            policy,
            dict,
        )
        or policy.get(
            "no_network_calls"
        )
        is not True
        or policy.get(
            "no_gemini_calls"
        )
        is not True
        or policy.get(
            "absence_of_corroboration_is_not_false"
        )
        is not True
        or policy.get(
            "semantic_contradiction_alone_cannot_change_merit"
        )
        is not True
        or policy.get(
            "direct_authority_alone_is_not_calibration_eligible"
        )
        is not True
    ):
        raise ValueError(
            "Negative Merit runtime "
            "safety policy is incomplete."
        )

    shadow = value.get(
        "shadow"
    )

    if not isinstance(
        shadow,
        dict,
    ):
        raise ValueError(
            "Negative Merit shadow "
            "payload is missing."
        )

    signal = _key(
        shadow.get(
            "signal"
        )
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
        or _key(
            shadow.get(
                "mode"
            )
        )
        != "shadow"
        or _clean(
            shadow.get(
                "claim_id"
            )
        )
        != claim_id
        or signal
        != (
            "verified_authority_machine_"
            "semantic_contradiction"
        )
        or _key(
            shadow.get(
                "severity_class"
            )
        )
        != (
            "two_gate_negative_"
            "evidence_candidate"
        )
    ):
        raise ValueError(
            "Negative Merit shadow "
            "identity or signal is invalid."
        )

    gates = shadow.get(
        "evidence_gates"
    )

    if (
        not isinstance(
            gates,
            dict,
        )
        or gates.get(
            "direct_authority_contradiction_lineage"
        )
        is not True
        or gates.get(
            "machine_verified_contradiction_semantics"
        )
        is not True
        or gates.get(
            "both_required"
        )
        is not True
        or gates.get(
            "claim_truth_established"
        )
        is not False
    ):
        raise ValueError(
            "Negative Merit two-gate "
            "verification is incomplete."
        )

    proposed = shadow.get(
        "proposed"
    )

    live = shadow.get(
        "live"
    )

    if (
        not isinstance(
            proposed,
            dict,
        )
        or proposed.get(
            "eligible_for_penalty_calibration"
        )
        is not True
        or abs(
            float(
                proposed.get(
                    "adjustment",
                    999,
                )
            )
        )
        > 1e-9
        or not isinstance(
            live,
            dict,
        )
        or live.get(
            "score_effect_enabled"
        )
        is not False
    ):
        raise ValueError(
            "Negative Merit shadow "
            "is not calibration-only."
        )

    shadow_policy = shadow.get(
        "policy"
    )

    if (
        not isinstance(
            shadow_policy,
            dict,
        )
        or shadow_policy.get(
            "absence_of_corroboration_is_not_negative_evidence"
        )
        is not True
        or shadow_policy.get(
            "single_source_exclusive_is_not_penalized"
        )
        is not True
        or shadow_policy.get(
            "model_only_contradiction_never_changes_merit"
        )
        is not True
        or shadow_policy.get(
            "verified_direct_authority_lineage_is_required"
        )
        is not True
        or shadow_policy.get(
            "machine_verified_contradiction_semantics_required_for_calibration"
        )
        is not True
        or shadow_policy.get(
            "live_negative_merit_is_disabled"
        )
        is not True
    ):
        raise ValueError(
            "Negative Merit shadow "
            "safety boundary is incomplete."
        )

    return {
        "claim_id": (
            claim_id
        ),
        "signal": (
            signal
        ),
    }


def apply_certified_live_negative_merit(
    *,
    enabled: bool,
    score: Dict[str, Any],
    negative_merit_result: Dict[str, Any] | None,
    certificate_path: Path,
    badge_resolver,
) -> Dict[str, Any]:
    if not isinstance(
        score,
        dict,
    ):
        raise ValueError(
            "Live Negative Merit score "
            "must be a dictionary."
        )

    if not enabled:
        return _fallback(
            score=score,
            enabled=False,
            reason=(
                "live_negative_merit_disabled"
            ),
        )

    try:
        certificate = (
            _read_certificate(
                certificate_path
            )
        )

    except Exception as error:
        return _fallback(
            score=score,
            enabled=True,
            reason=(
                "certificate_invalid:"
                + type(
                    error
                ).__name__
            ),
        )

    try:
        verified = (
            _validate_negative_runtime_result(
                negative_merit_result
            )
        )

    except Exception as error:
        return _fallback(
            score=score,
            enabled=True,
            reason=(
                "negative_evidence_not_certified:"
                + type(
                    error
                ).__name__
            ),
            certificate=certificate,
        )

    try:
        input_total = float(
            score[
                "total"
            ]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return _fallback(
            score=score,
            enabled=True,
            reason=(
                "input_total_invalid"
            ),
            certificate=certificate,
            claim_id=(
                verified[
                    "claim_id"
                ]
            ),
            signal=(
                verified[
                    "signal"
                ]
            ),
        )

    if not (
        0.0
        <= input_total
        <= 100.0
    ):
        return _fallback(
            score=score,
            enabled=True,
            reason=(
                "input_total_invalid"
            ),
            certificate=certificate,
            claim_id=(
                verified[
                    "claim_id"
                ]
            ),
            signal=(
                verified[
                    "signal"
                ]
            ),
        )

    adjustment = float(
        certificate[
            "certificate"
        ][
            "certified_adjustment"
        ]
    )

    if (
        abs(
            adjustment
            - (
                LIVE_NEGATIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT
            )
        )
        > 1e-9
        or adjustment
        >= 0.0
    ):
        return _fallback(
            score=score,
            enabled=True,
            reason=(
                "certified_adjustment_mismatch"
            ),
            certificate=certificate,
            claim_id=(
                verified[
                    "claim_id"
                ]
            ),
            signal=(
                verified[
                    "signal"
                ]
            ),
        )

    live_total_float = max(
        0.0,
        min(
            100.0,
            input_total
            + adjustment,
        ),
    )

    live_total = int(
        round(
            live_total_float
        )
    )

    try:
        live_badge = badge_resolver(
            live_total
        )

    except Exception as error:
        return _fallback(
            score=score,
            enabled=True,
            reason=(
                "score_application_failed:"
                + type(
                    error
                ).__name__
            ),
            certificate=certificate,
            claim_id=(
                verified[
                    "claim_id"
                ]
            ),
            signal=(
                verified[
                    "signal"
                ]
            ),
        )

    live_score = copy.deepcopy(
        score
    )

    live_score[
        "total"
    ] = live_total

    live_score[
        "badge"
    ] = live_badge

    components = live_score.get(
        "components"
    )

    if not isinstance(
        components,
        dict,
    ):
        components = {}

    components = dict(
        components
    )

    components[
        "certified_negative_merit_adjustment"
    ] = round(
        adjustment,
        2,
    )

    live_score[
        "components"
    ] = components

    calculation = live_score.get(
        "calculation"
    )

    if not isinstance(
        calculation,
        dict,
    ):
        calculation = {}

    calculation = dict(
        calculation
    )

    calculation[
        "total_before_certified_negative_merit"
    ] = int(
        round(
            input_total
        )
    )

    calculation[
        "certified_negative_merit_adjustment"
    ] = round(
        adjustment,
        2,
    )

    calculation[
        "final_total"
    ] = live_total

    live_score[
        "calculation"
    ] = calculation

    reasons = live_score.get(
        "reasons"
    )

    if not isinstance(
        reasons,
        list,
    ):
        reasons = []

    reasons = list(
        reasons
    )

    live_reason = (
        "Machine-verified direct-authority "
        "contradiction with verified "
        "contradiction semantics: "
        f"{int(round(adjustment))} "
        "certified Merit adjustment."
    )

    if (
        live_reason
        not in reasons
    ):
        reasons.append(
            live_reason
        )

    live_score[
        "reasons"
    ] = reasons[:10]

    return {
        "version": (
            LIVE_NEGATIVE_MERIT_RELEASE_RUNTIME_VERSION
        ),
        "status": "applied",
        "enabled": True,
        "score_effect_applied": True,
        "reason": (
            "authorized_two_gate_negative_evidence"
        ),
        "claim_id": (
            verified[
                "claim_id"
            ]
        ),
        "signal": (
            verified[
                "signal"
            ]
        ),
        "adjustment": round(
            adjustment,
            2,
        ),
        "input_total": int(
            round(
                input_total
            )
        ),
        "live_total": (
            live_total
        ),
        "certificate": {
            "valid": True,
            "certificate_sha256": (
                certificate[
                    "certificate_sha256"
                ]
            ),
            "raw_file_sha256": (
                certificate[
                    "raw_file_sha256"
                ]
            ),
            "required_certificate_sha256": (
                LIVE_NEGATIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
            ),
        },
        "score": (
            live_score
        ),
        "policy": {
            "certificate_required": True,
            "strict_two_gate_result_required": True,
            "absence_of_corroboration_is_not_negative_evidence": True,
            "club_denial_alone_is_not_negative_evidence": True,
            "model_only_contradiction_never_changes_merit": True,
            "positive_merit_composition_is_preserved": True,
            "score_is_clamped_zero_to_one_hundred": True,
            "claim_truth_established": False,
            "no_network_calls": True,
            "no_gemini_calls": True,
        },
    }
