from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from app.intelligence import canonical_claims
from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import partial_claim_semantics

from . import canonical_claim_extraction_live as product35c_live
from .golden_live_budget import (
    BudgetedGeminiGenerator,
    MultimodalGoldenLiveInputError,
    MultimodalGoldenLiveProviderError,
    capacity_snapshot,
    sqlite_connection_factory,
)


CLAIM_SEMANTIC_EXTRACTION_ROUTER_LIVE_VERSION = (
    "claim-semantic-extraction-router-live-v1"
)
LIVE_MODEL = "gemini-3.5-flash"
LIVE_MODE = "claim_semantic_extraction_router"
LIVE_CASE_ID = product35c_live.LIVE_CASE_ID
EXACT_PROVIDER_CALLS = 1
CLIENT_KEY = "eval35f:bellingham:hard-negative"
SOURCE_LABEL = "hard_negative"

SUBJECT_KEY = product35c_live.SUBJECT_KEY
REAL_MADRID_KEY = product35c_live.REAL_MADRID_KEY
DORTMUND_KEY = product35c_live.DORTMUND_KEY
ALLOWED_ENTITIES = dict(product35c_live.ALLOWED_ENTITIES)


class ClaimSemanticExtractionRouterLiveError(RuntimeError):
    pass


class ClaimSemanticExtractionRouterLiveInputError(
    ClaimSemanticExtractionRouterLiveError
):
    pass


class ClaimSemanticExtractionRouterLiveProviderError(
    ClaimSemanticExtractionRouterLiveError
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


def _response_text(response: Any) -> str:
    if isinstance(response, Mapping):
        value = response.get("text", "")
    else:
        value = getattr(response, "text", "")
    return str(value or "").strip()


def _new_client(api_key: str):
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception as error:
        raise ClaimSemanticExtractionRouterLiveProviderError(
            "Gemini client initialization failed."
        ) from error


def live_input() -> str:
    value = str(
        product35c_live.live_inputs().get(SOURCE_LABEL) or ""
    ).strip()
    if not value:
        raise ClaimSemanticExtractionRouterLiveInputError(
            "Frozen Bellingham hard-negative input is missing."
        )
    return value


def deterministic_anchor() -> Dict[str, Any]:
    return canonical_claims.normalize_canonical_claim(
        {
            "subject_key": SUBJECT_KEY,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {
                "destination": REAL_MADRID_KEY,
            },
            "facets": {
                "effective_period": "2023",
            },
        }
    )


def live_capacity_preflight(
    *,
    usage_connection_factory,
) -> Dict[str, Any]:
    snapshot = capacity_snapshot(
        usage_connection_factory=usage_connection_factory,
        model=LIVE_MODEL,
        client_keys=(CLIENT_KEY,),
        required_calls=EXACT_PROVIDER_CALLS,
        max_calls_per_client=1,
    )
    snapshot.update(
        {
            "exact_provider_calls": EXACT_PROVIDER_CALLS,
            "unique_source_count": 1,
            "hard_negative_only": True,
            "positive_sources_recalled": False,
            "deterministic_anchor_only": True,
            "call_two_forbidden": True,
        }
    )
    return snapshot


def _safe_route_row(
    *,
    parsed: Optional[Mapping[str, Any]],
    error: Optional[Exception] = None,
) -> Dict[str, Any]:
    if error is not None:
        return {
            "label": SOURCE_LABEL,
            "status": "invalid_output",
            "route": "none",
            "reason": "",
            "candidate": None,
            "identity_complete": False,
            "missing_identity_fields": [],
            "core_key": "",
            "core_fingerprint": "",
            "specific_fingerprint": "",
            "safe_acceptance": False,
            "safe_exclusion": False,
            "error_type": type(error).__name__,
            "error": str(error)[:240],
            "raw_provider_response_stored": False,
        }

    value = dict(parsed or {})
    candidate = value.get("candidate")
    return {
        "label": SOURCE_LABEL,
        "status": str(value.get("status") or ""),
        "route": str(value.get("route") or ""),
        "reason": str(value.get("reason") or "")[:240],
        "candidate": dict(candidate) if isinstance(candidate, Mapping) else None,
        "identity_complete": bool(value.get("identity_complete")),
        "missing_identity_fields": list(
            value.get("missing_identity_fields") or []
        ),
        "core_key": str(value.get("core_key") or ""),
        "core_fingerprint": str(value.get("core_fingerprint") or ""),
        "specific_fingerprint": str(value.get("specific_fingerprint") or ""),
        "safe_acceptance": bool(value.get("safe_acceptance")),
        "safe_exclusion": bool(value.get("safe_exclusion")),
        "raw_provider_response_stored": False,
    }


def _comparison(route_row: Mapping[str, Any]) -> Dict[str, Any]:
    candidate = route_row.get("candidate")
    route = str(route_row.get("route") or "")
    anchor = deterministic_anchor()

    if not isinstance(candidate, Mapping):
        return {
            "kind": "none",
            "status": "not_comparable",
            "same_core": False,
            "structural_conflicts": [],
            "safe_exclusion": False,
            "safe_acceptance": False,
        }

    if route == router.ROUTE_PARTIAL_SEMANTICS:
        result = partial_claim_semantics.compare_full_claim_to_partial_semantics(
            anchor,
            candidate,
            allowed_entity_keys=tuple(sorted(ALLOWED_ENTITIES)),
        )
        return {
            "kind": "full_vs_partial",
            "status": str(result["status"]),
            "same_core": False,
            "structural_conflicts": list(result["structural_conflicts"]),
            "safe_exclusion": bool(result["safe_exclusion"]),
            "safe_acceptance": bool(result["safe_acceptance"]),
        }

    if route == router.ROUTE_FULL_IDENTITY:
        result = canonical_claims.compare_canonical_claims(
            anchor,
            candidate,
        )
        return {
            "kind": "full_vs_full",
            "status": str(result["status"]),
            "same_core": bool(result["same_core"]),
            "structural_conflicts": list(result["material_conflicts"]),
            "safe_exclusion": False,
            "safe_acceptance": False,
        }

    return {
        "kind": "none",
        "status": "not_comparable",
        "same_core": False,
        "structural_conflicts": [],
        "safe_exclusion": False,
        "safe_acceptance": False,
    }


def _quality(
    route_row: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    failures = []

    if route_row.get("status") != router.ROUTER_STATUS_PARTIAL:
        failures.append("hard_negative_not_partial")

    if route_row.get("route") != router.ROUTE_PARTIAL_SEMANTICS:
        failures.append("hard_negative_wrong_route")

    candidate = route_row.get("candidate")
    if not isinstance(candidate, Mapping):
        failures.append("hard_negative_missing_candidate")
    else:
        if candidate.get("event_type") != "match_event":
            failures.append("hard_negative_event_type")
        if candidate.get("state") != "scored":
            failures.append("hard_negative_state")

    if route_row.get("identity_complete") is not False:
        failures.append("hard_negative_identity_complete")

    if list(route_row.get("missing_identity_fields") or []) != [
        "facets.event_key"
    ]:
        failures.append("hard_negative_missing_identity_fields")

    if any(
        str(route_row.get(field) or "")
        for field in (
            "core_key",
            "core_fingerprint",
            "specific_fingerprint",
        )
    ):
        failures.append("partial_received_fingerprint")

    if comparison.get("status") != "structurally_incompatible":
        failures.append("hard_negative_not_structurally_incompatible")

    if comparison.get("safe_exclusion") is not True:
        failures.append("hard_negative_not_safe_to_exclude")

    if comparison.get("safe_acceptance") is not False:
        failures.append("hard_negative_unsafe_acceptance")

    return {
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }


def _hard_safety(
    route_row: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    failures = []

    if route_row.get("raw_provider_response_stored") is not False:
        failures.append("raw_provider_response_stored")

    if route_row.get("route") == router.ROUTE_PARTIAL_SEMANTICS:
        if any(
            str(route_row.get(field) or "")
            for field in (
                "core_key",
                "core_fingerprint",
                "specific_fingerprint",
            )
        ):
            failures.append("partial_received_fingerprint")

        if comparison.get("safe_acceptance") is True:
            failures.append("partial_safe_acceptance_enabled")

    if (
        route_row.get("route") == router.ROUTE_FULL_IDENTITY
        and comparison.get("same_core") is True
    ):
        failures.append("hard_negative_merged_with_transfer_anchor")

    candidate = route_row.get("candidate")
    if isinstance(candidate, Mapping):
        forbidden = {
            str(key).casefold()
            for key in candidate
            if str(key).casefold()
            in canonical_claims.FORBIDDEN_IDENTITY_FIELDS
        }
        if forbidden:
            failures.append("forbidden_identity_field")

    return {
        "status": "pass" if not failures else "fail",
        "failures": sorted(set(failures)),
        "establishes_truth": False,
        "establishes_authority": False,
        "establishes_reliability": False,
        "establishes_independence": False,
        "establishes_corroboration": False,
        "affects_live_merit": False,
    }


def evaluate_live_router_hard_negative(
    *,
    api_key: str,
    usage_db_path: str | Path | None = None,
    usage_connection_factory=None,
    max_calls: int = EXACT_PROVIDER_CALLS,
    client=None,
    client_factory=None,
    generator: Optional[BudgetedGeminiGenerator] = None,
    event_sink: Optional[Callable[[Mapping[str, Any]], None]] = None,
) -> Dict[str, Any]:
    if int(max_calls) != EXACT_PROVIDER_CALLS:
        raise ClaimSemanticExtractionRouterLiveInputError(
            "#35F requires an exact one-call budget."
        )

    key = str(api_key or "").strip()
    if not key and client is None:
        raise ClaimSemanticExtractionRouterLiveInputError(
            "GEMINI_API_KEY is required for #35F live validation."
        )

    if usage_connection_factory is None:
        if usage_db_path is None:
            raise ClaimSemanticExtractionRouterLiveInputError(
                "Production Gemini usage DB path is required."
            )
        usage_connection_factory = sqlite_connection_factory(usage_db_path)

    preflight = live_capacity_preflight(
        usage_connection_factory=usage_connection_factory
    )
    if preflight.get("ready") is not True:
        raise ClaimSemanticExtractionRouterLiveInputError(
            "#35F provider-day capacity preflight failed: "
            + ", ".join(
                str(value)
                for value in preflight.get("failures", [])
            )
        )

    budget = generator or BudgetedGeminiGenerator(
        usage_connection_factory=usage_connection_factory,
        max_calls=EXACT_PROVIDER_CALLS,
        event_sink=event_sink,
    )
    if event_sink is not None and generator is not None:
        budget.event_sink = event_sink if callable(event_sink) else None

    if client is None:
        factory = client_factory if callable(client_factory) else _new_client
        client = factory(key)

    prompt = router.build_claim_semantic_extraction_router_prompt(
        claim_text=live_input(),
        subject_key=SUBJECT_KEY,
        allowed_entities=ALLOWED_ENTITIES,
    )

    provider_incomplete = False
    try:
        response = budget(
            client=client,
            client_key=CLIENT_KEY,
            mode=LIVE_MODE,
            model=LIVE_MODEL,
            contents=prompt,
        )
    except (
        MultimodalGoldenLiveProviderError,
        MultimodalGoldenLiveInputError,
    ) as error:
        provider_incomplete = True
        row = _safe_route_row(parsed=None, error=error)
    except Exception as error:
        provider_incomplete = True
        row = _safe_route_row(parsed=None, error=error)
    else:
        raw_text = _response_text(response)
        try:
            parsed = router.parse_claim_semantic_extraction_router_output(
                raw_text,
                expected_subject_key=SUBJECT_KEY,
                allowed_entity_keys=tuple(sorted(ALLOWED_ENTITIES)),
            )
            row = _safe_route_row(parsed=parsed)
        except router.ClaimSemanticExtractionRouterError as error:
            row = _safe_route_row(parsed=None, error=error)

    comparison = _comparison(row)
    quality = _quality(row, comparison)
    hard_safety = _hard_safety(row, comparison)
    provider = budget.summary()
    provider_complete = (
        not provider_incomplete
        and provider.get("call_count") == EXACT_PROVIDER_CALLS
        and all(
            entry.get("status") == "completed"
            for entry in provider.get("call_log", [])
        )
    )

    report = {
        "version": CLAIM_SEMANTIC_EXTRACTION_ROUTER_LIVE_VERSION,
        "mode": "live_one_call_three_way_router_validation",
        "case_id": LIVE_CASE_ID,
        "source_label": SOURCE_LABEL,
        "source_text": live_input(),
        "model": LIVE_MODEL,
        "provider_complete": bool(provider_complete),
        "exact_provider_calls_expected": EXACT_PROVIDER_CALLS,
        "capacity_preflight": preflight,
        "provider": provider,
        "deterministic_anchor": deterministic_anchor(),
        "extraction": row,
        "comparison": comparison,
        "quality": quality,
        "hard_safety": hard_safety,
        "policy": {
            "hard_negative_only": True,
            "positive_sources_recalled": False,
            "deterministic_anchor_only": True,
            "model_output_is_candidate_semantics_only": True,
            "three_way_router_is_product35e": True,
            "partial_semantics_validator_is_product35d": True,
            "full_identity_authority_is_product35a": True,
            "raw_provider_responses_stored": False,
            "raw_prompts_stored": False,
            "quality_failure_is_measured_result": True,
            "quality_failure_does_not_authorize_prompt_tuning": True,
            "quality_failure_does_not_authorize_gate_weakening": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_reliability": False,
            "establishes_independence": False,
            "establishes_corroboration": False,
            "affects_live_merit": False,
            "network_scope_is_gemini_only": True,
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
    "CLAIM_SEMANTIC_EXTRACTION_ROUTER_LIVE_VERSION",
    "LIVE_MODEL",
    "LIVE_MODE",
    "LIVE_CASE_ID",
    "EXACT_PROVIDER_CALLS",
    "CLIENT_KEY",
    "SOURCE_LABEL",
    "SUBJECT_KEY",
    "REAL_MADRID_KEY",
    "DORTMUND_KEY",
    "ALLOWED_ENTITIES",
    "ClaimSemanticExtractionRouterLiveError",
    "ClaimSemanticExtractionRouterLiveInputError",
    "ClaimSemanticExtractionRouterLiveProviderError",
    "live_input",
    "deterministic_anchor",
    "live_capacity_preflight",
    "evaluate_live_router_hard_negative",
]
