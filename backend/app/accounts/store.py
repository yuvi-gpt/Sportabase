from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import time
import uuid
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException

from app.accounts.preferences import Preferences, effective_preferences, validate_patch
from app.watchlists.runtime import client_key


VERSION = "sportabase-preferences-v1"
LOGGER = logging.getLogger(__name__)
EVENTS = frozenset({"landing_visit", "account_first_seen", "session_active", "analysis_initiated",
                    "analysis_completed", "first_analysis", "watch_created", "notification_enabled",
                    "notification_disabled", "settings_opened"})
PRIVATE_TABLES = ("product_notification_deliveries", "product_web_push_deliveries",
                  "product_notification_devices", "product_web_push_subscriptions",
                  "product_notification_alert_ledger", "product_alert_events", "product_watchlist_items", "user_history")


@contextmanager
def transaction(factory):
    conn = factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def subject_hash(subject):
    return hashlib.sha256(("sportabase:clerk:" + subject).encode()).hexdigest()


def owner_key(account_id):
    return "account:" + account_id


def ensure_account(conn, subject, *, allow_deleting=False):
    now = int(time.time())
    digest = subject_hash(subject)
    conn.execute("INSERT INTO product_accounts(id,subject_hash,created_at,last_seen_at) VALUES(?,?,?,?) ON CONFLICT(subject_hash) DO NOTHING",
                 ("acct_" + uuid.uuid4().hex, digest, now, now))
    row = dict(conn.execute("SELECT * FROM product_accounts WHERE subject_hash=?", (digest,)).fetchone())
    if row["status"] != "active" and not (allow_deleting and row["status"] == "deleting"):
        raise HTTPException(403, "This account is unavailable.")
    conn.execute("UPDATE product_accounts SET last_seen_at=? WHERE id=?", (now, row["id"]))
    return row


def installation(conn, account_id, device_id):
    row = conn.execute("SELECT * FROM product_installations WHERE account_id=? AND device_id=?", (account_id, device_id)).fetchone()
    if row is None:
        raise HTTPException(409, "Register this device before using Sportabase.")
    return dict(row)


def snapshot(conn, account_id, device_id):
    account = dict(conn.execute("SELECT * FROM product_accounts WHERE id=?", (account_id,)).fetchone())
    device = installation(conn, account_id, device_id)
    defaults = Preferences.model_validate(json.loads(account["defaults_json"])).model_dump()
    overrides = json.loads(device["overrides_json"])
    return {"version": VERSION, "account": {"id": account_id, "status": account["status"], "created_at": account["created_at"]},
            "account_revision": account["revision"], "device_revision": device["revision"],
            "device": {k: device[k] for k in ("device_id", "platform", "name", "last_seen_at")},
            "follows_defaults": bool(device["follows_defaults"]), "defaults": defaults, "overrides": overrides,
            "effective": effective_preferences(defaults, overrides, bool(device["follows_defaults"]))}


def register_installation(conn, account_id, device_id, platform, name):
    now = int(time.time())
    count = conn.execute("SELECT COUNT(*) FROM product_installations WHERE account_id=?", (account_id,)).fetchone()[0]
    exists = conn.execute("SELECT 1 FROM product_installations WHERE account_id=? AND device_id=?", (account_id, device_id)).fetchone()
    if count >= 50 and not exists:
        raise HTTPException(409, "Device limit reached.")
    conn.execute("""INSERT INTO product_installations(account_id,device_id,platform,name,created_at,last_seen_at)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(account_id,device_id) DO UPDATE SET
                    name=excluded.name,last_seen_at=excluded.last_seen_at""", (account_id, device_id, platform, name, now, now))
    if installation(conn, account_id, device_id)["platform"] != platform:
        raise HTTPException(409, "Device platform cannot change.")


def link_legacy(conn, account_id, device_id, legacy_id):
    """Possession of the pre-account bearer identity is the only historical proof.

    A UNIQUE link under the write transaction makes first claim atomic. Linking
    never uses an identity from a body/header to decide the authenticated account.
    """
    old = client_key(legacy_id)
    prior = conn.execute("SELECT account_id FROM product_legacy_links WHERE legacy_key=?", (old,)).fetchone()
    if prior:
        if prior["account_id"] != account_id:
            # Possession alone cannot move an identity after its first claim.  The
            # migration outcome is non-fatal so a different account can still
            # register the same physical installation without seeing private data.
            return "already_claimed_elsewhere"
        return "already_claimed_by_account"
    new = owner_key(account_id)
    conn.execute("INSERT INTO product_legacy_links VALUES(?,?,?,?)", (old, account_id, device_id, int(time.time())))
    # Merge duplicate watches before changing their owner. Distinct alerts survive;
    # only the same source event for the same target is deduplicated.
    for watch in conn.execute("SELECT * FROM product_watchlist_items WHERE client_key=?", (old,)).fetchall():
        duplicate = conn.execute("SELECT * FROM product_watchlist_items WHERE client_key=? AND target_kind=? AND target_id=?",
                                 (new, watch["target_kind"], watch["target_id"])).fetchone()
        if duplicate:
            conn.execute("DELETE FROM product_alert_events WHERE watch_id=? AND source_event_key IN (SELECT source_event_key FROM product_alert_events WHERE watch_id=?)", (watch["id"], duplicate["id"]))
            conn.execute("UPDATE product_alert_events SET watch_id=? WHERE watch_id=?", (duplicate["id"], watch["id"]))
            conn.execute("UPDATE product_watchlist_items SET event_watermark=MIN(event_watermark,?) WHERE id=?", (watch["event_watermark"], duplicate["id"]))
            conn.execute("DELETE FROM product_watchlist_items WHERE id=?", (watch["id"],))
    for provider, table in (("expo", "product_notification_devices"), ("web", "product_web_push_subscriptions")):
        for row in conn.execute(f"SELECT id FROM {table} WHERE client_key=?", (old,)).fetchall():
            conn.execute("INSERT INTO product_notification_bindings VALUES(?,?,?,?) ON CONFLICT(provider,registration_id) DO NOTHING", (provider, row["id"], account_id, device_id))
    for table in PRIVATE_TABLES[:-1]:
        conn.execute(f"UPDATE {table} SET client_key=? WHERE client_key=?", (new, old))
    history_key = hashlib.sha256(("installation:" + legacy_id).encode()).hexdigest()[:32]
    for row in conn.execute("SELECT h.*,m.title,m.canonical_url,m.mode FROM user_history h JOIN media_items m ON m.id=h.media_item_id WHERE h.client_key=?", (history_key,)).fetchall():
        if row["mode"] in ("article", "video"):
            try:
                epoch = int(datetime.fromisoformat(row["last_analyzed_at"]).timestamp())
            except (ValueError, TypeError):
                epoch = int(time.time())
            conn.execute("INSERT INTO product_activity VALUES(?,?,?,?,?,?,?,?,?)", ("act_" + uuid.uuid4().hex, account_id, device_id,
                         installation(conn, account_id, device_id)["platform"], row["mode"], row["title"][:240], safe_url(row["canonical_url"]), row["media_item_id"], epoch))
        conn.execute("""INSERT INTO user_history VALUES(?,?,?,?,?,?) ON CONFLICT(client_key,media_item_id) DO UPDATE SET
                     last_analyzed_at=MAX(user_history.last_analyzed_at,excluded.last_analyzed_at),
                     analysis_count=user_history.analysis_count+excluded.analysis_count""",
                     (new, row["media_item_id"], row["first_analyzed_at"], row["last_analyzed_at"], row["analysis_count"], row["last_snapshot_id"]))
    conn.execute("DELETE FROM user_history WHERE client_key=?", (history_key,))
    return "claimed"


def update_preferences(conn, account_id, device_id, scope, revision, patch, follows=None):
    current = snapshot(conn, account_id, device_id)
    if scope == "account":
        if revision != current["account_revision"]:
            raise HTTPException(409, "Settings changed elsewhere. Reload and try again.")
        was_analytics_enabled = current["defaults"]["analytics_enabled"]
        updated = {**current["defaults"], **validate_patch(patch, current["defaults"])}
        # Account-only privacy settings must not be silently weakened by a device.
        conn.execute("UPDATE product_accounts SET defaults_json=?,revision=revision+1 WHERE id=?", (json.dumps(updated), account_id))
        if not updated["analytics_enabled"]:
            conn.execute("DELETE FROM product_analytics WHERE account_id=?", (account_id,))
        # Existing override combinations must remain valid after a default changes.
        for device in conn.execute("SELECT * FROM product_installations WHERE account_id=?", (account_id,)).fetchall():
            effective_preferences(updated, json.loads(device["overrides_json"]), bool(device["follows_defaults"]))
        if updated["analytics_enabled"] and not was_analytics_enabled:
            try_record_event(conn, account_id, "account_first_seen", current["device"]["platform"])
    else:
        if revision != current["device_revision"]:
            raise HTTPException(409, "Device settings changed elsewhere. Reload and try again.")
        if "analytics_enabled" in patch or "activity_enabled" in patch:
            raise HTTPException(422, "Privacy controls apply to the account.")
        overrides = {**current["overrides"], **validate_patch(patch, current["effective"])}
        follow = current["follows_defaults"] if follows is None else follows
        effective_preferences(current["defaults"], overrides, follow)
        conn.execute("UPDATE product_installations SET overrides_json=?,follows_defaults=?,revision=revision+1 WHERE account_id=? AND device_id=?",
                     (json.dumps(overrides), int(follow), account_id, device_id))
    return snapshot(conn, account_id, device_id)


def safe_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            return ""
        # No arbitrary tracking/query credentials in activity. YouTube v is needed to reopen.
        from urllib.parse import parse_qs, urlencode
        query = ""
        if parsed.hostname.lower() in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            video = parse_qs(parsed.query).get("v", [""])[0]
            if video and len(video) <= 32:
                query = urlencode({"v": video})
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))[:2048]
    except ValueError:
        return ""


def record_event(conn, account_id, event, platform):
    if event not in EVENTS or platform not in ("web", "mobile", "extension"):
        raise ValueError("Invalid analytics event")
    if account_id:
        row = conn.execute("SELECT defaults_json FROM product_accounts WHERE id=?", (account_id,)).fetchone()
        if not row or not Preferences.model_validate(json.loads(row[0])).analytics_enabled:
            return
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Active-user signals are one per account/platform/day, not every API request.
    dedupe = f"{account_id}:{event}:{platform}:{day}" if event in ("session_active", "first_analysis") else uuid.uuid4().hex
    conn.execute("INSERT INTO product_analytics VALUES(?,?,?,?,?) ON CONFLICT(id) DO NOTHING", (dedupe, account_id, event, platform, day))
    conn.execute("DELETE FROM product_analytics WHERE day < date('now','-90 days')")


def try_record_event(conn, account_id, event, platform):
    """Record optional product analytics without changing an authoritative write."""
    try:
        record_event(conn, account_id, event, platform)
        return True
    except Exception:
        LOGGER.exception("Optional product analytics persistence failed", extra={"event": event, "platform": platform})
        return False


def record_event_best_effort(factory, account_id, event, platform):
    """Use a separate transaction so analytics cannot roll back core product state."""
    try:
        with transaction(factory) as conn:
            record_event(conn, account_id, event, platform)
        return True
    except Exception:
        LOGGER.exception("Optional product analytics transaction failed", extra={"event": event, "platform": platform})
        return False


def record_analysis(factory, account_id, device_id, kind, title, url):
    with transaction(factory) as conn:
        state = snapshot(conn, account_id, device_id)
        if state["account"]["status"] != "active":
            return
        if state["defaults"]["activity_enabled"]:
            canonical = conn.execute("SELECT id FROM media_items WHERE canonical_url=?", (url,)).fetchone()
            conn.execute("INSERT INTO product_activity VALUES(?,?,?,?,?,?,?,?,?)", ("act_" + uuid.uuid4().hex, account_id, device_id,
                         state["device"]["platform"], kind, str(title or f"{kind.title()} analysis")[:240], safe_url(url), canonical[0] if canonical else None, int(time.time())))
        first = conn.execute("UPDATE product_accounts SET first_analysis_at=? WHERE id=? AND first_analysis_at IS NULL", (int(time.time()), account_id)).rowcount
        if first:
            try_record_event(conn, account_id, "first_analysis", state["device"]["platform"])
        try_record_event(conn, account_id, "analysis_completed", state["device"]["platform"])


def record_analysis_best_effort(factory, account_id, device_id, kind, title, url):
    """Persist My Activity after provider success without replacing that success."""
    try:
        record_analysis(factory, account_id, device_id, kind, title, url)
        return True
    except Exception:
        LOGGER.exception("Optional My Activity persistence failed", extra={"kind": kind})
        return False


def revoke_device_notifications(conn, account_id, device_id):
    """Remove only push registrations bound to one authenticated installation."""
    owner = owner_key(account_id)
    rows = conn.execute(
        "SELECT provider,registration_id FROM product_notification_bindings WHERE account_id=? AND device_id=?",
        (account_id, device_id),
    ).fetchall()
    revoked = {"expo": 0, "web": 0}
    for row in rows:
        provider, registration_id = row["provider"], row["registration_id"]
        if provider == "expo":
            cursor = conn.execute(
                "DELETE FROM product_notification_devices WHERE id=? AND client_key=?",
                (registration_id, owner),
            )
        elif provider == "web":
            cursor = conn.execute(
                "DELETE FROM product_web_push_subscriptions WHERE id=? AND client_key=?",
                (registration_id, owner),
            )
        else:
            raise RuntimeError("Unknown notification binding provider")
        revoked[provider] += int(cursor.rowcount or 0)
    conn.execute(
        "DELETE FROM product_notification_bindings WHERE account_id=? AND device_id=?",
        (account_id, device_id),
    )
    return revoked


def erase_private_data(conn, account_id):
    for table in PRIVATE_TABLES:
        conn.execute(f"DELETE FROM {table} WHERE client_key=?", (owner_key(account_id),))
    for table in ("product_activity", "product_analytics", "product_notification_bindings", "product_legacy_links", "product_installations"):
        conn.execute(f"DELETE FROM {table} WHERE account_id=?", (account_id,))
    # Keep only the opaque row ID, the domain-separated subject hash and deleted
    # status needed to reject an old Clerk session.  Timestamps and revisions are
    # no longer operationally useful after deletion and are zeroed.
    conn.execute("""UPDATE product_accounts SET status='deleted',defaults_json='{}',revision=0,
                 created_at=0,last_seen_at=0,first_analysis_at=NULL WHERE id=?""", (account_id,))
