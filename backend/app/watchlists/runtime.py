from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


VERSION = "watchlists-alerts-v1"
WATCHABLE_KINDS = frozenset({"entity", "story", "claim", "media"})
WATCHLIST_CAP = 100
MAX_WATCHES_PER_RECONCILE = 100
EVENT_SCAN_BATCH = 200
MAX_ALERTS_PER_WATCH = 50
MAX_CURSOR_BYTES = 1024

_TARGETS = {
    "entity": ("canonical_entities", "canonical_name"),
    "story": ("intelligence_stories", "canonical_title"),
    "claim": ("intelligence_claims", "canonical_text"),
    "media": ("media_items", "title"),
}


class NotFoundError(RuntimeError):
    pass


class WatchlistLimitError(RuntimeError):
    pass


def client_key(installation_id: str) -> str:
    value = str(installation_id or "").strip()
    if not value or len(value) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("A valid x-sportabase-client-id header is required.")
    return hashlib.sha256(("sportabase:watchlists:v1:" + value).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex


def _target(conn, kind: str, target_id: str) -> dict[str, str] | None:
    if kind not in _TARGETS:
        raise ValueError("Watch target kind is invalid.")
    table, label_column = _TARGETS[kind]
    row = conn.execute(
        f"SELECT id, {label_column} AS label FROM {table} WHERE id = ?",
        (target_id,),
    ).fetchone()
    return {"id": str(row["id"]), "label": str(row["label"] or "")} if row else None


def _watch(row, target: dict[str, str]) -> dict[str, Any]:
    return {
        "id": row["id"], "target_kind": row["target_kind"],
        "target_id": row["target_id"], "target_label": target["label"],
        "created_at": row["created_at"], "last_reconciled_at": row["last_reconciled_at"],
    }


def create_watch(*, owner_key: str, target_kind: str, target_id: str, connection_factory) -> dict[str, Any]:
    kind = str(target_kind or "").strip().lower()
    resource_id = str(target_id or "").strip()
    if len(resource_id) < 1 or len(resource_id) > 128:
        raise ValueError("Watch target ID is invalid.")
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        target = _target(conn, kind, resource_id)
        if target is None:
            raise NotFoundError("Watch target not found.")
        existing = conn.execute(
            "SELECT * FROM product_watchlist_items WHERE client_key=? AND target_kind=? AND target_id=?",
            (owner_key, kind, resource_id),
        ).fetchone()
        if existing is not None:
            conn.commit()
            return {"watch": _watch(existing, target), "created": False}
        count = conn.execute("SELECT COUNT(*) FROM product_watchlist_items WHERE client_key=?", (owner_key,)).fetchone()[0]
        if count >= WATCHLIST_CAP:
            raise WatchlistLimitError(f"Watchlist limit of {WATCHLIST_CAP} reached.")
        watermark = conn.execute("SELECT COALESCE(MAX(sequence),0) FROM product_intelligence_events").fetchone()[0]
        created_at = _now()
        watch_id = _id("watch")
        conn.execute(
            "INSERT INTO product_watchlist_items(id,client_key,target_kind,target_id,created_at,event_watermark) VALUES(?,?,?,?,?,?)",
            (watch_id, owner_key, kind, resource_id, created_at, watermark),
        )
        row = conn.execute("SELECT * FROM product_watchlist_items WHERE id=?", (watch_id,)).fetchone()
        conn.commit()
        return {"watch": _watch(row, target), "created": True}
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise RuntimeError("Watchlist persistence conflict.") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_watches(*, owner_key: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        rows = conn.execute("SELECT * FROM product_watchlist_items WHERE client_key=? ORDER BY created_at,id", (owner_key,)).fetchall()
        items = [_watch(row, _target(conn, row["target_kind"], row["target_id"]) or {"label": ""}) for row in rows]
        return {"version": VERSION, "items": items, "count": len(items), "limit": WATCHLIST_CAP}
    finally:
        conn.close()


def delete_watch(*, owner_key: str, watch_id: str, connection_factory) -> None:
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute("DELETE FROM product_watchlist_items WHERE id=? AND client_key=?", (watch_id, owner_key))
        if cursor.rowcount != 1:
            raise NotFoundError("Watch item not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _event_details(conn, event, kind: str, target_id: str) -> dict[str, str] | None:
    table, source_id = event["source_table"], event["source_id"]
    row = None
    related_kind = related_id = ""
    if table == "verified_claim_entity_participants":
        row = conn.execute("SELECT claim_id,entity_id FROM verified_claim_entity_participants WHERE id=?", (source_id,)).fetchone()
        if row and ((kind == "entity" and row["entity_id"] == target_id) or (kind == "claim" and row["claim_id"] == target_id)):
            related_kind, related_id = ("claim", row["claim_id"]) if kind == "entity" else ("entity", row["entity_id"])
        else: row = None
    elif table == "story_claim_links":
        story_id, claim_id = source_id, event["source_related_id"]
        if kind == "story" and story_id == target_id: row, related_kind, related_id = True, "claim", claim_id
        elif kind == "claim" and claim_id == target_id: row, related_kind, related_id = True, "story", story_id
        elif kind == "entity":
            row = conn.execute("SELECT 1 FROM verified_claim_entity_participants WHERE claim_id=? AND entity_id=?", (claim_id, target_id)).fetchone()
            related_kind, related_id = "story", story_id
    elif table == "story_media_links":
        story_id, media_id = source_id, event["source_related_id"]
        if kind == "story" and story_id == target_id: row, related_kind, related_id = True, "media", media_id
        elif kind == "entity":
            row = conn.execute("SELECT 1 FROM story_claim_links l JOIN verified_claim_entity_participants p ON p.claim_id=l.claim_id WHERE l.story_id=? AND p.entity_id=? LIMIT 1", (story_id, target_id)).fetchone()
            related_kind, related_id = "media", media_id
    elif table in {"source_observations", "reporter_observations"} and kind == "story":
        row = conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND story_id=?", (source_id, target_id)).fetchone()
    elif table == "evidence_links" and kind == "story":
        row = conn.execute("SELECT evidence_id FROM evidence_links WHERE id=? AND story_id=?", (source_id, target_id)).fetchone()
        if row: related_kind, related_id = "evidence", row["evidence_id"]
    elif table == "claim_links" and kind == "claim":
        row = conn.execute("SELECT source_observation_id,reporter_observation_id,evidence_id FROM claim_links WHERE id=? AND claim_id=?", (source_id, target_id)).fetchone()
        if row:
            related_kind = "evidence" if row["evidence_id"] else ("reporter_observation" if row["reporter_observation_id"] else "source_observation")
            related_id = row["evidence_id"] or row["reporter_observation_id"] or row["source_observation_id"]
    elif table in {"adjudication_state_revisions", "adjudication_state_transitions"} and kind == "claim":
        row = conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND claim_id=?", (source_id, target_id)).fetchone()
    elif table == "analysis_snapshots" and kind in {"media", "story"}:
        column = "media_item_id" if kind == "media" else "story_id"
        row = conn.execute(f"SELECT media_item_id FROM analysis_snapshots WHERE id=? AND {column}=?", (source_id, target_id)).fetchone()
        if row and kind == "story": related_kind, related_id = "media", row["media_item_id"]
    if not row:
        return None
    return {"related_kind": related_kind, "related_id": str(related_id or "")}


def _summary(event_type: str, kind: str, label: str) -> str:
    activity = {
        "analysis_snapshot": "New analysis snapshot",
        "source_observation": "New source observation",
        "reporter_observation": "New reporter observation",
        "evidence": "New evidence activity",
        "adjudication_revision": "New adjudication revision",
        "adjudication_transition": "New adjudication transition",
    }.get(event_type, "New " + ("claim activity" if event_type in {"verified_claim_participation", "claim_link"} else "relationship activity"))
    return f"{activity} for {label or kind}"


def reconcile(*, owner_key: str, connection_factory) -> dict[str, int]:
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        watches = conn.execute("SELECT * FROM product_watchlist_items WHERE client_key=? ORDER BY created_at,id LIMIT ?", (owner_key, MAX_WATCHES_PER_RECONCILE)).fetchall()
        new_alerts = unchanged = 0
        for watch in watches:
            target = _target(conn, watch["target_kind"], watch["target_id"]) or {"label": watch["target_kind"]}
            events = conn.execute("SELECT * FROM product_intelligence_events WHERE sequence>? ORDER BY sequence LIMIT ?", (watch["event_watermark"], EVENT_SCAN_BATCH)).fetchall()
            watermark = watch["event_watermark"]
            watch_alerts = 0
            for event in events:
                details = _event_details(conn, event, watch["target_kind"], watch["target_id"])
                watermark = event["sequence"]
                if details is None:
                    continue
                detected = _now()
                cursor = conn.execute("""INSERT OR IGNORE INTO product_alert_events
                    (id,client_key,watch_id,target_kind,target_id,source_event_key,event_type,related_kind,related_id,summary,occurred_at,detected_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    _id("alert"), owner_key, watch["id"], watch["target_kind"], watch["target_id"],
                    event["source_event_key"], event["event_type"], details["related_kind"] or None,
                    details["related_id"] or None, _summary(event["event_type"], watch["target_kind"], target["label"]),
                    event["occurred_at"], detected,
                ))
                if cursor.rowcount:
                    new_alerts += 1
                    watch_alerts += 1
                if watch_alerts >= MAX_ALERTS_PER_WATCH:
                    break
            if not events or watch_alerts == 0:
                unchanged += 1
            conn.execute("UPDATE product_watchlist_items SET event_watermark=?,last_reconciled_at=? WHERE id=? AND client_key=?", (watermark, _now(), watch["id"], owner_key))
        conn.commit()
        return {"watches_checked": len(watches), "new_alerts": new_alerts, "unchanged_watches": unchanged}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cursor_scope(owner_key: str, unread_only: bool, target_kind: str) -> str:
    owner_scope = hashlib.sha256(("cursor:" + owner_key).encode()).hexdigest()[:16]
    return f"{owner_scope}:{int(unread_only)}:{target_kind}"


def _encode_cursor(scope: str, detected_at: str, alert_id: str) -> str:
    raw = json.dumps([VERSION, scope, detected_at, alert_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str, scope: str) -> tuple[str, str] | None:
    if not value: return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if len(raw) > MAX_CURSOR_BYTES: raise ValueError
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or len(parsed) != 4 or parsed[:2] != [VERSION, scope]: raise ValueError
        if not all(isinstance(x, str) for x in parsed[2:]): raise ValueError
        return parsed[2], parsed[3]
    except Exception as exc:
        raise ValueError("Cursor is invalid.") from exc


def _alert(row) -> dict[str, Any]:
    return {key: row[key] for key in ("id","target_kind","target_id","event_type","related_kind","related_id","summary","occurred_at","detected_at","read_at")}


def list_alerts(*, owner_key: str, unread_only: bool, target_kind: str, limit: int, cursor: str, connection_factory) -> dict[str, Any]:
    kind = str(target_kind or "").strip().lower()
    if kind and kind not in WATCHABLE_KINDS: raise ValueError("Alert target kind is invalid.")
    scope = _cursor_scope(owner_key, unread_only, kind)
    key = _decode_cursor(cursor, scope)
    clauses, params = ["client_key=?"], [owner_key]
    if unread_only: clauses.append("read_at IS NULL")
    if kind: clauses.append("target_kind=?"); params.append(kind)
    if key: clauses.append("(detected_at < ? OR (detected_at = ? AND id < ?))"); params.extend((key[0], key[0], key[1]))
    conn = connection_factory()
    try:
        rows = conn.execute("SELECT * FROM product_alert_events WHERE " + " AND ".join(clauses) + " ORDER BY detected_at DESC,id DESC LIMIT ?", (*params, limit + 1)).fetchall()
    finally: conn.close()
    more = len(rows) > limit
    page = rows[:limit]
    next_cursor = _encode_cursor(scope, page[-1]["detected_at"], page[-1]["id"]) if more and page else None
    return {"version": VERSION, "items": [_alert(row) for row in page], "pagination": {"limit": limit, "next_cursor": next_cursor}}


def mark_read(*, owner_key: str, alert_id: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM product_alert_events WHERE id=? AND client_key=?", (alert_id, owner_key)).fetchone()
        if row is None: raise NotFoundError("Alert not found.")
        if row["read_at"] is None:
            conn.execute("UPDATE product_alert_events SET read_at=? WHERE id=? AND client_key=?", (_now(), alert_id, owner_key))
            row = conn.execute("SELECT * FROM product_alert_events WHERE id=? AND client_key=?", (alert_id, owner_key)).fetchone()
        conn.commit()
        return _alert(row)
    except Exception:
        conn.rollback(); raise
    finally: conn.close()
