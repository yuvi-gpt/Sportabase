from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

from app.intelligence import canonical_claims
from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import claim_semantic_protocol_ownership as ownership
from app.intelligence import partial_claim_semantics

from . import claim_semantic_extraction_router_live as product35f_live
from .golden_live_budget import (
    BudgetedGeminiGenerator,
    MultimodalGoldenLiveInputError,
    MultimodalGoldenLiveProviderError,
    capacity_snapshot,
    sqlite_connection_factory,
)


CLAIM_SEMANTIC_PROTOCOL_OWNED_LIVE_VERSION = (
    "claim-semantic-protocol-owned-live-v1"
)
LIVE_MODEL = product35f_live.LIVE_MODEL
LIVE_MODE = "claim_semantic_protocol_owned_router"
LIVE_CASE_ID = product35f_live.LIVE_CASE_ID
EXACT_PROVIDER_CALLS = 1
CLIENT_KEY = "eval35h:bellingham:hard-negative"
SOURCE_LABEL = product35f_live.SOURCE_LABEL

SUBJECT_KEY = product35f_live.SUBJECT_KEY
REAL_MADRID_KEY = product35f_live.REAL_MADRID_KEY
DORTMUND_KEY = product35f_live.DORTMUND_KEY
ALLOWED_ENTITIES = dict(product35f_live.ALLOWED_ENTITIES)


class ClaimSemanticProtocolOwnedLiveError(RuntimeError):
    pass


class ClaimSemanticProtocolOwnedLiveInputError(
    ClaimSemanticProtocolOwnedLiveError
):
    pass


class ClaimSemanticProtocolOwnedLiveProviderError(
    ClaimSemanticProtocolOwnedLiveError
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
        raise ClaimSemanticProtocolOwnedLiveProviderError(
            "Gemini client initialization failed."
        ) from error


def live_input() -> str:
    return product35f_live.live_input()


def deterministic_anchor() -> Dict[str, Any]:
    return product35f_live.deterministic_anchor()


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
            "same_product35e_prompt": True,
            "protocol_ownership_is_product35g": True,
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
            "protocol_ownership": None,
            "error_type": type(error).__name__,
            "error": str(error)[:320],
            "raw_provider_response_stored": False,
        }

    value = dict(parsed or {})
    candidate = value.get("candidate")
    protocol = value.get("protocol_ownership")

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
        "protocol_ownership": (
            dict(protocol)
            if isinstance(protocol, Mapping)
            else None
        ),
        "raw_provider_response_stored": False,
    }


def _comparison(route_row: Mapping[str, Any]) -> Dict[str, Any]:
    return product35f_live._comparison(route_row)


def _quality(
    route_row: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    failures = list(
        product35f_live._quality(
            route_row,
            comparison,
        )["failures"]
    )

    protocol = route_row.get("protocol_ownership")
    if not isinstance(protocol, Mapping):
        failures.append("protocol_ownership_missing")
    else:
        if protocol.get("semantic_fields_rewritten") is not False:
            failures.append("semantic_fields_rewritten")
        if protocol.get("status_rewritten") is not False:
            failures.append("status_rewritten")
        if protocol.get("reason_rewritten") is not False:
            failures.append("reason_rewritten")

        if route_row.get("route") == router.ROUTE_PARTIAL_SEMANTICS:
            if (
                str(
                    protocol.get(
                        "validator_assigned_candidate_contract_version"
                    )
                    or ""
                )
                != partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION
            ):
                failures.append("partial_validator_version_wrong")

    return {
        "status": "pass" if not failures else "fail",
        "failures": sorted(set(failures)),
    }


def _hard_safety(
    route_row: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> Dict[str, Any]:
    base = product35f_live._hard_safety(
        route_row,
        comparison,
    )
    failures = list(base["failures"])

    protocol = route_row.get("protocol_ownership")
    if isinstance(protocol, Mapping):
        if protocol.get("semantic_fields_rewritten") is not False:
            failures.append("protocol_rewrote_semantics")
        if protocol.get("status_rewritten") is not False:
            failures.append("protocol_rewrote_status")
        if protocol.get("reason_rewritten") is not False:
            failures.append("protocol_rewrote_reason")
        if (
            protocol.get("candidate_contract_version_supplied_by_model") is True
            and protocol.get(
                "candidate_contract_version_removed_before_validation"
            ) is not True
        ):
            failures.append("model_candidate_version_not_removed")

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


def evaluate_live_protocol_owned_hard_negative(
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
        raise ClaimSemanticProtocolOwnedLiveInputError(
            "#35H requires an exact one-call budget."
        )

    key = str(api_key or "").strip()
    if not key and client is None:
        raise ClaimSemanticProtocolOwnedLiveInputError(
            "GEMINI_API_KEY is required for #35H live validation."
        )

    if usage_connection_factory is None:
        if usage_db_path is None:
            raise ClaimSemanticProtocolOwnedLiveInputError(
                "Production Gemini usage DB path is required."
            )
        usage_connection_factory = sqlite_connection_factory(usage_db_path)

    preflight = live_capacity_preflight(
        usage_connection_factory=usage_connection_factory
    )
    if preflight.get("ready") is not True:
        raise ClaimSemanticProtocolOwnedLiveInputError(
            "#35H provider-day capacity preflight failed: "
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
    prompt_digest = hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()

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
            parsed = ownership.parse_protocol_owned_claim_semantic_output(
                raw_text,
                expected_subject_key=SUBJECT_KEY,
                allowed_entity_keys=tuple(sorted(ALLOWED_ENTITIES)),
            )
            row = _safe_route_row(parsed=parsed)
        except ownership.ClaimSemanticProtocolOwnershipError as error:
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
        "version": CLAIM_SEMANTIC_PROTOCOL_OWNED_LIVE_VERSION,
        "mode": "live_one_call_protocol_owned_three_way_router_validation",
        "case_id": LIVE_CASE_ID,
        "source_label": SOURCE_LABEL,
        "source_text": live_input(),
        "model": LIVE_MODEL,
        "provider_complete": bool(provider_complete),
        "exact_provider_calls_expected": EXACT_PROVIDER_CALLS,
        "prompt_digest": prompt_digest,
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
            "same_product35e_prompt": True,
            "prompt_rewritten_after_product35f": False,
            "model_output_is_candidate_semantics_only": True,
            "protocol_ownership_is_product35g": True,
            "three_way_router_is_product35e": True,
            "partial_semantics_validator_is_product35d": True,
            "full_identity_authority_is_product35a": True,
            "model_controls_candidate_contract_version": False,
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
    "CLAIM_SEMANTIC_PROTOCOL_OWNED_LIVE_VERSION",
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
    "ClaimSemanticProtocolOwnedLiveError",
    "ClaimSemanticProtocolOwnedLiveInputError",
    "ClaimSemanticProtocolOwnedLiveProviderError",
    "live_input",
    "deterministic_anchor",
    "live_capacity_preflight",
    "evaluate_live_protocol_owned_hard_negative",
]
