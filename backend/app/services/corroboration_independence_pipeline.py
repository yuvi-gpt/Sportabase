from typing import Any, Dict

from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
    load_evidence_analysis_bundle_for_media_item,
)
from app.analysis.independence_verification import (
    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION,
)
from app.services.corroboration_independence import (
    CORROBORATION_INDEPENDENCE_PLAN_VERSION,
)
from app.services.corroboration_independence_materialization import (
    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION,
    materialize_verified_independence_evidence,
)
from app.services.corroboration_independence_semantics import (
    CORROBORATION_INDEPENDENCE_GEMINI_VERSION,
    assess_independence_pair_with_gemini,
)


CORROBORATION_INDEPENDENCE_PIPELINE_VERSION = (
    "corroboration-independence-pipeline-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _normalized_url(
    value: Any,
    *,
    normalize_url,
) -> str:
    raw = _clean(
        value
    )

    if not raw:
        return ""

    return _clean(
        normalize_url(
            raw
        )
    )


def _article_text_map(
    article_texts_by_url: Dict[str, str],
    *,
    normalize_url,
) -> Dict[str, str]:
    if not isinstance(
        article_texts_by_url,
        dict,
    ):
        raise ValueError(
            "Independence article text map "
            "must be a dictionary."
        )

    normalized = {}

    for raw_url, raw_text in (
        article_texts_by_url.items()
    ):
        url = _normalized_url(
            raw_url,
            normalize_url=(
                normalize_url
            ),
        )

        text = _clean(
            raw_text
        )

        if not url or not text:
            continue

        existing = normalized.get(
            url
        )

        if (
            existing is not None
            and existing != text
        ):
            raise ValueError(
                "Conflicting article text exists "
                "for the same normalized URL."
            )

        normalized[url] = text

    return normalized


def _require_semantic_result(
    *,
    result: Any,
    claim_id: str,
    pair_id: str,
) -> Dict[str, Any]:
    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Independence semantic result "
            "must be a dictionary."
        )

    if (
        _clean(
            result.get(
                "version"
            )
        )
        != CORROBORATION_INDEPENDENCE_GEMINI_VERSION
    ):
        raise ValueError(
            "Unsupported independence semantic "
            "result version."
        )

    if (
        _clean(
            result.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Independence semantic result "
            "claim ID does not match."
        )

    if (
        _clean(
            result.get(
                "pair_id"
            )
        )
        != pair_id
    ):
        raise ValueError(
            "Independence semantic result "
            "pair ID does not match."
        )

    return result


def _require_materialization_result(
    *,
    result: Any,
    claim_id: str,
    pair_id: str,
) -> Dict[str, Any]:
    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Independence materialization "
            "result must be a dictionary."
        )

    if (
        _clean(
            result.get(
                "version"
            )
        )
        != CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
    ):
        raise ValueError(
            "Unsupported independence "
            "materialization result version."
        )

    if (
        _clean(
            result.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Independence materialization "
            "claim ID does not match."
        )

    if (
        _clean(
            result.get(
                "pair_id"
            )
        )
        != pair_id
    ):
        raise ValueError(
            "Independence materialization "
            "pair ID does not match."
        )

    return result


def run_independence_verification_batch(
    *,
    claim: Dict[str, Any],
    plan: Dict[str, Any],
    media_item_id: str,
    article_texts_by_url: Dict[str, str],
    normalize_url,
    client: Any,
    client_key: str,
    generator,
    connection_factory,
    assessor=(
        assess_independence_pair_with_gemini
    ),
    materializer=(
        materialize_verified_independence_evidence
    ),
    evidence_loader=(
        load_evidence_analysis_bundle_for_media_item
    ),
) -> Dict[str, Any]:
    if not isinstance(
        claim,
        dict,
    ):
        raise ValueError(
            "Independence verification batch "
            "claim must be a dictionary."
        )

    if not isinstance(
        plan,
        dict,
    ):
        raise ValueError(
            "Independence verification batch "
            "plan must be a dictionary."
        )

    claim_id = _clean(
        claim.get("id")
    )

    media_id = _clean(
        media_item_id
    )

    if not claim_id:
        raise ValueError(
            "Independence verification batch "
            "claim ID is required."
        )

    if not media_id:
        raise ValueError(
            "Independence verification batch "
            "media item ID is required."
        )

    if (
        _clean(
            plan.get(
                "version"
            )
        )
        != CORROBORATION_INDEPENDENCE_PLAN_VERSION
    ):
        raise ValueError(
            "Unsupported independence "
            "verification plan version."
        )

    if (
        _clean(
            plan.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Independence verification plan "
            "claim ID does not match."
        )

    text_by_url = (
        _article_text_map(
            article_texts_by_url,
            normalize_url=(
                normalize_url
            ),
        )
    )

    raw_pairs = plan.get(
        "pairs",
        [],
    )

    if not isinstance(
        raw_pairs,
        list,
    ):
        raise ValueError(
            "Independence verification plan "
            "pairs must be a list."
        )

    pairs = []

    for pair in raw_pairs:
        if not isinstance(
            pair,
            dict,
        ):
            raise ValueError(
                "Independence verification "
                "pair must be a dictionary."
            )

        pair_id = _clean(
            pair.get(
                "pair_id"
            )
        )

        if not pair_id:
            raise ValueError(
                "Independence verification "
                "pair ID is required."
            )

        if (
            _clean(
                pair.get(
                    "claim_id"
                )
            )
            != claim_id
        ):
            raise ValueError(
                "Independence verification "
                "pair claim ID does not match."
            )

        if (
            _clean(
                pair.get(
                    "status"
                )
            ).lower()
            != "verification_required"
        ):
            raise ValueError(
                "Independence verification "
                "batch received a pair that "
                "does not require verification."
            )

        pairs.append(
            pair
        )

    pairs.sort(
        key=lambda row: (
            _clean(
                row.get(
                    "pair_id"
                )
            )
        )
    )

    results = []

    counts = {
        "verification_pairs": (
            len(pairs)
        ),
        "article_text_ready": 0,
        "article_text_missing": 0,
        "semantic_assessed": 0,
        "semantic_unavailable": 0,
        "semantic_failed": 0,
        "positive_independence_evidence": 0,
        "non_positive_assessments": 0,
        "materialization_attempts": 0,
        "verified_materialized": 0,
        "already_materialized": 0,
        "not_materialized": 0,
    }

    for pair in pairs:
        pair_id = _clean(
            pair.get(
                "pair_id"
            )
        )

        url_a = _normalized_url(
            pair.get(
                "provenance_url_a"
            ),
            normalize_url=(
                normalize_url
            ),
        )

        url_b = _normalized_url(
            pair.get(
                "provenance_url_b"
            ),
            normalize_url=(
                normalize_url
            ),
        )

        article_a_text = (
            text_by_url.get(
                url_a,
                "",
            )
        )

        article_b_text = (
            text_by_url.get(
                url_b,
                "",
            )
        )

        missing = []

        if not article_a_text:
            missing.append(
                "article_a"
            )

        if not article_b_text:
            missing.append(
                "article_b"
            )

        if missing:
            counts[
                "article_text_missing"
            ] += 1

            results.append(
                {
                    "pair_id": (
                        pair_id
                    ),
                    "status": (
                        "article_text_missing"
                    ),
                    "missing": (
                        missing
                    ),
                    "semantic_result": (
                        None
                    ),
                    "materialization": (
                        None
                    ),
                }
            )

            continue

        counts[
            "article_text_ready"
        ] += 1

        semantic_result = (
            assessor(
                claim=claim,
                pair=pair,
                article_a_text=(
                    article_a_text
                ),
                article_b_text=(
                    article_b_text
                ),
                client=client,
                client_key=(
                    client_key
                ),
                generator=(
                    generator
                ),
            )
        )

        semantic_result = (
            _require_semantic_result(
                result=(
                    semantic_result
                ),
                claim_id=(
                    claim_id
                ),
                pair_id=(
                    pair_id
                ),
            )
        )

        semantic_status = _clean(
            semantic_result.get(
                "status"
            )
        ).lower()

        if (
            semantic_status
            == "unavailable"
        ):
            counts[
                "semantic_unavailable"
            ] += 1

            results.append(
                {
                    "pair_id": (
                        pair_id
                    ),
                    "status": (
                        "semantic_unavailable"
                    ),
                    "missing": [],
                    "semantic_result": (
                        semantic_result
                    ),
                    "materialization": (
                        None
                    ),
                }
            )

            continue

        if (
            semantic_status
            == "assessment_failed"
        ):
            counts[
                "semantic_failed"
            ] += 1

            results.append(
                {
                    "pair_id": (
                        pair_id
                    ),
                    "status": (
                        "semantic_failed"
                    ),
                    "missing": [],
                    "semantic_result": (
                        semantic_result
                    ),
                    "materialization": (
                        None
                    ),
                }
            )

            continue

        if (
            semantic_status
            != "assessed"
        ):
            raise ValueError(
                "Unsupported independence "
                "semantic result status."
            )

        counts[
            "semantic_assessed"
        ] += 1

        assessment = (
            semantic_result.get(
                "assessment"
            )
        )

        if not isinstance(
            assessment,
            dict,
        ):
            raise ValueError(
                "Assessed independence semantic "
                "result requires an assessment."
            )

        if (
            _clean(
                assessment.get(
                    "version"
                )
            )
            != CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION
        ):
            raise ValueError(
                "Unsupported independence "
                "assessment version."
            )

        positive = bool(
            _clean(
                assessment.get(
                    "status"
                )
            ).lower()
            == "positive_independence_evidence"
            and assessment.get(
                (
                    "positive_independence_"
                    "evidence_present"
                )
            )
            is True
        )

        if not positive:
            counts[
                "non_positive_assessments"
            ] += 1

            results.append(
                {
                    "pair_id": (
                        pair_id
                    ),
                    "status": (
                        "not_positive"
                    ),
                    "missing": [],
                    "semantic_result": (
                        semantic_result
                    ),
                    "materialization": (
                        None
                    ),
                }
            )

            continue

        counts[
            "positive_independence_evidence"
        ] += 1

        counts[
            "materialization_attempts"
        ] += 1

        materialization = (
            materializer(
                claim=claim,
                pair=pair,
                semantic_result=(
                    semantic_result
                ),
                media_item_id=(
                    media_id
                ),
                article_a_text=(
                    article_a_text
                ),
                article_b_text=(
                    article_b_text
                ),
                normalize_url=(
                    normalize_url
                ),
                connection_factory=(
                    connection_factory
                ),
            )
        )

        materialization = (
            _require_materialization_result(
                result=(
                    materialization
                ),
                claim_id=(
                    claim_id
                ),
                pair_id=(
                    pair_id
                ),
            )
        )

        materialization_status = _clean(
            materialization.get(
                "status"
            )
        ).lower()

        if (
            materialization_status
            == (
                "materialized_verified_"
                "independence"
            )
        ):
            counts[
                "verified_materialized"
            ] += 1

        elif (
            materialization_status
            == "already_materialized"
        ):
            counts[
                "already_materialized"
            ] += 1

        elif (
            materialization_status
            == "not_materialized"
        ):
            counts[
                "not_materialized"
            ] += 1

        else:
            raise ValueError(
                "Unsupported independence "
                "materialization status."
            )

        results.append(
            {
                "pair_id": (
                    pair_id
                ),
                "status": (
                    materialization_status
                ),
                "missing": [],
                "semantic_result": (
                    semantic_result
                ),
                "materialization": (
                    materialization
                ),
            }
        )

    final_bundle = evidence_loader(
        media_item_id=(
            media_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        final_bundle,
        dict,
    ):
        raise ValueError(
            "Final evidence bundle must "
            "be a dictionary."
        )

    if (
        _clean(
            final_bundle.get(
                "version"
            )
        )
        != EVIDENCE_ANALYSIS_BUNDLE_VERSION
    ):
        raise ValueError(
            "Unsupported final evidence "
            "bundle version."
        )

    return {
        "version": (
            CORROBORATION_INDEPENDENCE_PIPELINE_VERSION
        ),
        "status": (
            "completed"
            if pairs
            else "no_verification_pairs"
        ),
        "claim_id": (
            claim_id
        ),
        "media_item_id": (
            media_id
        ),
        "plan_version": (
            CORROBORATION_INDEPENDENCE_PLAN_VERSION
        ),
        "results": (
            results
        ),
        "counts": (
            counts
        ),
        "evidence_bundle": (
            final_bundle
        ),
        "policy": {
            (
                "missing_article_text_does_"
                "not_establish_independence"
            ): True,
            (
                "semantic_failure_is_best_"
                "effort_per_pair"
            ): True,
            (
                "only_positive_grounded_"
                "assessment_reaches_"
                "materialization"
            ): True,
            (
                "materialization_errors_are_"
                "not_silenced"
            ): True,
            (
                "final_evidence_is_reloaded_"
                "after_batch"
            ): True,
            (
                "batch_does_not_decide_"
                "corroboration"
            ): True,
            (
                "batch_has_no_merit_effect"
            ): True,
        },
    }
