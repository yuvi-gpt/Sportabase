from __future__ import annotations

import unittest

from app.operations.control_room_usage_bridge import (
    CONTROL_ROOM_UPSTREAM_USAGE_VERSION,
    ControlRoomUsageBridgeMisconfigured,
    ControlRoomUsageBridgeUnavailable,
    fetch_control_room_upstream_usage,
)


SECRET = "s" * 44


class _Response:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def _payload():
    return {
        "generated_at": "2026-08-21T06:00:00+00:00",
        "usage_day_utc": "2026-08-21",
        "today": {
            "total_records": 18,
            "unique_clients": 2,
            "cache_hits": 1,
            "inflight_joins": 1,
            "gemini_attempts": 16,
            "successful_calls": 13,
            "failed_calls": 3,
            "reserved_calls": 0,
            "expired_reservations": 0,
            "prompt_tokens": 7677,
            "output_tokens": 2024,
            "thought_tokens": 12228,
            "total_tokens": 21929,
            "average_latency_ms": 4200,
            "fastest_latency_ms": 800,
            "slowest_latency_ms": 28000,
        },
        "today_metrics": {
            "success_rate_percent": 81.25,
            "failure_rate_percent": 18.75,
            "cache_hit_rate_percent": 5.56,
            "provider_avoidance_rate_percent": 11.11,
            "average_total_tokens_per_success": 1686.85,
            "estimated_paid_cost_usd": 0.05,
        },
        "limits": {
            "global_daily_call_cap": 16,
            "global_calls_remaining": 0,
            "client_daily_call_cap": 8,
            "private_future_field": SECRET,
        },
        "today_breakdown": [
            {
                "mode": "article",
                "model": "gemini-test",
                "status": "success",
                "cache_hit": False,
                "inflight_join": False,
                "request_count": 13,
                "prompt_tokens": 7677,
                "output_tokens": 2024,
                "thought_tokens": 12228,
                "total_tokens": 21929,
                "private_field": SECRET,
            }
        ],
        "mode_metrics": [
            {
                "mode": "article",
                "gemini_attempts": 16,
                "successful_calls": 13,
                "failed_calls": 3,
                "total_tokens": 21929,
                "success_rate_percent": 81.25,
                "estimated_paid_cost_usd": 0.05,
                "provider_calls_avoided": 2,
                "private_field": SECRET,
            }
        ],
        "failure_breakdown": [
            {
                "mode": "article",
                "failure_status_code": 503,
                "failure_type": "provider_capacity",
                "failure_count": 3,
                "failure_detail": SECRET,
            }
        ],
        "recent_days": [
            {
                "usage_day": "2026-08-21",
                "total_records": 18,
                "unique_clients": 2,
                "cache_hits": 1,
                "inflight_joins": 1,
                "gemini_attempts": 16,
                "successful_calls": 13,
                "failed_calls": 3,
                "total_tokens": 21929,
                "private_field": SECRET,
            }
        ],
        "rolling_window": {
            "requested_days": 7,
            "start_day_utc": "2026-08-15",
            "end_day_utc": "2026-08-21",
            "days_with_activity": 4,
            "private_field": SECRET,
        },
        "untrusted_extra": SECRET,
    }


class ControlRoomUsageBridgeTests(unittest.TestCase):
    def test_bridge_sends_server_credential_and_returns_curated_payload(self):
        calls = []

        def request_get(url, **kwargs):
            calls.append((url, kwargs))
            return _Response(payload=_payload())

        result = fetch_control_room_upstream_usage(
            api_origin="https://sportabase-api.example.com",
            admin_api_key=SECRET,
            days=7,
            timeout_seconds=10,
            request_get=request_get,
        )

        self.assertEqual(len(calls), 1)
        url, kwargs = calls[0]
        self.assertEqual(
            url,
            "https://sportabase-api.example.com/admin/usage/summary",
        )
        self.assertEqual(kwargs["params"], {"days": 7})
        self.assertEqual(kwargs["timeout"], 10.0)
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(
            kwargs["headers"]["x-sportabase-admin-key"],
            SECRET,
        )

        self.assertEqual(
            result["version"],
            CONTROL_ROOM_UPSTREAM_USAGE_VERSION,
        )
        self.assertEqual(result["source"], "sportabase-api")
        self.assertEqual(result["capacity"]["provider_attempts"], 16)
        self.assertEqual(result["capacity"]["remaining_calls"], 0)
        self.assertIs(result["capacity"]["exhausted"], True)
        self.assertEqual(result["summary"]["total_tokens"], 21929)
        self.assertEqual(result["metrics"]["success_rate_percent"], 81.25)
        self.assertEqual(
            result["failure_breakdown"],
            [
                {
                    "mode": "article",
                    "status_code": 503,
                    "failure_type": "provider_capacity",
                    "count": 3,
                }
            ],
        )
        self.assertNotIn(SECRET, repr(result))

    def test_missing_or_short_admin_key_fails_before_network(self):
        calls = []

        for key in ("", "short"):
            with self.subTest(key_length=len(key)):
                with self.assertRaises(ControlRoomUsageBridgeMisconfigured):
                    fetch_control_room_upstream_usage(
                        api_origin="https://sportabase-api.example.com",
                        admin_api_key=key,
                        request_get=lambda *args, **kwargs: calls.append(1),
                    )

        self.assertEqual(calls, [])

    def test_invalid_origins_fail_closed_before_network(self):
        calls = []
        invalid = (
            "",
            "http://sportabase-api.example.com",
            "https://user:pass@sportabase-api.example.com",
            "https://sportabase-api.example.com/private",
            "https://sportabase-api.example.com?x=1",
        )

        for origin in invalid:
            with self.subTest(origin=origin):
                with self.assertRaises(ControlRoomUsageBridgeMisconfigured):
                    fetch_control_room_upstream_usage(
                        api_origin=origin,
                        admin_api_key=SECRET,
                        request_get=lambda *args, **kwargs: calls.append(1),
                    )

        self.assertEqual(calls, [])

    def test_non_200_response_fails_without_echoing_secret_or_body(self):
        with self.assertRaises(ControlRoomUsageBridgeUnavailable) as caught:
            fetch_control_room_upstream_usage(
                api_origin="https://sportabase-api.example.com",
                admin_api_key=SECRET,
                request_get=lambda *args, **kwargs: _Response(
                    status_code=401,
                    payload={"detail": SECRET},
                ),
            )

        message = str(caught.exception)
        self.assertNotIn(SECRET, message)
        self.assertNotIn("detail", message)

    def test_invalid_json_response_fails_closed(self):
        with self.assertRaises(ControlRoomUsageBridgeUnavailable):
            fetch_control_room_upstream_usage(
                api_origin="https://sportabase-api.example.com",
                admin_api_key=SECRET,
                request_get=lambda *args, **kwargs: _Response(
                    status_code=200,
                    json_error=ValueError("bad json"),
                ),
            )

    def test_days_and_timeout_are_bounded_before_network(self):
        calls = []

        for days in (0, 31):
            with self.subTest(days=days):
                with self.assertRaises(ValueError):
                    fetch_control_room_upstream_usage(
                        api_origin="https://sportabase-api.example.com",
                        admin_api_key=SECRET,
                        days=days,
                        request_get=lambda *args, **kwargs: calls.append(1),
                    )

        with self.assertRaises(ControlRoomUsageBridgeMisconfigured):
            fetch_control_room_upstream_usage(
                api_origin="https://sportabase-api.example.com",
                admin_api_key=SECRET,
                timeout_seconds=0,
                request_get=lambda *args, **kwargs: calls.append(1),
            )

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
