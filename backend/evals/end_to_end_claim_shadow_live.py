from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, Mapping, Optional

from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import artifact_extraction
from app.services import multimodal_intelligence_bridge
from app.services import multimodal_structured_shadow_caller
from app.services import semantic_execution
from app.services import structured_claim_fusion

from .golden_live_budget import (
    BudgetedGeminiGenerator,
    MultimodalGoldenLiveInputError,
    MultimodalGoldenLiveProviderError,
    capacity_snapshot,
    sqlite_connection_factory,
)


END_TO_END_CLAIM_SHADOW_LIVE_VERSION = (
    "end-to-end-claim-shadow-live-v1"
)

LIVE_MODEL = "gemini-3.5-flash"
LIVE_MODE = "multimodal_fusion"
CLIENT_KEY = (
    "eval-claim-shadow-e2e:bellingham:partial-match-event"
)
EXACT_PROVIDER_CALLS = 1
SOURCE_LABEL = "partial_match_event"

ITEM_ID = "eval:claim-shadow:bellingham"
SUBJECT_KEY = "player|jude_bellingham"
SOURCE_TEXT = "Jude Bellingham scored in a league match."
SOURCE_URL = "https://example.invalid/sportabase/eval/claim-shadow"
OBSERVED_AT = "2026-08-18T12:00:00+00:00"

ALLOWED_ENTITIES = {
    SUBJECT_KEY: {
        "canonical_name": "Jude Bellingham",
        "entity_type": "player",
    },
}


class EndToEndClaimShadowLiveError(RuntimeError):
    pass


class EndToEndClaimShadowLiveInputError(
    EndToEndClaimShadowLiveError
):
    pass


class EndToEndClaimShadowLiveProviderError(
    EndToEndClaimShadowLiveError
):
    pass


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


def _model_dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value.dict()


def _new_client(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as error:
        raise EndToEndClaimShadowLiveProviderError(
            "Gemini client initialization failed."
        ) from error


def live_input() -> str:
    return SOURCE_TEXT


def structured_context() -> Dict[str, Any]:
    return (
        structured_claim_fusion
        .build_structured_claim_fusion_context(
            subject_key=SUBJECT_KEY,
            allowed_entity_keys=tuple(
                ALLOWED_ENTITIES
            ),
            allowed_entities=ALLOWED_ENTITIES,
        )
    )


def live_capacity_preflight(
    *,
    usage_connection_factory,
) -> Dict[str, Any]:
    snapshot = capacity_snapshot(
        usage_connection_factory=(
            usage_connection_factory
        ),
        model=LIVE_MODEL,
        client_keys=(CLIENT_KEY,),
        required_calls=EXACT_PROVIDER_CALLS,
        max_calls_per_client=1,
    )
    snapshot.update(
        {
            "exact_provider_calls": (
                EXACT_PROVIDER_CALLS
            ),
            "existing_fusion_mode_reused": True,
            "additional_structured_call": False,
            "call_two_forbidden": True,
            "raw_provider_response_stored": False,
            "raw_prompt_stored": False,
        }
    )
    return snapshot


def _source_artifact() -> (
    artifact_models.ExtractionArtifact
):
    return artifact_models.ExtractionArtifact(
        artifact_id="source:text",
        artifact_kind="text_component",
        modality="text",
        source_item_ids=[ITEM_ID],
        source_component_ids=["body"],
        content_hash=hashlib.sha256(
            SOURCE_TEXT.encode("utf-8")
        ).hexdigest(),
        payload={
            "role": "body",
            "text": SOURCE_TEXT,
            "language": "en",
        },
        provenance=(
            artifact_models
            .ArtifactProvenance(
                source_url=SOURCE_URL,
                observed_at=OBSERVED_AT,
                extraction_method=(
                    "claim_shadow_live_fixture"
                ),
            )
        ),
    )


def _item() -> content.UnifiedContentItem:
    return content.UnifiedContentItem(
        item_id=ITEM_ID,
        platform="web",
        platform_surface="article",
        container_kind="article",
        canonical_url=SOURCE_URL,
        observed_at=OBSERVED_AT,
        text_components=[
            content.TextComponent(
                component_id="body",
                role="body",
                text=SOURCE_TEXT,
            )
        ],
    )


def _bindings() -> bridge_models.BridgeBindings:
    return bridge_models.BridgeBindings(
        subject_key=SUBJECT_KEY,
        source_id="source:claim-shadow-eval",
        source_record_verified=True,
        media_item_id="media:claim-shadow-eval",
        media_item_record_verified=True,
    )


def _fusion_work() -> artifact_models.ArtifactWorkUnit:
    return artifact_models.ArtifactWorkUnit(
        work_id="work:claim-shadow-fusion",
        operation="multimodal_semantic_fusion",
        source_item_ids=[ITEM_ID],
        source_component_ids=["body"],
        parameters={
            "caption_media_pairs": [],
        },
    )


def _capture_prompt(
    *,
    context: Mapping[str, Any] | None,
) -> str:
    class PromptGenerator:
        def __init__(self):
            self.prompt = ""

        def __call__(self, **kwargs):
            self.prompt = str(
                kwargs["contents"][0]
            )
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "alignment_assessments": [],
                        "claim_candidates": [],
                    }
                )
            )

    generator = PromptGenerator()
    interpreter = (
        semantic_execution
        .GeminiSemanticInterpreter(
            client_factory=lambda: object(),
            generator=generator,
            client_key="prompt-capture",
            model=LIVE_MODEL,
        )
    )
    interpreter.fuse(
        [_source_artifact()],
        caption_media_pairs=[],
        structured_claim_context=context,
    )
    return generator.prompt


def _materialize_claim_candidate_artifact(
    *,
    interpreter: semantic_execution.GeminiSemanticInterpreter,
) -> artifact_models.ExtractionArtifact:
    executors = semantic_execution.build_semantic_executors(
        object(),
        interpreter=interpreter,
        perception_executor_builder=(
            lambda *_args, **_kwargs: {}
        ),
        structured_claim_context=(
            structured_context()
        ),
    )

    output_specs = executors[
        "multimodal_semantic_fusion"
    ](
        _fusion_work(),
        [_source_artifact()],
        {},
    )

    spec = next(
        row
        for row in output_specs
        if row.get("artifact_kind")
        == "claim_candidates"
    )

    return artifact_extraction._artifact(
        artifact_kind=spec["artifact_kind"],
        modality=spec["modality"],
        source_item_ids=[ITEM_ID],
        source_component_ids=["body"],
        payload=spec["payload"],
        provenance=(
            artifact_models
            .ArtifactProvenance(
                source_url=SOURCE_URL,
                observed_at=OBSERVED_AT,
                extraction_method=(
                    "claim_shadow_live_semantic_fusion"
                ),
            )
        ),
        metadata=spec.get("metadata"),
    )


def _safe_shadow_summary(
    result: Mapping[str, Any],
) -> Dict[str, Any]:
    report = result.get(
        "structured_shadow"
    )
    if not isinstance(report, Mapping):
        return {
            "status": "invalid_shadow_report",
            "structured_input": None,
            "candidate_rows": [],
            "policy": {},
        }

    rows = []
    for raw in list(
        report.get("candidate_rows")
        or []
    ):
        if not isinstance(raw, Mapping):
            continue
        candidate = raw.get("candidate")
        protocol = raw.get(
            "protocol_ownership"
        )
        rows.append(
            {
                "candidate_id": str(
                    raw.get("candidate_id")
                    or ""
                ),
                "production_claim_id": str(
                    raw.get(
                        "production_claim_id"
                    )
                    or ""
                ),
                "shadow_status": str(
                    raw.get("shadow_status")
                    or ""
                ),
                "router_status": str(
                    raw.get("router_status")
                    or ""
                ),
                "route": str(
                    raw.get("route")
                    or ""
                ),
                "reason": str(
                    raw.get("reason")
                    or ""
                )[:320],
                "candidate": (
                    dict(candidate)
                    if isinstance(
                        candidate,
                        Mapping,
                    )
                    else None
                ),
                "identity_complete": bool(
                    raw.get(
                        "identity_complete"
                    )
                ),
                "missing_identity_fields": list(
                    raw.get(
                        "missing_identity_fields"
                    )
                    or []
                ),
                "core_fingerprint": str(
                    raw.get(
                        "core_fingerprint"
                    )
                    or ""
                ),
                "specific_fingerprint": str(
                    raw.get(
                        "specific_fingerprint"
                    )
                    or ""
                ),
                "protocol_ownership": (
                    dict(protocol)
                    if isinstance(
                        protocol,
                        Mapping,
                    )
                    else None
                ),
                "persistence_allowed": bool(
                    raw.get(
                        "persistence_allowed"
                    )
                ),
                "replaces_production_identity": bool(
                    raw.get(
                        "replaces_production_identity"
                    )
                ),
                "story_membership_allowed": bool(
                    raw.get(
                        "story_membership_allowed"
                    )
                ),
                "corroboration_allowed": bool(
                    raw.get(
                        "corroboration_allowed"
                    )
                ),
                "live_merit_effect": bool(
                    raw.get(
                        "live_merit_effect"
                    )
                ),
                "raw_model_output_stored": bool(
                    raw.get(
                        "raw_model_output_stored"
                    )
                ),
            }
        )

    structured_input = report.get(
        "structured_input"
    )

    return {
        "status": str(
            report.get("status")
            or ""
        ),
        "structured_input": (
            dict(structured_input)
            if isinstance(
                structured_input,
                Mapping,
            )
            else None
        ),
        "candidate_rows": rows,
        "report_errors": list(
            report.get("report_errors")
            or []
        ),
        "raw_model_outputs_stored": bool(
            report.get(
                "raw_model_outputs_stored"
            )
        ),
        "persistence_allowed": bool(
            report.get(
                "persistence_allowed"
            )
        ),
        "replaces_production_identity": bool(
            report.get(
                "replaces_production_identity"
            )
        ),
        "story_membership_allowed": bool(
            report.get(
                "story_membership_allowed"
            )
        ),
        "corroboration_allowed": bool(
            report.get(
                "corroboration_allowed"
            )
        ),
        "live_merit_effect": bool(
            report.get(
                "live_merit_effect"
            )
        ),
    }


def _quality(
    shadow: Mapping[str, Any],
) -> Dict[str, Any]:
    failures = []

    structured_input = shadow.get(
        "structured_input"
    )
    if not isinstance(
        structured_input,
        Mapping,
    ):
        failures.append(
            "structured_input_summary_missing"
        )
    else:
        if (
            structured_input.get("source")
            != "semantic_manifest_sidecar"
        ):
            failures.append(
                "structured_input_source_wrong"
            )
        if int(
            structured_input.get(
                "provided_count",
                0,
            )
            or 0
        ) < 1:
            failures.append(
                "no_structured_sidecar_provided"
            )

    rows = list(
        shadow.get("candidate_rows")
        or []
    )
    matching = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        candidate = row.get("candidate")
        if not isinstance(candidate, Mapping):
            continue
        if (
            str(candidate.get("event_type") or "")
            == "match_event"
            and str(candidate.get("state") or "")
            == "scored"
        ):
            matching.append(row)

    if not matching:
        failures.append(
            "expected_scored_match_event_missing"
        )
    else:
        row = matching[0]
        if row.get("shadow_status") != "evaluated":
            failures.append(
                "expected_row_not_evaluated"
            )
        if row.get("router_status") != "partial":
            failures.append(
                "expected_router_status_not_partial"
            )
        if row.get("route") != "partial_semantics":
            failures.append(
                "expected_route_not_partial_semantics"
            )
        if (
            "facets.event_key"
            not in set(
                row.get(
                    "missing_identity_fields"
                )
                or []
            )
        ):
            failures.append(
                "event_key_not_reported_missing"
            )
        if row.get("core_fingerprint"):
            failures.append(
                "partial_received_core_fingerprint"
            )
        if row.get("specific_fingerprint"):
            failures.append(
                "partial_received_specific_fingerprint"
            )

    return {
        "status": (
            "pass"
            if not failures
            else "fail"
        ),
        "failures": sorted(
            set(failures)
        ),
    }


def _hard_safety(
    *,
    shadow: Mapping[str, Any],
    production_plan_unchanged: bool,
) -> Dict[str, Any]:
    failures = []

    if not production_plan_unchanged:
        failures.append(
            "production_plan_changed"
        )

    for field in (
        "raw_model_outputs_stored",
        "persistence_allowed",
        "replaces_production_identity",
        "story_membership_allowed",
        "corroboration_allowed",
        "live_merit_effect",
    ):
        if bool(shadow.get(field)):
            failures.append(
                "shadow_enabled_" + field
            )

    for row in list(
        shadow.get("candidate_rows")
        or []
    ):
        if not isinstance(row, Mapping):
            continue
        for field in (
            "raw_model_output_stored",
            "persistence_allowed",
            "replaces_production_identity",
            "story_membership_allowed",
            "corroboration_allowed",
            "live_merit_effect",
        ):
            if bool(row.get(field)):
                failures.append(
                    "candidate_enabled_" + field
                )

    return {
        "status": (
            "pass"
            if not failures
            else "fail"
        ),
        "failures": sorted(
            set(failures)
        ),
        "production_plan_unchanged": bool(
            production_plan_unchanged
        ),
        "establishes_truth": False,
        "establishes_authority": False,
        "establishes_reliability": False,
        "establishes_independence": False,
        "establishes_corroboration": False,
        "affects_live_merit": False,
    }


def evaluate_live_end_to_end_claim_shadow(
    *,
    api_key: str,
    usage_db_path: str | Path | None = None,
    usage_connection_factory=None,
    max_calls: int = EXACT_PROVIDER_CALLS,
    client=None,
    client_factory=None,
    generator: Optional[
        BudgetedGeminiGenerator
    ] = None,
    event_sink: Optional[
        Callable[[Mapping[str, Any]], None]
    ] = None,
) -> Dict[str, Any]:
    if int(max_calls) != EXACT_PROVIDER_CALLS:
        raise EndToEndClaimShadowLiveInputError(
            "End-to-End Claim Shadow Validation requires an exact one-call budget."
        )

    key = str(api_key or "").strip()
    if not key and client is None:
        raise EndToEndClaimShadowLiveInputError(
            "GEMINI_API_KEY is required for live validation."
        )

    if usage_connection_factory is None:
        if usage_db_path is None:
            raise EndToEndClaimShadowLiveInputError(
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
        )
    )
    if preflight.get("ready") is not True:
        raise EndToEndClaimShadowLiveInputError(
            "Provider-day capacity preflight failed: "
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
        max_calls=EXACT_PROVIDER_CALLS,
        event_sink=event_sink,
    )
    if (
        event_sink is not None
        and generator is not None
    ):
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

    base_prompt = _capture_prompt(
        context=None
    )
    structured_prompt = _capture_prompt(
        context=structured_context()
    )

    interpreter = (
        semantic_execution
        .GeminiSemanticInterpreter(
            client_factory=lambda: client,
            generator=budget,
            client_key=CLIENT_KEY,
            model=LIVE_MODEL,
        )
    )

    provider_incomplete = False
    evaluation_error = None
    claim_artifact = None

    try:
        claim_artifact = (
            _materialize_claim_candidate_artifact(
                interpreter=interpreter
            )
        )
    except (
        MultimodalGoldenLiveProviderError,
        MultimodalGoldenLiveInputError,
    ) as error:
        provider_incomplete = True
        evaluation_error = error
    except Exception as error:
        evaluation_error = error

    if claim_artifact is None:
        shadow = {
            "status": "not_evaluated",
            "structured_input": None,
            "candidate_rows": [],
            "report_errors": [
                type(evaluation_error).__name__
                + ":"
                + str(evaluation_error)[:320]
            ]
            if evaluation_error is not None
            else [],
            "raw_model_outputs_stored": False,
            "persistence_allowed": False,
            "replaces_production_identity": False,
            "story_membership_allowed": False,
            "corroboration_allowed": False,
            "live_merit_effect": False,
        }
        production_plan_unchanged = True
        candidate_count = 0
    else:
        manifest = artifact_models.ItemArtifactManifest(
            item_id=ITEM_ID,
            artifacts=[
                _source_artifact(),
                claim_artifact,
            ],
        )

        direct_plan = (
            multimodal_intelligence_bridge
            .build_item_intelligence_bridge(
                item=_item(),
                manifest=manifest,
                bindings=_bindings(),
            )
        )

        shadow_result = (
            multimodal_structured_shadow_caller
            .build_runtime_bridge_plan(
                item=_item(),
                manifest=manifest,
                bindings=_bindings(),
                shadow_enabled=True,
                structured_outputs_by_candidate_id=None,
                allowed_entity_keys=(
                    SUBJECT_KEY,
                ),
            )
        )

        shadow_plan = shadow_result[
            "production_plan"
        ]

        production_plan_unchanged = (
            _model_dump(direct_plan)
            == _model_dump(shadow_plan)
        )
        candidate_count = len(
            direct_plan.candidates
        )
        shadow = _safe_shadow_summary(
            shadow_result
        )

    quality = _quality(shadow)
    hard_safety = _hard_safety(
        shadow=shadow,
        production_plan_unchanged=(
            production_plan_unchanged
        ),
    )

    provider = budget.summary()
    provider_complete = (
        not provider_incomplete
        and provider.get("call_count")
        == EXACT_PROVIDER_CALLS
        and all(
            entry.get("status")
            == "completed"
            for entry in provider.get(
                "call_log",
                [],
            )
        )
    )

    prompt_delta = (
        len(structured_prompt)
        - len(base_prompt)
    )

    report = {
        "version": (
            END_TO_END_CLAIM_SHADOW_LIVE_VERSION
        ),
        "mode": (
            "live_one_call_existing_fusion_to_claim_shadow_validation"
        ),
        "source_label": SOURCE_LABEL,
        "source_text": SOURCE_TEXT,
        "model": LIVE_MODEL,
        "provider_complete": bool(
            provider_complete
        ),
        "exact_provider_calls_expected": (
            EXACT_PROVIDER_CALLS
        ),
        "provider": provider,
        "capacity_preflight": preflight,
        "prompt_measurement": {
            "base_prompt_digest": hashlib.sha256(
                base_prompt.encode("utf-8")
            ).hexdigest(),
            "structured_prompt_digest": hashlib.sha256(
                structured_prompt.encode("utf-8")
            ).hexdigest(),
            "base_prompt_chars": len(
                base_prompt
            ),
            "structured_prompt_chars": len(
                structured_prompt
            ),
            "prompt_char_delta": prompt_delta,
            "prompt_char_ratio": round(
                (
                    len(structured_prompt)
                    / max(1, len(base_prompt))
                ),
                4,
            ),
            "raw_prompt_stored": False,
        },
        "candidate_count": candidate_count,
        "shadow": shadow,
        "quality": quality,
        "hard_safety": hard_safety,
        "evaluation_error": (
            {
                "type": type(
                    evaluation_error
                ).__name__,
                "message": str(
                    evaluation_error
                )[:320],
            }
            if evaluation_error is not None
            else None
        ),
        "policy": {
            "existing_multimodal_fusion_mode_reused": True,
            "additional_structured_provider_call": False,
            "structured_output_travels_via_metadata_sidecar": True,
            "sidecar_collected_automatically": True,
            "production_plan_must_remain_identical": True,
            "raw_provider_response_stored": False,
            "raw_prompt_stored": False,
            "model_output_is_candidate_semantics_only": True,
            "model_does_not_establish_identity": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_reliability": False,
            "establishes_independence": False,
            "establishes_corroboration": False,
            "affects_live_merit": False,
            "quality_failure_is_measured_result": True,
            "quality_failure_does_not_authorize_gate_weakening": True,
            "call_two_forbidden": True,
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
    "END_TO_END_CLAIM_SHADOW_LIVE_VERSION",
    "LIVE_MODEL",
    "LIVE_MODE",
    "CLIENT_KEY",
    "EXACT_PROVIDER_CALLS",
    "SOURCE_LABEL",
    "ITEM_ID",
    "SUBJECT_KEY",
    "SOURCE_TEXT",
    "SOURCE_URL",
    "OBSERVED_AT",
    "ALLOWED_ENTITIES",
    "EndToEndClaimShadowLiveError",
    "EndToEndClaimShadowLiveInputError",
    "EndToEndClaimShadowLiveProviderError",
    "live_input",
    "structured_context",
    "live_capacity_preflight",
    "evaluate_live_end_to_end_claim_shadow",
]
