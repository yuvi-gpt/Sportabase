from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.intelligence.runtime_finalization import (
    finalize_structured_claim_materialization,
)
from app.intelligence.structured_claim_ingestion import (
    build_structured_claim_allowlist,
    materialize_selected_structured_claim_safely,
)
from app.services import multimodal_intelligence_runtime
from app.services import multimodal_shadow_api as base_shadow_api
from app.services import semantic_execution


MULTIMODAL_STRUCTURED_INGESTION_ADAPTER_VERSION = (
    "multimodal-structured-ingestion-adapter-v1"
)


def _clean(value: Any, maximum: int = 256) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _request_side_capture(
    request_payload: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    raw_side = request_payload.get(side)
    if not isinstance(raw_side, Mapping):
        return {}
    capture = raw_side.get("capture")
    return dict(capture) if isinstance(capture, Mapping) else {}


def _fallback_allowlist(
    *,
    subject_key: str,
) -> dict[str, Any]:
    subject = _clean(subject_key, 256).casefold()
    return {
        "version": MULTIMODAL_STRUCTURED_INGESTION_ADAPTER_VERSION,
        "status": "unavailable",
        "resolution_status": "subject_context_unavailable",
        "subject_key": subject,
        "allowed_entity_keys": [subject] if subject else [],
        "allowed_entities": (
            {
                subject: {
                    "entity_key": subject,
                    "canonical_name": "",
                    "entity_type": "",
                }
            }
            if subject
            else {}
        ),
        "counts": {
            "entities": 1 if subject else 0,
            "ambiguous_aliases_excluded": 0,
        },
        "policy": {
            "fallback_is_subject_only": True,
            "no_fuzzy_entity_guessing": True,
            "provider_call_performed": False,
            "affects_live_merit": False,
        },
    }


def _reports_by_side(diagnostics: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for raw in diagnostics:
        if not isinstance(raw, Mapping):
            continue
        side = _clean(raw.get("side"), 16).casefold()
        report = raw.get("structured_shadow")
        if side not in {"left", "right"} or not isinstance(report, Mapping):
            continue
        output[side] = dict(report)
    return output


def _selected_source_observation_id(
    result: Mapping[str, Any],
    side: str,
) -> str:
    stages = result.get("stages")
    if not isinstance(stages, Mapping):
        return ""
    side_stage = stages.get(side)
    if not isinstance(side_stage, Mapping):
        return ""
    persistence = side_stage.get("persistence")
    if not isinstance(persistence, Mapping):
        return ""
    rows = persistence.get("candidate_rows")
    if not isinstance(rows, list) or len(rows) != 1:
        return ""
    row = rows[0]
    if not isinstance(row, Mapping):
        return ""
    return _clean(row.get("source_observation_id"), 128)


def _materialization_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": _clean(value.get("version"), 128),
        "status": _clean(value.get("status"), 64),
        "reason": _clean(value.get("reason"), 128),
        "production_claim_id": _clean(
            value.get("production_claim_id"), 128
        ),
        "canonical_claim_id": _clean(
            value.get("canonical_claim_id"), 128
        ),
        "mapping_status": _clean(value.get("mapping_status"), 64),
        "policy": dict(value.get("policy") or {}),
    }


def _evolution_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    evolution = value.get("evolution")
    evolution = dict(evolution) if isinstance(evolution, Mapping) else {}
    return {
        "version": _clean(value.get("version"), 128),
        "status": _clean(value.get("status"), 64),
        "reason": _clean(value.get("reason"), 128),
        "canonical_claim_id": _clean(value.get("canonical_claim_id"), 128),
        "evolution_status": _clean(evolution.get("status"), 64),
        "family_key": _clean(evolution.get("family_key"), 256),
        "family_claim_count": int(evolution.get("family_claim_count") or 0),
        "links_written": int(evolution.get("links_written") or 0),
        "policy": dict(value.get("policy") or {}),
    }


def execute_multimodal_shadow_api(
    *,
    request_payload: Mapping[str, Any],
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    runtime_runner=(
        multimodal_intelligence_runtime
        .run_multimodal_intelligence_runtime
    ),
    interpreter_factory=(
        semantic_execution
        .GeminiSemanticInterpreter
    ),
    now_provider=None,
) -> dict[str, Any]:
    """Run existing multimodal shadow with structured claim fusion enabled.

    Structured claim semantics piggyback on the existing multimodal fusion
    provider call. The adapter captures the existing isolated shadow report and
    promotes a canonical identity only when both selected sides independently
    produce complete, compatible structured identities.
    """

    request_copy = copy.deepcopy(dict(request_payload))
    subject_key = _clean(request_copy.get("subject_key"), 256).casefold()

    try:
        allowlist = build_structured_claim_allowlist(
            subject_key=subject_key,
            left_capture=_request_side_capture(request_copy, "left"),
            right_capture=_request_side_capture(request_copy, "right"),
            connection_factory=connection_factory,
        )
    except Exception:
        # Base adapter still owns authoritative binding validation. A failed
        # optional mention-resolution pass must not break the legacy runtime.
        allowlist = _fallback_allowlist(subject_key=subject_key)

    diagnostics: list[dict[str, Any]] = []

    def structured_sink(payload):
        if isinstance(payload, Mapping):
            diagnostics.append(copy.deepcopy(dict(payload)))

    def structured_runtime(**kwargs):
        call_kwargs = dict(kwargs)
        call_kwargs.update(
            {
                "structured_claim_shadow_enabled": True,
                "structured_claim_allowed_entity_keys": tuple(
                    allowlist.get("allowed_entity_keys") or ()
                ),
                "structured_claim_allowed_entities": dict(
                    allowlist.get("allowed_entities") or {}
                ),
                "structured_shadow_sink": structured_sink,
            }
        )
        return runtime_runner(**call_kwargs)

    base_kwargs = {
        "request_payload": request_copy,
        "connection_factory": connection_factory,
        "gemini_client": gemini_client,
        "gemini_client_key": gemini_client_key,
        "gemini_generator": gemini_generator,
        "runtime_runner": structured_runtime,
        "interpreter_factory": interpreter_factory,
    }
    if now_provider is not None:
        base_kwargs["now_provider"] = now_provider

    payload = base_shadow_api.execute_multimodal_shadow_api(**base_kwargs)
    if not isinstance(payload, Mapping):
        return payload

    output = copy.deepcopy(dict(payload))
    raw_result = output.get("result")
    if not isinstance(raw_result, Mapping):
        return output

    result = copy.deepcopy(dict(raw_result))
    reports = _reports_by_side(diagnostics)

    materialization = materialize_selected_structured_claim_safely(
        production_claim_id=_clean(result.get("claim_id"), 128),
        subject_key=_clean(result.get("subject_key"), 256),
        left_candidate_id=_clean(result.get("left_candidate_id"), 256),
        right_candidate_id=_clean(result.get("right_candidate_id"), 256),
        left_shadow_report=reports.get("left"),
        right_shadow_report=reports.get("right"),
        left_source_observation_id=_selected_source_observation_id(
            result,
            "left",
        ),
        right_source_observation_id=_selected_source_observation_id(
            result,
            "right",
        ),
        connection_factory=connection_factory,
    )
    finalization = finalize_structured_claim_materialization(
        materialization=materialization,
        connection_factory=connection_factory,
    )

    stages = result.get("stages")
    stages = copy.deepcopy(dict(stages)) if isinstance(stages, Mapping) else {}
    stages["canonical_claim_materialization"] = materialization
    stages["claim_evolution_reconciliation"] = finalization
    stages["canonical_claim_story_materialization"] = finalization.get("story")
    result["stages"] = stages

    result["structured_claim_ingestion"] = {
        "version": MULTIMODAL_STRUCTURED_INGESTION_ADAPTER_VERSION,
        "status": "completed",
        "allowlist": {
            "status": _clean(allowlist.get("status"), 64),
            "resolution_status": _clean(
                allowlist.get("resolution_status"), 64
            ),
            "entity_count": int(
                (allowlist.get("counts") or {}).get("entities") or 0
            ),
            "ambiguous_aliases_excluded": int(
                (allowlist.get("counts") or {}).get(
                    "ambiguous_aliases_excluded"
                )
                or 0
            ),
        },
        "materialization": _materialization_summary(materialization),
        "evolution": _evolution_summary(finalization),
        "policy": {
            "existing_multimodal_fusion_call_reused": True,
            "additional_provider_calls": 0,
            "structured_shadow_cannot_select_production_claim": True,
            "dual_full_identity_required_for_materialization": True,
            "materialization_failure_is_advisory": True,
            "claim_evolution_runs_after_materialization": True,
            "claim_evolution_failure_is_advisory": True,
            "affects_live_merit": False,
        },
    }

    policy = result.get("policy")
    policy = copy.deepcopy(dict(policy)) if isinstance(policy, Mapping) else {}
    policy.update(
        {
            "structured_claim_shadow_enabled": True,
            "structured_claim_existing_fusion_call_reused": True,
            "structured_claim_additional_provider_calls": 0,
            "structured_claim_materialization_is_advisory": True,
            "claim_evolution_reconciliation_enabled": True,
            "claim_evolution_reconciliation_is_advisory": True,
            "canonical_identity_does_not_establish_truth": True,
        }
    )
    result["policy"] = policy
    output["result"] = result

    outer_policy = output.get("policy")
    if isinstance(outer_policy, Mapping):
        outer_policy = copy.deepcopy(dict(outer_policy))
        outer_policy.update(
            {
                "structured_claim_shadow_enabled": True,
                "structured_claim_additional_provider_calls": 0,
                "canonical_identity_materialization_advisory": True,
                "claim_evolution_reconciliation_enabled": True,
                "claim_evolution_reconciliation_advisory": True,
            }
        )
        output["policy"] = outer_policy

    return output


__all__ = [
    "MULTIMODAL_STRUCTURED_INGESTION_ADAPTER_VERSION",
    "execute_multimodal_shadow_api",
]
