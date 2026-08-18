from __future__ import annotations

import json
import re

from typing import Any, Dict, Mapping, Sequence

from app.intelligence import claim_semantic_extraction_router as router


CLAIM_SEMANTIC_PROTOCOL_OWNERSHIP_CONTRACT_VERSION = (
    "claim-semantic-protocol-ownership-contract-v1"
)

MODEL_PROTOCOL_POLICY = {
    "model_controls_outer_envelope_version": True,
    "outer_envelope_version_remains_strict": True,
    "model_controls_candidate_contract_version": False,
    "candidate_contract_version_is_transport_metadata": True,
    "candidate_contract_version_removed_before_validation": True,
    "validator_assigns_internal_candidate_contract_version": True,
    "semantic_fields_are_not_rewritten": True,
    "status_is_not_rewritten": True,
    "reason_is_not_rewritten": True,
    "unknown_semantic_fields_still_fail_closed": True,
    "forbidden_identity_fields_still_fail_closed": True,
    "status_mismatch_still_fails_closed": True,
    "partial_semantics_can_establish_same_claim": False,
    "fuzzy_similarity_used": False,
    "model_equivalence_decision_used": False,
    "establishes_truth": False,
    "establishes_authority": False,
    "establishes_reliability": False,
    "establishes_independence": False,
    "establishes_corroboration": False,
    "affects_live_merit": False,
    "training_eligible": False,
}


class ClaimSemanticProtocolOwnershipError(ValueError):
    pass


class ClaimSemanticProtocolOwnershipInputError(
    ClaimSemanticProtocolOwnershipError
):
    pass


class ClaimSemanticProtocolOwnershipOutputError(
    ClaimSemanticProtocolOwnershipError
):
    pass


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _token(value: Any) -> str:
    return (
        _clean_text(value)
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _parse_json_object(raw_output: Any) -> Dict[str, Any]:
    if isinstance(raw_output, Mapping):
        return dict(raw_output)

    text = str(raw_output or "").strip()

    if not text:
        raise ClaimSemanticProtocolOwnershipOutputError(
            "Claim semantic model output is empty."
        )

    fenced = re.fullmatch(
        r"\s*```(?:json)?\s*(.*?)\s*```\s*",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise ClaimSemanticProtocolOwnershipOutputError(
            "Claim semantic model output is not valid JSON."
        ) from error

    if not isinstance(parsed, dict):
        raise ClaimSemanticProtocolOwnershipOutputError(
            "Claim semantic model output must be a JSON object."
        )

    return parsed


def sanitize_model_protocol_metadata(
    raw_output: Any,
) -> Dict[str, Any]:
    """
    Remove only model-supplied nested candidate contract-version metadata.

    The outer #35E envelope version stays strict. Status, reason, and every
    semantic candidate field other than candidate.version are preserved and
    remain subject to the locked #35E/#35B/#35D validators.
    """

    payload = _parse_json_object(raw_output)
    outer_version = _clean_text(payload.get("version"))

    if outer_version != router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION:
        raise ClaimSemanticProtocolOwnershipOutputError(
            "Unsupported claim semantic extraction outer envelope version."
        )

    candidate = payload.get("candidate")
    version_removed = False

    if isinstance(candidate, Mapping):
        candidate_copy = dict(candidate)
        version_keys = [
            key
            for key in candidate_copy
            if _token(key) == "version"
        ]

        if len(version_keys) > 1:
            raise ClaimSemanticProtocolOwnershipOutputError(
                "Model candidate contains duplicate normalized version fields."
            )

        if version_keys:
            candidate_copy.pop(version_keys[0], None)
            version_removed = True

        payload["candidate"] = candidate_copy

    return {
        "version": CLAIM_SEMANTIC_PROTOCOL_OWNERSHIP_CONTRACT_VERSION,
        "sanitized_envelope": payload,
        "candidate_contract_version_supplied_by_model": version_removed,
        "candidate_contract_version_removed_before_validation": version_removed,
        "policy": dict(MODEL_PROTOCOL_POLICY),
    }


def parse_protocol_owned_claim_semantic_output(
    raw_output: Any,
    *,
    expected_subject_key: str,
    allowed_entity_keys: Sequence[str],
) -> Dict[str, Any]:
    prepared = sanitize_model_protocol_metadata(raw_output)

    try:
        parsed = router.parse_claim_semantic_extraction_router_output(
            prepared["sanitized_envelope"],
            expected_subject_key=expected_subject_key,
            allowed_entity_keys=allowed_entity_keys,
        )
    except router.ClaimSemanticExtractionRouterError as error:
        raise ClaimSemanticProtocolOwnershipOutputError(
            "Protocol-owned candidate failed the locked #35E router: "
            + str(error)
        ) from error

    output = dict(parsed)
    candidate = output.get("candidate")
    assigned_version = ""

    if isinstance(candidate, Mapping):
        assigned_version = _clean_text(candidate.get("version"))

    output["protocol_ownership"] = {
        "version": CLAIM_SEMANTIC_PROTOCOL_OWNERSHIP_CONTRACT_VERSION,
        "candidate_contract_version_supplied_by_model": bool(
            prepared["candidate_contract_version_supplied_by_model"]
        ),
        "candidate_contract_version_removed_before_validation": bool(
            prepared["candidate_contract_version_removed_before_validation"]
        ),
        "validator_assigned_candidate_contract_version": assigned_version,
        "semantic_fields_rewritten": False,
        "status_rewritten": False,
        "reason_rewritten": False,
        "policy": dict(MODEL_PROTOCOL_POLICY),
    }

    return output


def protocol_ownership_descriptor() -> Dict[str, Any]:
    return {
        "version": CLAIM_SEMANTIC_PROTOCOL_OWNERSHIP_CONTRACT_VERSION,
        "input_contract": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "provider_call_performed": False,
        "provider_calls_expected": 0,
        "provider_tokens_expected": 0,
        "model_controls_candidate_contract_version": False,
        "outer_envelope_version_remains_strict": True,
        "semantic_fields_rewritten": False,
        "status_rewritten": False,
        "production_bridge_changed": False,
        "database_mutation_expected": False,
        "live_merit_effect": False,
        "policy": dict(MODEL_PROTOCOL_POLICY),
    }


__all__ = [
    "CLAIM_SEMANTIC_PROTOCOL_OWNERSHIP_CONTRACT_VERSION",
    "MODEL_PROTOCOL_POLICY",
    "ClaimSemanticProtocolOwnershipError",
    "ClaimSemanticProtocolOwnershipInputError",
    "ClaimSemanticProtocolOwnershipOutputError",
    "sanitize_model_protocol_metadata",
    "parse_protocol_owned_claim_semantic_output",
    "protocol_ownership_descriptor",
]
