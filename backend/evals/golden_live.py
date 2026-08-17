from __future__ import annotations

import copy
import hashlib
import json
import tempfile

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from app.intelligence import entities as entity_runtime
from app.models import artifacts as artifact_models
from app.services import artifact_extraction
from app.services import multimodal_inbox_shadow_orchestration
from app.services import multimodal_shadow_orchestration
from app.services import multimodal_shadow_api
from app.services import multimodal_intelligence_runtime
from app.services import semantic_execution
from app.services import inbox_candidate_shadow_orchestration
from app.services import inbox_story_cluster_orchestration
from app.services import story_claim_graph_materialization

from .golden_capture import clean
from .golden_dataset import golden_dataset_descriptor
from .golden_runtime import (
    _factory,
    _initialize,
    _insert_entities,
    _store_captures,
)
from .golden_live_budget import (
    BudgetedGeminiGenerator,
    DEFAULT_MAX_PROVIDER_CALLS,
    MultimodalGoldenLiveBudgetExceeded,
    MultimodalGoldenLiveError,
    MultimodalGoldenLiveInputError,
    MultimodalGoldenLiveProviderError,
    capacity_snapshot,
    sqlite_connection_factory,
)
from .golden_live_scoring import (
    DEFAULT_LIVE_CASE_IDS,
    completed_case,
    noncompleted_case,
    provider_call_plan,
    selected_cases,
)
from .multimodal_golden_cases import (
    MULTIMODAL_GOLDEN_DATASET_ID,
)


MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION = (
    "multimodal-golden-live-eval-v2"
)
LIVE_MODEL = "gemini-3.5-flash"

EVAL_CLIENT_KEYS_BY_LABEL = {
    "related_primary": (
        "eval34b:bellingham:web-positive"
    ),
    "related_secondary": (
        "eval34b:bellingham:youtube-positive"
    ),
    "hard_negative_same_subject": (
        "eval34b:bellingham:x-hard-negative"
    ),
}


def _runtime_case(
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Adapt only the temporary live-eval copy to
    production canonical entity IDs.

    The frozen #33 corpus remains unchanged.
    """

    runtime = copy.deepcopy(
        dict(case)
    )

    for entity in runtime.get(
        "entities",
        [],
    ):
        if not isinstance(
            entity,
            dict,
        ):
            raise MultimodalGoldenLiveInputError(
                "Live golden entity is invalid."
            )

        entity_key = clean(
            entity.get(
                "entity_key"
            )
        )

        if not entity_key:
            raise MultimodalGoldenLiveInputError(
                "Live golden entity key "
                "is missing."
            )

        entity["id"] = (
            entity_runtime
            .canonical_entity_id_for_key(
                entity_key
            )
        )

    return runtime


def _copy_model(value):
    if hasattr(
        value,
        "model_copy",
    ):
        return value.model_copy(
            deep=True
        )

    return value.copy(
        deep=True
    )


def _eval_text_semantic_manifest(
    manifest,
    *,
    workspace,
    interpreter,
    perception_executor_builder=None,
    perception_options=None,
):
    """
    #34B evaluation-only semantic scheduling.

    The frozen #33 captures are text-only even when their
    platform label is X or YouTube. Production schedules
    multimodal_semantic_fusion only for items that actually
    contain media_components.

    #34B adds one temporary fusion work unit over the already
    materialized text artifacts so the existing production
    GeminiSemanticInterpreter, bridge, exact-common-claim gate,
    persistence, observation semantics, adjudication and graph
    paths can be evaluated without changing production behavior
    or mutating the frozen corpus.
    """

    runtime_manifest = (
        _copy_model(
            manifest
        )
    )

    already_has_fusion = any(
        getattr(
            work,
            "operation",
            "",
        )
        == "multimodal_semantic_fusion"
        for work
        in runtime_manifest.work_units
    )

    if not already_has_fusion:
        text_artifacts = [
            artifact
            for artifact
            in runtime_manifest.artifacts
            if (
                artifact.artifact_kind
                == "text_component"
            )
        ]

        if text_artifacts:
            component_ids = []

            for artifact in text_artifacts:
                for component_id in (
                    artifact
                    .source_component_ids
                ):
                    if (
                        component_id
                        and component_id
                        not in component_ids
                    ):
                        component_ids.append(
                            component_id
                        )

            first = text_artifacts[0]

            provenance = (
                artifact_models
                .ArtifactProvenance(
                    source_url=(
                        first
                        .provenance
                        .source_url
                    ),
                    observed_at=(
                        first
                        .provenance
                        .observed_at
                    ),
                    extraction_method=(
                        "evaluation_only:"
                        "text_semantic_fusion"
                    ),
                    source_content_hash=(
                        first
                        .provenance
                        .source_content_hash
                    ),
                    metadata={
                        "evaluation_only": True,
                        "frozen_dataset_mutated": False,
                        (
                            "production_semantic_"
                            "scheduling_changed"
                        ): False,
                    },
                )
            )

            fusion_work = (
                artifact_extraction
                ._work(
                    operation=(
                        "multimodal_semantic_fusion"
                    ),
                    source_item_ids=[
                        runtime_manifest
                        .item_id
                    ],
                    source_component_ids=(
                        component_ids
                    ),
                    strategy=(
                        "evaluation_text_"
                        "semantic_fusion"
                    ),
                    parameters={
                        "caption_media_pairs": [],
                        "platform": (
                            "evaluation_text_only"
                        ),
                        "platform_surface": (
                            "evaluation_text_only"
                        ),
                    },
                    provenance=(
                        provenance
                    ),
                    metadata={
                        "evaluation_only": True,
                        (
                            "uses_existing_"
                            "semantic_interpreter"
                        ): True,
                    },
                )
            )

            runtime_manifest.work_units.append(
                fusion_work
            )

            runtime_manifest.metadata = {
                **dict(
                    runtime_manifest
                    .metadata
                ),
                (
                    "evaluation_text_"
                    "semantic_adapter"
                ): True,
                "frozen_dataset_mutated":
                    False,
                (
                    "production_semantic_"
                    "scheduling_changed"
                ): False,
            }

            (
                artifact_models
                .validate_item_artifact_manifest(
                    runtime_manifest
                )
            )

    return (
        semantic_execution
        .execute_semantic_manifest(
            runtime_manifest,
            workspace=workspace,
            interpreter=interpreter,
            perception_executor_builder=(
                perception_executor_builder
            ),
            perception_options=(
                perception_options
            ),
        )
    )


def _eval_runtime_runner(**kwargs):
    call = dict(kwargs)

    call[
        "semantic_manifest_runner"
    ] = (
        _eval_text_semantic_manifest
    )

    return (
        multimodal_intelligence_runtime
        .run_multimodal_intelligence_runtime(
            **call
        )
    )


def _eval_shadow_api_runner(**kwargs):
    call = dict(kwargs)

    call["runtime_runner"] = (
        _eval_runtime_runner
    )

    return (
        multimodal_shadow_api
        .execute_multimodal_shadow_api(
            **call
        )
    )


def _eval_shadow_orchestration_runner(
    **kwargs,
):
    call = dict(kwargs)

    call["shadow_runner"] = (
        _eval_shadow_api_runner
    )

    return (
        multimodal_shadow_orchestration
        .execute_multimodal_shadow_orchestration(
            **call
        )
    )


def _eval_inbox_shadow_runner(**kwargs):
    call = dict(kwargs)

    call[
        "orchestration_runner"
    ] = (
        _eval_shadow_orchestration_runner
    )

    return (
        multimodal_inbox_shadow_orchestration
        .execute_multimodal_inbox_shadow_orchestration(
            **call
        )
    )


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _new_client(api_key: str):
    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except Exception as error:
        raise MultimodalGoldenLiveProviderError(
            "Gemini client initialization failed."
        ) from error


def live_capacity_preflight(
    *,
    usage_connection_factory,
    max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
) -> Dict[str, Any]:
    plan = provider_call_plan(
        DEFAULT_LIVE_CASE_IDS
    )
    required = int(plan["maximum_calls"])
    if int(max_calls) < required:
        return {
            "ready": False,
            "failures": [
                "configured_eval_budget_below_full_case_maximum"
            ],
            "required_calls": required,
            "configured_calls": int(max_calls),
        }

    snapshot = capacity_snapshot(
        usage_connection_factory=(
            usage_connection_factory
        ),
        model=LIVE_MODEL,
        client_keys=tuple(
            EVAL_CLIENT_KEYS_BY_LABEL.values()
        ),
        required_calls=required,
        max_calls_per_client=4,
    )
    snapshot["candidate_pair_count"] = int(
        plan["candidate_pair_count"]
    )
    snapshot["guaranteed_calls"] = int(
        plan["minimum_calls"]
    )
    snapshot["conditional_calls"] = int(
        plan["conditional_observation_calls"]
    )
    snapshot["possible_actual_calls"] = list(
        plan["possible_actual_calls"]
    )
    snapshot["hard_eval_cap"] = int(max_calls)
    snapshot["pair_client_bucket_count"] = len(
        EVAL_CLIENT_KEYS_BY_LABEL
    )
    return snapshot


def evaluate_live_golden_subset(
    *,
    api_key: str,
    usage_db_path: str | Path | None = None,
    usage_connection_factory=None,
    max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
    case_ids: Sequence[str] = DEFAULT_LIVE_CASE_IDS,
    client=None,
    client_factory=None,
    generator: Optional[BudgetedGeminiGenerator] = None,
    event_sink: Optional[
        Callable[[Dict[str, Any]], None]
    ] = None,
    cluster_runner=None,
    graph_materializer=(
        story_claim_graph_materialization
        .materialize_story_claim_graph
    ),
) -> Dict[str, Any]:
    key = clean(api_key)
    if not key and client is None:
        raise MultimodalGoldenLiveInputError(
            "GEMINI_API_KEY is required for the "
            "live golden evaluation."
        )

    chosen = selected_cases(case_ids)
    if tuple(case["case_id"] for case in chosen) != tuple(
        DEFAULT_LIVE_CASE_IDS
    ):
        raise MultimodalGoldenLiveInputError(
            "#34B live evaluation is frozen to the "
            "Bellingham full-case subset."
        )

    plan = provider_call_plan(case_ids)
    if int(max_calls) < int(plan["maximum_calls"]):
        raise MultimodalGoldenLiveInputError(
            "Provider budget is too small for the "
            "frozen full-case live plan; need "
            + str(plan["maximum_calls"])
            + " calls of headroom."
        )

    if usage_connection_factory is None:
        if usage_db_path is None:
            raise MultimodalGoldenLiveInputError(
                "Production Gemini usage DB path is required."
            )
        usage_connection_factory = (
            sqlite_connection_factory(
                usage_db_path
            )
        )

    preflight = live_capacity_preflight(
        usage_connection_factory=(
            usage_connection_factory
        ),
        max_calls=max_calls,
    )
    if preflight.get("ready") is not True:
        raise MultimodalGoldenLiveInputError(
            "#34B provider-day capacity preflight failed: "
            + ", ".join(
                str(value)
                for value in preflight.get(
                    "failures",
                    [],
                )
            )
        )

    budget = generator or BudgetedGeminiGenerator(
        usage_connection_factory=(
            usage_connection_factory
        ),
        max_calls=max_calls,
        event_sink=event_sink,
    )
    if not isinstance(
        budget,
        BudgetedGeminiGenerator,
    ):
        raise MultimodalGoldenLiveInputError(
            "Live golden generator must be "
            "BudgetedGeminiGenerator."
        )
    if event_sink is not None and generator is not None:
        budget.event_sink = (
            event_sink
            if callable(event_sink)
            else None
        )

    if client is None:
        factory = (
            client_factory
            if callable(client_factory)
            else _new_client
        )
        client = factory(key)

    cases = []
    provider_incomplete = False
    infrastructure_failures = []

    for case in chosen:
        calls_before = budget.call_count
        runtime_case = _runtime_case(
            case
        )

        with tempfile.TemporaryDirectory(
            prefix="sportabase-golden-live-"
        ) as tmp:
            db_path = Path(tmp) / "golden-live.db"
            _initialize(db_path)
            connection_factory = _factory(db_path)
            _insert_entities(
                runtime_case,
                connection_factory,
            )
            label_to_id, id_to_label = (
                _store_captures(
                    runtime_case,
                    connection_factory,
                )
            )

            def pair_candidate_shadow_runner(**kwargs):
                candidate_id = clean(
                    kwargs.get(
                        "candidate_capture_record_id"
                    )
                )
                label = clean(
                    id_to_label.get(candidate_id)
                )
                client_key = (
                    EVAL_CLIENT_KEYS_BY_LABEL.get(
                        label
                    )
                )
                if not client_key:
                    raise MultimodalGoldenLiveInputError(
                        "Unexpected #34B candidate pair: "
                        + (label or candidate_id)
                    )
                call_kwargs = dict(kwargs)
                call_kwargs["gemini_client_key"] = (
                    client_key
                )
                call_kwargs["shadow_runner"] = (
                    _eval_inbox_shadow_runner
                )
                return (
                    inbox_candidate_shadow_orchestration
                    .execute_multimodal_inbox_candidate_shadow(
                        **call_kwargs
                    )
                )

            try:
                if cluster_runner is None:
                    cluster = (
                        inbox_story_cluster_orchestration
                        .execute_multisource_inbox_story_cluster_shadow(
                            anchor_capture_record_id=(
                                label_to_id["anchor"]
                            ),
                            analysis_version=(
                                MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION
                            ),
                            scoring_version=(
                                MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION
                            ),
                            target_claim_id="",
                            scan_limit=100,
                            max_candidates=12,
                            connection_factory=(
                                connection_factory
                            ),
                            gemini_client=client,
                            gemini_client_key=(
                                "eval34b:cluster-router"
                            ),
                            gemini_generator=budget,
                            candidate_shadow_runner=(
                                pair_candidate_shadow_runner
                            ),
                        )
                    )
                else:
                    cluster = cluster_runner(
                        anchor_capture_record_id=(
                            label_to_id["anchor"]
                        ),
                        analysis_version=(
                            MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION
                        ),
                        scoring_version=(
                            MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION
                        ),
                        target_claim_id="",
                        scan_limit=100,
                        max_candidates=12,
                        connection_factory=(
                            connection_factory
                        ),
                        gemini_client=client,
                        gemini_client_key=(
                            "eval34b:test"
                        ),
                        gemini_generator=budget,
                    )

                graph = graph_materializer(
                    cluster_result=cluster,
                    connection_factory=(
                        connection_factory
                    ),
                )
                observed = completed_case(
                    case=case,
                    cluster=cluster,
                    graph=graph,
                    id_to_label=id_to_label,
                )

            except (
                inbox_story_cluster_orchestration
                .MultimodalInboxStoryClusterNotReady
            ) as error:
                observed = noncompleted_case(
                    case=case,
                    status="not_ready",
                    error=error,
                )

            except (
                inbox_story_cluster_orchestration
                .MultimodalInboxStoryClusterProviderUnavailable,
                MultimodalGoldenLiveBudgetExceeded,
                MultimodalGoldenLiveProviderError,
            ) as error:
                provider_incomplete = True
                observed = noncompleted_case(
                    case=case,
                    status="provider_failure",
                    error=error,
                )

            except (
                inbox_story_cluster_orchestration
                .MultimodalInboxStoryClusterExecutionError
            ) as error:
                provider_incomplete = True
                observed = noncompleted_case(
                    case=case,
                    status="execution_incomplete",
                    error=error,
                )

            except (
                inbox_story_cluster_orchestration
                .MultimodalInboxStoryClusterInputError,
                inbox_story_cluster_orchestration
                .MultimodalInboxStoryClusterIntegrityError,
                story_claim_graph_materialization
                .StoryClaimGraphMaterializationError,
                MultimodalGoldenLiveInputError,
            ) as error:
                infrastructure_failures.append(
                    {
                        "case_id": case["case_id"],
                        "error_type": (
                            type(error).__name__
                        ),
                        "error": str(error)[:240],
                    }
                )
                observed = noncompleted_case(
                    case=case,
                    status="hard_failure",
                    error=error,
                )

        observed["provider_calls"] = (
            budget.call_count - calls_before
        )
        cases.append(observed)

        if provider_incomplete:
            break

    provider = budget.summary()
    quality_failures = [
        row["case_id"]
        for row in cases
        if row["score"]["quality_status"]
        != "pass"
    ]
    safety_failures = [
        row["case_id"]
        for row in cases
        if row["score"]["hard_safety_status"]
        != "pass"
    ]

    provider_complete = (
        not provider_incomplete
        and not budget.budget_exhausted
        and len(cases) == len(chosen)
    )

    hard_safety_status = (
        "pass"
        if not safety_failures
        and not infrastructure_failures
        else "fail"
    )

    descriptor = golden_dataset_descriptor()
    report = {
        "version": (
            MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION
        ),
        "mode": "live_observed_subset",
        "dataset_id": (
            MULTIMODAL_GOLDEN_DATASET_ID
        ),
        "dataset_digest": descriptor[
            "dataset_digest"
        ],
        "subset_case_ids": [
            case["case_id"]
            for case in chosen
        ],
        "expected_case_count": len(chosen),
        "completed_case_count": len(cases),
        "provider_complete": provider_complete,
        "provider_plan": plan,
        "capacity_preflight": preflight,
        "hard_safety_status": (
            hard_safety_status
        ),
        "quality_case_failures": (
            quality_failures
        ),
        "hard_safety_case_failures": (
            safety_failures
        ),
        "infrastructure_failures": (
            infrastructure_failures
        ),
        "quality_case_pass_rate": (
            round(
                (
                    len(cases)
                    - len(quality_failures)
                )
                / len(cases),
                6,
            )
            if cases
            else 0.0
        ),
        "provider": provider,
        "cases": cases,
        "policy": {
            "evaluation_is_model_dependent": True,
            "explicit_live_opt_in_required_by_cli": True,
            "provider_call_budget_is_hard": True,
            "provider_call_budget_checked_before_call": True,
            "provider_call_plan_logged_before_calls": True,
            "exact_pre_run_call_count_not_fabricated": True,
            "per_call_token_usage_logged": True,
            "cumulative_token_usage_logged": True,
            "uses_product34a_capacity_runtime": True,
            "provider_day_preflight_required": True,
            "production_usage_ledger_written": True,
            "real_database_used_for_capacity_ledger": True,
            "real_database_used_for_eval_state": False,
            "temporary_database_per_case": True,
            "pair_specific_eval_client_buckets": True,
            "runtime_entity_ids_use_production_derivation": True,
            "evaluation_text_semantic_adapter": True,
            "production_semantic_scheduling_unchanged": True,
            "frozen_dataset_mutated": False,
            "network_scope_is_gemini_only": True,
            "quality_failures_are_reported_not_hidden": True,
            "quality_failures_do_not_enable_live_merit": True,
            "synthetic_merit_baseline_forbidden": True,
            "live_merit_effect_allowed": False,
            "golden_labels_do_not_establish_truth": True,
            "golden_labels_do_not_establish_authority": True,
            "golden_labels_do_not_establish_independence": True,
        },
    }

    report["report_digest"] = _digest(
        {
            key: value
            for key, value in report.items()
            if key != "report_digest"
        }
    )
    return report


__all__ = [
    "MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION",
    "LIVE_MODEL",
    "EVAL_CLIENT_KEYS_BY_LABEL",
    "DEFAULT_LIVE_CASE_IDS",
    "DEFAULT_MAX_PROVIDER_CALLS",
    "BudgetedGeminiGenerator",
    "MultimodalGoldenLiveError",
    "MultimodalGoldenLiveInputError",
    "live_capacity_preflight",
    "evaluate_live_golden_subset",
]
