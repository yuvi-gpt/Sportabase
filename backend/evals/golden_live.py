from __future__ import annotations

import hashlib
import json
import tempfile

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from app.services import inbox_story_cluster_orchestration
from app.services import story_claim_graph_materialization

from .golden_capture import clean
from .golden_dataset import golden_dataset_descriptor
from .golden_runtime import _factory, _initialize, _insert_entities, _store_captures
from .golden_live_budget import (
    BudgetedGeminiGenerator,
    DEFAULT_MAX_PROVIDER_CALLS,
    MultimodalGoldenLiveBudgetExceeded,
    MultimodalGoldenLiveError,
    MultimodalGoldenLiveInputError,
    MultimodalGoldenLiveProviderError,
)
from .golden_live_scoring import (
    DEFAULT_LIVE_CASE_IDS,
    completed_case,
    noncompleted_case,
    provider_call_plan,
    selected_cases,
)
from .multimodal_golden_cases import MULTIMODAL_GOLDEN_DATASET_ID


MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION = "multimodal-golden-live-eval-v1"


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


def evaluate_live_golden_subset(
    *,
    api_key: str,
    max_calls: int = DEFAULT_MAX_PROVIDER_CALLS,
    case_ids: Sequence[str] = DEFAULT_LIVE_CASE_IDS,
    client=None,
    client_factory=None,
    generator: Optional[BudgetedGeminiGenerator] = None,
    event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    cluster_runner=inbox_story_cluster_orchestration.execute_multisource_inbox_story_cluster_shadow,
    graph_materializer=story_claim_graph_materialization.materialize_story_claim_graph,
) -> Dict[str, Any]:
    key = clean(api_key)
    if not key and client is None:
        raise MultimodalGoldenLiveInputError(
            "GEMINI_API_KEY is required for the live golden evaluation."
        )

    chosen = selected_cases(case_ids)
    plan = provider_call_plan(case_ids)
    budget = generator or BudgetedGeminiGenerator(
        max_calls=max_calls,
        event_sink=event_sink,
    )
    if not isinstance(budget, BudgetedGeminiGenerator):
        raise MultimodalGoldenLiveInputError(
            "Live golden generator must be BudgetedGeminiGenerator."
        )
    if event_sink is not None and generator is not None:
        budget.event_sink = event_sink if callable(event_sink) else None
    if budget.max_calls < int(plan["maximum_calls"]):
        raise MultimodalGoldenLiveInputError(
            "Provider budget is too small for the frozen full-case live plan; "
            f"need {plan['maximum_calls']} calls of headroom."
        )

    if client is None:
        factory = client_factory if callable(client_factory) else _new_client
        client = factory(key)

    cases = []
    provider_incomplete = False
    infrastructure_failures = []

    for case in chosen:
        calls_before = budget.call_count
        with tempfile.TemporaryDirectory(prefix="sportabase-golden-live-") as tmp:
            db_path = Path(tmp) / "golden-live.db"
            _initialize(db_path)
            connection_factory = _factory(db_path)
            _insert_entities(case, connection_factory)
            label_to_id, id_to_label = _store_captures(case, connection_factory)
            try:
                cluster = cluster_runner(
                    anchor_capture_record_id=label_to_id["anchor"],
                    analysis_version=MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION,
                    scoring_version=MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION,
                    target_claim_id="",
                    scan_limit=100,
                    max_candidates=12,
                    connection_factory=connection_factory,
                    gemini_client=client,
                    gemini_client_key="golden-live-eval",
                    gemini_generator=budget,
                )
                graph = graph_materializer(
                    cluster_result=cluster,
                    connection_factory=connection_factory,
                )
                observed = completed_case(
                    case=case,
                    cluster=cluster,
                    graph=graph,
                    id_to_label=id_to_label,
                )
            except inbox_story_cluster_orchestration.MultimodalInboxStoryClusterNotReady as error:
                observed = noncompleted_case(case=case, status="not_ready", error=error)
            except (
                inbox_story_cluster_orchestration.MultimodalInboxStoryClusterProviderUnavailable,
                MultimodalGoldenLiveBudgetExceeded,
                MultimodalGoldenLiveProviderError,
            ) as error:
                provider_incomplete = True
                observed = noncompleted_case(case=case, status="provider_failure", error=error)
            except inbox_story_cluster_orchestration.MultimodalInboxStoryClusterExecutionError as error:
                provider_incomplete = True
                observed = noncompleted_case(case=case, status="execution_incomplete", error=error)
            except (
                inbox_story_cluster_orchestration.MultimodalInboxStoryClusterInputError,
                inbox_story_cluster_orchestration.MultimodalInboxStoryClusterIntegrityError,
                story_claim_graph_materialization.StoryClaimGraphMaterializationError,
            ) as error:
                infrastructure_failures.append({
                    "case_id": case["case_id"],
                    "error_type": type(error).__name__,
                    "error": str(error)[:240],
                })
                observed = noncompleted_case(case=case, status="hard_failure", error=error)
        observed["provider_calls"] = budget.call_count - calls_before
        cases.append(observed)
        if provider_incomplete:
            break

    provider = budget.summary()
    quality_failures = [
        row["case_id"] for row in cases if row["score"]["quality_status"] != "pass"
    ]
    safety_failures = [
        row["case_id"] for row in cases if row["score"]["hard_safety_status"] != "pass"
    ]
    provider_complete = (
        not provider_incomplete
        and not budget.budget_exhausted
        and len(cases) == len(chosen)
    )
    hard_safety_status = (
        "pass" if not safety_failures and not infrastructure_failures else "fail"
    )
    descriptor = golden_dataset_descriptor()
    report = {
        "version": MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION,
        "mode": "live_observed_subset",
        "dataset_id": MULTIMODAL_GOLDEN_DATASET_ID,
        "dataset_digest": descriptor["dataset_digest"],
        "subset_case_ids": [case["case_id"] for case in chosen],
        "expected_case_count": len(chosen),
        "completed_case_count": len(cases),
        "provider_complete": provider_complete,
        "provider_plan": plan,
        "hard_safety_status": hard_safety_status,
        "quality_case_failures": quality_failures,
        "hard_safety_case_failures": safety_failures,
        "infrastructure_failures": infrastructure_failures,
        "quality_case_pass_rate": (
            round((len(cases) - len(quality_failures)) / len(cases), 6)
            if cases else 0.0
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
            "production_usage_ledger_written": False,
            "real_database_used": False,
            "temporary_database_per_case": True,
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
    report["report_digest"] = _digest({
        key: value for key, value in report.items() if key != "report_digest"
    })
    return report


__all__ = [
    "MULTIMODAL_GOLDEN_LIVE_EVAL_VERSION",
    "DEFAULT_LIVE_CASE_IDS",
    "DEFAULT_MAX_PROVIDER_CALLS",
    "BudgetedGeminiGenerator",
    "MultimodalGoldenLiveError",
    "MultimodalGoldenLiveInputError",
    "evaluate_live_golden_subset",
]
