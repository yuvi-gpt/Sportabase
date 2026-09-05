from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.asymmetric import ec
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError


VERSION = "web-push-v1"
VAPID_PUBLIC_KEY_ENV = "SPORTABASE_WEB_PUSH_VAPID_PUBLIC_KEY"
VAPID_PRIVATE_KEY_ENV = "SPORTABASE_WEB_PUSH_VAPID_PRIVATE_KEY"
VAPID_SUBJECT_ENV = "SPORTABASE_WEB_PUSH_VAPID_SUBJECT"
MAX_SUBSCRIPTIONS_PER_CLIENT = 10
MAX_LEDGER_SCAN_PER_SUBSCRIPTION = 200
MAX_DELIVERIES_PER_REQUEST = 50
MAX_DELIVERY_ATTEMPTS = 5
RETRY_BASE_SECONDS = 15
RETRY_CAP_SECONDS = 900
WATCHABLE_KINDS = frozenset({"entity", "story", "claim", "media"})


class WebPushNotFoundError(RuntimeError):
    pass


class WebPushLimitError(RuntimeError):
    pass


class UnsafeWebPushEndpointError(RuntimeError):
    pass


class WebPushTransportError(requests.ConnectionError):
    pass


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _now(epoch: int | float | None = None) -> str:
    value = time.time() if epoch is None else float(epoch)
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _decode_b64url(value: str, label: str, *, maximum: int) -> tuple[str, bytes]:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"Web Push {label} is invalid.")
    try:
        decoded = base64.urlsafe_b64decode(normalized + "=" * (-len(normalized) % 4))
    except Exception as exc:
        raise ValueError(f"Web Push {label} is invalid.") from exc
    if not decoded or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for char in normalized):
        raise ValueError(f"Web Push {label} is invalid.")
    return normalized.rstrip("="), decoded


def _validate_public_key(value: str, label: str) -> str:
    normalized, decoded = _decode_b64url(value, label, maximum=128)
    if len(decoded) != 65 or decoded[0] != 4:
        raise ValueError(f"Web Push {label} is invalid.")
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded)
    except ValueError as exc:
        raise ValueError(f"Web Push {label} is invalid.") from exc
    return normalized


def _validate_auth_secret(value: str) -> str:
    normalized, decoded = _decode_b64url(value, "auth secret", maximum=64)
    if len(decoded) != 16:
        raise ValueError("Web Push auth secret is invalid.")
    return normalized


def _endpoint_parts(endpoint: str):
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Web Push endpoint is invalid.") from exc
    if (parsed.scheme != "https" or not parsed.hostname or "@" in parsed.netloc
            or parsed.fragment or port == 0 or "\\" in endpoint
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in endpoint)
            or "%" in parsed.hostname):
        raise ValueError("Web Push endpoint must be a valid HTTPS URL.")
    return parsed, 443 if port is None else port


def _resolve_public_endpoint(endpoint: str, *, resolver=None) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    parsed, port = _endpoint_parts(endpoint)
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeWebPushEndpointError("Web Push endpoint is not a public destination.")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = (literal,)
    else:
        try:
            resolver = resolver or socket.getaddrinfo
            records = resolver(hostname, port, type=socket.SOCK_STREAM)
        except OSError:
            raise WebPushTransportError("Web Push endpoint destination could not be resolved.") from None
        except ValueError:
            raise UnsafeWebPushEndpointError("Web Push endpoint destination could not be verified.") from None
        try:
            addresses = []
            for family, socktype, proto, _, sockaddr in records:
                if not isinstance(sockaddr[0], str):
                    raise ValueError("Invalid address record")
                address = ipaddress.ip_address(sockaddr[0])
                expected_family = socket.AF_INET if address.version == 4 else socket.AF_INET6
                if (family != expected_family or socktype != socket.SOCK_STREAM
                        or proto not in (0, socket.IPPROTO_TCP) or "%" in str(address)
                        or sockaddr[1] != port
                        or (address.version == 4 and len(sockaddr) != 2)
                        or (address.version == 6 and (len(sockaddr) != 4 or sockaddr[2:] != (0, 0)))):
                    raise ValueError("Invalid address record")
                addresses.append(address)
        except (ValueError, TypeError, IndexError):
            raise UnsafeWebPushEndpointError("Web Push endpoint destination could not be verified.") from None
    if not addresses or any(
        not address.is_global or address.is_multicast or address.is_reserved
        or address.is_loopback or address.is_link_local or address.is_unspecified
        or address.is_private for address in addresses
    ):
        raise UnsafeWebPushEndpointError("Web Push endpoint is not a public destination.")
    # Respect the OS resolver's address preference, but only after checking ALL answers.
    return addresses[0]


class _PinnedHTTPSConnection(HTTPSConnection):
    """Pin TCP and retain the request target; urllib3 owns all TLS operations."""

    def __init__(self, *args, pinned_address, request_target, **kwargs):
        super().__init__(*args, **kwargs)
        self._pinned_address = pinned_address
        self._request_target = request_target

    def request(self, method, url, *args, **kwargs):
        # Retain opaque path/query bytes, including percent-escape casing, which
        # urllib3's pool URL normalization would otherwise change.
        return super().request(method, self._request_target, *args, **kwargs)

    def _new_conn(self):
        # Do not use create_connection(): it calls getaddrinfo again. A canonical
        # numeric address with an explicit family goes straight to socket.connect.
        address = self._pinned_address
        family = socket.AF_INET if address.version == 4 else socket.AF_INET6
        destination = (str(address), self.port)
        if address.version == 6:
            destination += (0, 0)
        sock = None
        try:
            sock = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            for option in self.socket_options or ():
                sock.setsockopt(*option)
            sock.settimeout(self.timeout)
            sock.connect(destination)
            return sock
        except OSError as exc:
            if sock is not None:
                sock.close()
            if isinstance(exc, TimeoutError):
                raise ConnectTimeoutError(self, "Web Push connection timed out.") from None
            raise NewConnectionError(self, "Web Push connection failed.") from None


class _PinnedHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = _PinnedHTTPSConnection


class _PinnedWebPushAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, *, hostname, port, address, request_target):
        super().__init__(max_retries=0)
        self._pinned_pool = _PinnedHTTPSConnectionPool(
            hostname, port, pinned_address=address, request_target=request_target,
            server_hostname=hostname, assert_hostname=hostname,
            cert_reqs="CERT_REQUIRED",
        )

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        return self._pinned_pool

    def get_connection(self, url, proxies=None):
        # Requests before 2.32.2 uses this adapter extension point instead.
        return self._pinned_pool

    def close(self):
        self._pinned_pool.close()
        super().close()


class SafeWebPushSession(requests.Session):
    """Direct, one-attempt Web Push transport with an isolated pinned pool.

    Request preparation stays in requests; send deliberately calls the adapter
    directly, without Session.send's redirect, cookie, or response-hook machinery.
    """

    def __init__(self, *, resolver=None):
        super().__init__()
        self.trust_env = False
        self._sportabase_resolver = resolver

    def prepare_request(self, request):
        try:
            original, _ = _endpoint_parts(request.url)
            prepared = super().prepare_request(request)
        except (ValueError, requests.RequestException):
            raise UnsafeWebPushEndpointError("Web Push endpoint is invalid.") from None
        # Endpoint paths can contain opaque subscription tokens. Retain their
        # escapes and dot segments instead of requests' path normalization.
        if request.params or self.params:
            raise UnsafeWebPushEndpointError("Web Push endpoint is invalid.")
        authority = urlsplit(prepared.url).netloc
        prepared.url = "https://" + authority + (original.path or "/")
        if "?" in request.url:
            prepared.url += "?" + original.query
        return prepared

    def send(self, request, **kwargs):
        try:
            parsed, port = _endpoint_parts(request.url)
            address = _resolve_public_endpoint(request.url, resolver=self._sportabase_resolver)
        except ValueError:
            raise UnsafeWebPushEndpointError("Web Push endpoint is invalid.") from None
        if request.method != "POST" or kwargs.get("proxies") or self.proxies:
            raise UnsafeWebPushEndpointError("Web Push requires a direct HTTPS POST.")
        if kwargs.get("verify", self.verify) is not True:
            raise UnsafeWebPushEndpointError("Web Push requires certificate verification.")
        # The prepared URL supplies one canonical identity (including IDNA).
        hostname = parsed.hostname.rstrip(".")
        request.headers["Host"] = parsed.netloc
        request_target = (parsed.path or "/") + ("?" + parsed.query if "?" in request.url else "")
        adapter = _PinnedWebPushAdapter(
            hostname=hostname, port=port, address=address, request_target=request_target,
        )
        try:
            response = adapter.send(request, timeout=kwargs.get("timeout"), verify=True, proxies={})
            # Fully consume before closing this attempt's pool; no connection reuse
            # across resolutions, automatic redirects, or hidden transport retries.
            try:
                response.content
            finally:
                response.close()
            return response
        except (requests.RequestException, OSError):
            # Transport exceptions can contain endpoint tokens and socket addresses.
            raise WebPushTransportError("Web Push transport failed.") from None
        finally:
            adapter.close()


def validate_subscription(
    *, endpoint: str, p256dh: str, auth: str, expiration_time: Any = None,
    endpoint_resolver=None,
) -> tuple[str, str, str, int | None]:
    normalized_endpoint = str(endpoint or "").strip()
    if not 16 <= len(normalized_endpoint) <= 2048:
        raise ValueError("Web Push endpoint is invalid.")
    _endpoint_parts(normalized_endpoint)
    try:
        _resolve_public_endpoint(normalized_endpoint, resolver=endpoint_resolver)
    except (UnsafeWebPushEndpointError, WebPushTransportError) as exc:
        raise ValueError("Web Push endpoint must be a public HTTPS URL.") from exc
    public_key = _validate_public_key(p256dh, "p256dh key")
    auth_secret = _validate_auth_secret(auth)
    expires = None
    if expiration_time is not None:
        if isinstance(expiration_time, bool):
            raise ValueError("Web Push expirationTime is invalid.")
        try:
            expires = int(expiration_time)
        except (TypeError, ValueError) as exc:
            raise ValueError("Web Push expirationTime is invalid.") from exc
        if expires < 0 or expires > 9_007_199_254_740_991:
            raise ValueError("Web Push expirationTime is invalid.")
    return normalized_endpoint, public_key, auth_secret, expires


def _subscription_hash(endpoint: str, p256dh: str, auth: str) -> str:
    material = "\0".join((endpoint, p256dh, auth))
    return hashlib.sha256(("sportabase:web-push-subscription:v1:" + material).encode()).hexdigest()


def _subscription_id(digest: str) -> str:
    return "websub_" + digest[:32]


def _delivery_id(subscription_id: str, alert_id: str) -> str:
    digest = hashlib.sha256(
        ("sportabase:web-push-delivery:v1:" + subscription_id + ":" + alert_id).encode()
    ).hexdigest()
    return "webdelivery_" + digest[:32]


def _public_subscription(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "provider": "web_push",
        "enabled": bool(row["enabled"]),
        "expiration_time": row["expiration_time"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def web_push_config(*, env_getter=os.getenv) -> dict[str, Any]:
    public_key = _clean(env_getter(VAPID_PUBLIC_KEY_ENV, ""), 512)
    private_key = _clean(env_getter(VAPID_PRIVATE_KEY_ENV, ""), 4096)
    subject = _clean(env_getter(VAPID_SUBJECT_ENV, ""), 512)
    subject_valid = subject.startswith("mailto:") or subject.startswith("https://")
    try:
        public_key = _validate_public_key(public_key, "VAPID public key")
    except ValueError:
        public_key = ""
    configured = bool(public_key and private_key and subject_valid)
    return {
        "version": VERSION,
        "available": configured,
        "vapid_public_key": public_key if configured else "",
    }


def _private_config(*, env_getter=os.getenv) -> tuple[str, str, str] | None:
    public = _clean(env_getter(VAPID_PUBLIC_KEY_ENV, ""), 512)
    private = _clean(env_getter(VAPID_PRIVATE_KEY_ENV, ""), 4096)
    subject = _clean(env_getter(VAPID_SUBJECT_ENV, ""), 512)
    try:
        public = _validate_public_key(public, "VAPID public key")
    except ValueError:
        return None
    if not private or not (subject.startswith("mailto:") or subject.startswith("https://")):
        return None
    return public, private, subject


def register_subscription(*, owner_key: str, endpoint: str, p256dh: str, auth: str,
                          expiration_time: Any = None, connection_factory,
                          endpoint_resolver=None) -> dict[str, Any]:
    endpoint, p256dh, auth, expiration_time = validate_subscription(
        endpoint=endpoint, p256dh=p256dh, auth=auth, expiration_time=expiration_time,
        endpoint_resolver=endpoint_resolver,
    )
    digest = _subscription_hash(endpoint, p256dh, auth)
    subscription_id = _subscription_id(digest)
    now = _now()
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        watermark = int(conn.execute(
            "SELECT COALESCE(MAX(sequence),0) FROM product_notification_alert_ledger"
        ).fetchone()[0])
        existing = conn.execute(
            "SELECT * FROM product_web_push_subscriptions WHERE subscription_hash=?", (digest,)
        ).fetchone()
        registered = existing is None or existing["client_key"] != owner_key or not bool(existing["enabled"])
        if registered:
            count = int(conn.execute(
                "SELECT COUNT(*) FROM product_web_push_subscriptions WHERE client_key=? AND enabled=1 AND id<>?",
                (owner_key, subscription_id),
            ).fetchone()[0])
            if count >= MAX_SUBSCRIPTIONS_PER_CLIENT:
                raise WebPushLimitError(f"Web Push subscription limit of {MAX_SUBSCRIPTIONS_PER_CLIENT} reached.")
        if existing is None:
            conn.execute(
                """INSERT INTO product_web_push_subscriptions(
                id,client_key,subscription_hash,endpoint,p256dh,auth_secret,expiration_time,
                enabled,alert_watermark,created_at,updated_at,disabled_at
                ) VALUES(?,?,?,?,?,?,?,1,?,?,?,NULL)""",
                (subscription_id, owner_key, digest, endpoint, p256dh, auth, expiration_time,
                 watermark, now, now),
            )
        elif registered:
            conn.execute(
                """UPDATE product_web_push_deliveries SET status='cancelled',updated_at=?,
                lease_owner='',lease_expires_at_epoch=0 WHERE subscription_id=?
                AND status IN ('pending','sending')""", (now, subscription_id)
            )
            conn.execute(
                """UPDATE product_web_push_subscriptions SET client_key=?,endpoint=?,p256dh=?,
                auth_secret=?,expiration_time=?,enabled=1,alert_watermark=?,updated_at=?,disabled_at=NULL
                WHERE id=?""",
                (owner_key, endpoint, p256dh, auth, expiration_time, watermark, now, subscription_id),
            )
        else:
            conn.execute(
                "UPDATE product_web_push_subscriptions SET expiration_time=?,updated_at=? WHERE id=? AND client_key=?",
                (expiration_time, now, subscription_id, owner_key),
            )
        row = conn.execute(
            "SELECT * FROM product_web_push_subscriptions WHERE id=? AND client_key=?",
            (subscription_id, owner_key),
        ).fetchone()
        conn.commit()
        return {"version": VERSION, "subscription": _public_subscription(row), "registered": registered}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_subscriptions(*, owner_key: str, connection_factory) -> dict[str, Any]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            "SELECT * FROM product_web_push_subscriptions WHERE client_key=? AND enabled=1 ORDER BY created_at,id",
            (owner_key,),
        ).fetchall()
        return {"version": VERSION, "items": [_public_subscription(row) for row in rows],
                "count": len(rows), "limit": MAX_SUBSCRIPTIONS_PER_CLIENT}
    finally:
        conn.close()


def unregister_subscription(*, owner_key: str, subscription_id: str, connection_factory) -> None:
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "DELETE FROM product_web_push_subscriptions WHERE id=? AND client_key=?",
            (_clean(subscription_id, 128), owner_key),
        )
        if not cursor.rowcount:
            raise WebPushNotFoundError("Web Push subscription not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def active_client_keys(*, connection_factory) -> list[str]:
    conn = connection_factory()
    try:
        return [str(row["client_key"]) for row in conn.execute(
            "SELECT DISTINCT client_key FROM product_web_push_subscriptions WHERE enabled=1 AND endpoint<>'' ORDER BY client_key LIMIT 200"
        ).fetchall()]
    finally:
        conn.close()


def materialize_pending_deliveries(*, connection_factory, clock=time.time) -> dict[str, int]:
    now_epoch = max(0, int(clock()))
    now = _now(now_epoch)
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        subscriptions = conn.execute(
            "SELECT * FROM product_web_push_subscriptions WHERE enabled=1 AND endpoint<>'' ORDER BY client_key,created_at,id"
        ).fetchall()
        created = scanned = 0
        for subscription in subscriptions:
            rows = conn.execute(
                """SELECT sequence,alert_id FROM product_notification_alert_ledger
                WHERE client_key=? AND sequence>? ORDER BY sequence LIMIT ?""",
                (subscription["client_key"], int(subscription["alert_watermark"]), MAX_LEDGER_SCAN_PER_SUBSCRIPTION),
            ).fetchall()
            scanned += len(rows)
            for row in rows:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO product_web_push_deliveries(
                    id,client_key,subscription_id,alert_id,status,attempts,available_at_epoch,
                    lease_owner,lease_expires_at_epoch,provider_message_id,error_type,error_detail,
                    created_at,updated_at,accepted_at
                    ) VALUES(?,?,?,?,'pending',0,?,'',0,'','','',?,?,NULL)""",
                    (_delivery_id(subscription["id"], row["alert_id"]), subscription["client_key"],
                     subscription["id"], row["alert_id"], now_epoch, now, now),
                )
                created += int(cursor.rowcount or 0)
            if rows:
                conn.execute(
                    "UPDATE product_web_push_subscriptions SET alert_watermark=?,updated_at=? WHERE id=?",
                    (int(rows[-1]["sequence"]), now, subscription["id"]),
                )
        conn.commit()
        return {"web_subscriptions_checked": len(subscriptions), "web_ledger_rows_scanned": scanned,
                "web_deliveries_created": created}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _retry_delay(attempts: int) -> int:
    return min(RETRY_CAP_SECONDS, RETRY_BASE_SECONDS * (2 ** max(0, attempts - 1)))


def _claim(*, connection_factory, worker_id: str, now_epoch: int, lease_seconds: int) -> list[dict[str, Any]]:
    conn = connection_factory()
    try:
        conn.execute("BEGIN IMMEDIATE")
        now = _now(now_epoch)
        conn.execute("""UPDATE product_web_push_deliveries SET status='cancelled',updated_at=?,lease_owner='',lease_expires_at_epoch=0
            WHERE status IN ('pending','sending') AND subscription_id IN
            (SELECT id FROM product_web_push_subscriptions WHERE enabled=0 OR endpoint='')""", (now,))
        conn.execute("""UPDATE product_web_push_deliveries SET status='failed',updated_at=?,error_type='attempts_exhausted',
            error_detail='Web Push delivery attempts exhausted.',lease_owner='',lease_expires_at_epoch=0
            WHERE status IN ('pending','sending') AND attempts>=?""", (now, MAX_DELIVERY_ATTEMPTS))
        ids = [str(row["id"]) for row in conn.execute("""SELECT d.id FROM product_web_push_deliveries d
            JOIN product_web_push_subscriptions s ON s.id=d.subscription_id
            WHERE s.enabled=1 AND s.endpoint<>'' AND d.attempts<? AND
            ((d.status='pending' AND d.available_at_epoch<=?) OR (d.status='sending' AND d.lease_expires_at_epoch<=?))
            ORDER BY d.available_at_epoch,d.created_at,d.id LIMIT ?""",
            (MAX_DELIVERY_ATTEMPTS, now_epoch, now_epoch, MAX_DELIVERIES_PER_REQUEST)).fetchall()]
        if not ids:
            conn.commit()
            return []
        marks = ",".join("?" for _ in ids)
        conn.execute(f"""UPDATE product_web_push_deliveries SET status='sending',attempts=attempts+1,
            lease_owner=?,lease_expires_at_epoch=?,updated_at=? WHERE id IN ({marks})""",
            (worker_id, now_epoch + lease_seconds, now, *ids))
        rows = [dict(row) for row in conn.execute(f"""SELECT d.id,d.subscription_id,d.alert_id,d.attempts,
            s.endpoint,s.p256dh,s.auth_secret,a.target_kind,a.target_id,a.event_type,a.summary
            FROM product_web_push_deliveries d JOIN product_web_push_subscriptions s ON s.id=d.subscription_id
            JOIN product_alert_events a ON a.id=d.alert_id WHERE d.id IN ({marks}) ORDER BY d.created_at,d.id""", ids).fetchall()]
        conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def payload_for_delivery(row: dict[str, Any]) -> dict[str, Any]:
    kind = _clean(row.get("target_kind"), 16)
    if kind not in WATCHABLE_KINDS:
        raise ValueError("Web Push target kind is not watchable.")
    target_id = _clean(row.get("target_id"), 256)
    return {"sportabase_notification_version": VERSION, "alert_id": _clean(row.get("alert_id"), 128),
            "target_kind": kind, "target_id": target_id, "event_type": _clean(row.get("event_type"), 64),
            "summary": _clean(row.get("summary"), 240),
            "url": f"./?target_kind={kind}&target_id={target_id}"}


def _is_microsoft_wns_endpoint(endpoint: str) -> bool:
    hostname = (_endpoint_parts(endpoint)[0].hostname or "").casefold()
    return hostname == "notify.windows.com" or hostname.endswith(".notify.windows.com")


def _provider_headers(endpoint: str) -> dict[str, str]:
    if _is_microsoft_wns_endpoint(endpoint):
        return {"X-WNS-Type": "wns/raw", "Content-Type": "application/octet-stream"}
    return {}


def _default_sender(*, subscription_info, data: str, vapid_private_key: str,
                    vapid_claims: dict[str, str], timeout: float, headers=None):
    from pywebpush import webpush
    with SafeWebPushSession() as session:
        return webpush(subscription_info=subscription_info, data=data,
                       vapid_private_key=vapid_private_key, vapid_claims=vapid_claims,
                       ttl=300, timeout=timeout, headers=headers or {},
                       requests_session=session)


def _finish(*, connection_factory, row: dict[str, Any], now_epoch: int, outcome: str,
            error_type: str = "", error_detail: str = "") -> dict[str, int]:
    now = _now(now_epoch)
    attempts = int(row["attempts"])
    conn = connection_factory()
    result = {"web_accepted": 0, "web_retried": 0, "web_failed": 0, "web_invalid_subscriptions": 0}
    try:
        conn.execute("BEGIN IMMEDIATE")
        if outcome == "accepted":
            conn.execute("""UPDATE product_web_push_deliveries SET status='accepted',accepted_at=?,updated_at=?,
                error_type='',error_detail='',lease_owner='',lease_expires_at_epoch=0 WHERE id=?""", (now, now, row["id"]))
            result["web_accepted"] = 1
        elif outcome == "invalid":
            conn.execute("UPDATE product_web_push_subscriptions SET enabled=0,endpoint='',p256dh='',auth_secret='',updated_at=?,disabled_at=? WHERE id=?",
                         (now, now, row["subscription_id"]))
            conn.execute("""UPDATE product_web_push_deliveries SET status='cancelled',updated_at=?,error_type='subscription_invalid',
                error_detail=?,lease_owner='',lease_expires_at_epoch=0 WHERE subscription_id=? AND status IN ('pending','sending')""",
                         (now, _clean(error_detail, 1000) or "Web Push subscription is no longer valid.", row["subscription_id"]))
            conn.execute("""UPDATE product_web_push_deliveries SET status='failed',updated_at=?,error_type=?,
                error_detail=?,lease_owner='',lease_expires_at_epoch=0 WHERE id=?""",
                         (now, _clean(error_type, 128) or "subscription_invalid",
                          _clean(error_detail, 1000) or "Web Push subscription is no longer valid.", row["id"]))
            result["web_failed"] = 1
            result["web_invalid_subscriptions"] = 1
        elif outcome == "retry" and attempts < MAX_DELIVERY_ATTEMPTS:
            conn.execute("""UPDATE product_web_push_deliveries SET status='pending',available_at_epoch=?,updated_at=?,error_type=?,error_detail=?,
                lease_owner='',lease_expires_at_epoch=0 WHERE id=?""",
                         (now_epoch + _retry_delay(attempts), now, _clean(error_type, 128), _clean(error_detail, 1000), row["id"]))
            result["web_retried"] = 1
        else:
            final_type = "attempts_exhausted" if outcome == "retry" else (_clean(error_type, 128) or "provider_rejected")
            conn.execute("""UPDATE product_web_push_deliveries SET status='failed',updated_at=?,error_type=?,error_detail=?,
                lease_owner='',lease_expires_at_epoch=0 WHERE id=?""",
                         (now, final_type, _clean(error_detail, 1000), row["id"]))
            result["web_failed"] = 1
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _status_from_exception(exc: Exception) -> int:
    response = getattr(exc, "response", None)
    return int(getattr(response, "status_code", 0) or getattr(exc, "status_code", 0) or 0)


def dispatch_pending_deliveries(*, connection_factory, sender: Callable[..., Any] = _default_sender,
                                env_getter=os.getenv, clock=time.time, worker_id="web-push-worker",
                                lease_seconds=120, request_timeout_seconds=10.0) -> dict[str, int]:
    empty = {"web_claimed": 0, "web_accepted": 0, "web_retried": 0,
             "web_failed": 0, "web_invalid_subscriptions": 0, "web_configured": 0}
    config = _private_config(env_getter=env_getter)
    if config is None:
        return empty
    _, private_key, subject = config
    now_epoch = max(0, int(clock()))
    rows = _claim(connection_factory=connection_factory, worker_id=worker_id,
                  now_epoch=now_epoch, lease_seconds=lease_seconds)
    totals = {**empty, "web_claimed": len(rows), "web_configured": 1}
    invalid_subscriptions: set[str] = set()
    for row in rows:
        if row["subscription_id"] in invalid_subscriptions:
            continue
        subscription_info = {"endpoint": row["endpoint"],
                             "keys": {"p256dh": row["p256dh"], "auth": row["auth_secret"]}}
        # Only the provider call belongs inside this boundary. Persistence errors propagate.
        try:
            sender(subscription_info=subscription_info,
                   data=json.dumps(payload_for_delivery(row), separators=(",", ":")),
                   vapid_private_key=private_key, vapid_claims={"sub": subject},
                   timeout=request_timeout_seconds,
                   headers=_provider_headers(row["endpoint"]))
        except UnsafeWebPushEndpointError:
            result = _finish(connection_factory=connection_factory, row=row, now_epoch=now_epoch,
                             outcome="invalid", error_type="unsafe_endpoint",
                             error_detail="Web Push endpoint destination is unsafe.")
            invalid_subscriptions.add(row["subscription_id"])
        except Exception as exc:
            status = _status_from_exception(exc)
            detail = _clean(getattr(getattr(exc, "response", None), "text", ""), 1000)
            if not detail:
                detail = _clean(exc, 1000) or "Web Push transport failed."
            if status in {404, 410}:
                outcome, error_type = "invalid", f"provider_http_{status}"
                invalid_subscriptions.add(row["subscription_id"])
            elif status == 429 or status >= 500 or status == 0:
                outcome, error_type = "retry", f"provider_http_{status}" if status else "provider_transport"
            else:
                outcome, error_type = "failed", f"provider_http_{status}"
            result = _finish(connection_factory=connection_factory, row=row, now_epoch=now_epoch,
                             outcome=outcome, error_type=error_type, error_detail=detail)
        else:
            result = _finish(connection_factory=connection_factory, row=row, now_epoch=now_epoch,
                             outcome="accepted")
        for key, value in result.items():
            totals[key] += value
    return totals


__all__ = ["VERSION", "WATCHABLE_KINDS", "WebPushLimitError", "WebPushNotFoundError",
           "active_client_keys", "dispatch_pending_deliveries", "list_subscriptions",
           "materialize_pending_deliveries", "payload_for_delivery", "register_subscription",
           "unregister_subscription", "validate_subscription", "web_push_config"]
