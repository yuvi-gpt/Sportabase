from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.operations.control_room_ai_usage import (
    CONTROL_ROOM_AI_USAGE_VERSION,
    build_control_room_ai_usage_snapshot,
)
from app.routes.control_room_admin import build_router
from app.security.control_room import (
    CONTROL_ROOM_SECURITY_VERSION,
    ControlRoomAccessDenied,
    ControlRoomPrincipal,
)


NOW = 2_000_000_000


def _principal() -> ControlRoomPrincipal:
    return ControlRoomPrincipal(
        version=CONTROL_ROOM_SECURITY_VERSION,
        subject="owner-123",
        email="owner@example.com",
        email_verified=True,
        issuer="https://access.example.com",
        audience="control-room-audience",
        auth_strength="phishing_resistant",
        auth_methods=("passkey", "webauthn"),
        authenticated_at_epoch=NOW - 60,
        expires_at_epoch=NOW + 900,
    )


def _client(
    *,
    guard,
    usage_handler,
) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_router(
            require_control_room=guard,
            ai_usage_handler=usage_handler,
        )
    )
    return TestClient(app)


class ControlRoomAiUsageSnapshotTests(unittest.TestCase):
    def test_snapshot_reports_capacity_and_curates_sensitive_fields(self):
        audit = {
            "summary": {
                "provider_attempts": 13,
                "successful_calls": 10,
                "failed_calls": 3,
                "total_tokens": 21929,
            },
            "by_model": [
                {"model": "gemini-test", "provider_attempts": 13}
            ],
            "by_mode": [
                {"mode": "article_single_pass", "provider_attempts": 13}
            ],
            "failures": [
                {
                    "id": 7,
                    "created_at": "2026-08-21T01:00:00+00:00",
                    "client_key": "private-client-key",
                    "mode": "article_single_pass",
                    "model": "gemini-test",
                    "status_code": 503,
                    "failure_type": "provider_capacity",
                    "failure_detail": "raw provider detail",
                    "latency_ms": 28000,
                }
            ],
            "provider_calls": [
                {
                    "id": 8,
                    "created_at": "2026-08-21T01:01:00+00:00",
                    "client_key": "private-client-key",
                    "mode": "article_single_pass",
                    "model": "gemini-test",
                    "status": "success",
                    "prompt_tokens": 100,
                    "output_tokens": 20,
                    "thought_tokens": 5,
                    "total_tokens": 125,
                    "latency_ms": 1200,
                    "failure_status_code": None,
                    "failure_type": "",
                }
            ],
        }

        with patch(
            "app.operations.control_room_ai_usage."
            "build_provider_day_ai_usage_audit",
            return_value=audit,
        ):
            payload = build_control_room_ai_usage_snapshot(
                db_path="unused.db",
                provider_day="2026-08-21",
                global_daily_call_cap=16,
            )

        self.assertEqual(payload["version"], CONTROL_ROOM_AI_USAGE_VERSION)
        self.assertEqual(payload["provider_day"], "2026-08-21")
        self.assertEqual(
            payload["capacity"],
            {
                "global_daily_call_cap": 16,
                "provider_attempts": 13,
                "remaining_calls": 3,
                "capacity_used_percent": 81.25,
                "exhausted": False,
            },
        )
        self.assertEqual(payload["summary"]["total_tokens"], 21929)
        self.assertNotIn(
            "client_key",
            payload["recent_failures"][0],
        )
        self.assertNotIn(
            "failure_detail",
            payload["recent_failures"][0],
        )
        self.assertNotIn(
            "client_key",
            payload["recent_provider_calls"][0],
        )

    def test_snapshot_fails_closed_on_empty_provider_day(self):
        with self.assertRaisesRegex(ValueError, "provider_day is required"):
            build_control_room_ai_usage_snapshot(
                db_path="unused.db",
                provider_day="",
                global_daily_call_cap=16,
            )


class ControlRoomAiUsageRouteTests(unittest.TestCase):
    def test_authorized_owner_can_read_explicit_provider_day(self):
        guard_calls = []
        usage_calls = []

        def guard(request):
            guard_calls.append(request.url.path)
            return _principal()

        def usage_handler(provider_day):
            usage_calls.append(provider_day)
            return {
                "version": CONTROL_ROOM_AI_USAGE_VERSION,
                "provider_day": provider_day,
            }

        response = _client(
            guard=guard,
            usage_handler=usage_handler,
        ).get(
            "/admin/control-room/ai-usage",
            params={"provider_day": "2026-08-21"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            guard_calls,
            ["/admin/control-room/ai-usage"],
        )
        self.assertEqual(usage_calls, ["2026-08-21"])
        self.assertEqual(response.json()["provider_day"], "2026-08-21")

    def test_missing_provider_day_uses_provider_timezone_day(self):
        usage_calls = []

        def usage_handler(provider_day):
            usage_calls.append(provider_day)
            return {"provider_day": provider_day}

        client = _client(
            guard=lambda request: _principal(),
            usage_handler=usage_handler,
        )

        with patch(
            "app.routes.control_room_admin.provider_usage_day",
            return_value="2026-08-20",
        ):
            response = client.get("/admin/control-room/ai-usage")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(usage_calls, ["2026-08-20"])

    def test_guard_denial_happens_before_provider_day_validation_or_usage_read(self):
        usage_calls = []

        def denied_guard(request):
            del request
            raise ControlRoomAccessDenied("blocked")

        def usage_handler(provider_day):
            usage_calls.append(provider_day)
            return {}

        response = _client(
            guard=denied_guard,
            usage_handler=usage_handler,
        ).get(
            "/admin/control-room/ai-usage",
            params={"provider_day": "not-a-date"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(usage_calls, [])

    def test_invalid_provider_day_is_rejected_after_authorization(self):
        usage_calls = []

        def usage_handler(provider_day):
            usage_calls.append(provider_day)
            return {}

        response = _client(
            guard=lambda request: _principal(),
            usage_handler=usage_handler,
        ).get(
            "/admin/control-room/ai-usage",
            params={"provider_day": "21-08-2026"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "provider_day must use YYYY-MM-DD."},
        )
        self.assertEqual(usage_calls, [])


if __name__ == "__main__":
    unittest.main()
