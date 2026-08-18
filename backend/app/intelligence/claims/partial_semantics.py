from __future__ import annotations

import re
import unicodedata

from typing import Any, Dict, Mapping, Sequence

from app.intelligence import canonical_claims


PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION = (
    "partial-claim-semantics-contract-v1"
)
PARTIAL_CLAIM_COMPARISON_VERSION = (
    "partial-claim-comparison-v1"
)

STATUS_STRUCTURALLY_INCOMPATIBLE = "structurally_incompatible"
STATUS_UNDETERMINED = "undetermined"


PARTIAL_SEMANTICS_POLICY = {
    "partial_semantics_are_not_claim_identity": True,
    "partial_semantics_never_mint_fingerprints": True,
    "partial_semantics_can_establish_same_claim": False,
    "partial_semantics_can_support_safe_exclusion": True,
    "full_identity_required_for_acceptance": True,
    "structural_conflict_required_for_exclusion": True,
    "absence_of_conflict_is_not_equivalence": True,
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


class PartialClaimSemanticsError(ValueError):
    pass


class PartialClaimSemanticsInputError(PartialClaimSemanticsError):
    pass


class PartialClaimSemanticsCompleteError(PartialClaimSemanticsError):
    pass


_ALLOWED_TOP_LEVEL_FIELDS = frozenset({
    "version",
    "subject_key",
    "event_type",
    "state",
    "negated",
    "roles",
    "facets",
})


def _clean_text(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value or "")),
    ).strip()


def _token(value: Any) -> str:
    return (
        _clean_text(value)
        .casefold()
        .replace("-", "_")
        .replace(" ", "_")
    )


def _identifier(value: Any) -> str:
    return _clean_text(value).casefold()


def _reject_forbidden_fields(
    value: Mapping[str, Any],
    *,
    label: str,
) -> None:
    for raw_key in value:
        if _token(raw_key) in canonical_claims.FORBIDDEN_IDENTITY_FIELDS:
            raise PartialClaimSemanticsInputError(
                label
                + " contains forbidden identity field "
                + repr(str(raw_key))
                + "."
            )


def _normalize_event_type(value: Any) -> str:
    event_type = canonical_claims.EVENT_ALIASES.get(
        _token(value),
        "",
    )

    if not event_type:
        raise PartialClaimSemanticsInputError(
            "Unsupported partial semantic event_type: "
            + repr(_clean_text(value))
            + "."
        )

    return event_type


def _normalize_state(event_type: str, value: Any) -> str:
    raw = _clean_text(value)

    if not raw:
        return ""

    state = canonical_claims.STATE_ALIASES[event_type].get(
        _token(raw),
        "",
    )

    if not state:
        raise PartialClaimSemanticsInputError(
            "Unsupported partial semantic state "
            + repr(raw)
            + " for event_type "
            + event_type
            + "."
        )

    return state


def _normalize_negated(value: Any) -> bool | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    raise PartialClaimSemanticsInputError(
        "Partial semantic negated must be boolean when present."
    )


def _normalized_allowlist(
    allowed_entity_keys: Sequence[str],
) -> frozenset[str]:
    if isinstance(allowed_entity_keys, (str, bytes)):
        raise PartialClaimSemanticsInputError(
            "allowed_entity_keys must be a sequence of canonical entity keys."
        )

    values = {
        _identifier(value)
        for value in allowed_entity_keys
        if _identifier(value)
    }

    if not values:
        raise PartialClaimSemanticsInputError(
            "allowed_entity_keys may not be empty."
        )

    return frozenset(values)


def _normalize_named_values(
    value: Any,
    *,
    aliases: Mapping[str, str],
    label: str,
    entity_values: bool,
    allowed_entities: frozenset[str],
) -> Dict[str, str]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise PartialClaimSemanticsInputError(
            label + " must be an object."
        )

    _reject_forbidden_fields(value, label=label)
    output: Dict[str, str] = {}

    for raw_key, raw_value in value.items():
        canonical_key = aliases.get(
            _token(raw_key),
            "",
        )

        if not canonical_key:
            raise PartialClaimSemanticsInputError(
                label
                + " contains unsupported field "
                + repr(str(raw_key))
                + "."
            )

        normalized_value = _identifier(raw_value)

        if not normalized_value:
            continue

        if entity_values and normalized_value not in allowed_entities:
            raise PartialClaimSemanticsInputError(
                label
                + " references entity outside the allowed set: "
                + normalized_value
                + "."
            )

        existing = output.get(canonical_key)

        if existing is not None and existing != normalized_value:
            raise PartialClaimSemanticsInputError(
                label
                + " aliases disagree for "
                + canonical_key
                + "."
            )

        output[canonical_key] = normalized_value

    return {
        key: output[key]
        for key in sorted(output)
    }


def _candidate_for_full_contract(
    normalized: Mapping[str, Any],
) -> Dict[str, Any]:
    candidate: Dict[str, Any] = {
        "version": canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION,
        "subject_key": normalized["subject_key"],
        "event_type": normalized["event_type"],
        "state": normalized["state"],
        "roles": dict(normalized["roles"]),
        "facets": dict(normalized["facets"]),
    }

    if normalized["negated"] is not None:
        candidate["negated"] = normalized["negated"]

    return candidate


def _identity_completeness(
    normalized: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    missing: list[str] = []

    if not normalized["state"]:
        missing.append("state")

    rules = canonical_claims.EVENT_RULES[
        normalized["event_type"]
    ]

    for key in rules["required_roles"]:
        if key not in normalized["roles"]:
            missing.append("roles." + key)

    for key in rules["required_facets"]:
        if key not in normalized["facets"]:
            missing.append("facets." + key)

    for group in rules["required_any_facets"]:
        if not any(
            key in normalized["facets"]
            for key in group
        ):
            missing.append(
                "facets.one_of(" + ",".join(group) + ")"
            )

    if missing:
        return (False, sorted(missing))

    try:
        canonical_claims.normalize_canonical_claim(
            _candidate_for_full_contract(normalized)
        )
    except canonical_claims.CanonicalClaimError:
        return (False, ["full_contract_validation"])

    return (True, [])


def partial_semantic_candidate_schema() -> Dict[str, Any]:
    events: Dict[str, Any] = {}

    for event_type in sorted(canonical_claims.EVENT_RULES):
        rules = canonical_claims.EVENT_RULES[event_type]

        events[event_type] = {
            "states": sorted(
                set(
                    canonical_claims.STATE_ALIASES[event_type].values()
                )
            ),
            "roles": sorted(
                set(rules["role_aliases"].values())
            ),
            "facets": sorted(
                set(rules["facet_aliases"].values())
            ),
            "full_identity_required_roles": list(
                rules["required_roles"]
            ),
            "full_identity_required_facets": list(
                rules["required_facets"]
            ),
            "full_identity_required_any_facets": [
                list(group)
                for group in rules["required_any_facets"]
            ],
            "core_roles": list(rules["core_roles"]),
            "core_facets": list(rules["core_facets"]),
        }

    return {
        "version": PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
        "canonical_claim_version": (
            canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION
        ),
        "candidate_fields": sorted(_ALLOWED_TOP_LEVEL_FIELDS),
        "events": events,
        "forbidden_identity_fields": sorted(
            canonical_claims.FORBIDDEN_IDENTITY_FIELDS
        ),
        "policy": dict(PARTIAL_SEMANTICS_POLICY),
    }


def normalize_partial_semantic_candidate(
    value: Mapping[str, Any],
    *,
    allowed_entity_keys: Sequence[str],
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PartialClaimSemanticsInputError(
            "Partial semantic candidate must be an object."
        )

    _reject_forbidden_fields(
        value,
        label="Partial semantic candidate",
    )

    unknown = {
        str(key)
        for key in value
        if _token(key) not in _ALLOWED_TOP_LEVEL_FIELDS
    }

    if unknown:
        raise PartialClaimSemanticsInputError(
            "Partial semantic candidate contains unsupported fields: "
            + ", ".join(sorted(unknown))
            + "."
        )

    version = _clean_text(value.get("version"))

    if (
        version
        and version != PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION
    ):
        raise PartialClaimSemanticsInputError(
            "Unsupported partial semantic contract version."
        )

    allowed = _normalized_allowlist(allowed_entity_keys)
    subject_key = _identifier(value.get("subject_key"))

    if not subject_key:
        raise PartialClaimSemanticsInputError(
            "Partial semantic subject_key is required."
        )

    if subject_key not in allowed:
        raise PartialClaimSemanticsInputError(
            "Partial semantic subject_key is outside the allowed entity set."
        )

    event_type = _normalize_event_type(value.get("event_type"))
    rules = canonical_claims.EVENT_RULES[event_type]

    normalized = {
        "version": PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
        "subject_key": subject_key,
        "event_type": event_type,
        "state": _normalize_state(
            event_type,
            value.get("state"),
        ),
        "negated": _normalize_negated(value.get("negated")),
        "roles": _normalize_named_values(
            value.get("roles"),
            aliases=rules["role_aliases"],
            label="Partial semantic roles",
            entity_values=True,
            allowed_entities=allowed,
        ),
        "facets": _normalize_named_values(
            value.get("facets"),
            aliases=rules["facet_aliases"],
            label="Partial semantic facets",
            entity_values=False,
            allowed_entities=allowed,
        ),
    }

    identity_complete, missing = _identity_completeness(normalized)

    return {
        **normalized,
        "identity_complete": identity_complete,
        "missing_identity_fields": missing,
        "core_key": "",
        "core_fingerprint": "",
        "specific_fingerprint": "",
        "policy": dict(PARTIAL_SEMANTICS_POLICY),
    }


def require_incomplete_partial_semantics(
    value: Mapping[str, Any],
    *,
    allowed_entity_keys: Sequence[str],
) -> Dict[str, Any]:
    normalized = normalize_partial_semantic_candidate(
        value,
        allowed_entity_keys=allowed_entity_keys,
    )

    if normalized["identity_complete"]:
        raise PartialClaimSemanticsCompleteError(
            "Candidate satisfies the full #35A identity contract and must use the full identity path."
        )

    return normalized


def _overlap_conflicts(
    full_values: Mapping[str, str],
    partial_values: Mapping[str, str],
    *,
    prefix: str,
) -> list[str]:
    return [
        prefix + "." + key
        for key in sorted(
            set(full_values) & set(partial_values)
        )
        if full_values[key] != partial_values[key]
    ]


def compare_full_claim_to_partial_semantics(
    full_claim: Mapping[str, Any],
    partial_candidate: Mapping[str, Any],
    *,
    allowed_entity_keys: Sequence[str],
) -> Dict[str, Any]:
    try:
        full = canonical_claims.normalize_canonical_claim(full_claim)
    except canonical_claims.CanonicalClaimError as error:
        raise PartialClaimSemanticsInputError(
            "Full claim failed the #35A canonical identity contract: "
            + str(error)
        ) from error

    partial = require_incomplete_partial_semantics(
        partial_candidate,
        allowed_entity_keys=allowed_entity_keys,
    )

    conflicts: list[str] = []

    if full["subject_key"] != partial["subject_key"]:
        conflicts.append("subject_key")

    if full["event_type"] != partial["event_type"]:
        conflicts.append("event_type")
    else:
        if (
            partial["state"]
            and full["state"] != partial["state"]
        ):
            conflicts.append("state")

        if (
            partial["negated"] is not None
            and full["negated"] != partial["negated"]
        ):
            conflicts.append("negated")

        conflicts.extend(
            _overlap_conflicts(
                full["roles"],
                partial["roles"],
                prefix="roles",
            )
        )
        conflicts.extend(
            _overlap_conflicts(
                full["facets"],
                partial["facets"],
                prefix="facets",
            )
        )

    conflicts = sorted(set(conflicts))

    if conflicts:
        status = STATUS_STRUCTURALLY_INCOMPATIBLE
        safe_exclusion = True
    else:
        status = STATUS_UNDETERMINED
        safe_exclusion = False

    return {
        "version": PARTIAL_CLAIM_COMPARISON_VERSION,
        "status": status,
        "structural_conflicts": conflicts,
        "safe_exclusion": safe_exclusion,
        "safe_acceptance": False,
        "same_claim_established": False,
        "partial_identity_complete": False,
        "partial_missing_identity_fields": list(
            partial["missing_identity_fields"]
        ),
        "partial_core_key": "",
        "partial_core_fingerprint": "",
        "partial_specific_fingerprint": "",
        "policy": dict(PARTIAL_SEMANTICS_POLICY),
    }


__all__ = [
    "PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION",
    "PARTIAL_CLAIM_COMPARISON_VERSION",
    "STATUS_STRUCTURALLY_INCOMPATIBLE",
    "STATUS_UNDETERMINED",
    "PARTIAL_SEMANTICS_POLICY",
    "PartialClaimSemanticsError",
    "PartialClaimSemanticsInputError",
    "PartialClaimSemanticsCompleteError",
    "partial_semantic_candidate_schema",
    "normalize_partial_semantic_candidate",
    "require_incomplete_partial_semantics",
    "compare_full_claim_to_partial_semantics",
]
