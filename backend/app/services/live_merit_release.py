from __future__ import annotations

import copy
import hashlib
import json

from pathlib import Path
from typing import Any, Dict

from app.analysis.corroboration import (
    build_claim_corroboration_assessment,
)
from app.analysis.merit import (
    MERIT_CORROBORATION_OVERLAY_VERSION,
    MERIT_CORROBORATION_SHADOW_MAX_BOOST,
    build_merit_corroboration_overlay,
)
from app.analysis.merit_score_release import (
    MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
    validate_merit_score_release_certificate,
)
from app.analysis.stance import (
    build_claim_stance_analysis,
)
from app.analysis.support import (
    build_claim_support_provenance,
)
from app.services.direct_stakeholder_independence_verifier import (
    DIRECT_STAKEHOLDER_INDEPENDENCE_BASIS,
    DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
    build_direct_stakeholder_independence_candidate,
)


LIVE_MERIT_RELEASE_RUNTIME_VERSION = (
    "live-merit-release-runtime-v2"
)

LIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT = 6.0

LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256 = (
    "1d279803e73cae6aedccc47e8e23f649c4e6b60b8d4d886e591eb7484e63ac53"
)

DIRECT_STAKEHOLDER_EVIDENCE_TYPE = (
    "direct_stakeholder_independence_reference"
)

DIRECT_STAKEHOLDER_REFERENCE_PREFIX = (
    "direct-stakeholder-independence:"
)


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _metadata(value: Any) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(value or "{}")
        )
    except Exception as exc:
        raise ValueError(
            "Live Merit lineage metadata "
            "contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise ValueError(
            "Live Merit lineage metadata "
            "must be a dictionary."
        )

    return parsed


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
        (bytes, bytearray),
    ):
        raise ValueError(
            "Live Merit certificate bytes must be bytes."
        )

    raw = bytes(raw)

    raw_sha256 = hashlib.sha256(
        raw
    ).hexdigest()

    payload = json.loads(
        raw.decode("utf-8")
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Live Merit certificate must "
            "be a dictionary."
        )

    validated = (
        validate_merit_score_release_certificate(
            payload
        )
    )

    if (
        _clean(
            validated.get(
                "version"
            )
        )
        != MERIT_SCORE_RELEASE_CERTIFICATE_VERSION
    ):
        raise ValueError(
            "Live Merit certificate version "
            "is unsupported."
        )

    certificate_sha256 = _clean(
        validated.get(
            "certificate_sha256"
        )
    )

    if (
        certificate_sha256
        != LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
    ):
        raise ValueError(
            "Live Merit certificate identity "
            "does not match the pinned release."
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
            "Live Merit certificate is not "
            "authorized for release."
        )

    policy = validated.get(
        "policy",
        {},
    )

    if (
        not isinstance(
            policy,
            dict,
        )
        or policy.get(
            "certificate_does_not_itself_activate_live_merit"
        )
        is not True
        or policy.get(
            "human_review_not_part_of_release_path"
        )
        is not True
    ):
        raise ValueError(
            "Live Merit certificate policy "
            "contract is incomplete."
        )

    return {
        "certificate": validated,
        "certificate_sha256": (
            certificate_sha256
        ),
        "raw_file_sha256": raw_sha256,
    }


def live_merit_release_cache_token(
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
            raw_sha256 = hashlib.sha256(
                raw
            ).hexdigest()
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
            LIVE_MERIT_RELEASE_RUNTIME_VERSION,
            str(
                int(
                    bool(
                        enabled
                    )
                )
            ),
            state,
            raw_sha256,
            LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256,
        ]
    )

    return hashlib.sha256(
        token_payload.encode(
            "utf-8"
        )
    ).hexdigest()


def _legacy_result(
    *,
    legacy_score: Dict[str, Any],
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

    return {
        "version": (
            LIVE_MERIT_RELEASE_RUNTIME_VERSION
        ),
        "status": "legacy_fallback",
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
        "legacy_total": (
            legacy_score.get(
                "total"
            )
        ),
        "live_total": (
            legacy_score.get(
                "total"
            )
        ),
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
                LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
            ),
        },
        "strict_independence": {
            "verified": False,
            "assertion_id": "",
            "evidence_id": "",
        },
        "score": copy.deepcopy(
            legacy_score
        ),
        "policy": {
            "certificate_required": True,
            "direct_stakeholder_lineage_required_for_positive_effect": True,
            "model_only_independence_never_enables_live_boost": True,
            "failure_preserves_exact_legacy_score": True,
            "no_network_calls": True,
            "no_gemini_calls": True,
        },
    }


def _primary_claim(
    *,
    evidence_bundle: Dict[str, Any],
    media_item_id: str,
) -> Dict[str, Any] | None:
    media_id = _clean(
        media_item_id
    )

    if not media_id:
        return None

    prefix = (
        "article-primary|"
        + media_id
        + "|"
    )

    matches = []

    for row in evidence_bundle.get(
        "claims",
        [],
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        if _clean(
            row.get(
                "canonical_key"
            )
        ).startswith(
            prefix
        ):
            matches.append(
                row
            )

    if len(
        matches
    ) != 1:
        return None

    return matches[0]


def _row_for_claim(
    state: Dict[str, Any],
    claim_id: str,
) -> Dict[str, Any] | None:
    rows = [
        row
        for row in state.get(
            "claims",
            [],
        )
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

    if len(
        rows
    ) != 1:
        return None

    return rows[0]


def _strict_direct_stakeholder_lineage(
    *,
    claim_id: str,
    support_row: Dict[str, Any],
    connection_factory,
) -> Dict[str, Any] | None:
    assertions = support_row.get(
        "qualifying_independence_assertions",
        [],
    )

    if not isinstance(
        assertions,
        list,
    ):
        return None

    for assertion in assertions:
        if not isinstance(
            assertion,
            dict,
        ):
            continue

        assertion_id = _clean(
            assertion.get(
                "id"
            )
        )

        evidence_id = _clean(
            assertion.get(
                "provenance_evidence_id"
            )
        )

        left_type = _key(
            assertion.get(
                "observation_a_type"
            )
        )
        right_type = _key(
            assertion.get(
                "observation_b_type"
            )
        )
        left_id = _clean(
            assertion.get(
                "observation_a_id"
            )
        )
        right_id = _clean(
            assertion.get(
                "observation_b_id"
            )
        )

        if (
            not assertion_id
            or not evidence_id
            or left_type
            != "source_observation"
            or right_type
            != "source_observation"
            or not left_id
            or not right_id
        ):
            continue

        conn = connection_factory()

        try:
            assertion_row = conn.execute(
                """
                SELECT *
                FROM observation_independence_assertions
                WHERE id = ?
                """,
                (
                    assertion_id,
                ),
            ).fetchone()

            evidence_row = conn.execute(
                """
                SELECT *
                FROM evidence_records
                WHERE id = ?
                """,
                (
                    evidence_id,
                ),
            ).fetchone()

        finally:
            conn.close()

        if (
            assertion_row is None
            or evidence_row is None
        ):
            continue

        assertion_record = dict(
            assertion_row
        )
        evidence_record = dict(
            evidence_row
        )

        if (
            _key(
                assertion_record.get(
                    "verification_status"
                )
            )
            != "verified"
            or _clean(
                assertion_record.get(
                    "provenance_evidence_id"
                )
            )
            != evidence_id
        ):
            continue

        persisted_a_source = _clean(
            assertion_record.get(
                "observation_a_source_observation_id"
            )
        )
        persisted_b_source = _clean(
            assertion_record.get(
                "observation_b_source_observation_id"
            )
        )
        persisted_a_reporter = _clean(
            assertion_record.get(
                "observation_a_reporter_observation_id"
            )
        )
        persisted_b_reporter = _clean(
            assertion_record.get(
                "observation_b_reporter_observation_id"
            )
        )

        if (
            {
                persisted_a_source,
                persisted_b_source,
            }
            != {
                left_id,
                right_id,
            }
            or persisted_a_reporter
            or persisted_b_reporter
        ):
            continue

        try:
            assertion_metadata = _metadata(
                assertion_record.get(
                    "metadata_json"
                )
            )
            evidence_metadata = _metadata(
                evidence_record.get(
                    "metadata_json"
                )
            )
        except ValueError:
            continue

        expected_common = {
            "verifier_version": (
                DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION
            ),
            "basis": (
                DIRECT_STAKEHOLDER_INDEPENDENCE_BASIS
            ),
            "machine_verified": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        }

        if any(
            assertion_metadata.get(
                key
            )
            != value
            for (
                key,
                value,
            )
            in expected_common.items()
        ):
            continue

        if (
            _key(
                evidence_record.get(
                    "verification_status"
                )
            )
            != "verified"
            or _key(
                evidence_record.get(
                    "evidence_type"
                )
            )
            != DIRECT_STAKEHOLDER_EVIDENCE_TYPE
            or _clean(
                evidence_record.get(
                    "subject_key"
                )
            )
            != (
                "merit-score-release|"
                + claim_id
            )
            or not _clean(
                evidence_record.get(
                    "reference_key"
                )
            ).startswith(
                DIRECT_STAKEHOLDER_REFERENCE_PREFIX
            )
        ):
            continue

        if any(
            evidence_metadata.get(
                key
            )
            != value
            for (
                key,
                value,
            )
            in expected_common.items()
        ):
            continue

        try:
            candidate_result = (
                build_direct_stakeholder_independence_candidate(
                    claim_id=claim_id,
                    left_observation_id=left_id,
                    right_observation_id=right_id,
                    connection_factory=(
                        connection_factory
                    ),
                )
            )
        except Exception:
            continue

        if (
            candidate_result.get(
                "status"
            )
            != "verified_direct_stakeholder_independence"
        ):
            continue

        candidate = candidate_result.get(
            "candidate",
            {},
        )

        if not isinstance(
            candidate,
            dict,
        ):
            continue

        if (
            candidate.get(
                "basis"
            )
            != DIRECT_STAKEHOLDER_INDEPENDENCE_BASIS
            or set(
                candidate.get(
                    "participant_roles",
                    [],
                )
            )
            != {
                "origin",
                "destination",
            }
            or len(
                set(
                    candidate.get(
                        "source_ids",
                        [],
                    )
                )
            )
            != 2
            or len(
                set(
                    candidate.get(
                        "entity_ids",
                        [],
                    )
                )
            )
            != 2
        ):
            continue

        if (
            sorted(
                candidate.get(
                    "observation_ids",
                    [],
                )
            )
            != sorted(
                [
                    left_id,
                    right_id,
                ]
            )
        ):
            continue

        if (
            sorted(
                evidence_metadata.get(
                    "observation_ids",
                    [],
                )
            )
            != sorted(
                candidate.get(
                    "observation_ids",
                    [],
                )
            )
            or sorted(
                evidence_metadata.get(
                    "source_ids",
                    [],
                )
            )
            != sorted(
                candidate.get(
                    "source_ids",
                    [],
                )
            )
            or sorted(
                evidence_metadata.get(
                    "entity_ids",
                    [],
                )
            )
            != sorted(
                candidate.get(
                    "entity_ids",
                    [],
                )
            )
            or set(
                evidence_metadata.get(
                    "participant_roles",
                    [],
                )
            )
            != {
                "origin",
                "destination",
            }
        ):
            continue

        authority_lineage = (
            evidence_metadata.get(
                "authority_lineage"
            )
        )

        if (
            not isinstance(
                authority_lineage,
                list,
            )
            or len(
                authority_lineage
            )
            != 2
        ):
            continue

        return {
            "verified": True,
            "assertion_id": (
                assertion_id
            ),
            "evidence_id": (
                evidence_id
            ),
            "verifier_version": (
                DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION
            ),
            "basis": (
                DIRECT_STAKEHOLDER_INDEPENDENCE_BASIS
            ),
            "source_ids": sorted(
                candidate.get(
                    "source_ids",
                    [],
                )
            ),
            "entity_ids": sorted(
                candidate.get(
                    "entity_ids",
                    [],
                )
            ),
            "participant_roles": sorted(
                candidate.get(
                    "participant_roles",
                    [],
                )
            ),
        }

    return None


def apply_certified_live_merit(
    *,
    enabled: bool,
    legacy_score: Dict[str, Any],
    evidence_bundle: Dict[str, Any] | None,
    media_item_id: str,
    certificate_path: Path,
    connection_factory,
    badge_resolver,
) -> Dict[str, Any]:
    if not isinstance(
        legacy_score,
        dict,
    ):
        raise ValueError(
            "Live Merit legacy score must "
            "be a dictionary."
        )

    if not enabled:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=False,
            reason="live_merit_disabled",
        )

    try:
        certificate = _read_certificate(
            certificate_path
        )
    except Exception as error:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason=(
                "certificate_invalid:"
                + type(
                    error
                ).__name__
            ),
        )

    if not isinstance(
        evidence_bundle,
        dict,
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="evidence_bundle_unavailable",
            certificate=certificate,
        )

    claim = _primary_claim(
        evidence_bundle=(
            evidence_bundle
        ),
        media_item_id=(
            media_item_id
        ),
    )

    if claim is None:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="primary_claim_not_unique",
            certificate=certificate,
        )

    claim_id = _clean(
        claim.get(
            "id"
        )
    )

    if not claim_id:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="primary_claim_id_missing",
            certificate=certificate,
        )

    try:
        stance_state = (
            build_claim_stance_analysis(
                evidence_bundle
            )
        )
        support_state = (
            build_claim_support_provenance(
                evidence_bundle
            )
        )
        corroboration_state = (
            build_claim_corroboration_assessment(
                support_state=(
                    support_state
                ),
                stance_state=(
                    stance_state
                ),
            )
        )

        overlay = (
            build_merit_corroboration_overlay(
                legacy_score=(
                    legacy_score
                ),
                corroboration_state=(
                    corroboration_state
                ),
                claim_id=(
                    claim_id
                ),
            )
        )

    except Exception as error:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason=(
                "evidence_derivation_failed:"
                + type(
                    error
                ).__name__
            ),
            certificate=certificate,
            claim_id=claim_id,
        )

    if (
        overlay.get(
            "version"
        )
        != MERIT_CORROBORATION_OVERLAY_VERSION
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="overlay_version_mismatch",
            certificate=certificate,
            claim_id=claim_id,
        )

    signal = _key(
        overlay.get(
            "signal"
        )
    )

    proposed = overlay.get(
        "proposed",
        {},
    )

    if not isinstance(
        proposed,
        dict,
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="overlay_adjustment_invalid",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    try:
        adjustment = float(
            proposed.get(
                "adjustment",
                0.0,
            )
            or 0.0
        )

        max_adjustment = float(
            proposed.get(
                "max_adjustment",
                0.0,
            )
            or 0.0
        )

    except (
        TypeError,
        ValueError,
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="overlay_adjustment_invalid",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    if adjustment <= 0.0:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="overlay_no_positive_effect",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    if signal != "verified_corroboration":
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="certified_signal_mismatch",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    if (
        abs(
            adjustment
            - LIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT
        )
        > 1e-9
        or abs(
            max_adjustment
            - LIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT
        )
        > 1e-9
        or abs(
            float(
                MERIT_CORROBORATION_SHADOW_MAX_BOOST
            )
            - LIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT
        )
        > 1e-9
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="certified_adjustment_mismatch",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    overlay_live = overlay.get(
        "live",
        {},
    )

    if (
        not isinstance(
            overlay_live,
            dict,
        )
        or overlay_live.get(
            "score_effect_enabled"
        )
        is not False
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="overlay_not_shadow_only",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    support_row = _row_for_claim(
        support_state,
        claim_id,
    )

    if support_row is None:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="support_state_unavailable",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    try:
        strict_lineage = (
            _strict_direct_stakeholder_lineage(
                claim_id=claim_id,
                support_row=support_row,
                connection_factory=connection_factory,
            )
        )

    except Exception as error:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason=(
                "strict_lineage_revalidation_failed:"
                + type(error).__name__
            ),
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    if strict_lineage is None:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason=(
                "strict_direct_stakeholder_lineage_missing"
            ),
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    try:
        legacy_total = float(
            legacy_score[
                "total"
            ]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="legacy_total_invalid",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    if not (
        0.0
        <= legacy_total
        <= 100.0
    ):
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason="legacy_total_invalid",
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    live_total_float = min(
        100.0,
        legacy_total
        + adjustment,
    )

    live_total = int(
        round(
            live_total_float
        )
    )

    score = copy.deepcopy(
        legacy_score
    )

    score[
        "total"
    ] = live_total

    try:
        live_badge = badge_resolver(
            live_total
        )

    except Exception as error:
        return _legacy_result(
            legacy_score=legacy_score,
            enabled=True,
            reason=(
                "score_application_failed:"
                + type(error).__name__
            ),
            certificate=certificate,
            claim_id=claim_id,
            signal=signal,
        )

    score[
        "badge"
    ] = live_badge

    components = score.get(
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
        "certified_corroboration_overlay"
    ] = round(
        adjustment,
        2,
    )

    score[
        "components"
    ] = components

    calculation = score.get(
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
        "legacy_total_before_certified_corroboration"
    ] = int(
        round(
            legacy_total
        )
    )

    calculation[
        "certified_corroboration_adjustment"
    ] = round(
        adjustment,
        2,
    )

    calculation[
        "final_total"
    ] = live_total

    score[
        "calculation"
    ] = calculation

    reasons = score.get(
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
        "Machine-verified independent "
        "direct-stakeholder corroboration: "
        f"+{int(round(adjustment))} "
        "certified Merit adjustment."
    )

    if live_reason not in reasons:
        reasons.append(
            live_reason
        )

    score[
        "reasons"
    ] = reasons[:10]

    return {
        "version": (
            LIVE_MERIT_RELEASE_RUNTIME_VERSION
        ),
        "status": "applied",
        "enabled": True,
        "score_effect_applied": True,
        "reason": (
            "authorized_direct_stakeholder_corroboration"
        ),
        "claim_id": claim_id,
        "signal": signal,
        "adjustment": round(
            adjustment,
            2,
        ),
        "legacy_total": int(
            round(
                legacy_total
            )
        ),
        "live_total": live_total,
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
                LIVE_MERIT_RELEASE_REQUIRED_CERTIFICATE_SHA256
            ),
        },
        "strict_independence": (
            strict_lineage
        ),
        "score": score,
        "policy": {
            "certificate_required": True,
            "direct_stakeholder_lineage_required_for_positive_effect": True,
            "model_only_independence_never_enables_live_boost": True,
            "dependency_same_publisher_or_contested_never_receive_positive_effect": True,
            "failure_preserves_exact_legacy_score": True,
            "no_network_calls": True,
            "no_gemini_calls": True,
        },
    }
