from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.notifications import web_push
from app.notifications.runtime import register_device, run_notification_cycle
from app.routes.notifications_product import build_router
from app.watchlists.runtime import client_key, create_watch, reconcile


T0 = "2026-09-04T10:00:00+00:00"
T1 = "2026-09-04T10:05:00+00:00"
T2 = "2026-09-04T10:10:00+00:00"
P256DH = base64.urlsafe_b64encode(bytes.fromhex(
    "04"
    "6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"
    "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
)).decode().rstrip("=")
AUTH = base64.urlsafe_b64encode(b"a" * 16).decode().rstrip("=")
ENDPOINT = "https://push.example.test/subscription/one"
PUBLIC_RESOLVER = lambda host, port, **kwargs: [
    (2, 1, 6, "", ("8.8.8.8", port))
]
VAPID_ENV = {
    web_push.VAPID_PUBLIC_KEY_ENV: P256DH,
    web_push.VAPID_PRIVATE_KEY_ENV: "private-key-test-value",
    web_push.VAPID_SUBJECT_ENV: "mailto:push@example.test",
}


def _env(values=VAPID_ENV):
    return lambda name, default="": values.get(name, default)


def _factory(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "web-push.db"

    def factory():
        return connect_database(path)

    initialize_database(factory, SCHEMA)
    conn = factory()
    try:
        conn.execute("""INSERT INTO media_items(id,canonical_url,mode,title,latest_content_hash,
            first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?)""",
            ("media-1", "https://example.test/story", "article", "Example", "hash-1", T0, T0))
        conn.commit()
    finally:
        conn.close()
    return factory


def _snapshot(factory, analyzed_at, content_hash):
    conn = factory()
    try:
        conn.execute("""INSERT INTO analysis_snapshots(media_item_id,analyzed_at,mode,
            analysis_version,scoring_version,content_hash,context_hash,response_json)
            VALUES(?,?,?,?,?,?,?,?)""",
            ("media-1", analyzed_at, "article", "analysis-v1", "score-v1",
             content_hash, "context-1", "{}"))
        conn.commit()
    finally:
        conn.close()


def _register(factory, owner=None, endpoint=ENDPOINT):
    return web_push.register_subscription(
        owner_key=owner or client_key("client-a"), endpoint=endpoint,
        p256dh=P256DH, auth=AUTH, connection_factory=factory,
        endpoint_resolver=PUBLIC_RESOLVER,
    )


def _future_delivery(factory):
    owner = client_key("client-a")
    create_watch(owner_key=owner, target_kind="media", target_id="media-1", connection_factory=factory)
    _register(factory, owner)
    _snapshot(factory, T1, "future")
    assert reconcile(owner_key=owner, connection_factory=factory)["new_alerts"] == 1
    assert web_push.materialize_pending_deliveries(connection_factory=factory,
                                                   clock=lambda: 2_000_000_000)["web_deliveries_created"] == 1
    return owner


def _delivery(factory):
    conn = factory()
    try:
        return dict(conn.execute("SELECT * FROM product_web_push_deliveries").fetchone())
    finally:
        conn.close()


class ProviderError(RuntimeError):
    def __init__(self, status_code=0):
        super().__init__(f"provider {status_code or 'network'}")
        self.response = type("Response", (), {"status_code": status_code, "text": "safe provider error"})()


def test_web_routes_require_identity_and_hide_credentials(tmp_path, monkeypatch):
    factory = _factory(tmp_path)
    app = FastAPI()
    app.include_router(build_router(connection_factory=factory))
    client = TestClient(app)
    monkeypatch.setenv(web_push.VAPID_PUBLIC_KEY_ENV, P256DH)
    monkeypatch.setenv(web_push.VAPID_PRIVATE_KEY_ENV, "never-return-this")
    monkeypatch.setenv(web_push.VAPID_SUBJECT_ENV, "mailto:test@example.test")
    monkeypatch.setattr(web_push.socket, "getaddrinfo", PUBLIC_RESOLVER)

    assert client.get("/notifications/web/subscriptions").status_code == 401
    config = client.get("/notifications/web/config").json()
    assert config == {"version": "web-push-v1", "available": True, "vapid_public_key": P256DH}
    assert "private" not in str(config).lower()
    created = client.post("/notifications/web/subscriptions",
        headers={"x-sportabase-client-id": "client-a"},
        json={"endpoint": ENDPOINT, "expirationTime": None,
              "keys": {"p256dh": P256DH, "auth": AUTH}})
    assert created.status_code == 200
    forbidden = {"endpoint", "p256dh", "auth", "auth_secret", "client_key"}
    assert forbidden.isdisjoint(str(created.json()).lower().replace("'", '"').split('"'))
    listed = client.get("/notifications/web/subscriptions",
                        headers={"x-sportabase-client-id": "client-a"})
    assert listed.status_code == 200 and listed.json()["count"] == 1
    assert not any(secret in listed.text for secret in (ENDPOINT, P256DH, AUTH))


def test_registration_baseline_idempotency_and_cross_client_delete(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(owner_key=owner, target_kind="media", target_id="media-1", connection_factory=factory)
    _snapshot(factory, T1, "old")
    assert reconcile(owner_key=owner, connection_factory=factory)["new_alerts"] == 1
    first = _register(factory, owner)
    second = _register(factory, owner)
    assert first["registered"] is True
    assert second["registered"] is False
    assert first["subscription"]["id"] == second["subscription"]["id"]
    assert web_push.materialize_pending_deliveries(connection_factory=factory)["web_deliveries_created"] == 0
    with pytest.raises(web_push.WebPushNotFoundError):
        web_push.unregister_subscription(owner_key=client_key("client-b"),
            subscription_id=first["subscription"]["id"], connection_factory=factory)


@pytest.mark.parametrize("endpoint,p256dh,auth", [
    ("http://push.example.test/x", P256DH, AUTH),
    ("https://user:pass@push.example.test/x", P256DH, AUTH),
    ("https://127.0.0.1/push", P256DH, AUTH),
    (ENDPOINT, "bad", AUTH),
    (ENDPOINT, P256DH, "bad"),
])
def test_malformed_subscriptions_rejected(tmp_path, endpoint, p256dh, auth):
    with pytest.raises(ValueError):
        web_push.register_subscription(owner_key=client_key("client-a"), endpoint=endpoint,
            p256dh=p256dh, auth=auth, connection_factory=_factory(tmp_path),
            endpoint_resolver=PUBLIC_RESOLVER)


def test_materialization_is_once_and_payload_is_safe(tmp_path):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    assert web_push.materialize_pending_deliveries(connection_factory=factory,
                                                   clock=lambda: 2_000_000_001)["web_deliveries_created"] == 0
    row = _delivery(factory)
    conn = factory()
    try:
        alert = dict(conn.execute("SELECT * FROM product_alert_events WHERE id=?", (row["alert_id"],)).fetchone())
    finally:
        conn.close()
    payload = web_push.payload_for_delivery(alert)
    assert payload["target_kind"] == "media"
    assert "client_key" not in payload
    assert len(payload["summary"]) <= 240


def test_successful_delivery_marks_accepted(tmp_path):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    calls = []
    result = web_push.dispatch_pending_deliveries(connection_factory=factory,
        sender=lambda **kwargs: calls.append(kwargs), env_getter=_env(), clock=lambda: 2_000_000_000)
    assert result["web_accepted"] == 1 and len(calls) == 1
    assert _delivery(factory)["status"] == "accepted"
    assert ENDPOINT in str(calls[0]["subscription_info"])
    assert "client_key" not in calls[0]["data"]


@pytest.mark.parametrize("status", [404, 410])
def test_invalid_subscription_is_disabled_and_credentials_cleared(tmp_path, status):
    factory = _factory(tmp_path)
    owner = _future_delivery(factory)
    def sender(**kwargs): raise ProviderError(status)
    result = web_push.dispatch_pending_deliveries(connection_factory=factory,
        sender=sender, env_getter=_env(), clock=lambda: 2_000_000_000)
    assert result["web_invalid_subscriptions"] == 1
    assert web_push.list_subscriptions(owner_key=owner, connection_factory=factory)["count"] == 0
    conn = factory()
    try:
        row = conn.execute("SELECT * FROM product_web_push_subscriptions").fetchone()
        assert row["endpoint"] == row["p256dh"] == row["auth_secret"] == ""
    finally:
        conn.close()


def test_invalid_current_delivery_fails_and_other_queued_delivery_is_cancelled(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(owner_key=owner, target_kind="media", target_id="media-1", connection_factory=factory)
    _register(factory, owner)
    _snapshot(factory, T1, "future-one")
    assert reconcile(owner_key=owner, connection_factory=factory)["new_alerts"] == 1
    _snapshot(factory, T2, "future-two")
    assert reconcile(owner_key=owner, connection_factory=factory)["new_alerts"] == 1
    assert web_push.materialize_pending_deliveries(connection_factory=factory,
        clock=lambda: 2_000_000_000)["web_deliveries_created"] == 2
    calls = []
    def gone(**kwargs):
        calls.append(kwargs)
        raise ProviderError(410)
    result = web_push.dispatch_pending_deliveries(connection_factory=factory,
        sender=gone, env_getter=_env(), clock=lambda: 2_000_000_000)
    assert result["web_failed"] == 1
    assert result["web_retried"] == 0
    assert len(calls) == 1
    conn = factory()
    try:
        rows = conn.execute("SELECT status,error_type FROM product_web_push_deliveries ORDER BY created_at,id").fetchall()
        assert rows[0]["status"] == "failed"
        assert rows[0]["error_type"] == "provider_http_410"
        assert rows[1]["status"] == "cancelled"
        assert rows[1]["error_type"] == "subscription_invalid"
    finally:
        conn.close()


@pytest.mark.parametrize("endpoint", [
    "https://localhost/push",
    "https://127.0.0.1/push",
    "https://10.0.0.1/push",
    "https://[::1]/push",
    "https://[fe80::1]/push",
])
def test_local_and_literal_private_endpoints_are_rejected(tmp_path, endpoint):
    with pytest.raises(ValueError, match="public HTTPS URL"):
        web_push.register_subscription(owner_key=client_key("client-a"), endpoint=endpoint,
            p256dh=P256DH, auth=AUTH, connection_factory=_factory(tmp_path),
            endpoint_resolver=PUBLIC_RESOLVER)


def test_hostname_resolving_to_non_global_address_is_rejected(tmp_path):
    private_resolver = lambda host, port, **kwargs: [
        (2, 1, 6, "", ("192.168.1.10", port)),
        (10, 1, 6, "", ("fe80::1", port, 0, 0)),
    ]
    with pytest.raises(ValueError, match="public HTTPS URL"):
        web_push.register_subscription(owner_key=client_key("client-a"), endpoint=ENDPOINT,
            p256dh=P256DH, auth=AUTH, connection_factory=_factory(tmp_path),
            endpoint_resolver=private_resolver)


def test_public_endpoint_passes_and_safe_session_never_follows_redirect(monkeypatch):
    calls = []
    response = type("Response", (), {
        "status_code": 302, "text": "", "headers": {"Location": "http://127.0.0.1/admin"}
    })()
    def fake_request(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response
    monkeypatch.setattr(web_push.requests.Session, "request", fake_request)
    session = web_push.SafeWebPushSession(resolver=PUBLIC_RESOLVER)
    result = session.post(ENDPOINT, data=b"encrypted")
    assert result is response
    assert len(calls) == 1
    assert calls[0][2]["allow_redirects"] is False


def test_safe_session_revalidates_dns_on_every_dispatch(monkeypatch):
    resolutions = iter(["8.8.8.8", "127.0.0.1"])
    resolver = lambda host, port, **kwargs: [(2, 1, 6, "", (next(resolutions), port))]
    monkeypatch.setattr(web_push.requests.Session, "request",
                        lambda self, method, url, **kwargs: object())
    session = web_push.SafeWebPushSession(resolver=resolver)
    session.post(ENDPOINT)
    with pytest.raises(web_push.UnsafeWebPushEndpointError):
        session.post(ENDPOINT)


@pytest.mark.parametrize("endpoint,expected", [
    ("https://wns2-bl2p.notify.windows.com/w/token", {"X-WNS-Type": "wns/raw", "Content-Type": "application/octet-stream"}),
    ("https://fcm.googleapis.com/wp/token", {}),
    ("https://updates.push.services.mozilla.com/wpush/token", {}),
    ("https://web.push.apple.com/token", {}),
    ("https://arbitrary.example/push", {}),
])
def test_wns_headers_are_destination_specific(endpoint, expected):
    assert web_push._provider_headers(endpoint) == expected


@pytest.mark.parametrize("endpoint,has_wns_header", [
    ("https://edge.notify.windows.com/w/token", True),
    ("https://fcm.googleapis.com/wp/token", False),
])
def test_default_provider_boundary_passes_wns_headers_only_to_microsoft(
    monkeypatch, endpoint, has_wns_header
):
    calls = []
    monkeypatch.setattr("pywebpush.webpush", lambda **kwargs: calls.append(kwargs))
    web_push._default_sender(
        subscription_info={"endpoint": endpoint, "keys": {"p256dh": P256DH, "auth": AUTH}},
        data="{}", vapid_private_key="private", vapid_claims={"sub": "mailto:test@example.test"},
        timeout=10, headers=web_push._provider_headers(endpoint),
    )
    assert len(calls) == 1
    assert isinstance(calls[0]["requests_session"], web_push.SafeWebPushSession)
    assert ("X-WNS-Type" in calls[0]["headers"]) is has_wns_header


@pytest.mark.parametrize("p256dh,auth", [
    (base64.urlsafe_b64encode(b"x" * 65).decode().rstrip("="), AUTH),
    (base64.urlsafe_b64encode(b"\x04" + b"x" * 63).decode().rstrip("="), AUTH),
    (P256DH, base64.urlsafe_b64encode(b"short").decode().rstrip("=")),
    (P256DH, base64.urlsafe_b64encode(b"a" * 17).decode().rstrip("=")),
])
def test_push_key_material_requires_protocol_shapes(tmp_path, p256dh, auth):
    with pytest.raises(ValueError):
        web_push.register_subscription(owner_key=client_key("client-a"), endpoint=ENDPOINT,
            p256dh=p256dh, auth=auth, connection_factory=_factory(tmp_path),
            endpoint_resolver=PUBLIC_RESOLVER)


def test_invalid_vapid_public_key_is_not_advertised():
    values = {**VAPID_ENV, web_push.VAPID_PUBLIC_KEY_ENV: "not-a-p256-key"}
    assert web_push.web_push_config(env_getter=_env(values)) == {
        "version": "web-push-v1", "available": False, "vapid_public_key": ""
    }


@pytest.mark.parametrize("status", [0, 429, 500, 503])
def test_retryable_provider_failures_are_bounded(tmp_path, status):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    def sender(**kwargs): raise ProviderError(status)
    result = web_push.dispatch_pending_deliveries(connection_factory=factory,
        sender=sender, env_getter=_env(), clock=lambda: 2_000_000_000)
    assert result["web_retried"] == 1
    assert _delivery(factory)["status"] == "pending"


def test_permanent_4xx_fails_and_attempt_exhaustion_stops(tmp_path):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    def bad_request(**kwargs): raise ProviderError(400)
    result = web_push.dispatch_pending_deliveries(connection_factory=factory,
        sender=bad_request, env_getter=_env(), clock=lambda: 2_000_000_000)
    assert result["web_failed"] == 1 and _delivery(factory)["status"] == "failed"

    factory2 = _factory(tmp_path / "second")
    _future_delivery(factory2)
    conn = factory2()
    try:
        conn.execute("UPDATE product_web_push_deliveries SET attempts=4")
        conn.commit()
    finally:
        conn.close()
    def unavailable(**kwargs): raise ProviderError(503)
    exhausted = web_push.dispatch_pending_deliveries(connection_factory=factory2,
        sender=unavailable, env_getter=_env(), clock=lambda: 2_000_000_000)
    assert exhausted["web_failed"] == 1
    assert _delivery(factory2)["error_type"] == "attempts_exhausted"


def test_missing_vapid_does_not_break_expo(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(owner_key=owner, target_kind="media", target_id="media-1", connection_factory=factory)
    register_device(owner_key=owner, push_token="ExpoPushToken[webpushcompatibilitytest]",
                    platform="android", connection_factory=factory)
    _register(factory, owner)
    _snapshot(factory, T1, "new")
    calls = []
    class Accepted:
        status_code = 200
        text = ""
        def json(self): return {"data": [{"status": "ok", "id": "expo-ticket"}]}
    result = run_notification_cycle(connection_factory=factory,
        http_post=lambda *args, **kwargs: calls.append(kwargs) or Accepted(),
        env_getter=_env({}), clock=lambda: 2_000_000_000)
    assert result["accepted"] == 1 and len(calls) == 1
    assert result["web_configured"] == 0


def test_additive_migration_preserves_expo_rows(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    registered = register_device(owner_key=owner,
        push_token="ExpoPushToken[migrationpreservesdevice]", platform="ios",
        connection_factory=factory)
    conn = factory()
    try:
        conn.execute("DROP TABLE product_web_push_deliveries")
        conn.execute("DROP TABLE product_web_push_subscriptions")
        conn.commit()
    finally:
        conn.close()
    initialize_database(factory, SCHEMA)
    conn = factory()
    try:
        device = conn.execute("SELECT * FROM product_notification_devices WHERE id=?",
                              (registered["device"]["id"],)).fetchone()
        assert device is not None and device["provider"] == "expo"
        assert conn.execute("SELECT COUNT(*) FROM product_web_push_subscriptions").fetchone()[0] == 0
    finally:
        conn.close()


def test_watchable_kinds_remain_exactly_four():
    assert web_push.WATCHABLE_KINDS == {"entity", "story", "claim", "media"}
