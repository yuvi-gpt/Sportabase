from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.intelligence.claims import identity as claim_identity


CLAIM_EVOLUTION_VERSION = "claim-evolution-reconciliation-v1"
CLAIM_EVOLUTION_FAMILY_VERSION = "claim-evolution-family-v1"
CLAIM_EVOLUTION_LINK_VERSION = "claim-evolution-link-v1"

_EVOLUTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim_evolution_links (
  id TEXT PRIMARY KEY,
  predecessor_claim_id TEXT NOT NULL,
  successor_claim_id TEXT NOT NULL,
  subject_key TEXT NOT NULL,
  family_key TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    relationship_type IN (
      'progresses_to',
      'resolves_to',
      'contradicts'
    )
  ),
  CHECK (predecessor_claim_id <> successor_claim_id),
  UNIQUE (
    predecessor_claim_id,
    successor_claim_id,
    relationship_type
  ),
  FOREIGN KEY(predecessor_claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE,
  FOREIGN KEY(successor_claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_claim_evolution_predecessor
ON claim_evolution_links(predecessor_claim_id);

CREATE INDEX IF NOT EXISTS idx_claim_evolution_successor
ON claim_evolution_links(successor_claim_id);

CREATE INDEX IF NOT EXISTS idx_claim_evolution_family
ON claim_evolution_links(family_key, observed_at);

CREATE INDEX IF NOT EXISTS idx_claim_evolution_subject
ON claim_evolution_links(subject_key, observed_at);
"""

_PROGRESS_ORDER = {
    "transfer": (
        "interest",
        "approach",
        "negotiating",
        "agreed",
        "medical",
        "completed",
    ),
    "contract": (
        "offered",
        "negotiating",
        "agreed",
        "signed",
        "extended",
    ),
    "tenure": (
        "linked",
        "interviewed",
        "appointed",
        "remaining",
        "departing",
        "departed",
    ),
    "retirement": (
        "announced",
        "retired",
    ),
}

_TERMINAL_OUTCOMES = {
    "transfer": frozenset({"failed", "cancelled"}),
    "contract": frozenset({"expired", "terminated"}),
    "tenure": frozenset({"dismissed"}),
}

_EXPLICIT_TRANSITIONS = {
    "injury": {
        "injured": frozenset({
            "diagnosed", "doubtful", "ruled_out", "surgery_planned",
            "surgery_completed", "recovering", "returned",
        }),
        "diagnosed": frozenset({
            "doubtful", "ruled_out", "surgery_planned",
            "surgery_completed", "recovering", "returned",
        }),
        "doubtful": frozenset({"ruled_out", "recovering", "returned"}),
        "ruled_out": frozenset({
            "surgery_planned", "surgery_completed", "recovering", "returned",
        }),
        "surgery_planned": frozenset({"surgery_completed", "recovering", "returned"}),
        "surgery_completed": frozenset({"recovering", "returned"}),
        "recovering": frozenset({"returned"}),
    },
    "availability": {
        "doubtful": frozenset({"available", "unavailable"}),
        "unavailable": frozenset({"available"}),
        "suspended": frozenset({"available"}),
        "rested": frozenset({"available"}),
    },
    "lineup": {
        "selected": frozenset({"starting", "benched", "omitted"}),
        "starting": frozenset({"substituted_off"}),
        "benched": frozenset({"substituted_on"}),
    },
    "disciplinary": {
        "investigated": frozenset({
            "charged", "suspended", "banned", "fined", "penalized", "cleared",
        }),
        "charged": frozenset({
            "suspended", "banned", "fined", "penalized", "cleared", "appealed",
        }),
        "suspended": frozenset({"appealed", "overturned", "cleared"}),
        "banned": frozenset({"appealed", "overturned", "cleared"}),
        "fined": frozenset({"appealed", "overturned", "cleared"}),
        "penalized": frozenset({"appealed", "overturned", "cleared"}),
        "appealed": frozenset({"overturned", "cleared"}),
    },
}


def _clean(value: Any, maximum: int = 1000) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _utc_timestamp(value: Any) -> str:
    text = _clean(value, 128)
    if not text:
        return ""
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return ""
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return ""
    return parsed.astimezone(timezone.utc).isoformat()


def _family_scope(candidate: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    normalized = claim_identity.normalize_canonical_claim(candidate)
    event_type = normalized["event_type"]
    rules = claim_identity.EVENT_RULES[event_type]

    roles = {
        key: normalized["roles"][key]
        for key in rules["core_roles"]
        if key in normalized["roles"]
    }
    facets = {
        key: normalized["facets"][key]
        for key in rules["core_facets"]
        if key in normalized["facets"]
    }

    if event_type in {"contract", "tenure"}:
        effective_period = normalized["facets"].get("effective_period")
        if not effective_period:
            return None, "effective_period_required_for_recurrent_event"
        facets["effective_period"] = effective_period

    if event_type == "injury" and not normalized["facets"].get("episode_key"):
        return None, "episode_key_required_for_recurrent_injury"

    if event_type == "disciplinary":
        anchors = {
            key: normalized["facets"][key]
            for key in ("event_key", "competition_key", "effective_period")
            if key in normalized["facets"]
        }
        if not anchors:
            return None, "disciplinary_scope_anchor_required"
        facets.update(anchors)

    payload = {
        "version": CLAIM_EVOLUTION_FAMILY_VERSION,
        "subject_key": normalized["subject_key"],
        "event_type": event_type,
        "roles": {key: roles[key] for key in sorted(roles)},
        "facets": {key: facets[key] for key in sorted(facets)},
    }
    return payload, ""


def claim_evolution_family(candidate: Mapping[str, Any]) -> dict[str, Any]:
    normalized = claim_identity.normalize_canonical_claim(candidate)
    payload, reason = _family_scope(normalized)
    if payload is None:
        return {
            "version": CLAIM_EVOLUTION_VERSION,
            "status": "insufficient_scope",
            "reason": reason,
            "subject_key": normalized["subject_key"],
            "event_type": normalized["event_type"],
            "family_key": "",
            "family_fingerprint": "",
            "policy": _policy(),
        }

    fingerprint = hashlib.sha256(
        (
            CLAIM_EVOLUTION_FAMILY_VERSION
            + "|"
            + _canonical_json(payload)
        ).encode("utf-8")
    ).hexdigest()
    family_key = (
        "claim-evolution|"
        + CLAIM_EVOLUTION_FAMILY_VERSION
        + "|"
        + payload["subject_key"]
        + "|"
        + fingerprint
    )
    return {
        "version": CLAIM_EVOLUTION_VERSION,
        "status": "ready",
        "reason": "",
        "subject_key": payload["subject_key"],
        "event_type": payload["event_type"],
        "family_key": family_key,
        "family_fingerprint": fingerprint,
        "payload": payload,
        "policy": _policy(),
    }


def _material_conflicts(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> list[str]:
    conflicts: list[str] = []
    for bucket in ("roles", "facets"):
        left_values = left.get(bucket) or {}
        right_values = right.get(bucket) or {}
        for key in sorted(set(left_values) & set(right_values)):
            if left_values[key] != right_values[key]:
                conflicts.append(bucket + "." + key)
    return conflicts


def classify_claim_evolution(
    predecessor: Mapping[str, Any],
    successor: Mapping[str, Any],
) -> dict[str, Any]:
    left = claim_identity.normalize_canonical_claim(predecessor)
    right = claim_identity.normalize_canonical_claim(successor)
    left_family = claim_evolution_family(left)
    right_family = claim_evolution_family(right)

    base = {
        "version": CLAIM_EVOLUTION_VERSION,
        "relationship_type": "",
        "predecessor_state": left["state"],
        "successor_state": right["state"],
        "family_key": "",
        "material_conflicts": [],
        "policy": _policy(),
    }

    if left_family["status"] != "ready" or right_family["status"] != "ready":
        reason = (
            left_family.get("reason")
            if left_family["status"] != "ready"
            else right_family.get("reason")
        )
        return {**base, "status": "not_related", "reason": reason}

    if left_family["family_key"] != right_family["family_key"]:
        return {**base, "status": "not_related", "reason": "different_family"}

    base["family_key"] = left_family["family_key"]
    conflicts = _material_conflicts(left, right)
    if conflicts:
        return {
            **base,
            "status": "conflict",
            "reason": "material_conflict",
            "material_conflicts": conflicts,
        }

    if left["state"] == right["state"]:
        if left["negated"] != right["negated"]:
            return {
                **base,
                "status": "related",
                "reason": "same_state_negation_flip",
                "relationship_type": "contradicts",
            }
        return {**base, "status": "not_related", "reason": "same_state"}

    if left["negated"] != right["negated"]:
        return {
            **base,
            "status": "conflict",
            "reason": "negation_changed_across_state_transition",
        }

    event_type = left["event_type"]
    order = _PROGRESS_ORDER.get(event_type)
    if order:
        terminals = _TERMINAL_OUTCOMES.get(event_type, frozenset())
        if right["state"] in terminals and left["state"] not in terminals:
            return {
                **base,
                "status": "related",
                "reason": "terminal_outcome",
                "relationship_type": "resolves_to",
            }
        if left["state"] in order and right["state"] in order:
            if order.index(right["state"]) > order.index(left["state"]):
                return {
                    **base,
                    "status": "related",
                    "reason": "forward_state_progression",
                    "relationship_type": "progresses_to",
                }
        return {
            **base,
            "status": "not_related",
            "reason": "unsupported_or_backward_transition",
        }

    allowed = _EXPLICIT_TRANSITIONS.get(event_type, {}).get(
        left["state"], frozenset()
    )
    if right["state"] in allowed:
        return {
            **base,
            "status": "related",
            "reason": "allowed_state_transition",
            "relationship_type": "progresses_to",
        }

    return {
        **base,
        "status": "not_related",
        "reason": "unsupported_or_backward_transition",
    }


def _ensure_schema(conn) -> None:
    conn.executescript(_EVOLUTION_SCHEMA)


def _policy() -> dict[str, bool]:
    return {
        "deterministic_only": True,
        "no_model_call_performed": True,
        "does_not_establish_truth": True,
        "does_not_establish_authority": True,
        "does_not_establish_independence": True,
        "does_not_establish_corroboration": True,
        "affects_live_merit": False,
        "recurrent_weakly_scoped_events_fail_closed": True,
    }


def _structured_claim_from_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    metadata = _json_object(row.get("metadata_json"))
    candidate = metadata.get("structured_claim")
    if not isinstance(candidate, Mapping):
        return None
    try:
        return claim_identity.normalize_canonical_claim(candidate)
    except Exception:
        return None


def _link_id(predecessor_id: str, successor_id: str, relationship_type: str) -> str:
    digest = hashlib.sha256(
        (
            CLAIM_EVOLUTION_LINK_VERSION
            + "|"
            + predecessor_id
            + "|"
            + successor_id
            + "|"
            + relationship_type
        ).encode("utf-8")
    ).hexdigest()
    return "claim-evolution-" + digest[:40]


def _persist_link(
    *,
    predecessor_id: str,
    successor_id: str,
    subject_key: str,
    family_key: str,
    relationship_type: str,
    observed_at: str,
    transition: Mapping[str, Any],
    connection_factory,
) -> dict[str, Any]:
    seen_at = _utc_timestamp(observed_at)
    if not seen_at:
        raise ValueError("Claim evolution observed_at must be timezone-aware ISO-8601.")

    link_id = _link_id(predecessor_id, successor_id, relationship_type)
    metadata = {
        "version": CLAIM_EVOLUTION_LINK_VERSION,
        "transition_reason": _clean(transition.get("reason"), 128),
        "predecessor_state": _clean(transition.get("predecessor_state"), 64),
        "successor_state": _clean(transition.get("successor_state"), 64),
        "truth_established": False,
        "authority_established": False,
        "independence_established": False,
        "affects_live_merit": False,
    }

    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO claim_evolution_links (
              id,
              predecessor_claim_id,
              successor_claim_id,
              subject_key,
              family_key,
              relationship_type,
              observed_at,
              recorded_at,
              metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              observed_at = excluded.observed_at,
              recorded_at = excluded.recorded_at,
              metadata_json = excluded.metadata_json
            """,
            (
                link_id,
                predecessor_id,
                successor_id,
                subject_key,
                family_key,
                relationship_type,
                seen_at,
                seen_at,
                _canonical_json(metadata),
            ),
        )
        row = conn.execute(
            "SELECT * FROM claim_evolution_links WHERE id = ?",
            (link_id,),
        ).fetchone()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if row is None:
        raise RuntimeError("Claim evolution link persistence failed.")
    return dict(row)


def reconcile_claim_evolution(
    *,
    claim_id: str,
    connection_factory,
) -> dict[str, Any]:
    target_id = _clean(claim_id, 128)
    if not target_id:
        raise ValueError("Claim evolution requires a claim ID.")
    if connection_factory is None:
        raise ValueError("Claim evolution requires database access.")

    conn = connection_factory()
    try:
        _ensure_schema(conn)
        target = conn.execute(
            "SELECT * FROM intelligence_claims WHERE id = ?",
            (target_id,),
        ).fetchone()
        if target is None:
            conn.commit()
            return {
                "version": CLAIM_EVOLUTION_VERSION,
                "status": "not_found",
                "claim_id": target_id,
                "links": [],
                "policy": _policy(),
            }
        target_row = dict(target)
        subject_key = _clean(target_row.get("subject_key"), 256).casefold()
        rows = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE subject_key = ?
            ORDER BY first_seen_at, id
            """,
            (subject_key,),
        ).fetchall()
        conn.commit()
    finally:
        conn.close()

    target_candidate = _structured_claim_from_row(target_row)
    if target_candidate is None:
        return {
            "version": CLAIM_EVOLUTION_VERSION,
            "status": "not_reconciled",
            "reason": "structured_identity_unavailable",
            "claim_id": target_id,
            "links": [],
            "policy": _policy(),
        }

    target_family = claim_evolution_family(target_candidate)
    if target_family["status"] != "ready":
        return {
            "version": CLAIM_EVOLUTION_VERSION,
            "status": "not_reconciled",
            "reason": target_family.get("reason") or "insufficient_scope",
            "claim_id": target_id,
            "links": [],
            "policy": _policy(),
        }

    family_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for raw in rows:
        row = dict(raw)
        candidate = _structured_claim_from_row(row)
        if candidate is None:
            continue
        family = claim_evolution_family(candidate)
        if family.get("family_key") != target_family["family_key"]:
            continue
        family_rows.append((row, candidate))

    if len(family_rows) < 2:
        return {
            "version": CLAIM_EVOLUTION_VERSION,
            "status": "no_prior_claims",
            "reason": "family_has_single_claim",
            "claim_id": target_id,
            "family_key": target_family["family_key"],
            "links": [],
            "policy": _policy(),
        }

    persisted: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for successor_index in range(1, len(family_rows)):
        successor_row, successor_candidate = family_rows[successor_index]
        chosen = None
        for predecessor_index in range(successor_index - 1, -1, -1):
            predecessor_row, predecessor_candidate = family_rows[predecessor_index]
            transition = classify_claim_evolution(
                predecessor_candidate,
                successor_candidate,
            )
            decisions.append({
                "predecessor_claim_id": _clean(predecessor_row.get("id"), 128),
                "successor_claim_id": _clean(successor_row.get("id"), 128),
                "status": transition.get("status"),
                "reason": transition.get("reason"),
                "relationship_type": transition.get("relationship_type"),
            })
            if transition.get("status") == "related":
                chosen = (predecessor_row, successor_row, transition)
                break

        if chosen is None:
            continue

        predecessor_row, successor_row, transition = chosen
        observed_at = (
            _utc_timestamp(successor_row.get("first_seen_at"))
            or _utc_timestamp(successor_row.get("last_seen_at"))
        )
        persisted.append(
            _persist_link(
                predecessor_id=_clean(predecessor_row.get("id"), 128),
                successor_id=_clean(successor_row.get("id"), 128),
                subject_key=subject_key,
                family_key=target_family["family_key"],
                relationship_type=_clean(transition.get("relationship_type"), 64),
                observed_at=observed_at,
                transition=transition,
                connection_factory=connection_factory,
            )
        )

    target_links = [
        row
        for row in persisted
        if _clean(row.get("predecessor_claim_id"), 128) == target_id
        or _clean(row.get("successor_claim_id"), 128) == target_id
    ]

    return {
        "version": CLAIM_EVOLUTION_VERSION,
        "status": "reconciled",
        "reason": "deterministic_family_reconciliation_complete",
        "claim_id": target_id,
        "family_key": target_family["family_key"],
        "family_claim_count": len(family_rows),
        "links_written": len(persisted),
        "links": target_links,
        "decisions": decisions[-64:],
        "policy": _policy(),
    }


def reconcile_claim_evolution_safely(**kwargs) -> dict[str, Any]:
    try:
        return reconcile_claim_evolution(**kwargs)
    except Exception as error:
        return {
            "version": CLAIM_EVOLUTION_VERSION,
            "status": "unavailable",
            "reason": "claim_evolution_runtime_failure",
            "error_type": type(error).__name__,
            "links": [],
            "policy": {
                **_policy(),
                "failure_is_advisory": True,
                "error_message_not_exposed": True,
            },
        }


def load_claim_evolution(
    *,
    claim_id: str,
    connection_factory,
) -> dict[str, Any]:
    target_id = _clean(claim_id, 128)
    if not target_id:
        raise ValueError("Claim evolution requires a claim ID.")

    conn = connection_factory()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT *
            FROM claim_evolution_links
            WHERE predecessor_claim_id = ?
               OR successor_claim_id = ?
            ORDER BY observed_at, id
            """,
            (target_id, target_id),
        ).fetchall()
        conn.commit()
    finally:
        conn.close()

    return {
        "version": CLAIM_EVOLUTION_VERSION,
        "status": "ok",
        "claim_id": target_id,
        "links": [dict(row) for row in rows],
        "policy": _policy(),
    }


__all__ = [
    "CLAIM_EVOLUTION_VERSION",
    "CLAIM_EVOLUTION_FAMILY_VERSION",
    "CLAIM_EVOLUTION_LINK_VERSION",
    "claim_evolution_family",
    "classify_claim_evolution",
    "reconcile_claim_evolution",
    "reconcile_claim_evolution_safely",
    "load_claim_evolution",
]
