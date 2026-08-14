from typing import Any, Dict

from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
    load_evidence_analysis_bundle_for_media_item,
)
from app.services.corroboration_discovery import (
    CORROBORATION_CANDIDATE_COLLECTION_VERSION,
    CORROBORATION_SEARCH_PLAN_VERSION,
    build_claim_corroboration_search_plan,
    collect_corroboration_candidates,
)
from app.services.corroboration_graph import (
    CORROBORATION_GRAPH_PLAN_VERSION,
    build_corroboration_graph_plan,
)
from app.services.corroboration_materialization import (
    CORROBORATION_GRAPH_MATERIALIZATION_VERSION,
    materialize_corroboration_graph_plan,
)
from app.services.corroboration_semantics import (
    CORROBORATION_SEMANTIC_BATCH_VERSION,
    assess_candidate_collection_semantics_with_gemini,
)


CORROBORATION_PIPELINE_VERSION = (
    "corroboration-pipeline-v1"
)


def _clean(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def _require_stage_result(
    *,
    stage_name: str,
    result: Any,
    expected_version: str,
    claim_id: str = "",
) -> Dict[str, Any]:
    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            f"{stage_name} result must "
            "be a dictionary."
        )

    version = _clean(
        result.get("version")
    )

    if version != expected_version:
        raise ValueError(
            f"{stage_name} returned an "
            "unsupported version."
        )

    if claim_id:
        stage_claim_id = _clean(
            result.get("claim_id")
        )

        if stage_claim_id != claim_id:
            raise ValueError(
                f"{stage_name} claim ID "
                "does not match the "
                "pipeline claim."
            )

    return result


def run_claim_corroboration_pipeline(
    *,
    claim: Dict[str, Any],
    media_item_id: str,
    source_url: str,
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
    search_plan_builder=(
        build_claim_corroboration_search_plan
    ),
    candidate_collector=(
        collect_corroboration_candidates
    ),
    semantic_batch_assessor=(
        assess_candidate_collection_semantics_with_gemini
    ),
    graph_plan_builder=(
        build_corroboration_graph_plan
    ),
    graph_materializer=(
        materialize_corroboration_graph_plan
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
            "Corroboration pipeline claim "
            "must be a dictionary."
        )

    claim_id = _clean(
        claim.get("id")
    )

    if not claim_id:
        raise ValueError(
            "Corroboration pipeline claim "
            "ID is required."
        )

    normalized_media_item_id = _clean(
        media_item_id
    )

    if not normalized_media_item_id:
        raise ValueError(
            "Corroboration pipeline media "
            "item ID is required."
        )

    search_plan = (
        search_plan_builder(
            claim=claim,
            source_url=source_url,
            freshness=freshness,
        )
    )

    search_plan = _require_stage_result(
        stage_name=(
            "Corroboration search plan"
        ),
        result=search_plan,
        expected_version=(
            CORROBORATION_SEARCH_PLAN_VERSION
        ),
        claim_id=claim_id,
    )

    collection = candidate_collector(
        plan=search_plan,
        api_key=news_api_key,
        normalize_url=normalize_url,
        domain_resolver=domain_resolver,
        fetch_article=fetch_article,
        extract_article=extract_article,
        max_candidates=max_candidates,
        results_per_query=(
            results_per_query
        ),
    )

    collection = _require_stage_result(
        stage_name=(
            "Corroboration candidate "
            "collection"
        ),
        result=collection,
        expected_version=(
            CORROBORATION_CANDIDATE_COLLECTION_VERSION
        ),
        claim_id=claim_id,
    )

    semantic_batch = (
        semantic_batch_assessor(
            claim=claim,
            collection=collection,
            client=gemini_client,
            client_key=(
                gemini_client_key
            ),
            generator=(
                gemini_generator
            ),
            max_assessments=(
                max_assessments
            ),
        )
    )

    semantic_batch = _require_stage_result(
        stage_name=(
            "Corroboration semantic batch"
        ),
        result=semantic_batch,
        expected_version=(
            CORROBORATION_SEMANTIC_BATCH_VERSION
        ),
        claim_id=claim_id,
    )

    graph_plan = graph_plan_builder(
        claim=claim,
        collection=collection,
        semantic_batch=semantic_batch,
        normalize_url=normalize_url,
        domain_resolver=domain_resolver,
    )

    graph_plan = _require_stage_result(
        stage_name=(
            "Corroboration graph plan"
        ),
        result=graph_plan,
        expected_version=(
            CORROBORATION_GRAPH_PLAN_VERSION
        ),
        claim_id=claim_id,
    )

    materialization = (
        graph_materializer(
            plan=graph_plan,
            normalize_url=normalize_url,
            domain_resolver=(
                domain_resolver
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    materialization = (
        _require_stage_result(
            stage_name=(
                "Corroboration graph "
                "materialization"
            ),
            result=materialization,
            expected_version=(
                CORROBORATION_GRAPH_MATERIALIZATION_VERSION
            ),
            claim_id=claim_id,
        )
    )

    evidence_bundle = evidence_loader(
        media_item_id=(
            normalized_media_item_id
        ),
        connection_factory=(
            connection_factory
        ),
    )

    evidence_bundle = (
        _require_stage_result(
            stage_name=(
                "Evidence analysis bundle"
            ),
            result=evidence_bundle,
            expected_version=(
                EVIDENCE_ANALYSIS_BUNDLE_VERSION
            ),
        )
    )

    outcome = _clean(
        materialization.get("status")
    ) or "unknown"

    return {
        "version": (
            CORROBORATION_PIPELINE_VERSION
        ),
        "status": "completed",
        "outcome": outcome,
        "claim_id": claim_id,
        "media_item_id": (
            normalized_media_item_id
        ),
        "stages": {
            "search_plan": (
                search_plan
            ),
            "candidate_collection": (
                collection
            ),
            "semantic_batch": (
                semantic_batch
            ),
            "graph_plan": (
                graph_plan
            ),
            "materialization": (
                materialization
            ),
            "evidence_bundle": (
                evidence_bundle
            ),
        },
        "policy": {
            (
                "search_is_discovery_only"
            ): True,
            (
                "semantic_assessment_does_"
                "not_establish_independence"
            ): True,
            (
                "materialization_does_not_"
                "create_independence_assertions"
            ): True,
            (
                "pipeline_does_not_decide_"
                "corroboration"
            ): True,
            (
                "pipeline_has_no_merit_effect"
            ): True,
            (
                "evidence_is_reloaded_after_"
                "materialization"
            ): True,
        },
    }
