from typing import (
    Any,
    Dict,
)


ARTICLE_INTELLIGENCE_PUBLIC_VERSION = (
    "article-intelligence-public-v1"
)


_SIGNAL_COPY = {
    "verified_corroboration": {
        "label": "Verified independent support",
        "detail": (
            "Sportabase found explicit support from "
            "multiple sources and verified that the "
            "supporting reporting is independent."
        ),
        "independence_status": "established",
        "corroboration_status": "established",
    },
    "verified_corroboration_contested": {
        "label": "Corroborated but contested",
        "detail": (
            "Independent supporting evidence exists, "
            "but explicit contradictory reporting is "
            "also present."
        ),
        "independence_status": "established",
        "corroboration_status": "contested",
    },
    "support_dependency_present": {
        "label": "Support is not independent",
        "detail": (
            "Supporting reports are present, but a "
            "recorded reporting dependency prevents "
            "them from counting as independent "
            "corroboration."
        ),
        "independence_status": "not_established",
        "corroboration_status": "not_established",
    },
    "support_independence_unknown": {
        "label": "Independence still unverified",
        "detail": (
            "Multiple sources support the claim, but "
            "Sportabase has not verified that their "
            "reporting is independent."
        ),
        "independence_status": "unknown",
        "corroboration_status": "not_established",
    },
    "no_verified_corroboration_boost": {
        "label": "No verified corroboration yet",
        "detail": (
            "Sportabase does not currently have enough "
            "verified independent support to establish "
            "corroboration."
        ),
        "independence_status": "unknown",
        "corroboration_status": "not_established",
    },
}


_SKIP_COPY = {
    "shadow_disabled": (
        "Cross-source evidence checking is not enabled "
        "for this analysis."
    ),
    "news_api_key_missing": (
        "Cross-source evidence search is temporarily "
        "unavailable."
    ),
    "gemini_unavailable": (
        "Cross-source semantic verification is "
        "temporarily unavailable."
    ),
    "article_text_missing": (
        "There was not enough article text to run the "
        "cross-source evidence check."
    ),
    "article_type_not_claim_seeded": (
        "This article type does not contain a suitable "
        "primary factual claim for cross-source "
        "corroboration."
    ),
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


def _count(
    value: Any,
) -> int:
    try:
        result = int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0

    return max(
        result,
        0,
    )


def _base() -> Dict[str, Any]:
    return {
        "version": (
            ARTICLE_INTELLIGENCE_PUBLIC_VERSION
        ),
        "status": "unavailable",
        "label": "Evidence check unavailable",
        "detail": (
            "Cross-source evidence intelligence "
            "was not available for this analysis."
        ),
        "signal": "",
        "candidate_count": 0,
        "verification_pairs": 0,
        "corroboration_status": "unknown",
        "independence_status": "unknown",
        "contested": False,
        "provisional": True,
        "affects_merit_score": False,
    }


def build_article_intelligence_public_summary(
    shadow: Any,
) -> Dict[str, Any]:
    result = _base()

    if not isinstance(
        shadow,
        dict,
    ):
        return result

    shadow_status = _key(
        shadow.get(
            "status"
        )
    )

    if shadow_status == "completed":
        signal = _key(
            shadow.get(
                "signal"
            )
        )

        copy = _SIGNAL_COPY.get(
            signal,
            _SIGNAL_COPY[
                "no_verified_corroboration_boost"
            ],
        )

        candidate_count = _count(
            shadow.get(
                "candidate_count"
            )
        )

        verification_pairs = _count(
            shadow.get(
                "verification_pairs"
            )
        )

        contested = (
            signal
            == "verified_corroboration_contested"
        )

        return {
            "version": (
                ARTICLE_INTELLIGENCE_PUBLIC_VERSION
            ),
            "status": "available",
            "label": copy[
                "label"
            ],
            "detail": copy[
                "detail"
            ],
            "signal": signal,
            "candidate_count": (
                candidate_count
            ),
            "verification_pairs": (
                verification_pairs
            ),
            "corroboration_status": (
                copy[
                    "corroboration_status"
                ]
            ),
            "independence_status": (
                copy[
                    "independence_status"
                ]
            ),
            "contested": contested,
            "provisional": True,
            "affects_merit_score": False,
        }

    if (
        shadow_status
        in {
            "skipped",
            "not_claim_bearing",
        }
    ):
        reason = _key(
            shadow.get(
                "reason"
            )
        )

        result[
            "detail"
        ] = _SKIP_COPY.get(
            reason,
            (
                "Cross-source evidence intelligence "
                "was not available for this article."
            ),
        )

        if (
            reason
            == "article_type_not_claim_seeded"
        ):
            result[
                "label"
            ] = "No claim-level evidence check"

        return result

    if shadow_status == "failed":
        result[
            "detail"
        ] = (
            "Sportabase could not complete the "
            "cross-source evidence check. The normal "
            "article analysis is still available."
        )

        return result

    return result
