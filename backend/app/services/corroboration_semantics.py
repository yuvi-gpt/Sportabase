from typing import Any, Dict

from app.analysis.candidate_semantics import (
    build_candidate_semantic_prompt,
    normalize_candidate_semantic_assessment,
)


CORROBORATION_SEMANTIC_GEMINI_VERSION = (
    "corroboration-semantic-gemini-v1"
)

CORROBORATION_SEMANTIC_GEMINI_MODE = (
    "corroboration_candidate_semantics"
)

CORROBORATION_SEMANTIC_GEMINI_MODEL = (
    "gemini-3.5-flash"
)


def assess_candidate_semantics_with_gemini(
    *,
    claim: Dict[str, Any],
    candidate: Dict[str, Any],
    client: Any,
    client_key: str,
    generator,
) -> Dict[str, Any]:
    # Build first so malformed/unresolved inputs fail
    # deterministically instead of being hidden by
    # provider availability.
    prompt = build_candidate_semantic_prompt(
        claim=claim,
        candidate=candidate,
    )

    normalized_client_key = str(
        client_key or "anonymous"
    ).strip() or "anonymous"

    base = {
        "version": (
            CORROBORATION_SEMANTIC_GEMINI_VERSION
        ),
        "mode": (
            CORROBORATION_SEMANTIC_GEMINI_MODE
        ),
        "model": (
            CORROBORATION_SEMANTIC_GEMINI_MODEL
        ),
        "claim_id": str(
            claim.get("id") or ""
        ).strip(),
        "candidate_url": str(
            candidate.get("final_url")
            or candidate.get("normalized_url")
            or candidate.get("url")
            or ""
        ).strip(),
    }

    if client is None:
        return {
            **base,
            "status": "unavailable",
            "reason": "gemini_unavailable",
            "error_type": "",
            "error": "",
            "assessment": None,
        }

    try:
        response = generator(
            client=client,
            client_key=normalized_client_key,
            mode=(
                CORROBORATION_SEMANTIC_GEMINI_MODE
            ),
            model=(
                CORROBORATION_SEMANTIC_GEMINI_MODEL
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
                "candidate semantic response."
            )

        assessment = (
            normalize_candidate_semantic_assessment(
                raw,
                claim_id=base["claim_id"],
                candidate_url=(
                    base["candidate_url"]
                ),
            )
        )

    except Exception as error:
        return {
            **base,
            "status": "assessment_failed",
            "reason": (
                "semantic_provider_or_parse_failure"
            ),
            "error_type": (
                type(error).__name__
            ),
            "error": str(error)[:240],
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
