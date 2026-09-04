from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.notifications.runtime import (
    list_devices,
    register_device,
    run_notification_cycle,
)
from app.routes.notifications_product import build_router
from app.watchlists.runtime import client_key, create_watch, reconcile


T0 = "2026-09-04T10:00:00+00:00"
T1 = "2026-09-04T10:05:00+00:00"
T2 = "2026-09-04T10:10:00+00:00"


class _ExpoResponse:
    def __init__(self, tickets, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self._tickets = tickets

    def json(self):
        return {"data": self._tickets}


def _factory(tmp_path):
    path = tmp_path / "notifications.db"

    def connection_factory():
        return connect_database(path)

    initialize_database(connection_factory, SCHEMA)

    conn = connection_factory()
    try:
        conn.execute(
            """
            INSERT INTO media_items(
              id,canonical_url,mode,title,latest_content_hash,
              first_seen_at,last_seen_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                "media-1",
                "https://example.com/story",
                "article",
                "Example story",
                "hash-1",
                T0,
                T0,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return connection_factory


def _snapshot(factory, analyzed_at, content_hash):
    conn = factory()
    try:
        conn.execute(
            """
            INSERT INTO analysis_snapshots(
              media_item_id,analyzed_at,mode,analysis_version,scoring_version,
              content_hash,context_hash,response_json
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                "media-1",
                analyzed_at,
                "article",
                "analysis-v1",
                "score-v1",
                content_hash,
                "context-1",
                "{}",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _accepted_post(calls):
    def post(url, *, json, headers, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _ExpoResponse(
            [
                {"status": "ok", "id": f"ticket-{index + 1}"}
                for index, _ in enumerate(json)
            ]
        )

    return post


def test_push_cycle_reconciles_then_delivers_exactly_once(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(
        owner_key=owner,
        target_kind="media",
        target_id="media-1",
        connection_factory=factory,
    )
    registration = register_device(
        owner_key=owner,
        push_token="ExpoPushToken[aaaaaaaaaaaaaaaaaaaaaaaa]",
        platform="android",
        connection_factory=factory,
    )
    assert registration["registered"] is True
    assert "push_token" not in registration["device"]

    _snapshot(factory, T1, "content-1")
    calls = []
    result = run_notification_cycle(
        connection_factory=factory,
        http_post=_accepted_post(calls),
        clock=lambda: 2_000_000_000,
        worker_id="test-worker",
    )

    assert result["new_alerts"] == 1
    assert result["deliveries_created"] == 1
    assert result["accepted"] == 1
    assert len(calls) == 1
    assert len(calls[0]["json"]) == 1
    message = calls[0]["json"][0]
    assert message["data"]["target_kind"] == "media"
    assert message["data"]["target_id"] == "media-1"
    assert "client" not in message["data"]

    second = run_notification_cycle(
        connection_factory=factory,
        http_post=_accepted_post(calls),
        clock=lambda: 2_000_000_030,
        worker_id="test-worker",
    )
    assert second["new_alerts"] == 0
    assert second["deliveries_created"] == 0
    assert second["claimed"] == 0
    assert len(calls) == 1


def test_device_registration_baselines_existing_alerts(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(
        owner_key=owner,
        target_kind="media",
        target_id="media-1",
        connection_factory=factory,
    )
    _snapshot(factory, T1, "content-before-registration")
    assert reconcile(owner_key=owner, connection_factory=factory)["new_alerts"] == 1

    register_device(
        owner_key=owner,
        push_token="ExpoPushToken[bbbbbbbbbbbbbbbbbbbbbbbb]",
        platform="ios",
        connection_factory=factory,
    )
    calls = []
    first = run_notification_cycle(
        connection_factory=factory,
        http_post=_accepted_post(calls),
        clock=lambda: 2_000_000_000,
    )
    assert first["deliveries_created"] == 0
    assert first["claimed"] == 0
    assert calls == []

    _snapshot(factory, T2, "content-after-registration")
    second = run_notification_cycle(
        connection_factory=factory,
        http_post=_accepted_post(calls),
        clock=lambda: 2_000_000_030,
    )
    assert second["new_alerts"] == 1
    assert second["deliveries_created"] == 1
    assert second["accepted"] == 1
    assert len(calls) == 1


def test_device_not_registered_disables_future_push(tmp_path):
    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(
        owner_key=owner,
        target_kind="media",
        target_id="media-1",
        connection_factory=factory,
    )
    register_device(
        owner_key=owner,
        push_token="ExpoPushToken[cccccccccccccccccccccccc]",
        platform="android",
        connection_factory=factory,
    )
    _snapshot(factory, T1, "content-invalid-device")

    def rejected_post(url, *, json, headers, timeout):
        return _ExpoResponse(
            [
                {
                    "status": "error",
                    "message": "The device is not registered.",
                    "details": {"error": "DeviceNotRegistered"},
                }
                for _ in json
            ]
        )

    result = run_notification_cycle(
        connection_factory=factory,
        http_post=rejected_post,
        clock=lambda: 2_000_000_000,
    )
    assert result["failed"] == 1
    assert result["invalid_devices"] == 1
    assert list_devices(owner_key=owner, connection_factory=factory)["count"] == 0


def test_notification_routes_are_private_and_never_return_token(tmp_path):
    factory = _factory(tmp_path)
    app = FastAPI()
    app.include_router(build_router(connection_factory=factory))
    client = TestClient(app)

    unauthorized = client.get("/notifications/devices")
    assert unauthorized.status_code == 401

    created = client.post(
        "/notifications/devices",
        headers={"x-sportabase-client-id": "client-a"},
        json={
            "push_token": "ExpoPushToken[dddddddddddddddddddddddd]",
            "platform": "android",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["device"]["enabled"] is True
    assert "push_token" not in payload["device"]
    device_id = payload["device"]["id"]

    cross_client = client.delete(
        f"/notifications/devices/{device_id}",
        headers={"x-sportabase-client-id": "client-b"},
    )
    assert cross_client.status_code == 404

    removed = client.delete(
        f"/notifications/devices/{device_id}",
        headers={"x-sportabase-client-id": "client-a"},
    )
    assert removed.status_code == 204

    listed = client.get(
        "/notifications/devices",
        headers={"x-sportabase-client-id": "client-a"},
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 0


def test_delivery_persistence_error_is_not_reclassified_as_transport(tmp_path, monkeypatch):
    import pytest
    import app.notifications.runtime as notification_runtime

    factory = _factory(tmp_path)
    owner = client_key("client-a")
    create_watch(
        owner_key=owner,
        target_kind="media",
        target_id="media-1",
        connection_factory=factory,
    )
    register_device(
        owner_key=owner,
        push_token="ExpoPushToken[eeeeeeeeeeeeeeeeeeeeeeee]",
        platform="android",
        connection_factory=factory,
    )
    _snapshot(factory, T1, "content-persistence-error")

    calls = []

    def fail_once_then_retry(**kwargs):
        calls.append(kwargs.get("transport_error_type", ""))
        if len(calls) == 1:
            raise RuntimeError("delivery persistence failed")
        return {
            "accepted": 0,
            "retried": 1,
            "failed": 0,
            "invalid_devices": 0,
        }

    monkeypatch.setattr(
        notification_runtime,
        "_finish_batch",
        fail_once_then_retry,
    )

    with pytest.raises(RuntimeError, match="delivery persistence failed"):
        run_notification_cycle(
            connection_factory=factory,
            http_post=_accepted_post([]),
            clock=lambda: 2_000_000_000,
        )

    assert calls == [""]
