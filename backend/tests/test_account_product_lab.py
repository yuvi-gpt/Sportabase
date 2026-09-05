import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import jwt
import pytest

from app.accounts.auth import AuthConfig, ClerkVerifier, configured_verifier
from app.accounts.boundary import AccountBoundary
from app.accounts import notification_policy
from app.accounts.preferences import Preferences, delivery_time
from app.accounts import store
from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.routes.account_product import build_router
from app.routes.watchlists_product import build_router as watches_router
from app.routes.notifications_product import build_router as notifications_router
from app.routes import product_api
from app.models.api import AnalyzeResponse
from app.application.composition import create_application


ISSUER = "https://clerk.example.test"
DEVICE = str(uuid.UUID(int=1))
OTHER_DEVICE = str(uuid.UUID(int=2))


def test_shared_preference_contract_matches_backend_defaults():
    contract = json.loads(
        (Path(__file__).parents[2] / "frontend" / "preferences-contract.json").read_text(encoding="utf-8")
    )
    defaults = Preferences().model_dump()

    assert contract["version"] == store.VERSION
    assert contract["defaults"] == defaults
    assert set(contract["fields"]) == set(defaults)
    assert set().union(*map(set, contract["sections"].values())) == set(defaults)


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    return private, {**jwk, "kid": "local-one", "use": "sig", "alg": "RS256"}


def token(keys, subject="user_a", **changes):
    now = int(time.time())
    claims = dict(sub=subject, sid="sess_test", iss=ISSUER, iat=now, nbf=now-1, exp=now+300,
                  aud="sportabase", azp="https://app.example.test", fva=[0, -1])
    claims.update(changes)
    return jwt.encode(claims, keys[0], algorithm="RS256", headers={"kid": "local-one"})


@pytest.fixture
def lab(tmp_path, keys):
    factory = lambda: connect_database(tmp_path / "account.db")
    initialize_database(factory, SCHEMA)
    verifier = ClerkVerifier(AuthConfig(ISSUER, "sportabase", ("https://app.example.test",)), fetch_keys=lambda: {"keys": [keys[1]]})
    provider = Mock()
    def admin(request):
        if request.headers.get("x-admin-key") != "local-admin":
            raise HTTPException(403)
    app = FastAPI()
    app.add_middleware(AccountBoundary, connection_factory=factory, verifier=verifier)
    app.include_router(build_router(connection_factory=factory, require_admin=admin, provider_delete=provider))
    app.include_router(watches_router(connection_factory=factory))
    app.include_router(notifications_router(connection_factory=factory))
    @app.get("/intelligence/public")
    def public():
        return {"public": True}
    client = TestClient(app)
    def headers(subject="user_a", device=DEVICE, **claims):
        return {"Authorization": "Bearer " + token(keys, subject, **claims), "X-Sportabase-Device-ID": device}
    def bootstrap(subject="user_a", device=DEVICE, legacy=None):
        body = {"platform": "web", "name": "Test browser"}
        if legacy: body["legacy_client_id"] = legacy
        return client.post("/account/bootstrap", headers=headers(subject, device), json=body)
    return client, factory, headers, bootstrap, provider


@pytest.mark.parametrize("change", [dict(exp=1), dict(nbf=int(time.time())+3600), dict(iss="https://wrong.test"),
                                   dict(aud="wrong"), dict(azp="https://attacker.test"), dict(azp=""),
                                   dict(sub=""), dict(sid=""), dict(sid=1), dict(sid=[]), dict(sts="pending")])
def test_jwt_adversarial_claims(keys, change):
    verifier = ClerkVerifier(AuthConfig(ISSUER, "sportabase", ("https://app.example.test",)), fetch_keys=lambda: {"keys": [keys[1]]})
    with pytest.raises(HTTPException) as exc:
        verifier.verify(token(keys, **change))
    assert exc.value.status_code == 401
    assert "local-one" not in exc.value.detail


@pytest.mark.parametrize("bad", ["", "bad", "a.b.c", "x"*17000])
def test_malformed_jwt(keys, bad):
    verifier = ClerkVerifier(AuthConfig(ISSUER), fetch_keys=Mock(side_effect=AssertionError("No network")))
    with pytest.raises(HTTPException): verifier.verify(bad)


def test_none_hs256_signature_unknown_kid_rotation(keys):
    clock = [0]
    fetch = Mock(return_value={"keys": [keys[1]]})
    verifier = ClerkVerifier(AuthConfig(ISSUER, "sportabase"), fetch_keys=fetch, clock=lambda: clock[0])
    good = token(keys)
    assert verifier.verify(good)["sub"] == "user_a"
    claims = jwt.decode(good, options={"verify_signature": False})
    bad_tokens = [jwt.encode(claims, "", algorithm="none", headers={"kid": "local-one"}),
                  jwt.encode(claims, "secret", algorithm="HS256", headers={"kid": "local-one"}),
                  jwt.encode(claims, rsa.generate_private_key(public_exponent=65537, key_size=2048), algorithm="RS256", headers={"kid": "local-one"}),
                  jwt.encode(claims, keys[0], algorithm="RS256", headers={"kid": "rotated"})]
    for bad in bad_tokens:
        with pytest.raises(HTTPException): verifier.verify(bad)
    assert fetch.call_count == 1
    clock[0] = 31
    fetch.return_value = {"keys": [{**keys[1], "kid": "rotated"}]}
    assert verifier.verify(bad_tokens[-1])["sub"] == "user_a"
    clock[0] = 400
    fetch.side_effect = RuntimeError("private JWKS details")
    with pytest.raises(HTTPException): verifier.verify(bad_tokens[-1])


def test_native_token_without_azp_is_accepted_but_known_azp_is_allowlisted(keys):
    verifier = ClerkVerifier(AuthConfig(ISSUER, "sportabase", ("https://app.example.test",)),
                             fetch_keys=lambda: {"keys": [keys[1]]})
    assert verifier.verify(token(keys, azp=None))["sub"] == "user_a"
    with pytest.raises(HTTPException):
        verifier.verify(token(keys, azp="https://other.example.test"))


def test_production_auth_and_cors_configuration_fail_closed(monkeypatch):
    monkeypatch.setenv("SPORTABASE_ENV", "production")
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
    monkeypatch.delenv("SPORTABASE_ALLOWED_ORIGINS", raising=False)
    configured_verifier.cache_clear()
    with pytest.raises(RuntimeError, match="CLERK_AUTHORIZED_PARTIES"):
        configured_verifier()
    with pytest.raises(RuntimeError, match="SPORTABASE_ALLOWED_ORIGINS"):
        create_application()
    configured_verifier.cache_clear()


@pytest.mark.parametrize("path", ["/account", "/account/export", "/account/activity", "/account/devices", "/watchlists", "/watchlists/alerts", "/notifications/devices", "/notifications/web/config", "/analyze", "/analyze/video", "/resolve-content", "/content/browser-capture"])
def test_product_gate_missing_token_and_header_spoof(lab, path):
    client, _, _, _, _ = lab
    for headers in ({}, {"X-User-ID": "user_a", "X-Sportabase-Client-ID": "anything", "X-Sportabase-Device-ID": DEVICE}):
        response = client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == "*"
        assert response.headers["cache-control"] == "no-store"
    assert client.get("/intelligence/public").status_code == 200


def test_defaults_overrides_revision_and_device_isolation(lab):
    client, factory, headers, bootstrap, _ = lab
    state = bootstrap().json()
    assert state["follows_defaults"]
    bootstrap(device=OTHER_DEVICE)
    def update(scope, revision, patch, **extra):
        return client.patch("/account/preferences", headers=headers(), json=dict(version=store.VERSION, scope=scope, revision=revision, preferences=patch, **extra))
    assert update("account", 1, {"appearance": "dark"}).status_code == 200
    assert update("account", 1, {"appearance": "light"}).status_code == 409
    state = update("device", 1, {"appearance": "light"}, follows_defaults=False).json()
    assert state["effective"]["appearance"] == "light"
    assert client.get("/account", headers=headers(device=OTHER_DEVICE)).json()["effective"]["appearance"] == "dark"
    assert update("device", 2, {}, follows_defaults=True).json()["effective"]["appearance"] == "dark"
    assert update("device", 3, {"analytics_enabled": True}).status_code == 422
    bootstrap("user_b")
    assert client.get("/account", headers=headers("user_b")).json()["defaults"]["appearance"] == "system"
    assert client.get("/account", headers=headers("user_b", OTHER_DEVICE)).status_code == 409


@pytest.mark.parametrize("patch", [{"appearance": "red"}, {"panel_size": 400}, {"push_token": "sensitive"},
                                   {"timezone": "not/a/zone"}, {"quiet_hours_start": "25:00"},
                                   {"quiet_hours_enabled": True, "quiet_hours_start": "07:00", "quiet_hours_end": "07:00"},
                                   {"notifications_enabled": "false"}, {"language": "unsupported"}])
def test_invalid_preferences_rejected(lab, patch):
    client, _, headers, bootstrap, _ = lab
    bootstrap()
    response = client.patch("/account/preferences", headers=headers(), json={"version": store.VERSION, "scope": "account", "revision": 1, "preferences": patch})
    assert response.status_code == 422


@pytest.mark.parametrize("platform", ["web", "mobile", "extension"])
def test_link_is_idempotent_preserves_private_data_and_cannot_be_stolen(lab, platform):
    client, factory, headers, bootstrap, _ = lab
    legacy = f"legacy-installation-capability-{platform}-1234"
    with store.transaction(factory) as conn:
        conn.execute("INSERT INTO product_watchlist_items(id,client_key,target_kind,target_id,created_at) VALUES(?,?,'media','media-1','2026-01-01')", (f"watch-{platform}", store.client_key(legacy)))
    body = {"platform": platform, "name": "Shared device", "legacy_client_id": legacy}
    first = client.post("/account/bootstrap", headers=headers(), json=body)
    assert first.status_code == 200
    assert first.json()["legacy_migration"]["status"] == "claimed"
    assert client.post("/account/bootstrap", headers=headers(), json=body).json()["legacy_migration"]["status"] == "already_claimed_by_account"
    switched = client.post("/account/bootstrap", headers=headers("user_b"), json=body)
    assert switched.status_code == 200
    assert switched.json()["legacy_migration"]["status"] == "already_claimed_elsewhere"
    assert client.get("/watchlists", headers=headers("user_b")).json()["items"] == []
    assert client.get("/account/activity", headers=headers("user_b")).json()["items"] == []
    assert client.post("/account/bootstrap", headers=headers("user_b"), json=body).status_code == 200
    with store.transaction(factory) as conn:
        link = conn.execute("SELECT account_id FROM product_legacy_links WHERE legacy_key=?", (store.client_key(legacy),)).fetchone()
        assert link["account_id"] == first.json()["account"]["id"]
        assert conn.execute("SELECT client_key FROM product_watchlist_items WHERE id=?", (f"watch-{platform}",)).fetchone()[0] == store.owner_key(first.json()["account"]["id"])
    returned = client.post("/account/bootstrap", headers=headers(), json=body)
    assert returned.status_code == 200
    assert len(client.get("/watchlists", headers=headers()).json()["items"]) == 1


def test_activity_pagination_privacy_export_clear_and_cross_account(lab):
    client, factory, headers, bootstrap, _ = lab
    a = bootstrap().json()["account"]["id"]
    bootstrap("user_b")
    for kind in ("article", "video", "article"):
        store.record_analysis(factory, a, DEVICE, kind, "Safe display title", "https://example.com/story?token=secret#private")
    result = client.get("/account/activity?limit=2", headers=headers()).json()
    assert len(result["items"]) == 2 and result["next"]
    page2 = client.get("/account/activity", params=result["next"], headers=headers()).json()
    assert len(page2["items"]) == 1
    assert len(client.get("/account/activity?kind=video", headers=headers()).json()["items"]) == 1
    assert client.get("/account/activity?q=%25", headers=headers()).json()["items"] == []
    assert client.get("/account/activity", headers=headers("user_b")).json()["items"] == []
    exported = client.get("/account/export", headers=headers())
    assert "secret" not in exported.text and "subject_hash" not in exported.text
    assert client.request("DELETE", "/account/activity", headers=headers("user_b"), json={"confirmation": "CLEAR MY ACTIVITY"}).status_code == 204
    assert len(client.get("/account/activity", headers=headers()).json()["items"]) == 3
    assert client.request("DELETE", "/account/activity", headers=headers(), json={"confirmation": "CLEAR MY ACTIVITY"}).status_code == 204
    assert client.get("/account/activity", headers=headers()).json()["items"] == []


def test_export_includes_only_sanitized_account_owned_user_history(lab):
    client, factory, headers, bootstrap, _ = lab
    a = bootstrap().json()["account"]["id"]
    b = bootstrap("user_b").json()["account"]["id"]
    with store.transaction(factory) as conn:
        for media_id, url in (("media-a", "https://example.com/private?token=secret"),
                              ("media-b", "https://example.com/other?private=yes")):
            conn.execute("""INSERT INTO media_items(id,canonical_url,mode,title,latest_content_hash,first_seen_at,last_seen_at)
                         VALUES(?,?,'article','Private body must not export','hash','now','now')""", (media_id, url))
        conn.execute("INSERT INTO user_history VALUES(?,?,?,?,?,NULL)", (store.owner_key(a), "media-a", "2026-01-01", "2026-01-02", 3))
        conn.execute("INSERT INTO user_history VALUES(?,?,?,?,?,NULL)", (store.owner_key(b), "media-b", "2026-02-01", "2026-02-02", 7))
    exported = client.get("/account/export", headers=headers()).json()
    assert exported["user_history"] == [{"media_item_id": "media-a", "first_analyzed_at": "2026-01-01",
                                          "last_analyzed_at": "2026-01-02", "analysis_count": 3}]
    serialized = json.dumps(exported)
    assert "secret" not in serialized and "private=yes" not in serialized and "Private body" not in serialized


@pytest.mark.parametrize("zone,start,end,at,expected", [
    ("UTC", "22:00", "07:00", "2026-09-05T23:30:00+00:00", "2026-09-06T07:00:00+00:00"),
    ("Asia/Kolkata", "22:00", "07:00", "2026-09-05T18:00:00+00:00", "2026-09-06T01:30:00+00:00"),
    ("America/New_York", "22:00", "02:30", "2026-03-08T06:45:00+00:00", "2026-03-08T07:00:00+00:00"),
    ("America/New_York", "22:00", "02:30", "2026-11-01T05:45:00+00:00", "2026-11-01T07:30:00+00:00"),
    ("UTC", "09:00", "17:00", "2026-09-05T12:00:00+00:00", "2026-09-05T17:00:00+00:00"),
])
def test_quiet_hours_timezone_dst(zone, start, end, at, expected):
    prefs = Preferences(quiet_hours_enabled=True, timezone=zone, quiet_hours_start=start, quiet_hours_end=end).model_dump()
    epoch = lambda value: int(datetime.fromisoformat(value).timestamp())
    assert delivery_time(prefs, "entity", epoch(at)) == epoch(expected)
    assert delivery_time({**prefs, "entity_alerts": False}, "entity", epoch(at)) is None
    assert delivery_time({**prefs, "notifications_enabled": False}, "entity", epoch(at)) is None


def test_deletion_recent_intent_private_cleanup_canonical_preserved_and_provider_failure(lab):
    client, factory, headers, bootstrap, provider = lab
    a = bootstrap().json()["account"]["id"]
    b = bootstrap("user_b").json()["account"]["id"]
    with store.transaction(factory) as conn:
        conn.execute("INSERT INTO media_items(id,canonical_url,mode,title,latest_content_hash,first_seen_at,last_seen_at) VALUES('canonical','https://example.com/','article','Title','hash','now','now')")
    body = {"confirmation": "DELETE MY ACCOUNT"}
    assert client.request("DELETE", "/account", headers=headers(fva=[6, -1]), json=body).status_code == 403
    provider.side_effect = HTTPException(503, "Pending")
    assert client.request("DELETE", "/account", headers=headers(), json=body).status_code == 503
    assert client.get("/account/export", headers=headers()).status_code == 403
    assert client.get("/account", headers=headers("user_b")).status_code == 200
    provider.side_effect = None
    assert client.request("DELETE", "/account", headers=headers(), json=body).status_code == 204
    assert bootstrap().status_code == 403  # old unexpired JWT cannot recreate account
    with store.transaction(factory) as conn:
        assert conn.execute("SELECT COUNT(*) FROM media_items WHERE id='canonical'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM product_installations WHERE account_id=?", (a,)).fetchone()[0] == 0
        assert conn.execute("SELECT status FROM product_accounts WHERE id=?", (b,)).fetchone()[0] == "active"
        tombstone = dict(conn.execute("SELECT * FROM product_accounts WHERE id=?", (a,)).fetchone())
        assert tombstone["status"] == "deleted" and tombstone["defaults_json"] == "{}"
        assert tombstone["revision"] == tombstone["created_at"] == tombstone["last_seen_at"] == 0
        assert tombstone["first_analysis_at"] is None and len(tombstone["subject_hash"]) == 64
    provider.assert_called_with("user_a")


def test_analytics_opt_in_narrow_metadata_admin_only(lab):
    client, factory, headers, bootstrap, _ = lab
    bootstrap()
    client.post("/account/events", headers=headers(), json={"event": "settings_opened"})
    with store.transaction(factory) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_analytics").fetchone()[0] == 0
    assert client.post("/account/events", headers=headers(), json={"event": "settings_opened", "token": "secret"}).status_code == 422
    assert client.get("/admin/product-analytics").status_code == 403
    assert client.get("/admin/product-analytics", headers={"x-admin-key": "local-admin"}).json()["registered_accounts"] == 1
    client.patch("/account/preferences", headers=headers(), json={"version": store.VERSION, "scope": "account", "revision": 1, "preferences": {"analytics_enabled": True}})
    client.post("/account/events", headers=headers(), json={"event": "settings_opened"})
    data = client.get("/admin/product-analytics", headers={"x-admin-key": "local-admin"}).json()
    assert data["events_90d"]["settings_opened"] == 1 and data["events_90d"]["account_first_seen"] == 1
    assert data["dau"] == 1 and data["returning_active_accounts_30d"] == 0


def test_anonymous_landing_event_is_narrow_and_has_no_identity(lab):
    client, factory, _, _, _ = lab
    assert client.post("/product-events/landing", json={"platform": "web"}).status_code == 204
    assert client.post("/product-events/landing", json={"platform": "web", "referrer": "private"}).status_code == 422
    with store.transaction(factory) as conn:
        row = conn.execute("SELECT account_id,event,platform FROM product_analytics").fetchone()
        assert dict(row) == {"account_id": None, "event": "landing_visit", "platform": "web"}


def test_watch_and_notification_events_and_registration_ownership(lab):
    client, factory, headers, bootstrap, _ = lab
    bootstrap()
    opted_in = client.patch("/account/preferences", headers=headers(), json={
        "version": store.VERSION, "scope": "account", "revision": 1,
        "preferences": {"analytics_enabled": True},
    })
    assert opted_in.status_code == 200
    with store.transaction(factory) as conn:
        conn.execute("""INSERT INTO media_items(id,canonical_url,mode,title,latest_content_hash,first_seen_at,last_seen_at)
          VALUES('watched-media','https://example.com/watch','article','Title','hash','now','now')""")
    watch = client.post("/watchlists", headers=headers(), json={"target_kind": "media", "target_id": "watched-media"})
    assert watch.status_code == 200 and watch.json()["created"]
    assert client.post("/watchlists", headers=headers(), json={"target_kind": "media", "target_id": "watched-media"}).json()["created"] is False

    token_value = "ExpoPushToken[account-ownership-test]"
    registered = client.post("/notifications/devices", headers=headers(), json={"push_token": token_value, "platform": "ios"})
    assert registered.status_code == 200
    registration_id = registered.json()["device"]["id"]
    bootstrap("user_b")
    assert client.post("/notifications/devices", headers=headers("user_b"), json={"push_token": token_value, "platform": "ios"}).status_code == 422
    assert client.delete(f"/notifications/devices/{registration_id}", headers=headers("user_b")).status_code == 404
    assert client.delete(f"/notifications/devices/{registration_id}", headers=headers()).status_code == 204
    with store.transaction(factory) as conn:
        events = [row[0] for row in conn.execute("SELECT event FROM product_analytics ORDER BY event")]
        assert events.count("watch_created") == 1
        assert "notification_enabled" in events and "notification_disabled" in events
        assert conn.execute("SELECT COUNT(*) FROM product_notification_bindings WHERE registration_id=?", (registration_id,)).fetchone()[0] == 0


def test_optional_analytics_failures_do_not_break_watch_or_notification(monkeypatch, lab):
    client, factory, headers, bootstrap, _ = lab
    bootstrap()
    with store.transaction(factory) as conn:
        conn.execute("""INSERT INTO media_items(id,canonical_url,mode,title,latest_content_hash,first_seen_at,last_seen_at)
          VALUES('analytics-watch','https://example.com/watch','article','Title','hash','now','now')""")
    monkeypatch.setattr(store, "record_event", Mock(side_effect=RuntimeError("analytics db locked")))
    watch = client.post("/watchlists", headers=headers(), json={"target_kind": "media", "target_id": "analytics-watch"})
    assert watch.status_code == 200 and watch.json()["created"]
    registered = client.post("/notifications/devices", headers=headers(),
                             json={"push_token": "ExpoPushToken[analytics-failure-test]", "platform": "ios"})
    assert registered.status_code == 200
    with store.transaction(factory) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_notification_bindings").fetchone()[0] == 1


def test_notification_binding_failure_compensates_registration(monkeypatch, lab):
    client, factory, headers, bootstrap, _ = lab
    bootstrap()
    monkeypatch.setattr(notification_policy, "bind_registration", Mock(side_effect=RuntimeError("binding db locked")))
    response = client.post("/notifications/devices", headers=headers(),
                           json={"push_token": "ExpoPushToken[binding-failure-test]", "platform": "ios"})
    assert response.status_code == 503
    with store.transaction(factory) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_notification_devices").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM product_notification_bindings").fetchone()[0] == 0


def test_current_device_sign_out_revokes_only_its_push_and_allows_account_switch(lab):
    client, factory, headers, bootstrap, _ = lab
    a = bootstrap().json()["account"]["id"]
    bootstrap(device=OTHER_DEVICE)
    current_token = "ExpoPushToken[current-shared-device]"
    other_token = "ExpoPushToken[other-account-device]"
    current = client.post("/notifications/devices", headers=headers(), json={"push_token": current_token, "platform": "ios"}).json()
    other = client.post("/notifications/devices", headers=headers(device=OTHER_DEVICE), json={"push_token": other_token, "platform": "ios"}).json()
    with store.transaction(factory) as conn:
        conn.execute("INSERT INTO product_watchlist_items(id,client_key,target_kind,target_id,created_at) VALUES('a-watch',?,'media','m','now')", (store.owner_key(a),))
        conn.execute("""INSERT INTO product_web_push_subscriptions(id,client_key,subscription_hash,endpoint,p256dh,auth_secret,created_at,updated_at)
                     VALUES('web-current',?,'hash-current','https://push.example/current','key','auth','now','now')""", (store.owner_key(a),))
        conn.execute("""INSERT INTO product_web_push_subscriptions(id,client_key,subscription_hash,endpoint,p256dh,auth_secret,created_at,updated_at)
                     VALUES('web-other',?,'hash-other','https://push.example/other','key','auth','now','now')""", (store.owner_key(a),))
        conn.execute("INSERT INTO product_notification_bindings VALUES('web','web-current',?,?)", (a, DEVICE))
        conn.execute("INSERT INTO product_notification_bindings VALUES('web','web-other',?,?)", (a, OTHER_DEVICE))
    signed_out = client.post("/account/device/sign-out", headers=headers())
    assert signed_out.status_code == 200 and signed_out.json()["revoked"] == {"expo": 1, "web": 1}
    with store.transaction(factory) as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_notification_devices WHERE id=?", (current["device"]["id"],)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM product_notification_devices WHERE id=?", (other["device"]["id"],)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM product_web_push_subscriptions WHERE id='web-current'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM product_web_push_subscriptions WHERE id='web-other'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM product_watchlist_items WHERE client_key=?", (store.owner_key(a),)).fetchone()[0] == 1
    bootstrap("user_b")
    b_registration = client.post("/notifications/devices", headers=headers("user_b"), json={"push_token": current_token, "platform": "ios"})
    assert b_registration.status_code == 200
    assert client.get("/watchlists/alerts", headers=headers("user_b")).json()["items"] == []


def test_completed_analysis_survives_activity_database_failure():
    provider_calls = []
    def analyze(req, request):
        provider_calls.append(req.url)
        return AnalyzeResponse(url=req.url, title=req.title, tldr=["Summary"], merit_score=60, badge="Developing")
    router = product_api.build_router(
        health_handler=lambda: {"ok": True}, ingest_handler=lambda: {}, stories_handler=lambda **_: [],
        resolve_content_handler=lambda req: None, browser_capture_handler=lambda req: None,
        analyze_video_handler=lambda req, request: None, analyze_handler=analyze,
        operational_event_recorder=None, connection_factory=lambda: (_ for _ in ()).throw(RuntimeError("activity db locked")),
    )
    app = FastAPI()
    @app.middleware("http")
    async def account_state(request, call_next):
        request.state.account = {"id": "acct_test"}; request.state.device_id = DEVICE
        return await call_next(request)
    app.include_router(router)
    response = TestClient(app).post("/analyze", json={"title": "A complete analysis", "url": "https://example.com/story",
                                                        "text": "Enough article text for a completed provider analysis response to pass validation."})
    assert response.status_code == 200
    assert response.json()["merit_score"] == 60
    assert provider_calls == ["https://example.com/story"]


@pytest.mark.parametrize("provider", ["expo", "web"])
def test_delivery_policy_keeps_alerts_and_postpones_without_attempt(lab, provider):
    from app.accounts.notification_policy import eligible_at, filter_claims
    client, factory, headers, bootstrap, _ = lab
    account = bootstrap().json()["account"]["id"]
    owner = store.owner_key(account)
    epoch = int(datetime(2026, 9, 5, 23, tzinfo=timezone.utc).timestamp())
    with store.transaction(factory) as conn:
        conn.execute("UPDATE product_accounts SET defaults_json=? WHERE id=?", (json.dumps(Preferences(quiet_hours_enabled=True).model_dump()), account))
        conn.execute("INSERT INTO product_watchlist_items(id,client_key,target_kind,target_id,created_at) VALUES('w',?,'entity','e','now')", (owner,))
        conn.execute("INSERT INTO product_alert_events(id,client_key,watch_id,target_kind,target_id,source_event_key,event_type,summary,occurred_at,detected_at) VALUES('a',?,'w','entity','e','event','change','Summary','now','now')", (owner,))
        conn.execute("INSERT INTO product_notification_bindings VALUES(?,'reg',?,?)", (provider, account, DEVICE))
        if provider == "expo":
            conn.execute("INSERT INTO product_notification_devices(id,client_key,token_hash,push_token,platform,created_at,updated_at) VALUES('reg',?,'hash','token','ios','now','now')", (owner,))
            table, column = "product_notification_deliveries", "device_id"
        else:
            conn.execute("INSERT INTO product_web_push_subscriptions(id,client_key,subscription_hash,endpoint,p256dh,auth_secret,created_at,updated_at) VALUES('reg',?,'hash','endpoint','key','auth','now','now')", (owner,))
            table, column = "product_web_push_deliveries", "subscription_id"
        conn.execute(f"INSERT INTO {table}(id,client_key,{column},alert_id,created_at,updated_at) VALUES('d',?,'reg','a','now','now')", (owner,))
        assert eligible_at(conn, owner, provider, "reg", "a", epoch) == epoch+8*3600
        assert filter_claims(conn, ["d"], provider, epoch) == []
        row = conn.execute(f"SELECT * FROM {table}").fetchone()
        assert row["attempts"] == 0 and row["status"] == "pending" and row["available_at_epoch"] == epoch+8*3600
        conn.execute("UPDATE product_accounts SET defaults_json=? WHERE id=?", (json.dumps({"entity_alerts": False}), account))
        assert filter_claims(conn, ["d"], provider, epoch) == []
        assert conn.execute("SELECT COUNT(*) FROM product_alert_events").fetchone()[0] == 1
        assert conn.execute(f"SELECT status FROM {table}").fetchone()[0] == "cancelled"
