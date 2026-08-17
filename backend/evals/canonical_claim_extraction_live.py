from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from app.intelligence import canonical_claim_extraction
from app.intelligence import canonical_claims

from .golden_live_budget import (
    BudgetedGeminiGenerator,
    MultimodalGoldenLiveInputError,
    MultimodalGoldenLiveProviderError,
    capacity_snapshot,
    sqlite_connection_factory,
)
from .multimodal_golden_cases import STANDARD_CASES


CANONICAL_CLAIM_EXTRACTION_LIVE_VERSION = (
    "canonical-claim-extraction-live-v1"
)
LIVE_MODEL = "gemini-3.5-flash"
LIVE_MODE = "canonical_claim_extraction"
LIVE_CASE_ID = "football_bellingham_real_madrid_2023"
EXACT_PROVIDER_CALLS = 4

SUBJECT_KEY = "football|player|jude-bellingham"
REAL_MADRID_KEY = "football|club|real-madrid"
DORTMUND_KEY = "football|club|borussia-dortmund"

ALLOWED_ENTITIES = {
    SUBJECT_KEY: {
        "canonical_name": "Jude Bellingham",
        "entity_type": "player",
    },
    REAL_MADRID_KEY: {
        "canonical_name": "Real Madrid",
        "entity_type": "club",
    },
    DORTMUND_KEY: {
        "canonical_name": "Borussia Dortmund",
        "entity_type": "club",
    },
}

CLIENT_KEYS = {
    "anchor": "eval35c:bellingham:anchor",
    "web_positive": "eval35c:bellingham:web-positive",
    "youtube_positive": "eval35c:bellingham:youtube-positive",
    "hard_negative": "eval35c:bellingham:hard-negative",
}


class CanonicalClaimExtractionLiveError(RuntimeError):
    pass


class CanonicalClaimExtractionLiveInputError(
    CanonicalClaimExtractionLiveError
):
    pass


class CanonicalClaimExtractionLiveProviderError(
    CanonicalClaimExtractionLiveError
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
        raise CanonicalClaimExtractionLiveProviderError(
            "Gemini client initialization failed."
        ) from error


def _frozen_case() -> Dict[str, Any]:
    for case in STANDARD_CASES:
        if str(case.get("case_id") or "") == LIVE_CASE_ID:
            return dict(case)
    raise CanonicalClaimExtractionLiveInputError(
        "Frozen Bellingham case is missing."
    )


def live_inputs() -> Dict[str, str]:
    case = _frozen_case()
    related = list(case.get("related") or [])
    if len(related) != 2:
        raise CanonicalClaimExtractionLiveInputError(
            "Frozen Bellingham case must contain exactly two positive candidates."
        )
    output = {
        "anchor": str(case.get("anchor") or "").strip(),
        "web_positive": str(related[0] or "").strip(),
        "youtube_positive": str(related[1] or "").strip(),
        "hard_negative": str(case.get("hard_negative") or "").strip(),
    }
    if any(not value for value in output.values()):
        raise CanonicalClaimExtractionLiveInputError(
            "Frozen Bellingham live input is empty."
        )
    return output


def live_capacity_preflight(
    *,
    usage_connection_factory,
) -> Dict[str, Any]:
    snapshot = capacity_snapshot(
        usage_connection_factory=usage_connection_factory,
        model=LIVE_MODEL,
        client_keys=tuple(CLIENT_KEYS.values()),
        required_calls=EXACT_PROVIDER_CALLS,
        max_calls_per_client=1,
    )
    snapshot.update(
        {
            "exact_provider_calls": EXACT_PROVIDER_CALLS,
            "unique_source_count": EXACT_PROVIDER_CALLS,
            "one_call_per_unique_source": True,
            "pairwise_repeated_anchor_calls": False,
            "call_five_forbidden": True,
        }
    )
    return snapshot


def _safe_extraction_row(
    *,
    label: str,
    parsed: Optional[Mapping[str, Any]],
    error: Optional[Exception] = None,
) -> Dict[str, Any]:
    if error is not None:
        return {
            "label": label,
            "status": "invalid_output",
            "reason": "",
            "candidate": None,
            "core_key": "",
            "core_fingerprint": "",
            "specific_fingerprint": "",
            "error_type": type(error).__name__,
            "error": str(error)[:240],
            "raw_provider_response_stored": False,
        }

    value = dict(parsed or {})
    candidate = value.get("candidate")
    return {
        "label": label,
        "status": str(value.get("status") or ""),
        "reason": str(value.get("reason") or "")[:240],
        "candidate": dict(candidate) if isinstance(candidate, Mapping) else None,
        "core_key": str(value.get("core_key") or ""),
        "core_fingerprint": str(value.get("core_fingerprint") or ""),
        "specific_fingerprint": str(value.get("specific_fingerprint") or ""),
        "raw_provider_response_stored": False,
    }


def _comparison(
    anchor: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> Dict[str, Any]:
    left = anchor.get("candidate")
    right = candidate.get("candidate")
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return {
            "status": "not_comparable",
            "same_core": False,
            "same_specific": False,
            "material_conflicts": [],
        }
    result = canonical_claims.compare_canonical_claims(left, right)
    return {
        "status": result["status"],
        "same_core": bool(result["same_core"]),
        "same_specific": bool(result["same_specific"]),
        "material_conflicts": list(result["material_conflicts"]),
    }


def _quality(
    extractions: Mapping[str, Mapping[str, Any]],
    comparisons: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    failures = []

    anchor = extractions["anchor"]
    anchor_candidate = anchor.get("candidate")
    if anchor.get("status") != "extracted" or not isinstance(anchor_candidate, Mapping):
        failures.append("anchor_not_extracted")
    else:
        if anchor_candidate.get("event_type") != "transfer":
            failures.append("anchor_event_type")
        if anchor_candidate.get("state") != "completed":
            failures.append("anchor_state")
        if (
            dict(anchor_candidate.get("roles") or {}).get("destination")
            != REAL_MADRID_KEY
        ):
            failures.append("anchor_destination")

    for label in ("web_positive", "youtube_positive"):
        row = extractions[label]
        if row.get("status") != "extracted":
            failures.append(label + "_not_extracted")
            continue
        status = comparisons[label].get("status")
        if status not in {
            "exact_specific_match",
            "same_core_no_material_conflict",
        }:
            failures.append(label + "_did_not_converge")

    negative = extractions["hard_negative"]
    if negative.get("status") != "extracted":
        failures.append("hard_negative_not_extracted")
    elif comparisons["hard_negative"].get("status") != "different_core":
        failures.append("hard_negative_did_not_split")

    return {
        "status": "pass" if not failures else "fail",
        "failures": failures,
    }


def _hard_safety(
    extractions: Mapping[str, Mapping[str, Any]],
    comparisons: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    failures = []

    negative = extractions["hard_negative"]
    if negative.get("status") == "extracted":
        if comparisons["hard_negative"].get("same_core") is True:
            failures.append("hard_negative_merged_with_anchor")

    for row in extractions.values():
        candidate = row.get("candidate")
        if not isinstance(candidate, Mapping):
            continue
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
        "establishes_independence": False,
        "establishes_corroboration": False,
        "affects_live_merit": False,
    }


def evaluate_live_extraction(
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
        raise CanonicalClaimExtractionLiveInputError(
            "#35C requires an exact four-call budget."
        )

    key = str(api_key or "").strip()
    if not key and client is None:
        raise CanonicalClaimExtractionLiveInputError(
            "GEMINI_API_KEY is required for #35C live extraction."
        )

    if usage_connection_factory is None:
        if usage_db_path is None:
            raise CanonicalClaimExtractionLiveInputError(
                "Production Gemini usage DB path is required."
            )
        usage_connection_factory = sqlite_connection_factory(usage_db_path)

    preflight = live_capacity_preflight(
        usage_connection_factory=usage_connection_factory
    )
    if preflight.get("ready") is not True:
        raise CanonicalClaimExtractionLiveInputError(
            "#35C provider-day capacity preflight failed: "
            + ", ".join(str(value) for value in preflight.get("failures", []))
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

    inputs = live_inputs()
    allowed_keys = tuple(sorted(ALLOWED_ENTITIES))
    rows: Dict[str, Dict[str, Any]] = {}
    provider_incomplete = False

    for label in ("anchor", "web_positive", "youtube_positive", "hard_negative"):
        prompt = canonical_claim_extraction.build_canonical_claim_extraction_prompt(
            claim_text=inputs[label],
            subject_key=SUBJECT_KEY,
            allowed_entities=ALLOWED_ENTITIES,
        )
        try:
            response = budget(
                client=client,
                client_key=CLIENT_KEYS[label],
                mode=LIVE_MODE,
                model=LIVE_MODEL,
                contents=prompt,
            )
        except (MultimodalGoldenLiveProviderError, MultimodalGoldenLiveInputError) as error:
            provider_incomplete = True
            rows[label] = _safe_extraction_row(label=label, parsed=None, error=error)
            break
        except Exception as error:
            provider_incomplete = True
            rows[label] = _safe_extraction_row(label=label, parsed=None, error=error)
            break

        raw_text = _response_text(response)
        try:
            parsed = canonical_claim_extraction.parse_canonical_claim_extraction_output(
                raw_text,
                expected_subject_key=SUBJECT_KEY,
                allowed_entity_keys=allowed_keys,
            )
            rows[label] = _safe_extraction_row(label=label, parsed=parsed)
        except canonical_claim_extraction.CanonicalClaimExtractionError as error:
            rows[label] = _safe_extraction_row(label=label, parsed=None, error=error)

    for label in ("anchor", "web_positive", "youtube_positive", "hard_negative"):
        rows.setdefault(
            label,
            _safe_extraction_row(
                label=label,
                parsed=None,
                error=CanonicalClaimExtractionLiveProviderError(
                    "Provider sequence stopped before this source."
                ),
            ),
        )

    comparisons = {
        label: _comparison(rows["anchor"], rows[label])
        for label in ("web_positive", "youtube_positive", "hard_negative")
    }
    quality = _quality(rows, comparisons)
    hard_safety = _hard_safety(rows, comparisons)
    provider = budget.summary()
    provider_complete = (
        not provider_incomplete
        and provider.get("call_count") == EXACT_PROVIDER_CALLS
        and all(
            row.get("status") == "completed"
            for row in provider.get("call_log", [])
        )
    )

    report = {
        "version": CANONICAL_CLAIM_EXTRACTION_LIVE_VERSION,
        "mode": "live_structured_extraction",
        "case_id": LIVE_CASE_ID,
        "model": LIVE_MODEL,
        "provider_complete": bool(provider_complete),
        "exact_provider_calls_expected": EXACT_PROVIDER_CALLS,
        "capacity_preflight": preflight,
        "provider": provider,
        "extractions": [rows[label] for label in (
            "anchor",
            "web_positive",
            "youtube_positive",
            "hard_negative",
        )],
        "comparisons": comparisons,
        "quality": quality,
        "hard_safety": hard_safety,
        "policy": {
            "one_provider_call_per_unique_source": True,
            "pairwise_repeated_anchor_calls": False,
            "model_output_is_candidate_semantics_only": True,
            "deterministic_identity_authority_is_product35a": True,
            "structured_extraction_boundary_is_product35b": True,
            "entity_allowlist_enforced": True,
            "raw_provider_responses_stored": False,
            "raw_prompts_stored": False,
            "quality_failure_does_not_authorize_prompt_tuning": True,
            "quality_failure_does_not_authorize_gate_weakening": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "establishes_corroboration": False,
            "affects_live_merit": False,
            "network_scope_is_gemini_only": True,
        },
    }
    report["report_digest"] = _digest(
        {key: value for key, value in report.items() if key != "report_digest"}
    )
    return report


__all__ = [
    "CANONICAL_CLAIM_EXTRACTION_LIVE_VERSION",
    "LIVE_MODEL",
    "LIVE_MODE",
    "LIVE_CASE_ID",
    "EXACT_PROVIDER_CALLS",
    "SUBJECT_KEY",
    "REAL_MADRID_KEY",
    "DORTMUND_KEY",
    "ALLOWED_ENTITIES",
    "CLIENT_KEYS",
    "CanonicalClaimExtractionLiveError",
    "CanonicalClaimExtractionLiveInputError",
    "CanonicalClaimExtractionLiveProviderError",
    "live_inputs",
    "live_capacity_preflight",
    "evaluate_live_extraction",
]
