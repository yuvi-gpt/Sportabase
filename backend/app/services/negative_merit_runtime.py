from typing import Any, Dict

from app.analysis.negative_merit import (
    build_negative_merit_shadow,
)
from app.services.direct_stakeholder_contradiction_verifier import (
    persist_direct_stakeholder_contradiction_verification,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    persist_machine_verified_contradiction_semantics_verification,
)


NEGATIVE_MERIT_RUNTIME_VERSION = (
    "negative-merit-runtime-v2"
)


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _primary_claim(
    *,
    evidence_bundle: Dict[str, Any],
    media_item_id: str,
):
    prefix = (
        "article-primary|"
        + _clean(media_item_id)
        + "|"
    )

    matches = [
        row
        for row in evidence_bundle.get(
            "claims",
            [],
        )
        if (
            isinstance(row, dict)
            and _clean(
                row.get("canonical_key")
            ).startswith(prefix)
        )
    ]

    return (
        matches[0]
        if len(matches) == 1
        else None
    )


def _contradiction_observation_ids(
    *,
    evidence_bundle: Dict[str, Any],
    claim_id: str,
):
    values = set()

    for link in evidence_bundle.get(
        "claim_links",
        [],
    ):
        if not isinstance(
            link,
            dict,
        ):
            continue

        if (
            _clean(
                link.get("claim_id")
            )
            != claim_id
            or _key(
                link.get(
                    "relationship_type"
                )
            )
            != "contradicts"
        ):
            continue

        source_observation_id = _clean(
            link.get(
                "source_observation_id"
            )
        )

        if not source_observation_id:
            if (
                _key(
                    link.get("target_type")
                )
                == "source_observation"
            ):
                source_observation_id = (
                    _clean(
                        link.get(
                            "target_id"
                        )
                    )
                )

        if source_observation_id:
            values.add(
                source_observation_id
            )

    return sorted(values)


def _summary(
    verification: Dict[str, Any],
):
    evidence = verification.get(
        "evidence"
    )

    return {
        "status": verification.get(
            "status"
        ),
        "persisted": (
            verification.get(
                "persisted"
            )
            is True
        ),
        "evidence_id": (
            _clean(
                evidence.get("id")
            )
            if isinstance(
                evidence,
                dict,
            )
            else ""
        ),
    }


def run_negative_merit_shadow(
    *,
    legacy_score: Dict[str, Any],
    evidence_bundle: Dict[str, Any] | None,
    media_item_id: str,
    connection_factory,
) -> Dict[str, Any]:
    base = {
        "version": (
            NEGATIVE_MERIT_RUNTIME_VERSION
        ),
        "mode": "shadow",
        "live_merit_effect_enabled": False,
        "claim_truth_established": False,
        "provider_call_performed": False,
        "policy": {
            "no_network_calls": True,
            "no_gemini_calls": True,
            "absence_of_corroboration_is_not_false": True,
            "semantic_contradiction_alone_cannot_change_merit": True,
            "direct_authority_alone_is_not_calibration_eligible": True,
            "machine_verified_semantics_are_required_for_calibration": True,
            "live_negative_merit_is_disabled": True,
        },
    }

    if not isinstance(
        evidence_bundle,
        dict,
    ):
        return {
            **base,
            "status": (
                "evidence_bundle_unavailable"
            ),
            "claim_id": "",
            "contradiction_observation_ids": [],
            "verifications": [],
            "shadow": None,
        }

    claim = _primary_claim(
        evidence_bundle=evidence_bundle,
        media_item_id=media_item_id,
    )

    if claim is None:
        return {
            **base,
            "status": (
                "primary_claim_not_unique"
            ),
            "claim_id": "",
            "contradiction_observation_ids": [],
            "verifications": [],
            "shadow": None,
        }

    claim_id = _clean(
        claim.get("id")
    )

    if not claim_id:
        return {
            **base,
            "status": (
                "primary_claim_id_missing"
            ),
            "claim_id": "",
            "contradiction_observation_ids": [],
            "verifications": [],
            "shadow": None,
        }

    observation_ids = (
        _contradiction_observation_ids(
            evidence_bundle=(
                evidence_bundle
            ),
            claim_id=claim_id,
        )
    )

    verifications = []

    for observation_id in observation_ids:
        try:
            result = (
                persist_direct_stakeholder_contradiction_verification(
                    claim_id=claim_id,
                    observation_id=(
                        observation_id
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                )
            )

        except Exception as error:
            result = {
                "status": (
                    "verification_failed:"
                    + type(error).__name__
                ),
                "persisted": False,
                "evidence": None,
            }

        verifications.append(
            result
        )

    qualifying = [
        result
        for result in verifications
        if (
            isinstance(
                result,
                dict,
            )
            and result.get(
                "persisted"
            )
            is True
        )
    ]

    selected = (
        qualifying[0]
        if qualifying
        else None
    )

    semantic_verification = None

    if selected is not None:
        try:
            semantic_verification = (
                persist_machine_verified_contradiction_semantics_verification(
                    claim_id=(
                        claim_id
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                )
            )

        except Exception as error:
            semantic_verification = {
                "status": (
                    "semantic_verification_failed:"
                    + type(
                        error
                    ).__name__
                ),
                "persisted": False,
                "evidence": None,
            }

    shadow = (
        build_negative_merit_shadow(
            legacy_score=legacy_score,
            claim_id=claim_id,
            contradiction_verification=(
                selected
            ),
            semantic_verification=(
                semantic_verification
            ),
        )
    )

    eligible = bool(
        shadow.get(
            "proposed",
            {},
        ).get(
            "eligible_for_penalty_calibration",
            False,
        )
    )

    return {
        **base,
        "status": (
            "negative_evidence_calibration_eligible"
            if eligible
            else "no_certified_negative_evidence"
        ),
        "claim_id": claim_id,
        "contradiction_observation_ids": (
            observation_ids
        ),
        "verifications": [
            _summary(row)
            for row in verifications
        ],
        "semantic_verification": (
            _summary(
                semantic_verification
            )
            if isinstance(
                semantic_verification,
                dict,
            )
            else None
        ),
        "shadow": shadow,
    }


def refresh_negative_merit_after_intelligence(
    *,
    prior_result: Dict[str, Any],
    intelligence_shadow: Dict[str, Any] | None,
    legacy_score: Dict[str, Any],
    media_item_id: str,
    evidence_state_loader,
    connection_factory,
    runtime_runner=run_negative_merit_shadow,
) -> Dict[str, Any]:
    prior = (
        prior_result
        if isinstance(
            prior_result,
            dict,
        )
        else {
            "version": (
                NEGATIVE_MERIT_RUNTIME_VERSION
            ),
            "status": "failed_closed",
            "mode": "shadow",
            "live_merit_effect_enabled": False,
            "claim_truth_established": False,
            "provider_call_performed": False,
        }
    )

    if (
        not isinstance(
            intelligence_shadow,
            dict,
        )
        or _key(
            intelligence_shadow.get(
                "status"
            )
        )
        != "completed"
    ):
        return prior

    normalized_media_item_id = _clean(
        media_item_id
    )

    if not normalized_media_item_id:
        return prior

    try:
        evidence_state = (
            evidence_state_loader(
                media_item_id=(
                    normalized_media_item_id
                ),
            )
        )

        if not isinstance(
            evidence_state,
            dict,
        ):
            return prior

        evidence_bundle = (
            evidence_state.get(
                "bundle"
            )
        )

        if not isinstance(
            evidence_bundle,
            dict,
        ):
            return prior

        refreshed = runtime_runner(
            legacy_score=legacy_score,
            evidence_bundle=(
                evidence_bundle
            ),
            media_item_id=(
                normalized_media_item_id
            ),
            connection_factory=(
                connection_factory
            ),
        )

        if not isinstance(
            refreshed,
            dict,
        ):
            return prior

    except Exception:
        return prior

    result = dict(
        refreshed
    )

    result[
        "refresh"
    ] = {
        "performed": True,
        "source": (
            "post_article_intelligence_shadow"
        ),
        "prior_status": _clean(
            prior.get(
                "status"
            )
        ),
        "provider_call_performed": False,
        "live_merit_effect_enabled": False,
        "claim_truth_established": False,
    }

    return result
