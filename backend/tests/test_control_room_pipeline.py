from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.operations.control_room_pipeline import (
    CONTROL_ROOM_PIPELINE_VERSION,
    build_control_room_pipeline_snapshot,
)
from app.operations.control_room_usage_bridge import (
    ControlRoomUsageBridgeMisconfigured,
    ControlRoomUsageBridgeUnavailable,
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


def _client(*, guard, pipeline_handler) -> TestClient:
    app = FastAPI()
    app.include_router(
        build_router(
            require_control_room=guard,
            ai_usage_handler=lambda days: {"days": days},
            pipeline_handler=pipeline_handler,
        )
    )
    return TestClient(app)


class ControlRoomPipelineSnapshotTests(unittest.TestCase):
    def test_snapshot_reports_only_defensible_pipeline_signals(self):
        upstream = {
            "source": "sportabase-api",
            "upstream_generated_at": "2026-08-21T12:00:00+00:00",
            "usage_day_utc": "2026-08-21",
            "summary": {
                "records": 6,
                "provider_attempts": 4,
                "successful_calls": 3,
                "failed_calls": 1,
                "cache_hits": 2,
                "inflight_joins": 0,
                "average_latency_ms": 1250,
                "private_field": "do-not-forward",
            },
            "metrics": {
                "success_rate_percent": 75.0,
                "failure_rate_percent": 25.0,
                "cache_hit_rate_percent": 33.33,
            },
            "mode_metrics": [
                {
                    "mode": "article",
                    "total_records": 4,
                    "gemini_attempts": 3,
                    "successful_calls": 2,
                    "failed_calls": 1,
                    "cache_hits": 1,
                    "inflight_joins": 0,
                    "success_rate_percent": 66.67,
                    "failure_rate_percent": 33.33,
                    "cache_hit_rate_percent": 25.0,
                    "client_key": "private-client",
                },
                {
                    "mode": "video",
                    "total_records": 2,
                    "gemini_attempts": 1,
                    "successful_calls": 1,
                    "failed_calls": 0,
                    "cache_hits": 1,
                    "inflight_joins": 0,
                    "success_rate_percent": 100.0,
                    "failure_rate_percent": 0.0,
                    "cache_hit_rate_percent": 50.0,
                },
            ],
            "recent_days": [
                {
                    "usage_day": "2026-08-21",
                    "total_records": 6,
                    "provider_attempts": 4,
                    "successful_calls": 3,
                    "failed_calls": 1,
                    "cache_hits": 2,
                    "inflight_joins": 0,
                    "secret": "drop-me",
                }
            ],
            "window": {
                "requested_days": 7,
                "start_day_utc": "2026-08-15",
                "end_day_utc": "2026-08-21",
                "days_with_activity": 1,
            },
        }

        payload = build_control_room_pipeline_snapshot(upstream)

        self.assertEqual(
            payload["version"],
            CONTROL_ROOM_PIPELINE_VERSION,
        )
        self.assertEqual(payload["state"]["activity"], "active")
        self.assertEqual(
            payload["state"]["outcomes"],
            "failures_observed",
        )
        self.assertEqual(payload["state"]["coverage"], "partial")
        self.assertEqual(payload["today"]["article_records"], 4)
        self.assertEqual(payload["today"]["video_records"], 2)
        self.assertEqual(payload["today"]["other_records"], 0)
        self.assertEqual(payload["today"]["cache_hits"], 2)
        self.assertNotIn("client_key", payload["by_mode"][0])
        self.assertNotIn("secret", payload["recent_days"][0])
        self.assertEqual(
            payload["instrumentation"]["analysis_activity"],
            "live",
        )
        self.assertEqual(
            payload["instrumentation"]["browser_capture_ingestion"],
            "not_available_from_upstream_contract",
        )
        self.assertEqual(
            payload["instrumentation"]["extraction_stage"],
            "not_available_from_upstream_contract",
        )
        self.assertEqual(
            payload["instrumentation"]["automation_jobs"],
            "not_available_from_upstream_contract",
        )

    def test_empty_snapshot_is_idle_not_claimed_healthy(self):
        payload = build_control_room_pipeline_snapshot(
            {
                "source": "sportabase-api",
                "summary": {},
                "metrics": {},
                "mode_metrics": [],
                "recent_days": [],
                "window": {},
            }
        )

        self.assertEqual(payload["state"]["activity"], "idle")
        self.assertEqual(
            payload["state"]["outcomes"],
            "no_failures_observed",
        )
        self.assertEqual(payload["state"]["coverage"], "partial")

    def test_snapshot_rejects_non_mapping(self):
        with self.assertRaisesRegex(
            ValueError,
            "upstream_usage must be an object",
        ):
            build_control_room_pipeline_snapshot([])


class ControlRoomPipelineRouteTests(unittest.TestCase):
    def test_authorized_owner_can_read_pipeline_window(self):
        calls = []

        def pipeline_handler(days):
            calls.append(days)
            return {
                "version": CONTROL_ROOM_PIPELINE_VERSION,
                "window": {"requested_days": days},
            }

        response = _client(
            guard=lambda request: _principal(),
            pipeline_handler=pipeline_handler,
        ).get(
            "/admin/control-room/pipeline",
            params={"days": "7"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [7])
        self.assertEqual(
            response.json()["window"]["requested_days"],
            7,
        )

    def test_guard_denial_happens_before_days_validation_or_pipeline_read(self):
        calls = []

        def denied_guard(request):
            del request
            raise ControlRoomAccessDenied("blocked")

        def pipeline_handler(days):
            calls.append(days)
            return {}

        response = _client(
            guard=denied_guard,
            pipeline_handler=pipeline_handler,
        ).get(
            "/admin/control-room/pipeline",
            params={"days": "not-a-number"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(calls, [])

    def test_invalid_days_is_rejected_after_authorization(self):
        calls = []

        def pipeline_handler(days):
            calls.append(days)
            return {}

        response = _client(
            guard=lambda request: _principal(),
            pipeline_handler=pipeline_handler,
        ).get(
            "/admin/control-room/pipeline",
            params={"days": "31"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(calls, [])
        self.assertEqual(
            response.json(),
            {"detail": "days must be an integer between 1 and 30."},
        )

    def test_upstream_unavailable_maps_to_502(self):
        def pipeline_handler(days):
            del days
            raise ControlRoomUsageBridgeUnavailable("offline")

        response = _client(
            guard=lambda request: _principal(),
            pipeline_handler=pipeline_handler,
        ).get("/admin/control-room/pipeline")

        self.assertEqual(response.status_code, 502)

    def test_upstream_misconfiguration_maps_to_503(self):
        def pipeline_handler(days):
            del days
            raise ControlRoomUsageBridgeMisconfigured("missing")

        response = _client(
            guard=lambda request: _principal(),
            pipeline_handler=pipeline_handler,
        ).get("/admin/control-room/pipeline")

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
