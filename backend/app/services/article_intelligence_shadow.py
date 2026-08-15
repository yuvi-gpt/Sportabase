import hashlib
import re

from typing import Any, Dict

from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)
from app.intelligence.observations import (
    record_source_observation,
)
from app.intelligence.sources import (
    source_domain_for_url,
    upsert_intelligence_source,
)
from app.services.intelligence_pipeline import (
    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
    run_sportabase_intelligence_pipeline,
)
from app.services.article_adjudication_runtime import (
    ARTICLE_ADJUDICATION_RUNTIME_VERSION,
    run_article_adjudication_runtime,
)

from app.analysis.snapshot_assembly import (
    build_model_assisted_evidence_snapshot,
)

from app.services.observation_semantics import (
    assess_claim_observation_semantics_with_gemini,
)

from app.services.model_assisted_baseline_runtime import (
    MODEL_ASSISTED_BASELINE_RUNTIME_VERSION,
    persist_model_assisted_baseline_revision,
)


ARTICLE_INTELLIGENCE_SHADOW_VERSION = (
    "article-intelligence-shadow-v1"
)


ARTICLE_PRIMARY_CLAIM_TYPES = {
    "official_announcement",
    "transfer_official",
    "transfer_report",
    "transfer_rumor",
    "injury_confirmed",
    "injury_rumor",
    "lineup_confirmed",
    "lineup_predicted",
    "squad_news",
    "discipline_legal",
    "managerial_news",
    "contract_news",
    "fixture_schedule",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _skip(
    reason: str,
) -> Dict[str, Any]:
    return {
        "version": (
            ARTICLE_INTELLIGENCE_SHADOW_VERSION
        ),
        "status": "skipped",
        "mode": "shadow",
        "reason": reason,
        "live_merit_effect_enabled": False,
        "truth_established": False,
    }


def build_article_primary_claim_seed(
    *,
    media_item_id: str,
    title: str,
    url: str,
    article_type: str,
    observed_at: str,
    normalize_url,
) -> Dict[str, Any]:
    media_id = _clean(
        media_item_id
    )

    canonical_text = _clean(
        title
    )

    normalized_type = _key(
        article_type
    )

    normalized_observed_at = _clean(
        observed_at
    )

    if not media_id:
        raise ValueError(
            "Article intelligence media "
            "item ID is required."
        )

    if not canonical_text:
        raise ValueError(
            "Article intelligence title "
            "is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Article intelligence observed "
            "time is required."
        )

    if (
        normalized_type
        not in ARTICLE_PRIMARY_CLAIM_TYPES
    ):
        return {
            "version": (
                ARTICLE_INTELLIGENCE_SHADOW_VERSION
            ),
            "status": "not_claim_bearing",
            "reason": (
                "article_type_not_claim_seeded"
            ),
            "article_type": (
                normalized_type
            ),
        }

    normalized_url = _clean(
        normalize_url(
            url
        )
    )

    if not normalized_url:
        raise ValueError(
            "Article intelligence URL "
            "could not be normalized."
        )

    text_hash = hashlib.sha256(
        canonical_text
        .casefold()
        .encode(
            "utf-8"
        )
    ).hexdigest()

    canonical_key = (
        "article-primary|"
        + media_id
        + "|"
        + text_hash
    )

    subject_key = (
        "article-media|"
        + media_id
    )

    return {
        "version": (
            ARTICLE_INTELLIGENCE_SHADOW_VERSION
        ),
        "status": "claim_seed_ready",
        "media_item_id": media_id,
        "canonical_key": (
            canonical_key
        ),
        "subject_key": subject_key,
        "canonical_text": (
            canonical_text
        ),
        "claim_type": (
            "headline_assertion"
        ),
        "article_type": (
            normalized_type
        ),
        "canonical_url": (
            normalized_url
        ),
        "observed_at": (
            normalized_observed_at
        ),
        "policy": {
            (
                "headline_is_recorded_as_"
                "reported_claim"
            ): True,
            (
                "headline_does_not_"
                "establish_truth"
            ): True,
            (
                "claim_identity_is_"
                "deterministic"
            ): True,
        },
    }


def persist_article_primary_claim_seed(
    *,
    seed: Dict[str, Any],
    type_confidence: float,
    normalize_url,
    connection_factory,
    source_upserter=(
        upsert_intelligence_source
    ),
    claim_upserter=(
        upsert_intelligence_claim
    ),
    observation_recorder=(
        record_source_observation
    ),
    claim_link_recorder=(
        record_claim_link
    ),
) -> Dict[str, Any]:
    if not isinstance(
        seed,
        dict,
    ):
        raise ValueError(
            "Article intelligence seed "
            "must be a dictionary."
        )

    if (
        seed.get(
            "status"
        )
        != "claim_seed_ready"
    ):
        raise ValueError(
            "Article intelligence seed "
            "is not ready."
        )

    canonical_url = _clean(
        seed.get(
            "canonical_url"
        )
    )

    observed_at = _clean(
        seed.get(
            "observed_at"
        )
    )

    domain_resolver = (
        lambda value: (
            source_domain_for_url(
                value,
                normalize_url=(
                    normalize_url
                ),
            )
        )
    )

    source = source_upserter(
        url=canonical_url,
        display_name=(
            domain_resolver(
                canonical_url
            )
        ),
        source_type="publisher",
        seen_at=observed_at,
        metadata={
            "seeded_by": (
                ARTICLE_INTELLIGENCE_SHADOW_VERSION
            ),
        },
        domain_resolver=(
            domain_resolver
        ),
        connection_factory=(
            connection_factory
        ),
    )

    claim = claim_upserter(
        canonical_key=(
            seed[
                "canonical_key"
            ]
        ),
        subject_key=(
            seed[
                "subject_key"
            ]
        ),
        canonical_text=(
            seed[
                "canonical_text"
            ]
        ),
        claim_type=(
            seed[
                "claim_type"
            ]
        ),
        seen_at=observed_at,
        metadata={
            "seed_basis": (
                "article_headline"
            ),
            "article_type": (
                seed[
                    "article_type"
                ]
            ),
            "truth_established": False,
        },
        id_resolver=(
            claim_id_for_canonical_key
        ),
        connection_factory=(
            connection_factory
        ),
    )

    observation = (
        observation_recorder(
            source_id=(
                source["id"]
            ),
            media_item_id=(
                seed[
                    "media_item_id"
                ]
            ),
            subject_key=(
                seed[
                    "subject_key"
                ]
            ),
            observation_type=(
                "article_headline_report"
            ),
            status="reported",
            claim_summary=(
                seed[
                    "canonical_text"
                ]
            ),
            provenance_url=(
                canonical_url
            ),
            confidence=None,
            observed_at=(
                observed_at
            ),
            metadata={
                "article_type": (
                    seed[
                        "article_type"
                    ]
                ),
                "type_confidence": (
                    float(
                        type_confidence
                    )
                ),
                "truth_established": (
                    False
                ),
            },
            normalize_url=(
                normalize_url
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    observation_row = (
        observation[
            "observation"
        ]
    )

    link = claim_link_recorder(
        claim_id=(
            claim["id"]
        ),
        source_observation_id=(
            observation_row[
                "id"
            ]
        ),
        relationship_type="supports",
        confidence=None,
        observed_at=(
            observed_at
        ),
        metadata={
            "relationship_basis": (
                "publisher_reports_claim"
            ),
            "truth_established": False,
        },
        connection_factory=(
            connection_factory
        ),
    )

    return {
        "version": (
            ARTICLE_INTELLIGENCE_SHADOW_VERSION
        ),
        "status": "seed_persisted",
        "claim": claim,
        "source": source,
        "observation": (
            observation_row
        ),
        "claim_link": (
            link["link"]
        ),
        "policy": {
            (
                "support_link_means_"
                "reported_support_not_truth"
            ): True,
            (
                "current_source_does_not_"
                "establish_independence"
            ): True,
        },
    }


def run_article_intelligence_shadow(
    *,
    enabled: bool,
    media_item_id: str,
    observed_at: str,
    title: str,
    article_text: str,
    url: str,
    article_type: str,
    type_confidence: float,
    legacy_score: Dict[str, Any],
    news_api_key: str,
    normalize_url,
    fetch_article,
    extract_article,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    connection_factory,
    semantic_assessor=(
        assess_claim_observation_semantics_with_gemini
    ),
    snapshot_builder=(
        build_model_assisted_evidence_snapshot
    ),
    baseline_runtime_runner=(
        persist_model_assisted_baseline_revision
    ),
    pipeline_runner=(
        run_sportabase_intelligence_pipeline
    ),
    seed_persister=(
        persist_article_primary_claim_seed
    ),
    adjudication_runner=(
        run_article_adjudication_runtime
    ),
) -> Dict[str, Any]:
    if not enabled:
        return _skip(
            "shadow_disabled"
        )

    if not _clean(
        news_api_key
    ):
        return _skip(
            "news_api_key_missing"
        )

    if gemini_client is None:
        return _skip(
            "gemini_unavailable"
        )

    normalized_text = _clean(
        article_text
    )

    if not normalized_text:
        return _skip(
            "article_text_missing"
        )

    seed = (
        build_article_primary_claim_seed(
            media_item_id=(
                media_item_id
            ),
            title=title,
            url=url,
            article_type=(
                article_type
            ),
            observed_at=(
                observed_at
            ),
            normalize_url=(
                normalize_url
            ),
        )
    )

    if (
        seed.get(
            "status"
        )
        != "claim_seed_ready"
    ):
        return _skip(
            str(
                seed.get(
                    "reason"
                )
                or "claim_seed_unavailable"
            )
        )

    persisted = seed_persister(
        seed=seed,
        type_confidence=(
            type_confidence
        ),
        normalize_url=(
            normalize_url
        ),
        connection_factory=(
            connection_factory
        ),
    )

    claim = persisted.get(
        "claim"
    )

    if not isinstance(
        claim,
        dict,
    ):
        raise ValueError(
            "Article intelligence seed "
            "did not produce a claim."
        )

    persisted_source = persisted.get(
        "source"
    )

    primary_baseline = {
        "version": (
            MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
        ),
        "status": "skipped",
        "reason": (
            "seed_source_unavailable"
        ),
        "bound_evaluator_runs": [],
        "policy": {
            "best_effort_shadow_stage": True,
            "does_not_change_live_merit": True,
        },
    }

    if isinstance(
        persisted_source,
        dict,
    ):
        try:
            source_id = _clean(
                persisted_source.get(
                    "id"
                )
            )

            subject_key = _clean(
                claim.get(
                    "subject_key"
                )
            )

            if not source_id:
                raise ValueError(
                    "Primary baseline source ID "
                    "is required."
                )

            if not subject_key:
                raise ValueError(
                    "Primary baseline claim subject "
                    "key is required."
                )

            semantic_source = {
                "url": (
                    seed[
                        "canonical_url"
                    ]
                ),
                "title": (
                    seed[
                        "canonical_text"
                    ]
                ),
                "text": (
                    normalized_text
                ),
                "actor_id": (
                    source_id
                ),
                "source_domain": (
                    source_domain_for_url(
                        seed[
                            "canonical_url"
                        ],
                        normalize_url=(
                            normalize_url
                        ),
                    )
                ),
                "observed_at": (
                    observed_at
                ),
            }

            semantic_result = (
                semantic_assessor(
                    claim=claim,
                    source=(
                        semantic_source
                    ),
                    context={},
                    client=(
                        gemini_client
                    ),
                    client_key=(
                        gemini_client_key
                    ),
                    generator=(
                        gemini_generator
                    ),
                )
            )

            if not isinstance(
                semantic_result,
                dict,
            ):
                raise ValueError(
                    "Primary semantic assessment "
                    "returned an invalid result."
                )

            if (
                _key(
                    semantic_result.get(
                        "status"
                    )
                )
                != "assessed"
            ):
                primary_baseline = {
                    "version": (
                        MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
                    ),
                    "status": "skipped",
                    "reason": (
                        _clean(
                            semantic_result.get(
                                "reason"
                            )
                        )
                        or (
                            "primary_semantics_"
                            "not_assessed"
                        )
                    ),
                    "semantic_result": (
                        semantic_result
                    ),
                    "bound_evaluator_runs": [],
                    "policy": {
                        "best_effort_shadow_stage": True,
                        "does_not_change_live_merit": True,
                    },
                }

            else:
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
                        "Primary semantic assessment "
                        "is missing."
                    )

                assembly = snapshot_builder(
                    claim=claim,
                    source=(
                        semantic_source
                    ),
                    semantic_assessment=(
                        assessment
                    ),
                    as_of=(
                        observed_at
                    ),
                )

                if not isinstance(
                    assembly,
                    dict,
                ):
                    raise ValueError(
                        "Primary baseline snapshot "
                        "assembly is invalid."
                    )

                if (
                    _key(
                        assembly.get(
                            "status"
                        )
                    )
                    != "assembled"
                ):
                    primary_baseline = {
                        "version": (
                            MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
                        ),
                        "status": "skipped",
                        "reason": (
                            "primary_snapshot_"
                            "unresolved"
                        ),
                        "assembly": (
                            assembly
                        ),
                        "bound_evaluator_runs": [],
                        "policy": {
                            "best_effort_shadow_stage": True,
                            "does_not_change_live_merit": True,
                        },
                    }

                else:
                    primary_baseline = (
                        baseline_runtime_runner(
                            assembly=(
                                assembly
                            ),
                            semantic_assessment=(
                                assessment
                            ),
                            source_id=(
                                source_id
                            ),
                            subject_key=(
                                subject_key
                            ),
                            media_item_id=(
                                seed[
                                    "media_item_id"
                                ]
                            ),
                            recorded_at=(
                                observed_at
                            ),
                            normalize_url=(
                                normalize_url
                            ),
                            connection_factory=(
                                connection_factory
                            ),
                        )
                    )

                    if not isinstance(
                        primary_baseline,
                        dict,
                    ):
                        raise ValueError(
                            "Primary baseline runtime "
                            "returned an invalid result."
                        )

                    if (
                        _clean(
                            primary_baseline.get(
                                "version"
                            )
                        )
                        != (
                            MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
                        )
                    ):
                        raise ValueError(
                            "Primary baseline runtime "
                            "version is unsupported."
                        )

        except Exception as error:
            primary_baseline = {
                "version": (
                    MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
                ),
                "status": "failed",
                "reason": (
                    "primary_baseline_"
                    "best_effort_failure"
                ),
                "error_type": (
                    type(
                        error
                    ).__name__
                ),
                "error": str(
                    error
                )[:240],
                "bound_evaluator_runs": [],
                "policy": {
                    "best_effort_shadow_stage": True,
                    "failure_does_not_block_article_pipeline": True,
                    "does_not_change_live_merit": True,
                },
            }

    pipeline = pipeline_runner(
        claim=claim,
        media_item_id=(
            seed[
                "media_item_id"
            ]
        ),
        source_url=(
            seed[
                "canonical_url"
            ]
        ),
        source_article_text=(
            normalized_text
        ),
        legacy_score=(
            legacy_score
        ),
        news_api_key=(
            news_api_key
        ),
        normalize_url=(
            normalize_url
        ),
        domain_resolver=(
            lambda value: (
                source_domain_for_url(
                    value,
                    normalize_url=(
                        normalize_url
                    ),
                )
            )
        ),
        fetch_article=(
            fetch_article
        ),
        extract_article=(
            extract_article
        ),
        gemini_client=(
            gemini_client
        ),
        gemini_client_key=(
            gemini_client_key
        ),
        gemini_generator=(
            gemini_generator
        ),
        connection_factory=(
            connection_factory
        ),
    )

    if not isinstance(
        pipeline,
        dict,
    ):
        raise ValueError(
            "Article intelligence pipeline "
            "result must be a dictionary."
        )

    if (
        _clean(
            pipeline.get(
                "version"
            )
        )
        != SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
    ):
        raise ValueError(
            "Article intelligence pipeline "
            "returned an unsupported version."
        )

    if (
        _key(
            pipeline.get(
                "mode"
            )
        )
        != "shadow"
    ):
        raise ValueError(
            "Article intelligence pipeline "
            "must remain in shadow mode."
        )

    live = pipeline.get(
        "live"
    )

    if not isinstance(
        live,
        dict,
    ):
        raise ValueError(
            "Article intelligence pipeline "
            "requires a live state."
        )

    if (
        live.get(
            "merit_score_effect_enabled"
        )
        is not False
    ):
        raise ValueError(
            "Article intelligence shadow "
            "cannot enable live Merit."
        )

    baseline_evaluator_runs = (
        primary_baseline.get(
            "bound_evaluator_runs",
            [],
        )
        if isinstance(
            primary_baseline,
            dict,
        )
        else []
    )

    if not isinstance(
        baseline_evaluator_runs,
        list,
    ):
        baseline_evaluator_runs = []

    try:
        adjudication_runtime = (
            adjudication_runner(
                claim=claim,
                pipeline=pipeline,
                as_of=observed_at,
                additional_evaluator_runs=(
                    baseline_evaluator_runs
                ),
                connection_factory=(
                    connection_factory
                ),
            )
        )

        if not isinstance(
            adjudication_runtime,
            dict,
        ):
            raise ValueError(
                "Article adjudication runtime "
                "returned an invalid result."
            )

    except Exception as error:
        adjudication_runtime = {
            "version": (
                ARTICLE_ADJUDICATION_RUNTIME_VERSION
            ),
            "status": "failed",
            "claim_id": (
                claim["id"]
            ),
            "error_type": (
                type(error).__name__
            ),
            "error": str(
                error
            )[:240],
            "live_merit_effect_enabled": False,
            "training_eligible": False,
        }

    stages = pipeline.get(
        "stages",
        {},
    )

    if not isinstance(
        stages,
        dict,
    ):
        stages = {}

    overlay = stages.get(
        "merit_overlay",
        {},
    )

    if not isinstance(
        overlay,
        dict,
    ):
        overlay = {}

    proposed = overlay.get(
        "proposed",
        {},
    )

    if not isinstance(
        proposed,
        dict,
    ):
        proposed = {}

    independence_plan = stages.get(
        "independence_plan",
        {},
    )

    if not isinstance(
        independence_plan,
        dict,
    ):
        independence_plan = {}

    plan_counts = independence_plan.get(
        "counts",
        {},
    )

    if not isinstance(
        plan_counts,
        dict,
    ):
        plan_counts = {}

    corroboration_pipeline = stages.get(
        "corroboration_pipeline",
        {},
    )

    if not isinstance(
        corroboration_pipeline,
        dict,
    ):
        corroboration_pipeline = {}

    corroboration_stages = (
        corroboration_pipeline.get(
            "stages",
            {},
        )
    )

    if not isinstance(
        corroboration_stages,
        dict,
    ):
        corroboration_stages = {}

    collection = corroboration_stages.get(
        "candidate_collection",
        {},
    )

    if not isinstance(
        collection,
        dict,
    ):
        collection = {}

    collection_counts = collection.get(
        "counts",
        {},
    )

    if not isinstance(
        collection_counts,
        dict,
    ):
        collection_counts = {}

    return {
        "version": (
            ARTICLE_INTELLIGENCE_SHADOW_VERSION
        ),
        "status": "completed",
        "mode": "shadow",
        "claim_id": (
            claim["id"]
        ),
        "primary_baseline": (
            primary_baseline
        ),
        "signal": (
            overlay.get(
                "signal",
                ""
            )
        ),
        "candidate_count": int(
            collection_counts.get(
                "resolved",
                0,
            )
            or 0
        ),
        "verification_pairs": int(
            plan_counts.get(
                "verification_pairs",
                0,
            )
            or 0
        ),
        "proposed_adjustment": (
            proposed.get(
                "adjustment",
                0.0,
            )
        ),
        "shadow_total": (
            proposed.get(
                "shadow_total"
            )
        ),
        "live_total": (
            live.get(
                "total"
            )
        ),
        "live_merit_effect_enabled": False,
        "truth_established": False,
        "adjudication": (
            adjudication_runtime
        ),
        "policy": {
            (
                "headline_seed_is_"
                "reporting_evidence_only"
            ): True,
            (
                "source_diversity_does_not_"
                "establish_independence"
            ): True,
            (
                "corroboration_does_not_"
                "establish_truth"
            ): True,
            (
                "shadow_has_no_live_"
                "merit_effect"
            ): True,
            (
                "primary_model_baseline_"
                "is_shadow_only"
            ): True,
            (
                "primary_baseline_failure_"
                "does_not_block_article"
            ): True,
        },
    }
