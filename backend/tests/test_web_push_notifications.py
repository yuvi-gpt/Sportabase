from __future__ import annotations

import base64
import io
import ipaddress
import socket
import ssl
from unittest.mock import Mock

import pytest
from py_vapid import Vapid
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


def _dns_record(address, port=443):
    ipv6 = ipaddress.ip_address(address).version == 6
    return (socket.AF_INET6 if ipv6 else socket.AF_INET, socket.SOCK_STREAM,
            socket.IPPROTO_TCP, "", (address, port, 0, 0) if ipv6 else (address, port))


@pytest.fixture
def push_wire(monkeypatch):
    """Exercise real requests/urllib3 down to TCP connect and TLS wrap_socket.

    Only OS sockets and the TLS handshake are fake. urllib3 still constructs its
    SSLContext, loads normal CAs, and checks the supplied certificate hostname.
    """
    class Wire:
        addresses = ["8.8.8.8"]
        response = b"HTTP/1.1 201 Created\r\nContent-Length: 0\r\n\r\n"
        certificate = None
        connect_error = None
        tls_error = None

        def __init__(self):
            self.sockets = []
            self.tls = []
            self.matches = []
            self.dns = Mock(side_effect=lambda host, port, **kwargs: [
                _dns_record(address, port) for address in self.addresses
            ])

    wire = Wire()

    class FakeSocket:
        def __init__(self, family, socktype, proto):
            self.family, self.socktype, self.proto = family, socktype, proto
            self.destination = None
            self.sent = b""
            self.closed = False
            wire.sockets.append(self)

        def setsockopt(self, *args): pass
        def settimeout(self, value): self.timeout = value
        def gettimeout(self): return self.timeout
        def connect(self, destination):
            self.destination = destination
            if wire.connect_error:
                raise wire.connect_error
        def sendall(self, data): self.sent += bytes(data)
        def makefile(self, *args): return io.BytesIO(wire.response)
        def getpeercert(self):
            return wire.certificate or {"subjectAltName": (("DNS", self.server_hostname),)}
        def close(self): self.closed = True

    def wrap_socket(context, sock, *, server_hostname, **kwargs):
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.get_ca_certs()
        wire.tls.append(server_hostname)
        if wire.tls_error:
            raise wire.tls_error
        sock.server_hostname = server_hostname
        return sock

    from urllib3 import connection
    original_match = connection._match_hostname
    def match_hostname(cert, asserted_hostname, hostname_checks_common_name):
        wire.matches.append(asserted_hostname)
        return original_match(cert, asserted_hostname, hostname_checks_common_name)

    monkeypatch.setattr(socket, "socket", FakeSocket)
    monkeypatch.setattr(socket, "getaddrinfo", wire.dns)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap_socket)
    monkeypatch.setattr(connection, "_match_hostname", match_hostname)
    return wire


@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
@pytest.mark.parametrize("authority,identity,port", [
    ("push.example.test", "push.example.test", 443),
    ("push.example.test:443", "push.example.test", 443),
    ("push.example.test:8443", "push.example.test", 8443),
    ("püsh.example.test", "xn--psh-hoa.example.test", 443),
    ("push.example.test.", "push.example.test", 443),
])
def test_public_resolution_pins_socket_and_preserves_tls_and_http_identity(
    push_wire, address, authority, identity, port
):
    push_wire.addresses = [address]
    path = "/subscription/a%2Fb?token=a%2Bb&v=1&v=2"
    with web_push.SafeWebPushSession() as session:
        response = session.post("https://" + authority + path, data=b"encrypted", timeout=10,
                                headers={"Host": "attacker.example"})
    assert response.status_code == 201
    push_wire.dns.assert_called_once_with(identity, port, type=socket.SOCK_STREAM)
    sock, = push_wire.sockets
    ipv6 = ":" in address
    assert sock.family == (socket.AF_INET6 if ipv6 else socket.AF_INET)
    assert sock.destination == ((address, port, 0, 0) if ipv6 else (address, port))
    assert push_wire.tls == push_wire.matches == [identity]
    expected_host = authority.replace("püsh", "xn--psh-hoa")
    assert f"Host: {expected_host}\r\n".encode() in sock.sent
    assert sock.sent.startswith(f"POST {path} HTTP/1.1\r\n".encode())
    assert sock.sent.endswith(b"encrypted")
    assert sock.closed


@pytest.mark.parametrize("private", ["127.0.0.1", "169.254.169.254"])
def test_rebinding_cannot_change_socket_destination_and_next_attempt_revalidates(push_wire, private):
    push_wire.dns.side_effect = [[_dns_record("8.8.8.8")], [_dns_record(private)]]
    with web_push.SafeWebPushSession() as session:
        session.post(ENDPOINT)
        assert push_wire.dns.call_count == 1
        assert [sock.destination for sock in push_wire.sockets] == [("8.8.8.8", 443)]
        with pytest.raises(web_push.UnsafeWebPushEndpointError):
            session.post(ENDPOINT)
    assert push_wire.dns.call_count == 2
    assert len(push_wire.sockets) == 1


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.1.2.3", "172.16.0.1", "172.31.255.254", "192.168.1.1",
    "169.254.169.254", "0.0.0.0", "100.64.0.1", "192.0.2.1", "224.0.0.1", "240.0.0.1",
    "::1", "fe80::1", "fc00::1", "fd00::1", "::", "ff02::1", "2001:db8::1",
    "::ffff:127.0.0.1", "64:ff9b:1::a00:1", "64:ff9b::7f00:1", "2002:7f00:1::",
])
@pytest.mark.parametrize("mixed", [False, True])
def test_unsafe_dns_answer_rejects_entire_destination_before_connect(push_wire, address, mixed):
    push_wire.addresses = (["8.8.8.8"] if mixed else []) + [address]
    with web_push.SafeWebPushSession() as session:
        with pytest.raises(web_push.UnsafeWebPushEndpointError):
            session.post(ENDPOINT)
    assert not push_wire.sockets


@pytest.mark.parametrize("endpoint", [
    "https://localhost./push", "https://sub.localhost./push", "https://127.0.0.1/push",
    "https://10.0.0.1/push", "https://172.16.0.1/push", "https://192.168.0.1/push",
    "https://169.254.169.254/push", "https://[::1]/push", "https://[fc00::1]/push",
    "https://[fe80::1]/push", "https://[::]/push", "https://[ff02::1]/push",
    "https://[2606:4700:4700::1111%25eth0]/push", "https://push.example.test:0/push",
])
def test_unsafe_literal_and_localhost_endpoints_cannot_connect(push_wire, endpoint):
    with web_push.SafeWebPushSession() as session:
        with pytest.raises(web_push.UnsafeWebPushEndpointError):
            session.post(endpoint)
    assert not push_wire.sockets


@pytest.mark.parametrize("address", ["8.8.8.8", "2606:4700:4700::1111"])
def test_public_literal_needs_no_resolver_and_formats_ipv6_host(push_wire, address):
    authority = f"[{address}]:8443" if ":" in address else f"{address}:8443"
    push_wire.certificate = {"subjectAltName": (("IP Address", address),)}
    with web_push.SafeWebPushSession() as session:
        session.post(f"https://{authority}/push")
    push_wire.dns.assert_not_called()
    sock, = push_wire.sockets
    assert sock.destination[0:2] == (address, 8443)
    assert f"Host: {authority}\r\n".encode() in sock.sent
    assert push_wire.matches == [address]


def test_all_public_answers_choose_first_in_resolver_order(push_wire):
    push_wire.addresses = ["2606:4700:4700::1111", "8.8.8.8", "1.1.1.1"]
    with web_push.SafeWebPushSession() as session:
        session.post(ENDPOINT)
    assert [sock.destination for sock in push_wire.sockets] == [(push_wire.addresses[0], 443, 0, 0)]


@pytest.mark.parametrize("path", [
    "/a/../push/%7Etoken?key=%2B&key=%7E", "//push/token?key=one", "/push?", "/?key=one",
    "/push/%2ftoken?key=%2b&key=%7e",
])
def test_original_endpoint_path_and_query_survive_request_preparation(push_wire, path):
    with web_push.SafeWebPushSession() as session:
        session.post("https://push.example.test" + path)
    assert push_wire.sockets[0].sent.startswith(f"POST {path} HTTP/1.1\r\n".encode())


def test_prepared_request_cannot_bypass_pin_or_force_redirects(push_wire):
    request = web_push.requests.Request("POST", ENDPOINT).prepare()
    push_wire.response = b"HTTP/1.1 302 Redirect\r\nLocation: https://127.0.0.1/\r\nContent-Length: 0\r\n\r\n"
    with web_push.SafeWebPushSession() as session:
        response = session.send(request, allow_redirects=True)
    assert response.status_code == 302
    assert push_wire.dns.call_count == len(push_wire.sockets) == 1
    assert push_wire.sockets[0].destination == ("8.8.8.8", 443)


def test_registration_dns_outage_has_generic_validation_error(push_wire):
    push_wire.dns.side_effect = socket.gaierror("secret DNS detail")
    with pytest.raises(ValueError, match="public HTTPS URL"):
        web_push.validate_subscription(endpoint=ENDPOINT, p256dh=P256DH, auth=AUTH)
    assert not push_wire.sockets


@pytest.mark.parametrize("records", [[], None, [(2,)], [_dns_record("8.8.8.8", 80)],
    [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", 443))],
    [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443, 0, 1))],
])
def test_malformed_dns_records_fail_closed(push_wire, records):
    push_wire.dns.side_effect = None
    push_wire.dns.return_value = records
    with web_push.SafeWebPushSession() as session:
        with pytest.raises(web_push.UnsafeWebPushEndpointError):
            session.post(ENDPOINT)
    assert not push_wire.sockets


@pytest.mark.parametrize("no_proxy", ["", "*", "push.example.test"])
def test_environment_proxies_cannot_bypass_pinning(push_wire, monkeypatch, no_proxy):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(name, "http://127.0.0.1:9999")
    monkeypatch.setenv("NO_PROXY", no_proxy)
    with web_push.SafeWebPushSession() as session:
        assert session.trust_env is False
        session.post(ENDPOINT)
    assert [sock.destination for sock in push_wire.sockets] == [("8.8.8.8", 443)]
    assert push_wire.tls == ["push.example.test"]
    assert b"CONNECT " not in push_wire.sockets[0].sent


@pytest.mark.parametrize("kwargs", [
    {"proxies": {"https": "http://127.0.0.1:9999"}}, {"verify": False},
])
def test_explicit_proxy_or_disabled_tls_is_rejected(push_wire, kwargs):
    with web_push.SafeWebPushSession() as session:
        with pytest.raises(web_push.UnsafeWebPushEndpointError):
            session.post(ENDPOINT, **kwargs)
    assert not push_wire.sockets


@pytest.mark.parametrize("failure", ["hostname", "chain", "connect", "timeout", "dns"])
def test_transport_failure_has_no_unpinned_fallback_and_no_secret_details(push_wire, failure):
    if failure == "hostname":
        push_wire.certificate = {"subjectAltName": (("DNS", "attacker.example"),)}
    elif failure == "chain":
        push_wire.tls_error = ssl.SSLCertVerificationError("private certificate detail")
    elif failure == "connect":
        push_wire.connect_error = OSError("8.8.8.8 secret endpoint token")
    elif failure == "timeout":
        push_wire.connect_error = TimeoutError("8.8.8.8 secret endpoint token")
    else:
        push_wire.dns.side_effect = socket.gaierror("internal DNS detail")
    with web_push.SafeWebPushSession() as session:
        with pytest.raises(web_push.WebPushTransportError) as error:
            session.post(ENDPOINT, timeout=1)
    assert str(error.value) in {
        "Web Push transport failed.", "Web Push endpoint destination could not be resolved."
    }
    assert push_wire.dns.call_count == 1
    assert len(push_wire.sockets) == (0 if failure == "dns" else 1)
    assert not any(sock.sent for sock in push_wire.sockets)
    assert all(sock.closed for sock in push_wire.sockets)


def _real_provider_sender(**kwargs):
    vapid = Vapid()
    vapid.generate_keys()
    return web_push._default_sender(**{**kwargs, "vapid_private_key": vapid})


def test_reconciliation_and_materialization_remain_provider_free(tmp_path, monkeypatch, push_wire):
    forbidden = Mock(side_effect=AssertionError("Provider call during reconciliation"))
    monkeypatch.setattr("pywebpush.webpush", forbidden)
    monkeypatch.setattr(web_push.requests.Session, "request", forbidden)
    factory = _factory(tmp_path)
    _future_delivery(factory)
    assert _delivery(factory)["status"] == "pending"
    forbidden.assert_not_called()
    push_wire.dns.assert_not_called()
    assert not push_wire.sockets


@pytest.mark.parametrize("status", [301, 302, 307, 308])
@pytest.mark.parametrize("location", [
    "http://127.0.0.1/admin", "https://169.254.169.254/latest", "https://other.example.test/push",
])
def test_real_provider_redirect_is_failed_without_second_connection(tmp_path, push_wire, status, location):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    push_wire.response = (
        f"HTTP/1.1 {status} Redirect\r\nLocation: {location}\r\nContent-Length: 0\r\n\r\n"
    ).encode()
    result = web_push.dispatch_pending_deliveries(
        connection_factory=factory, sender=_real_provider_sender,
        env_getter=_env(), clock=lambda: 2_000_000_000,
    )
    assert result["web_failed"] == 1 and result["web_retried"] == 0
    assert _delivery(factory)["error_type"] == f"provider_http_{status}"
    assert push_wire.dns.call_count == len(push_wire.sockets) == 1
    assert push_wire.sockets[0].destination == ("8.8.8.8", 443)


@pytest.mark.parametrize("status,outcome", [
    (201, "web_accepted"), (404, "web_invalid_subscriptions"), (410, "web_invalid_subscriptions"),
    (429, "web_retried"), (500, "web_retried"), (503, "web_retried"), (400, "web_failed"),
])
def test_real_provider_preserves_delivery_outcomes(tmp_path, push_wire, status, outcome):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    push_wire.response = f"HTTP/1.1 {status} Provider\r\nContent-Length: 0\r\n\r\n".encode()
    result = web_push.dispatch_pending_deliveries(
        connection_factory=factory, sender=_real_provider_sender,
        env_getter=_env(), clock=lambda: 2_000_000_000,
    )
    assert result[outcome] == 1
    assert push_wire.dns.call_count == len(push_wire.sockets) == 1


@pytest.mark.parametrize("failure", ["unsafe", "dns", "connect"])
def test_real_transport_failure_invalidation_and_retry_semantics(tmp_path, push_wire, failure):
    factory = _factory(tmp_path)
    _future_delivery(factory)
    if failure == "unsafe":
        push_wire.addresses = ["8.8.8.8", "169.254.169.254"]
    elif failure == "dns":
        push_wire.dns.side_effect = socket.gaierror("secret DNS detail")
    else:
        push_wire.connect_error = OSError("secret socket detail")
    result = web_push.dispatch_pending_deliveries(
        connection_factory=factory, sender=_real_provider_sender,
        env_getter=_env(), clock=lambda: 2_000_000_000,
    )
    assert result["web_invalid_subscriptions" if failure == "unsafe" else "web_retried"] == 1
    assert _delivery(factory)["error_type"] == ("unsafe_endpoint" if failure == "unsafe" else "provider_transport")
    assert "secret" not in _delivery(factory)["error_detail"]
    assert len(push_wire.sockets) == (1 if failure == "connect" else 0)


@pytest.mark.parametrize("hostname,wns", [
    ("edge.notify.windows.com", True), ("fcm.googleapis.com", False),
    ("notify.windows.com.attacker.test", False), ("evilnotify.windows.com", False),
])
def test_real_pywebpush_wns_uses_same_pinned_transport(push_wire, hostname, wns):
    endpoint = f"https://{hostname}/w/token"
    _real_provider_sender(
        subscription_info={"endpoint": endpoint, "keys": {"p256dh": P256DH, "auth": AUTH}},
        data="{}", vapid_claims={"sub": "mailto:test@example.test"}, timeout=10,
        headers=web_push._provider_headers(endpoint),
    )
    sock, = push_wire.sockets
    assert sock.destination == ("8.8.8.8", 443)
    assert push_wire.tls == push_wire.matches == [hostname]
    assert f"Host: {hostname}\r\n".encode() in sock.sent
    assert (b"x-wns-type: wns/raw\r\n" in sock.sent.lower()) is wns
    if wns:
        assert b"content-type: application/octet-stream\r\n" in sock.sent.lower()


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
