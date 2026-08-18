from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping, Sequence

from app.intelligence import claim_semantic_extraction_router as router
from app.models import intelligence_bridge as bridge_models


STRUCTURED_CLAIM_FUSION_VERSION = "structured-claim-fusion-v1"
STRUCTURED_CLAIM_FUSION_CONTEXT_VERSION = (
    "structured-claim-fusion-context-v1"
)
STRUCTURED_CLAIM_CONTEXT_OPTION = (
    "_sportabase_structured_claim_context"
)


STRUCTURED_CLAIM_FUSION_POLICY = {
    "default_enabled": False,
    "existing_multimodal_fusion_call_reused": True,
    "additional_provider_call_required": False,
    "context_transport_uses_existing_perception_options": True,
    "context_option_removed_before_perception_builder": True,
    "structured_output_is_candidate_semantics_only": True,
    "expected_subject_must_be_canonically_bound": True,
    "subject_must_be_in_entity_allowlist": True,
    "entity_keys_are_never_invented": True,
    "nested_candidate_version_is_model_owned": False,
    "router_envelope_version_is_required": True,
    "three_way_statuses_are_extracted_partial_insufficient": True,
    "downstream_protocol_boundary_owns_validation": True,
    "fusion_does_not_establish_identity": True,
    "fusion_does_not_establish_truth": True,
    "fusion_does_not_establish_authority": True,
    "fusion_does_not_establish_reliability": True,
    "fusion_does_not_establish_independence": True,
    "fusion_does_not_establish_corroboration": True,
    "fusion_does_not_affect_live_merit": True,
    "fusion_does_not_create_training_labels": True,
}


class StructuredClaimFusionError(ValueError):
    pass


class StructuredClaimFusionInputError(
    StructuredClaimFusionError
):
    pass


def _clean(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _identifier(value: Any) -> str:
    return _clean(value).casefold()


def _entity_type_from_key(entity_key: str) -> str:
    value = _identifier(entity_key)
    if "|" not in value:
        return ""
    return value.split("|", 1)[0]


def _bound_subject_key(
    bindings: bridge_models.BridgeBindings,
) -> str:
    explicit = _identifier(
        bindings.subject_key
    )
    if explicit:
        return explicit

    resolution = dict(
        bindings.subject_resolution
        or {}
    )
    if (
        _identifier(
            resolution.get("status")
        )
        != "exact_unique"
    ):
        return ""

    entity = resolution.get("entity")
    if not isinstance(entity, Mapping):
        return ""

    return _identifier(
        entity.get("entity_key")
    )


def _normalize_allowed_entities(
    *,
    allowed_entity_keys: Sequence[str],
    allowed_entities: Mapping[str, Any] | None,
) -> Dict[str, Dict[str, str]]:
    if isinstance(
        allowed_entity_keys,
        (str, bytes),
    ):
        raise StructuredClaimFusionInputError(
            "allowed_entity_keys must be a sequence."
        )

    output: Dict[
        str,
        Dict[str, str],
    ] = {}

    if allowed_entities is not None:
        if not isinstance(
            allowed_entities,
            Mapping,
        ):
            raise StructuredClaimFusionInputError(
                "allowed_entities must be a mapping when supplied."
            )

        for raw_key, raw_value in (
            allowed_entities.items()
        ):
            entity_key = _identifier(raw_key)
            if not entity_key:
                raise StructuredClaimFusionInputError(
                    "allowed_entities contains an empty entity key."
                )
            if entity_key in output:
                raise StructuredClaimFusionInputError(
                    "allowed_entities contains a duplicate normalized key."
                )

            if isinstance(raw_value, Mapping):
                canonical_name = _clean(
                    raw_value.get("canonical_name")
                    or raw_value.get("name")
                )
                entity_type = _clean(
                    raw_value.get("entity_type")
                    or raw_value.get("type")
                ).casefold()
            else:
                canonical_name = _clean(raw_value)
                entity_type = ""

            output[entity_key] = {
                "entity_key": entity_key,
                "canonical_name": canonical_name,
                "entity_type": (
                    entity_type
                    or _entity_type_from_key(
                        entity_key
                    )
                ),
            }

    for raw_key in allowed_entity_keys:
        entity_key = _identifier(raw_key)
        if not entity_key:
            continue
        output.setdefault(
            entity_key,
            {
                "entity_key": entity_key,
                "canonical_name": "",
                "entity_type": (
                    _entity_type_from_key(
                        entity_key
                    )
                ),
            },
        )

    return {
        key: output[key]
        for key in sorted(output)
    }


def build_structured_claim_fusion_context(
    *,
    subject_key: str,
    allowed_entity_keys: Sequence[str],
    allowed_entities: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    subject = _identifier(subject_key)
    if not subject:
        raise StructuredClaimFusionInputError(
            "subject_key is required."
        )

    entities = _normalize_allowed_entities(
        allowed_entity_keys=allowed_entity_keys,
        allowed_entities=allowed_entities,
    )
    if not entities:
        raise StructuredClaimFusionInputError(
            "At least one canonical entity must be allowed."
        )
    if subject not in entities:
        raise StructuredClaimFusionInputError(
            "subject_key must be present in the entity allowlist."
        )

    return {
        "version": (
            STRUCTURED_CLAIM_FUSION_CONTEXT_VERSION
        ),
        "enabled": True,
        "subject_key": subject,
        "allowed_entity_keys": list(
            entities
        ),
        "allowed_entities": entities,
        "router_output_version": (
            router
            .CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION
        ),
        "policy": dict(
            STRUCTURED_CLAIM_FUSION_POLICY
        ),
    }


def structured_claim_fusion_context_for_bindings(
    *,
    bindings: bridge_models.BridgeBindings,
    allowed_entity_keys: Sequence[str],
    allowed_entities: Mapping[str, Any] | None = None,
) -> Dict[str, Any] | None:
    if not isinstance(
        bindings,
        bridge_models.BridgeBindings,
    ):
        raise StructuredClaimFusionInputError(
            "bindings must be BridgeBindings."
        )

    subject = _bound_subject_key(
        bindings
    )
    if not subject:
        return None

    try:
        return build_structured_claim_fusion_context(
            subject_key=subject,
            allowed_entity_keys=(
                allowed_entity_keys
            ),
            allowed_entities=(
                allowed_entities
            ),
        )
    except StructuredClaimFusionInputError:
        return None


def require_structured_claim_fusion_context(
    raw: Any,
) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise StructuredClaimFusionInputError(
            "structured claim fusion context must be a mapping."
        )

    value = dict(raw)
    if (
        _clean(value.get("version"))
        != STRUCTURED_CLAIM_FUSION_CONTEXT_VERSION
        or value.get("enabled") is not True
    ):
        raise StructuredClaimFusionInputError(
            "structured claim fusion context version/state is invalid."
        )

    return build_structured_claim_fusion_context(
        subject_key=value.get("subject_key", ""),
        allowed_entity_keys=(
            value.get("allowed_entity_keys")
            or ()
        ),
        allowed_entities=(
            value.get("allowed_entities")
        ),
    )


def build_structured_claim_fusion_prompt_fragment(
    raw_context: Mapping[str, Any],
) -> str:
    context = require_structured_claim_fusion_context(
        raw_context
    )

    output_shape = {
        "version": (
            router
            .CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION
        ),
        "status": (
            "extracted|partial|insufficient"
        ),
        "candidate": {
            "subject_key": context[
                "subject_key"
            ],
            "event_type": "one allowed event",
            "state": "one allowed state when supported",
            "negated": False,
            "roles": {},
            "facets": {},
        },
        "reason": "",
    }

    return (
        "\n\nTask 3: for EVERY claim candidate, also propose structured "
        "claim semantics for the expected canonical subject below. "
        "Place that proposal in the same candidate object under "
        "structured_claim_output. The normal candidate text and source "
        "artifact IDs remain required.\n\n"
        "The structured proposal is candidate semantics only. It does not "
        "decide identity, truth, verification, credibility, authority, "
        "reliability, independence, corroboration, training eligibility, "
        "or Merit.\n\n"
        "Use exactly one structured status: extracted, partial, or insufficient. "
        "Use extracted only when the candidate text supplies every field "
        "required for complete canonical identity. Use partial when supported "
        "event semantics exist but durable identity fields are missing. Use "
        "insufficient when neither a valid full nor partial candidate is "
        "supported. Never invent missing identity details.\n\n"
        "For extracted or partial, candidate must be an object for the expected "
        "subject. For insufficient, candidate must be null and reason must be "
        "non-empty. Never put a contract version inside the nested candidate. "
        "Never invent an entity key; use only the allowlist below.\n\n"
        "Expected subject key:\n"
        + context["subject_key"]
        + "\n\nAllowed canonical entities:\n"
        + json.dumps(
            list(
                context[
                    "allowed_entities"
                ].values()
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n\nDeterministic downstream router contract:\n"
        + json.dumps(
            router
            .claim_semantic_extraction_router_schema(),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n\nRequired structured_claim_output envelope:\n"
        + json.dumps(
            output_shape,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def structured_claim_fusion_descriptor() -> Dict[str, Any]:
    return {
        "version": STRUCTURED_CLAIM_FUSION_VERSION,
        "context_version": (
            STRUCTURED_CLAIM_FUSION_CONTEXT_VERSION
        ),
        "provider_call_performed": False,
        "additional_provider_calls_expected": 0,
        "database_writes_expected": 0,
        "establishes_identity": False,
        "affects_live_merit": False,
        "policy": dict(
            STRUCTURED_CLAIM_FUSION_POLICY
        ),
    }


__all__ = [
    "STRUCTURED_CLAIM_FUSION_VERSION",
    "STRUCTURED_CLAIM_FUSION_CONTEXT_VERSION",
    "STRUCTURED_CLAIM_CONTEXT_OPTION",
    "STRUCTURED_CLAIM_FUSION_POLICY",
    "StructuredClaimFusionError",
    "StructuredClaimFusionInputError",
    "build_structured_claim_fusion_context",
    "structured_claim_fusion_context_for_bindings",
    "require_structured_claim_fusion_context",
    "build_structured_claim_fusion_prompt_fragment",
    "structured_claim_fusion_descriptor",
]
