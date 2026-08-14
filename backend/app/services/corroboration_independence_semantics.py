from typing import Any, Dict

from app.analysis.independence_verification import (
    build_independence_verification_prompt,
    normalize_independence_verification_assessment,
)


CORROBORATION_INDEPENDENCE_GEMINI_VERSION = (
    "corroboration-independence-gemini-v1"
)

CORROBORATION_INDEPENDENCE_GEMINI_MODE = (
    "corroboration_independence_evidence"
)

CORROBORATION_INDEPENDENCE_GEMINI_MODEL = (
    "gemini-3.5-flash"
)


def assess_independence_pair_with_gemini(
    *,
    claim: Dict[str, Any],
    pair: Dict[str, Any],
    article_a_text: str,
    article_b_text: str,
    client: Any,
    client_key: str,
    generator,
) -> Dict[str, Any]:
    prompt = (
        build_independence_verification_prompt(
            claim=claim,
            pair=pair,
            article_a_text=(
                article_a_text
            ),
            article_b_text=(
                article_b_text
            ),
        )
    )

    claim_id = str(
        claim.get("id") or ""
    ).strip()

    pair_id = str(
        pair.get("pair_id") or ""
    ).strip()

    normalized_client_key = (
        str(
            client_key or "anonymous"
        ).strip()
        or "anonymous"
    )

    base = {
        "version": (
            CORROBORATION_INDEPENDENCE_GEMINI_VERSION
        ),
        "mode": (
            CORROBORATION_INDEPENDENCE_GEMINI_MODE
        ),
        "model": (
            CORROBORATION_INDEPENDENCE_GEMINI_MODEL
        ),
        "claim_id": claim_id,
        "pair_id": pair_id,
        "policy": {
            (
                "provider_output_is_not_"
                "trusted_without_normalization"
            ): True,
            (
                "provider_does_not_directly_"
                "create_assertions"
            ): True,
            (
                "provider_has_no_merit_effect"
            ): True,
        },
    }

    if client is None:
        return {
            **base,
            "status": "unavailable",
            "reason": (
                "gemini_unavailable"
            ),
            "error_type": "",
            "error": "",
            "assessment": None,
        }

    try:
        response = generator(
            client=client,
            client_key=(
                normalized_client_key
            ),
            mode=(
                CORROBORATION_INDEPENDENCE_GEMINI_MODE
            ),
            model=(
                CORROBORATION_INDEPENDENCE_GEMINI_MODEL
            ),
            contents=prompt,
        )

        raw = str(
            getattr(
                response,
                "text",
                "",
            )
            or ""
        ).strip()

        if not raw:
            raise ValueError(
                "Gemini returned an empty "
                "independence response."
            )

        assessment = (
            normalize_independence_verification_assessment(
                raw,
                claim_id=claim_id,
                pair_id=pair_id,
                article_a_text=(
                    article_a_text
                ),
                article_b_text=(
                    article_b_text
                ),
            )
        )

    except Exception as error:
        return {
            **base,
            "status": (
                "assessment_failed"
            ),
            "reason": (
                "independence_provider_or_"
                "parse_failure"
            ),
            "error_type": (
                type(error).__name__
            ),
            "error": str(
                error
            )[:240],
            "assessment": None,
        }

    return {
        **base,
        "status": "assessed",
        "reason": "",
        "error_type": "",
        "error": "",
        "assessment": assessment,
    }
