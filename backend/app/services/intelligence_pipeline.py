from typing import Any, Dict

from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
)
from app.analysis.merit import (
    MERIT_CORROBORATION_OVERLAY_VERSION,
    build_merit_corroboration_overlay,
)
from app.services.corroboration_independence import (
    CORROBORATION_INDEPENDENCE_PLAN_VERSION,
    build_corroboration_independence_plan,
)
from app.services.corroboration_independence_pipeline import (
    CORROBORATION_INDEPENDENCE_PIPELINE_VERSION,
    run_independence_verification_batch,
)
from app.services.corroboration_pipeline import (
    CORROBORATION_PIPELINE_VERSION,
    run_claim_corroboration_pipeline,
)
from app.services.corroboration_resolution import (
    CORROBORATION_RESOLUTION_VERSION,
    resolve_corroboration_from_independence_batch,
)


SPORTABASE_INTELLIGENCE_PIPELINE_VERSION = (
    "sportabase-intelligence-pipeline-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _score(
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
            f"{label} must be between "
            "0 and 100."
        )

    return result


def _require_result(
    *,
    stage_name: str,
    result: Any,
    expected_version: str,
) -> Dict[str, Any]:
    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            f"{stage_name} result must "
            "be a dictionary."
        )

    if (
        _clean(
            result.get(
                "version"
            )
        )
        != expected_version
    ):
        raise ValueError(
            f"{stage_name} returned an "
            "unsupported version."
        )

    return result


def _require_claim_media(
    *,
    stage_name: str,
    result: Dict[str, Any],
    claim_id: str,
    media_item_id: str,
) -> None:
    if (
        _clean(
            result.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            f"{stage_name} claim ID "
            "does not match."
        )

    if (
        _clean(
            result.get(
                "media_item_id"
            )
        )
        != media_item_id
    ):
        raise ValueError(
            f"{stage_name} media item "
            "ID does not match."
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


def _add_article_text(
    mapping: Dict[str, str],
    *,
    url: Any,
    text: Any,
    normalize_url,
) -> None:
    normalized_url = (
        _normalized_url(
            url,
            normalize_url=(
                normalize_url
            ),
        )
    )

    normalized_text = _clean(
        text
    )

    if (
        not normalized_url
        or not normalized_text
    ):
        return

    existing = mapping.get(
        normalized_url
    )

    if (
        existing is not None
        and existing
        != normalized_text
    ):
        raise ValueError(
            "Conflicting article text exists "
            "for the same normalized URL."
        )

    mapping[
        normalized_url
    ] = normalized_text


def build_pipeline_article_text_map(
    *,
    source_url: str,
    source_article_text: str,
    candidate_collection: Dict[str, Any],
    normalize_url,
) -> Dict[str, str]:
    if not isinstance(
        candidate_collection,
        dict,
    ):
        raise ValueError(
            "Candidate collection must "
            "be a dictionary."
        )

    article_texts = {}

    _add_article_text(
        article_texts,
        url=source_url,
        text=source_article_text,
        normalize_url=normalize_url,
    )

    resolved_candidates = (
        candidate_collection.get(
            "resolved_candidates",
            [],
        )
    )

    if not isinstance(
        resolved_candidates,
        list,
    ):
        raise ValueError(
            "Resolved corroboration "
            "candidates must be a list."
        )

    for candidate in (
        resolved_candidates
    ):
        if not isinstance(
            candidate,
            dict,
        ):
            continue

        candidate_url = (
            candidate.get(
                "final_url"
            )
            or candidate.get(
                "normalized_url"
            )
            or candidate.get(
                "url"
            )
        )

        _add_article_text(
            article_texts,
            url=candidate_url,
            text=candidate.get(
                "text"
            ),
            normalize_url=normalize_url,
        )

    return article_texts


def run_sportabase_intelligence_pipeline(
    *,
    claim: Dict[str, Any],
    media_item_id: str,
    source_url: str,
    source_article_text: str,
    legacy_score: Dict[str, Any],
    news_api_key: str,
    normalize_url,
    domain_resolver,
    fetch_article,
    extract_article,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    connection_factory,
    freshness: str = "pw",
    max_candidates: int = 8,
    results_per_query: int = 20,
    max_assessments: int = 8,
    corroboration_runner=(
        run_claim_corroboration_pipeline
    ),
    independence_plan_builder=(
        build_corroboration_independence_plan
    ),
    independence_batch_runner=(
        run_independence_verification_batch
    ),
    corroboration_resolver=(
        resolve_corroboration_from_independence_batch
    ),
    merit_overlay_builder=(
        build_merit_corroboration_overlay
    ),
) -> Dict[str, Any]:
    if not isinstance(
        claim,
        dict,
    ):
        raise ValueError(
            "Intelligence pipeline claim "
            "must be a dictionary."
        )

    claim_id = _clean(
        claim.get(
            "id"
        )
    )

    media_id = _clean(
        media_item_id
    )

    normalized_source_url = _clean(
        source_url
    )

    normalized_source_text = _clean(
        source_article_text
    )

    if not claim_id:
        raise ValueError(
            "Intelligence pipeline claim "
            "ID is required."
        )

    if not media_id:
        raise ValueError(
            "Intelligence pipeline media "
            "item ID is required."
        )

    if not normalized_source_url:
        raise ValueError(
            "Intelligence pipeline source "
            "URL is required."
        )

    if not normalized_source_text:
        raise ValueError(
            "Intelligence pipeline source "
            "article text is required."
        )

    if not isinstance(
        legacy_score,
        dict,
    ):
        raise ValueError(
            "Intelligence pipeline legacy "
            "score must be a dictionary."
        )

    legacy_total = _score(
        legacy_score.get(
            "total"
        ),
        label=(
            "Legacy Merit total"
        ),
    )

    # -----------------------------------------------------
    # 1. Discover + semantically assess + materialize
    #    candidate support evidence.
    # -----------------------------------------------------

    corroboration_pipeline = (
        corroboration_runner(
            claim=claim,
            media_item_id=media_id,
            source_url=(
                normalized_source_url
            ),
            news_api_key=news_api_key,
            normalize_url=normalize_url,
            domain_resolver=domain_resolver,
            fetch_article=fetch_article,
            extract_article=extract_article,
            gemini_client=gemini_client,
            gemini_client_key=(
                gemini_client_key
            ),
            gemini_generator=(
                gemini_generator
            ),
            connection_factory=(
                connection_factory
            ),
            freshness=freshness,
            max_candidates=max_candidates,
            results_per_query=(
                results_per_query
            ),
            max_assessments=(
                max_assessments
            ),
        )
    )

    corroboration_pipeline = (
        _require_result(
            stage_name=(
                "Corroboration pipeline"
            ),
            result=(
                corroboration_pipeline
            ),
            expected_version=(
                CORROBORATION_PIPELINE_VERSION
            ),
        )
    )

    _require_claim_media(
        stage_name=(
            "Corroboration pipeline"
        ),
        result=(
            corroboration_pipeline
        ),
        claim_id=claim_id,
        media_item_id=media_id,
    )

    if (
        _clean(
            corroboration_pipeline.get(
                "status"
            )
        ).lower()
        != "completed"
    ):
        raise ValueError(
            "Corroboration pipeline must "
            "complete before independence "
            "planning."
        )

    stages = (
        corroboration_pipeline.get(
            "stages"
        )
    )

    if not isinstance(
        stages,
        dict,
    ):
        raise ValueError(
            "Corroboration pipeline stages "
            "must be a dictionary."
        )

    candidate_collection = (
        stages.get(
            "candidate_collection"
        )
    )

    if not isinstance(
        candidate_collection,
        dict,
    ):
        raise ValueError(
            "Corroboration pipeline requires "
            "a candidate collection."
        )

    evidence_bundle = stages.get(
        "evidence_bundle"
    )

    evidence_bundle = (
        _require_result(
            stage_name=(
                "Corroboration evidence bundle"
            ),
            result=evidence_bundle,
            expected_version=(
                EVIDENCE_ANALYSIS_BUNDLE_VERSION
            ),
        )
    )

    # -----------------------------------------------------
    # 2. Build conservative source-independence plan.
    # -----------------------------------------------------

    independence_plan = (
        independence_plan_builder(
            evidence_bundle=(
                evidence_bundle
            ),
            claim_id=claim_id,
        )
    )

    independence_plan = (
        _require_result(
            stage_name=(
                "Independence plan"
            ),
            result=(
                independence_plan
            ),
            expected_version=(
                CORROBORATION_INDEPENDENCE_PLAN_VERSION
            ),
        )
    )

    if (
        _clean(
            independence_plan.get(
                "claim_id"
            )
        )
        != claim_id
    ):
        raise ValueError(
            "Independence plan claim ID "
            "does not match."
        )

    # -----------------------------------------------------
    # 3. Reuse already-resolved article text.
    # -----------------------------------------------------

    article_texts_by_url = (
        build_pipeline_article_text_map(
            source_url=(
                normalized_source_url
            ),
            source_article_text=(
                normalized_source_text
            ),
            candidate_collection=(
                candidate_collection
            ),
            normalize_url=(
                normalize_url
            ),
        )
    )

    # -----------------------------------------------------
    # 4. Verify candidate-pair independence.
    # -----------------------------------------------------

    independence_batch = (
        independence_batch_runner(
            claim=claim,
            plan=(
                independence_plan
            ),
            media_item_id=(
                media_id
            ),
            article_texts_by_url=(
                article_texts_by_url
            ),
            normalize_url=(
                normalize_url
            ),
            client=gemini_client,
            client_key=(
                gemini_client_key
            ),
            generator=(
                gemini_generator
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    independence_batch = (
        _require_result(
            stage_name=(
                "Independence batch"
            ),
            result=(
                independence_batch
            ),
            expected_version=(
                CORROBORATION_INDEPENDENCE_PIPELINE_VERSION
            ),
        )
    )

    _require_claim_media(
        stage_name=(
            "Independence batch"
        ),
        result=(
            independence_batch
        ),
        claim_id=claim_id,
        media_item_id=media_id,
    )

    batch_status = _clean(
        independence_batch.get(
            "status"
        )
    ).lower()

    if batch_status not in {
        "completed",
        "no_verification_pairs",
    }:
        raise ValueError(
            "Independence batch must "
            "complete before corroboration "
            "resolution."
        )

    # -----------------------------------------------------
    # 5. Resolve corroboration from verified evidence.
    # -----------------------------------------------------

    resolution = (
        corroboration_resolver(
            batch_result=(
                independence_batch
            )
        )
    )

    resolution = (
        _require_result(
            stage_name=(
                "Corroboration resolution"
            ),
            result=resolution,
            expected_version=(
                CORROBORATION_RESOLUTION_VERSION
            ),
        )
    )

    _require_claim_media(
        stage_name=(
            "Corroboration resolution"
        ),
        result=resolution,
        claim_id=claim_id,
        media_item_id=media_id,
    )

    if (
        _clean(
            resolution.get(
                "status"
            )
        ).lower()
        != "assessed"
    ):
        raise ValueError(
            "Corroboration resolution "
            "must be assessed."
        )

    resolution_stages = (
        resolution.get(
            "stages"
        )
    )

    if not isinstance(
        resolution_stages,
        dict,
    ):
        raise ValueError(
            "Corroboration resolution stages "
            "must be a dictionary."
        )

    corroboration_state = (
        resolution_stages.get(
            "corroboration"
        )
    )

    if not isinstance(
        corroboration_state,
        dict,
    ):
        raise ValueError(
            "Corroboration resolution "
            "requires corroboration state."
        )

    # -----------------------------------------------------
    # 6. Calculate SHADOW Merit only.
    # -----------------------------------------------------

    merit_overlay = (
        merit_overlay_builder(
            legacy_score=(
                legacy_score
            ),
            corroboration_state=(
                corroboration_state
            ),
            claim_id=claim_id,
        )
    )

    merit_overlay = (
        _require_result(
            stage_name=(
                "Merit corroboration overlay"
            ),
            result=merit_overlay,
            expected_version=(
                MERIT_CORROBORATION_OVERLAY_VERSION
            ),
        )
    )

    live = merit_overlay.get(
        "live",
        {},
    )

    if not isinstance(
        live,
        dict,
    ):
        raise ValueError(
            "Merit overlay live state "
            "must be a dictionary."
        )

    if (
        live.get(
            "score_effect_enabled"
        )
        is not False
    ):
        raise ValueError(
            "Unified intelligence pipeline "
            "cannot enable live Merit."
        )

    live_total = _score(
        live.get(
            "total"
        ),
        label=(
            "Merit overlay live total"
        ),
    )

    if (
        abs(
            live_total
            - legacy_total
        )
        > 1e-9
    ):
        raise ValueError(
            "Shadow pipeline cannot change "
            "the live Merit total."
        )

    return {
        "version": (
            SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
        ),
        "status": "completed",
        "mode": "shadow",
        "claim_id": claim_id,
        "media_item_id": media_id,
        "article_text_count": (
            len(
                article_texts_by_url
            )
        ),
        "stages": {
            "corroboration_pipeline": (
                corroboration_pipeline
            ),
            "independence_plan": (
                independence_plan
            ),
            "independence_batch": (
                independence_batch
            ),
            "corroboration_resolution": (
                resolution
            ),
            "merit_overlay": (
                merit_overlay
            ),
        },
        "live": {
            "merit_score_effect_enabled": (
                False
            ),
            "legacy_total": (
                legacy_total
            ),
            "total": (
                live_total
            ),
        },
        "policy": {
            (
                "candidate_article_text_is_"
                "reused_for_independence"
            ): True,
            (
                "search_results_do_not_"
                "establish_support"
            ): True,
            (
                "distinct_sources_do_not_"
                "establish_independence"
            ): True,
            (
                "absence_of_dependency_does_"
                "not_establish_independence"
            ): True,
            (
                "verified_independence_is_"
                "required_for_corroboration"
            ): True,
            (
                "corroboration_does_not_"
                "establish_truth"
            ): True,
            (
                "shadow_pipeline_has_no_"
                "live_merit_effect"
            ): True,
        },
    }
