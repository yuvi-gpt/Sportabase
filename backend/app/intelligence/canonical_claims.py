from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from typing import Any, Dict, Mapping, Sequence


CANONICAL_CLAIM_CONTRACT_VERSION = "canonical-claim-contract-v1"
CANONICAL_CLAIM_CORE_FINGERPRINT_VERSION = "canonical-claim-core-fingerprint-v1"
CANONICAL_CLAIM_SPECIFIC_FINGERPRINT_VERSION = "canonical-claim-specific-fingerprint-v1"
CANONICAL_CLAIM_COMPATIBILITY_VERSION = "canonical-claim-compatibility-v1"


class CanonicalClaimError(ValueError):
    pass


class CanonicalClaimInputError(CanonicalClaimError):
    pass


class CanonicalClaimConflictError(CanonicalClaimError):
    pass


FORBIDDEN_IDENTITY_FIELDS = frozenset({
    "truth", "is_true", "verified", "verification",
    "authority", "source_authority",
    "reliability", "reliability_score", "trust", "trust_score",
    "credibility", "credibility_score",
    "independence", "independent", "is_independent",
    "corroboration", "corroborated",
    "merit", "merit_score", "live_merit", "score_effect",
    "training_eligible",
    "confidence", "model_confidence", "source_confidence",
    "source_url", "publisher", "reporter", "provider", "model",
})


EVENT_ALIASES = {
    "move": "transfer",
    "player_move": "transfer",
    "driver_move": "transfer",
    "transfer": "transfer",
    "contract": "contract",
    "contract_status": "contract",
    "appointment": "tenure",
    "manager_appointment": "tenure",
    "coach_appointment": "tenure",
    "employment": "tenure",
    "tenure": "tenure",
    "retirement": "retirement",
    "injury": "injury",
    "medical": "injury",
    "availability": "availability",
    "selection_availability": "availability",
    "lineup": "lineup",
    "team_selection": "lineup",
    "match_result": "match_result",
    "race_result": "match_result",
    "game_result": "match_result",
    "match_event": "match_event",
    "race_event": "match_event",
    "game_event": "match_event",
    "championship": "championship",
    "title": "championship",
    "title_result": "championship",
    "disciplinary": "disciplinary",
    "discipline": "disciplinary",
}


STATE_ALIASES = {
    "transfer": {
        "interest": "interest", "interested": "interest", "linked": "interest",
        "target": "interest", "targeting": "interest",
        "approach": "approach", "approached": "approach", "contacted": "approach",
        "negotiating": "negotiating", "negotiation": "negotiating", "talks": "negotiating",
        "agreed": "agreed", "agreement": "agreed", "deal_agreed": "agreed",
        "agreement_in_principle": "agreed",
        "medical": "medical", "medical_scheduled": "medical", "medical_completed": "medical",
        "completed": "completed", "complete": "completed", "signed": "completed",
        "joined": "completed", "transferred": "completed", "presented": "completed",
        "announced_as_player": "completed",
        "failed": "failed", "collapsed": "failed",
        "cancelled": "cancelled", "canceled": "cancelled",
    },
    "contract": {
        "offered": "offered", "offer": "offered",
        "negotiating": "negotiating", "talks": "negotiating",
        "agreed": "agreed", "agreement": "agreed",
        "signed": "signed", "renewed": "extended", "extended": "extended",
        "extension": "extended", "expired": "expired", "ended": "expired",
        "terminated": "terminated", "released": "terminated",
    },
    "tenure": {
        "linked": "linked", "candidate": "linked", "interviewed": "interviewed",
        "appointed": "appointed", "hired": "appointed", "incoming": "appointed",
        "remaining": "remaining", "staying": "remaining", "stay": "remaining",
        "departing": "departing", "leaving": "departing", "step_down": "departing",
        "stepping_down": "departing", "departed": "departed", "left": "departed",
        "dismissed": "dismissed", "sacked": "dismissed", "fired": "dismissed",
    },
    "retirement": {
        "announced": "announced", "retiring": "announced", "will_retire": "announced",
        "retired": "retired",
    },
    "injury": {
        "injured": "injured", "diagnosed": "diagnosed", "doubtful": "doubtful",
        "ruled_out": "ruled_out", "surgery_planned": "surgery_planned",
        "surgery_completed": "surgery_completed", "recovering": "recovering",
        "returned": "returned", "cleared": "returned",
    },
    "availability": {
        "available": "available", "fit": "available", "doubtful": "doubtful",
        "questionable": "doubtful", "unavailable": "unavailable", "out": "unavailable",
        "suspended": "suspended", "rested": "rested",
    },
    "lineup": {
        "selected": "selected", "starting": "starting", "starter": "starting",
        "benched": "benched", "bench": "benched", "omitted": "omitted",
        "dropped": "omitted", "substituted_on": "substituted_on",
        "subbed_on": "substituted_on", "substituted_off": "substituted_off",
        "subbed_off": "substituted_off",
    },
    "match_result": {
        "won": "won", "win": "won", "victory": "won",
        "lost": "lost", "loss": "lost", "defeat": "lost",
        "drew": "drew", "draw": "drew",
    },
    "match_event": {
        "scored": "scored", "goal": "scored", "assist": "assisted", "assisted": "assisted",
        "penalty_scored": "penalty_scored", "penalty_missed": "penalty_missed",
        "yellow_card": "yellow_card", "booked": "yellow_card",
        "red_card": "red_card", "sent_off": "red_card",
        "retired": "retired", "dnf": "retired", "pole": "pole",
        "pole_position": "pole", "podium": "podium",
    },
    "championship": {
        "won": "won", "secured": "won", "clinched": "won",
        "champion": "won", "champions": "won", "lost": "lost",
    },
    "disciplinary": {
        "charged": "charged", "investigated": "investigated",
        "suspended": "suspended", "banned": "banned", "fined": "fined",
        "penalized": "penalized", "penalised": "penalized",
        "cleared": "cleared", "appealed": "appealed", "overturned": "overturned",
    },
}


EVENT_RULES = {
    "transfer": {
        "role_aliases": {
            "destination": "destination", "to": "destination",
            "new_club": "destination", "new_team": "destination",
            "new_organization": "destination", "origin": "origin", "from": "origin",
            "former_club": "origin", "former_team": "origin",
            "former_organization": "origin",
        },
        "facet_aliases": {
            "transfer_kind": "transfer_kind", "type": "transfer_kind",
            "deal_type": "transfer_kind", "effective_period": "effective_period",
            "year": "effective_period", "season": "effective_period",
            "effective_time": "effective_period",
        },
        "core_roles": ("destination",),
        "core_facets": (),
        "required_roles": ("destination",),
        "required_facets": (),
        "required_any_facets": (),
    },
    "contract": {
        "role_aliases": {
            "organization": "organization", "club": "organization",
            "team": "organization", "employer": "organization",
        },
        "facet_aliases": {
            "contract_kind": "contract_kind", "type": "contract_kind",
            "effective_period": "effective_period", "season": "effective_period",
            "year": "effective_period", "through": "effective_period",
        },
        "core_roles": ("organization",),
        "core_facets": (),
        "required_roles": ("organization",),
        "required_facets": (),
        "required_any_facets": (),
    },
    "tenure": {
        "role_aliases": {
            "organization": "organization", "club": "organization",
            "team": "organization", "employer": "organization",
        },
        "facet_aliases": {
            "role": "role", "title": "role", "job": "role",
            "effective_period": "effective_period", "season": "effective_period",
            "year": "effective_period",
        },
        "core_roles": ("organization",),
        "core_facets": ("role",),
        "required_roles": ("organization",),
        "required_facets": (),
        "required_any_facets": (),
    },
    "retirement": {
        "role_aliases": {},
        "facet_aliases": {
            "scope": "scope", "retirement_scope": "scope",
            "effective_period": "effective_period", "after": "effective_period",
            "year": "effective_period",
        },
        "core_roles": (),
        "core_facets": ("scope",),
        "required_roles": (),
        "required_facets": ("scope",),
        "required_any_facets": (),
    },
    "injury": {
        "role_aliases": {"team": "team", "club": "team"},
        "facet_aliases": {
            "body_region": "body_region", "body_part": "body_region",
            "injury_type": "injury_type", "diagnosis": "injury_type",
            "episode_key": "episode_key", "event_key": "episode_key",
            "effective_period": "effective_period", "date": "effective_period",
        },
        "core_roles": (),
        "core_facets": ("episode_key",),
        "required_roles": (),
        "required_facets": (),
        "required_any_facets": (("episode_key", "body_region"),),
    },
    "availability": {
        "role_aliases": {"team": "team", "club": "team", "opponent": "opponent"},
        "facet_aliases": {
            "event_key": "event_key", "match_key": "event_key",
            "race_key": "event_key", "context_key": "event_key",
            "competition_key": "competition_key",
        },
        "core_roles": (),
        "core_facets": ("event_key",),
        "required_roles": (),
        "required_facets": ("event_key",),
        "required_any_facets": (),
    },
    "lineup": {
        "role_aliases": {"team": "team", "club": "team", "opponent": "opponent"},
        "facet_aliases": {
            "event_key": "event_key", "match_key": "event_key",
            "race_key": "event_key", "context_key": "event_key",
            "competition_key": "competition_key", "position": "position",
        },
        "core_roles": (),
        "core_facets": ("event_key",),
        "required_roles": (),
        "required_facets": ("event_key",),
        "required_any_facets": (),
    },
    "match_result": {
        "role_aliases": {
            "opponent": "opponent", "home_team": "home_team", "away_team": "away_team",
        },
        "facet_aliases": {
            "event_key": "event_key", "match_key": "event_key",
            "race_key": "event_key", "game_key": "event_key",
            "competition_key": "competition_key", "score": "score",
        },
        "core_roles": (),
        "core_facets": ("event_key",),
        "required_roles": (),
        "required_facets": ("event_key",),
        "required_any_facets": (),
    },
    "match_event": {
        "role_aliases": {
            "team": "team", "club": "team", "opponent": "opponent",
            "secondary_subject": "secondary_subject",
        },
        "facet_aliases": {
            "event_key": "event_key", "match_key": "event_key",
            "race_key": "event_key", "game_key": "event_key",
            "competition_key": "competition_key", "event_slot": "event_slot",
        },
        "core_roles": (),
        "core_facets": ("event_key",),
        "required_roles": (),
        "required_facets": ("event_key",),
        "required_any_facets": (),
    },
    "championship": {
        "role_aliases": {},
        "facet_aliases": {
            "competition_key": "competition_key", "competition": "competition_key",
            "championship_key": "competition_key", "effective_period": "effective_period",
            "season": "effective_period", "year": "effective_period",
        },
        "core_roles": (),
        "core_facets": ("competition_key", "effective_period"),
        "required_roles": (),
        "required_facets": ("competition_key", "effective_period"),
        "required_any_facets": (),
    },
    "disciplinary": {
        "role_aliases": {"team": "team", "club": "team"},
        "facet_aliases": {
            "event_key": "event_key", "match_key": "event_key",
            "race_key": "event_key", "competition_key": "competition_key",
            "sanction_type": "sanction_type", "effective_period": "effective_period",
        },
        "core_roles": (),
        "core_facets": (),
        "required_roles": (),
        "required_facets": (),
        "required_any_facets": (("event_key", "competition_key", "effective_period"),),
    },
}


_TOP_LEVEL_FIELDS = frozenset({
    "version", "subject_key", "event_type", "state", "negated", "roles", "facets",
})


def _clean_text(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value or "")),
    ).strip()


def _token(value: Any) -> str:
    return _clean_text(value).casefold().replace("-", "_").replace(" ", "_")


def _identifier(value: Any) -> str:
    return _clean_text(value).casefold()


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _normalize_event_type(value: Any) -> str:
    event_type = EVENT_ALIASES.get(_token(value), "")

    if not event_type:
        raise CanonicalClaimInputError(
            "Unsupported canonical claim event_type: " + repr(_clean_text(value))
        )

    return event_type


def _normalize_state(event_type: str, value: Any) -> str:
    state = STATE_ALIASES[event_type].get(_token(value), "")

    if not state:
        raise CanonicalClaimInputError(
            "Unsupported canonical claim state "
            + repr(_clean_text(value))
            + " for event_type "
            + event_type
            + "."
        )

    return state


def _normalize_negated(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    raise CanonicalClaimInputError("Canonical claim negated must be boolean.")


def _reject_forbidden_mapping_fields(value: Mapping[str, Any], *, label: str) -> None:
    for raw_key in value:
        if _token(raw_key) in FORBIDDEN_IDENTITY_FIELDS:
            raise CanonicalClaimInputError(
                label + " contains forbidden identity field " + repr(str(raw_key)) + "."
            )


def _normalize_named_values(
    value: Any,
    *,
    aliases: Mapping[str, str],
    label: str,
) -> Dict[str, str]:
    if value is None:
        return {}

    if not isinstance(value, Mapping):
        raise CanonicalClaimInputError(label + " must be an object.")

    _reject_forbidden_mapping_fields(value, label=label)
    output: Dict[str, str] = {}

    for raw_key, raw_value in value.items():
        canonical_key = aliases.get(_token(raw_key), "")

        if not canonical_key:
            raise CanonicalClaimInputError(
                label + " contains unsupported field " + repr(str(raw_key)) + "."
            )

        normalized_value = _identifier(raw_value)

        if not normalized_value:
            continue

        existing = output.get(canonical_key)

        if existing is not None and existing != normalized_value:
            raise CanonicalClaimConflictError(
                label + " aliases disagree for " + canonical_key + "."
            )

        output[canonical_key] = normalized_value

    return {key: output[key] for key in sorted(output)}


def _validate_required_fields(normalized: Mapping[str, Any]) -> None:
    event_type = str(normalized["event_type"])
    rules = EVENT_RULES[event_type]
    roles = normalized["roles"]
    facets = normalized["facets"]

    for key in rules["required_roles"]:
        if key not in roles:
            raise CanonicalClaimInputError(
                event_type + " canonical claim requires role " + key + "."
            )

    for key in rules["required_facets"]:
        if key not in facets:
            raise CanonicalClaimInputError(
                event_type + " canonical claim requires facet " + key + "."
            )

    for group in rules["required_any_facets"]:
        if not any(key in facets for key in group):
            raise CanonicalClaimInputError(
                event_type
                + " canonical claim requires at least one of: "
                + ", ".join(group)
                + "."
            )


def normalize_canonical_claim(value: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CanonicalClaimInputError("Canonical claim candidate must be an object.")

    _reject_forbidden_mapping_fields(value, label="Canonical claim")

    unknown = {
        str(key)
        for key in value
        if _token(key) not in _TOP_LEVEL_FIELDS
    }

    if unknown:
        raise CanonicalClaimInputError(
            "Canonical claim contains unsupported top-level fields: "
            + ", ".join(sorted(unknown))
            + "."
        )

    version = _clean_text(value.get("version"))

    if version and version != CANONICAL_CLAIM_CONTRACT_VERSION:
        raise CanonicalClaimInputError("Unsupported canonical claim contract version.")

    subject_key = _identifier(value.get("subject_key"))

    if not subject_key:
        raise CanonicalClaimInputError("Canonical claim subject_key is required.")

    event_type = _normalize_event_type(value.get("event_type"))
    state = _normalize_state(event_type, value.get("state"))
    rules = EVENT_RULES[event_type]

    result = {
        "version": CANONICAL_CLAIM_CONTRACT_VERSION,
        "subject_key": subject_key,
        "event_type": event_type,
        "state": state,
        "negated": _normalize_negated(value.get("negated")),
        "roles": _normalize_named_values(
            value.get("roles"), aliases=rules["role_aliases"], label="Canonical claim roles"
        ),
        "facets": _normalize_named_values(
            value.get("facets"), aliases=rules["facet_aliases"], label="Canonical claim facets"
        ),
    }

    _validate_required_fields(result)
    return result


def canonical_claim_core_payload(value: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = normalize_canonical_claim(value)
    rules = EVENT_RULES[normalized["event_type"]]

    core_roles = {
        key: normalized["roles"][key]
        for key in rules["core_roles"]
        if key in normalized["roles"]
    }
    core_facets = {
        key: normalized["facets"][key]
        for key in rules["core_facets"]
        if key in normalized["facets"]
    }

    return {
        "version": CANONICAL_CLAIM_CORE_FINGERPRINT_VERSION,
        "subject_key": normalized["subject_key"],
        "event_type": normalized["event_type"],
        "state": normalized["state"],
        "negated": normalized["negated"],
        "roles": {key: core_roles[key] for key in sorted(core_roles)},
        "facets": {key: core_facets[key] for key in sorted(core_facets)},
    }


def canonical_claim_specific_payload(value: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = normalize_canonical_claim(value)

    return {
        "version": CANONICAL_CLAIM_SPECIFIC_FINGERPRINT_VERSION,
        "subject_key": normalized["subject_key"],
        "event_type": normalized["event_type"],
        "state": normalized["state"],
        "negated": normalized["negated"],
        "roles": dict(normalized["roles"]),
        "facets": dict(normalized["facets"]),
    }


def _fingerprint(namespace: str, payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        (namespace + "|" + _canonical_json(payload)).encode("utf-8")
    ).hexdigest()


def canonical_claim_core_fingerprint(value: Mapping[str, Any]) -> str:
    return _fingerprint(
        CANONICAL_CLAIM_CORE_FINGERPRINT_VERSION,
        canonical_claim_core_payload(value),
    )


def canonical_claim_specific_fingerprint(value: Mapping[str, Any]) -> str:
    return _fingerprint(
        CANONICAL_CLAIM_SPECIFIC_FINGERPRINT_VERSION,
        canonical_claim_specific_payload(value),
    )


def canonical_claim_core_key(value: Mapping[str, Any]) -> str:
    normalized = normalize_canonical_claim(value)
    return (
        "structured-claim|"
        + CANONICAL_CLAIM_CONTRACT_VERSION
        + "|"
        + normalized["subject_key"]
        + "|"
        + canonical_claim_core_fingerprint(normalized)
    )


def _overlap_conflicts(
    left: Mapping[str, str],
    right: Mapping[str, str],
    *,
    prefix: str,
) -> Sequence[str]:
    return tuple(
        prefix + "." + key
        for key in sorted(set(left) & set(right))
        if left[key] != right[key]
    )


def compare_canonical_claims(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> Dict[str, Any]:
    left_normalized = normalize_canonical_claim(left)
    right_normalized = normalize_canonical_claim(right)

    left_core = canonical_claim_core_fingerprint(left_normalized)
    right_core = canonical_claim_core_fingerprint(right_normalized)
    left_specific = canonical_claim_specific_fingerprint(left_normalized)
    right_specific = canonical_claim_specific_fingerprint(right_normalized)

    conflicts = []

    if left_core == right_core:
        conflicts.extend(
            _overlap_conflicts(
                left_normalized["roles"],
                right_normalized["roles"],
                prefix="roles",
            )
        )
        conflicts.extend(
            _overlap_conflicts(
                left_normalized["facets"],
                right_normalized["facets"],
                prefix="facets",
            )
        )

    if left_core != right_core:
        status = "different_core"
    elif conflicts:
        status = "material_conflict"
    else:
        status = (
            "exact_specific_match"
            if left_specific == right_specific
            else "same_core_no_material_conflict"
        )

    return {
        "version": CANONICAL_CLAIM_COMPATIBILITY_VERSION,
        "status": status,
        "same_core": left_core == right_core,
        "same_specific": left_specific == right_specific,
        "material_conflicts": sorted(conflicts),
        "left_core_fingerprint": left_core,
        "right_core_fingerprint": right_core,
        "left_specific_fingerprint": left_specific,
        "right_specific_fingerprint": right_specific,
        "policy": {
            "deterministic_only": True,
            "fuzzy_similarity_used": False,
            "model_equivalence_decision_used": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "establishes_corroboration": False,
            "affects_live_merit": False,
            "source_confidence_part_of_identity": False,
            "source_reliability_part_of_identity": False,
        },
    }
