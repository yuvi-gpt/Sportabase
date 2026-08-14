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


CORROBORATION_SEMANTIC_BATCH_VERSION = (
    "corroboration-semantic-batch-v1"
)


def assess_candidate_collection_semantics_with_gemini(
    *,
    claim: Dict[str, Any],
    collection: Dict[str, Any],
    client: Any,
    client_key: str,
    generator,
    max_assessments: int = 8,
) -> Dict[str, Any]:
    if not isinstance(claim, dict):
        raise ValueError(
            "Semantic batch claim must be a dictionary."
        )

    if not isinstance(collection, dict):
        raise ValueError(
            "Semantic candidate collection must "
            "be a dictionary."
        )

    if (
        isinstance(max_assessments, bool)
        or not isinstance(max_assessments, int)
        or max_assessments < 1
        or max_assessments > 20
    ):
        raise ValueError(
            "Semantic assessment limit must be "
            "between 1 and 20."
        )

    canonical_text = str(
        claim.get("canonical_text") or ""
    ).strip()

    if not canonical_text:
        raise ValueError(
            "Claim canonical text is required "
            "for semantic batch assessment."
        )

    raw_candidates = collection.get(
        "resolved_candidates",
        [],
    )

    if not isinstance(raw_candidates, list):
        raw_candidates = []

    base = {
        "version": (
            CORROBORATION_SEMANTIC_BATCH_VERSION
        ),
        "claim_id": str(
            claim.get("id") or ""
        ).strip(),
        "collection_version": str(
            collection.get("version") or ""
        ).strip(),
        "policy": {
            (
                "candidate_failures_are_"
                "best_effort"
            ): True,
            (
                "semantic_support_does_not_"
                "establish_independence"
            ): True,
            (
                "semantic_batch_does_not_"
                "establish_corroboration"
            ): True,
            (
                "semantic_batch_has_no_"
                "merit_effect"
            ): True,
        },
    }

    resolved_candidates = []

    for candidate in raw_candidates:
        if not isinstance(candidate, dict):
            continue

        if (
            str(
                candidate.get(
                    "resolution_status"
                )
                or ""
            ).strip().lower()
            != "resolved"
        ):
            continue

        resolved_candidates.append(
            candidate
        )

    if not resolved_candidates:
        return {
            **base,
            "status": "no_resolved_candidates",
            "candidate_assessments": [],
            "counts": {
                "resolved_candidates": 0,
                "assessment_attempts": 0,
                "assessed": 0,
                "failed": 0,
                "unavailable": 0,
                "not_attempted": 0,
                "supports": 0,
                "contradictions": 0,
                "neutral_same_claim": 0,
                "explicit_dependencies": 0,
                "independence_established": 0,
                "corroboration_established": 0,
            },
        }

    rows = []

    assessed_count = 0
    failed_count = 0
    unavailable_count = 0
    not_attempted_count = 0

    support_count = 0
    contradiction_count = 0
    neutral_count = 0
    dependency_count = 0

    attempts = 0

    for index, candidate in enumerate(
        resolved_candidates
    ):
        candidate_url = str(
            candidate.get("final_url")
            or candidate.get("normalized_url")
            or candidate.get("url")
            or ""
        ).strip()

        provenance = {
            "candidate_url": candidate_url,
            "source_domain": str(
                candidate.get(
                    "final_source_domain"
                )
                or candidate.get(
                    "source_domain"
                )
                or ""
            ).strip(),
            "same_source_domain": bool(
                candidate.get(
                    "final_same_source_domain"
                )
                or candidate.get(
                    "same_source_domain"
                )
            ),
            "provider": str(
                candidate.get("provider") or ""
            ).strip(),
            "provider_rank": candidate.get(
                "provider_rank"
            ),
        }

        if index >= max_assessments:
            rows.append(
                {
                    **provenance,
                    "status": (
                        "not_assessed_limit"
                    ),
                    "semantic_result": None,
                }
            )

            not_attempted_count += 1
            continue

        attempts += 1

        try:
            result = (
                assess_candidate_semantics_with_gemini(
                    claim=claim,
                    candidate=candidate,
                    client=client,
                    client_key=client_key,
                    generator=generator,
                )
            )
        except Exception as error:
            rows.append(
                {
                    **provenance,
                    "status": (
                        "assessment_failed"
                    ),
                    "semantic_result": {
                        "status": (
                            "assessment_failed"
                        ),
                        "reason": (
                            "semantic_batch_"
                            "orchestration_failure"
                        ),
                        "error_type": (
                            type(error).__name__
                        ),
                        "error": str(
                            error
                        )[:240],
                        "assessment": None,
                    },
                }
            )

            failed_count += 1
            continue

        result_status = str(
            result.get("status") or ""
        ).strip()

        rows.append(
            {
                **provenance,
                "status": result_status,
                "semantic_result": result,
            }
        )

        if result_status == "assessed":
            assessed_count += 1

            assessment = result.get(
                "assessment"
            )

            if isinstance(
                assessment,
                dict,
            ):
                if assessment.get(
                    "support_present"
                ) is True:
                    support_count += 1

                if assessment.get(
                    "contradiction_present"
                ) is True:
                    contradiction_count += 1

                if (
                    assessment.get(
                        "claim_relevance"
                    )
                    == "same_claim"
                    and assessment.get(
                        "claim_stance"
                    )
                    == "neutral"
                ):
                    neutral_count += 1

                if assessment.get(
                    "explicit_dependency_present"
                ) is True:
                    dependency_count += 1

        elif result_status == "unavailable":
            unavailable_count += 1

        else:
            failed_count += 1

    if assessed_count:
        status = (
            "assessed_candidates_available"
        )

    elif (
        unavailable_count
        and not failed_count
    ):
        status = "semantic_provider_unavailable"

    else:
        status = "no_successful_assessments"

    return {
        **base,
        "status": status,
        "candidate_assessments": rows,
        "counts": {
            "resolved_candidates": len(
                resolved_candidates
            ),
            "assessment_attempts": attempts,
            "assessed": assessed_count,
            "failed": failed_count,
            "unavailable": unavailable_count,
            "not_attempted": (
                not_attempted_count
            ),
            "supports": support_count,
            "contradictions": (
                contradiction_count
            ),
            "neutral_same_claim": (
                neutral_count
            ),
            "explicit_dependencies": (
                dependency_count
            ),
            "independence_established": 0,
            "corroboration_established": 0,
        },
    }
