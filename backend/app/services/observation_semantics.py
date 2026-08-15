from typing import (
    Any,
    Dict,
    Optional,
)


from app.analysis.observation_semantics import (
    build_claim_observation_semantic_prompt,
    normalize_claim_observation_semantics,
)


OBSERVATION_SEMANTIC_GEMINI_VERSION = (
    "claim-observation-semantic-gemini-v1"
)

OBSERVATION_SEMANTIC_GEMINI_MODE = (
    "claim_observation_semantics"
)

OBSERVATION_SEMANTIC_GEMINI_MODEL = (
    "gemini-3.5-flash"
)


def assess_claim_observation_semantics_with_gemini(
    *,
    claim: Dict[str, Any],
    source: Dict[str, Any],
    context: Optional[
        Dict[str, Any]
    ] = None,
    client: Any,
    client_key: str,
    generator,
) -> Dict[str, Any]:
    prompt = (
        build_claim_observation_semantic_prompt(
            claim=claim,
            source=source,
            context=context,
        )
    )

    claim_id = str(
        claim.get(
            "id"
        )
        or claim.get(
            "claim_id"
        )
        or ""
    ).strip()

    source_url = str(
        source.get(
            "final_url"
        )
        or source.get(
            "normalized_url"
        )
        or source.get(
            "url"
        )
        or ""
    ).strip()

    normalized_client_key = (
        str(
            client_key
            or "anonymous"
        ).strip()
        or "anonymous"
    )

    base = {
        "version": (
            OBSERVATION_SEMANTIC_GEMINI_VERSION
        ),
        "mode": (
            OBSERVATION_SEMANTIC_GEMINI_MODE
        ),
        "model": (
            OBSERVATION_SEMANTIC_GEMINI_MODEL
        ),
        "claim_id": (
            claim_id
        ),
        "source_url": (
            source_url
        ),
        "policy": {
            "provider_failure_is_best_effort": True,
            "model_output_is_model_assisted": True,
            "model_output_is_not_training_truth": True,
            "no_live_merit_effect": True,
        },
    }

    if client is None:
        return {
            **base,
            "status": (
                "unavailable"
            ),
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
                OBSERVATION_SEMANTIC_GEMINI_MODE
            ),
            model=(
                OBSERVATION_SEMANTIC_GEMINI_MODEL
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
                "observation semantic response."
            )

        assessment = (
            normalize_claim_observation_semantics(
                raw,
                claim_id=claim_id,
                source_url=(
                    source_url
                ),
                context=context,
                evaluator_id=(
                    OBSERVATION_SEMANTIC_GEMINI_VERSION
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
                "observation_semantic_"
                "provider_or_parse_failure"
            ),
            "error_type": (
                type(
                    error
                ).__name__
            ),
            "error": str(
                error
            )[
                :240
            ],
            "assessment": None,
        }

    return {
        **base,
        "status": "assessed",
        "reason": "",
        "error_type": "",
        "error": "",
        "assessment": (
            assessment
        ),
    }
