from datetime import datetime, timedelta, timezone
import json
import os
import time
from typing import Literal
from urllib.parse import quote

import requests
from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.accounts.auth import recent_intent
from app.accounts import store


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Bootstrap(StrictModel):
    platform: Literal["web", "mobile", "extension"]
    name: str = Field(min_length=1, max_length=80)
    legacy_client_id: str | None = Field(default=None, min_length=16, max_length=200)


class SettingsUpdate(StrictModel):
    version: Literal["sportabase-preferences-v1"]
    scope: Literal["account", "device"]
    revision: int = Field(ge=1)
    preferences: dict = Field(default_factory=dict)
    follows_defaults: bool | None = None


class Intent(StrictModel):
    confirmation: str


class Event(StrictModel):
    event: Literal["settings_opened"]


class LandingEvent(StrictModel):
    platform: Literal["web"]


def delete_clerk_user(subject):
    secret = os.getenv("CLERK_SECRET_KEY", "")
    if not secret:
        raise HTTPException(503, "Account deletion is not configured. Contact support.")
    try:
        response = requests.delete("https://api.clerk.com/v1/users/" + quote(subject, safe=""),
                                   headers={"Authorization": "Bearer " + secret}, timeout=10, allow_redirects=False)
        if response.status_code not in (200, 204, 404):
            raise ValueError("Provider deletion failed")
    except Exception as exc:
        raise HTTPException(503, "Deletion is pending. Sign in again to retry deletion.") from exc


def build_router(*, connection_factory, require_admin, provider_delete=delete_clerk_user):
    router = APIRouter(tags=["account-product"])

    @router.post("/account/bootstrap")
    def bootstrap(body: Bootstrap, request: Request):
        with store.transaction(connection_factory) as conn:
            account_id = request.state.account["id"]
            store.register_installation(conn, account_id, request.state.device_id, body.platform, body.name)
            migration = (store.link_legacy(conn, account_id, request.state.device_id, body.legacy_client_id)
                         if body.legacy_client_id else "not_requested")
            return {**store.snapshot(conn, account_id, request.state.device_id),
                    "legacy_migration": {"status": migration}}

    @router.get("/account")
    def profile(request: Request):
        with store.transaction(connection_factory) as conn:
            return store.snapshot(conn, request.state.account["id"], request.state.device_id)

    @router.patch("/account/preferences")
    def preferences(body: SettingsUpdate, request: Request):
        try:
            with store.transaction(connection_factory) as conn:
                return store.update_preferences(conn, request.state.account["id"], request.state.device_id,
                                                body.scope, body.revision, body.preferences, body.follows_defaults)
        except ValidationError as exc:
            raise HTTPException(422, "Invalid preferences. Check the selected values and quiet hours.") from exc

    @router.get("/account/devices")
    def devices(request: Request):
        with store.transaction(connection_factory) as conn:
            rows = conn.execute("SELECT device_id,platform,name,follows_defaults,created_at,last_seen_at FROM product_installations WHERE account_id=? ORDER BY last_seen_at DESC", (request.state.account["id"],)).fetchall()
            return {"items": [{**dict(row), "current": row["device_id"] == request.state.device_id} for row in rows]}

    @router.get("/account/activity")
    def activity(request: Request, kind: Literal["", "article", "video"] = "", q: str = Query("", max_length=120),
                 limit: int = Query(30, ge=1, le=100), before: int = Query(0, ge=0), cursor: str = Query("", max_length=80)):
        with store.transaction(connection_factory) as conn:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            rows = conn.execute("""SELECT id,kind,title,url,media_item_id,created_at,platform FROM product_activity
              WHERE account_id=? AND (?='' OR kind=?) AND title LIKE ? ESCAPE '\\'
              AND (?=0 OR created_at<? OR (created_at=? AND id<?)) ORDER BY created_at DESC,id DESC LIMIT ?""",
              (request.state.account["id"], kind, kind, "%" + escaped + "%", before, before, before, cursor, limit + 1)).fetchall()
            items = [dict(row) for row in rows[:limit]]
            last = items[-1] if items and len(rows) > limit else None
            return {"items": items, "next": {"before": last["created_at"], "cursor": last["id"]} if last else None}

    @router.delete("/account/activity", status_code=204)
    def clear_activity(body: Intent, request: Request):
        if body.confirmation != "CLEAR MY ACTIVITY":
            raise HTTPException(422, "Confirm clearing My Activity.")
        with store.transaction(connection_factory) as conn:
            conn.execute("DELETE FROM product_activity WHERE account_id=?", (request.state.account["id"],))
            conn.execute("DELETE FROM user_history WHERE client_key=?", (store.owner_key(request.state.account["id"]),))
        return Response(status_code=204)

    @router.get("/account/export")
    def export(request: Request):
        with store.transaction(connection_factory) as conn:
            account_id = request.state.account["id"]
            data = {"version": "sportabase-personal-export-v1", "settings": store.snapshot(conn, account_id, request.state.device_id)}
            for name, table in (("devices", "product_installations"), ("activity", "product_activity")):
                data[name] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE account_id=?", (account_id,))]
            for name, table in (("watches", "product_watchlist_items"), ("alerts", "product_alert_events")):
                data[name] = [{k: row[k] for k in row.keys() if k != "client_key"} for row in conn.execute(f"SELECT * FROM {table} WHERE client_key=?", (store.owner_key(account_id),))]
            # Explicit columns: never serialize a provider registration or JWT row.
            data["notification_registrations"] = [dict(row) for row in conn.execute("SELECT provider,registration_id,device_id FROM product_notification_bindings WHERE account_id=?", (account_id,))]
            # Personal history is distinct from canonical Intelligence History.
            # Export only account-owned references and counters, never media bodies,
            # transcripts, URLs, provider payloads or snapshot contents.
            data["user_history"] = [dict(row) for row in conn.execute(
                """SELECT media_item_id,first_analyzed_at,last_analyzed_at,analysis_count
                   FROM user_history WHERE client_key=? ORDER BY last_analyzed_at DESC,media_item_id""",
                (store.owner_key(account_id),),
            )]
            return Response(json.dumps(data), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="sportabase-personal-data.json"', "Cache-Control": "no-store"})

    @router.post("/account/device/sign-out")
    def prepare_device_sign_out(request: Request):
        """Revoke only this account/device's push ownership before Clerk sign-out."""
        with store.transaction(connection_factory) as conn:
            revoked = store.revoke_device_notifications(
                conn, request.state.account["id"], request.state.device_id
            )
        return {"version": "sportabase-device-sign-out-v1", "revoked": revoked}

    @router.delete("/account", status_code=204)
    def delete_account(body: Intent, request: Request):
        if body.confirmation != "DELETE MY ACCOUNT":
            raise HTTPException(422, "Confirm deleting your account.")
        recent_intent(request.state.clerk_claims)
        if provider_delete is delete_clerk_user and not os.getenv("CLERK_SECRET_KEY"):
            raise HTTPException(503, "Account deletion is not configured. Contact support.")
        account_id = request.state.account["id"]
        # Durable fail-closed saga: revoke product access and credentials before the
        # provider call. On failure the user may only retry deletion, never use data.
        with store.transaction(connection_factory) as conn:
            conn.execute("UPDATE product_accounts SET status='deleting' WHERE id=?", (account_id,))
            for table, credential in (("product_notification_devices", "push_token"), ("product_web_push_subscriptions", "endpoint")):
                conn.execute(f"UPDATE {table} SET enabled=0,{credential}='' WHERE client_key=?", (store.owner_key(account_id),))
            conn.execute("UPDATE product_web_push_subscriptions SET p256dh='',auth_secret='' WHERE client_key=?", (store.owner_key(account_id),))
        provider_delete(request.state.clerk_claims["sub"])
        with store.transaction(connection_factory) as conn:
            store.erase_private_data(conn, account_id)
        return Response(status_code=204)

    @router.post("/account/events", status_code=204)
    def event(body: Event, request: Request):
        store.record_event_best_effort(connection_factory, request.state.account["id"], body.event,
                                       request.state.account_device["platform"])
        return Response(status_code=204)

    @router.post("/product-events/landing", status_code=204)
    def landing_event(body: LandingEvent):
        # Anonymous acquisition is aggregate-only: no IP, user agent, URL, referrer,
        # installation ID, or arbitrary metadata enters the product event table.
        store.record_event_best_effort(connection_factory, None, "landing_visit", body.platform)
        return Response(status_code=204)

    @router.get("/admin/product-analytics")
    def aggregates(request: Request):
        require_admin(request)
        with store.transaction(connection_factory) as conn:
            now = datetime.now(timezone.utc)
            result = {"registered_accounts": conn.execute("SELECT COUNT(*) FROM product_accounts WHERE status='active'").fetchone()[0],
                      "new_accounts_7d": conn.execute("SELECT COUNT(*) FROM product_accounts WHERE status='active' AND created_at>=?", (int(time.time()) - 7*86400,)).fetchone()[0],
                      "completed_first_analysis_accounts": conn.execute("SELECT COUNT(*) FROM product_accounts WHERE status='active' AND first_analysis_at IS NOT NULL").fetchone()[0],
                      "measurement": "Events and active-user counts include analytics opt-ins only; account counts are operational totals."}
            for label, days in (("dau", 1), ("wau", 7), ("mau", 30)):
                day = (now - timedelta(days=days-1)).strftime("%Y-%m-%d")
                result[label] = conn.execute("SELECT COUNT(DISTINCT account_id) FROM product_analytics WHERE event='session_active' AND day>=?", (day,)).fetchone()[0]
            result["events_90d"] = {row["event"]: row["count"] for row in conn.execute("SELECT event,COUNT(*) AS count FROM product_analytics GROUP BY event")}
            result["watch_creator_accounts"] = conn.execute("SELECT COUNT(DISTINCT client_key) FROM product_watchlist_items WHERE client_key LIKE 'account:%'").fetchone()[0]
            result["notification_enabled_devices"] = conn.execute("SELECT COUNT(*) FROM product_notification_devices WHERE enabled=1 AND client_key LIKE 'account:%'").fetchone()[0] + conn.execute("SELECT COUNT(*) FROM product_web_push_subscriptions WHERE enabled=1 AND client_key LIKE 'account:%'").fetchone()[0]
            result["returning_active_accounts_30d"] = conn.execute("""SELECT COUNT(*) FROM (
              SELECT account_id FROM product_analytics WHERE event='session_active' AND day>=? AND account_id IS NOT NULL
              GROUP BY account_id HAVING COUNT(DISTINCT day)>=2)""", ((now - timedelta(days=29)).strftime("%Y-%m-%d"),)).fetchone()[0]
            return result

    return router
