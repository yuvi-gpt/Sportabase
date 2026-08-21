from __future__ import annotations

import unittest

from app.operations.control_room_cold_start import (
    CONTROL_ROOM_UPSTREAM_TOTAL_WAIT_BUDGET_SECONDS,
    build_cold_start_timeout_plan,
    fetch_with_cold_start_resilience,
)
from app.operations.control_room_usage_bridge import (
    ControlRoomUsageBridgeMisconfigured,
    ControlRoomUsageBridgeUnavailable,
)


class ControlRoomColdStartTests(unittest.TestCase):
    def test_default_ten_second_primary_plan_fits_measured_cold_start(self):
        self.assertEqual(
            build_cold_start_timeout_plan(10),
            (10.0, 60.0, 10.0),
        )

    def test_plan_stays_within_total_wait_budget(self):
        for primary in (1, 5, 10, 30, 45, 60):
            with self.subTest(primary=primary):
                plan = build_cold_start_timeout_plan(primary)
                self.assertLessEqual(
                    sum(plan),
                    CONTROL_ROOM_UPSTREAM_TOTAL_WAIT_BUDGET_SECONDS,
                )
                self.assertTrue(all(timeout > 0 for timeout in plan))
                self.assertTrue(all(timeout <= 60 for timeout in plan))

        self.assertEqual(
            build_cold_start_timeout_plan(60),
            (60.0, 30.0),
        )

    def test_first_failure_then_long_retry_success(self):
        calls = []

        def usage_fetcher(timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise ControlRoomUsageBridgeUnavailable("cold")
            return {"ok": True}

        result = fetch_with_cold_start_resilience(
            usage_fetcher=usage_fetcher,
            primary_timeout_seconds=10,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls, [10.0, 60.0])

    def test_fast_failure_then_long_timeout_then_final_retry_success(self):
        calls = []

        def usage_fetcher(timeout):
            calls.append(timeout)
            if len(calls) < 3:
                raise ControlRoomUsageBridgeUnavailable("still waking")
            return {"ok": True}

        result = fetch_with_cold_start_resilience(
            usage_fetcher=usage_fetcher,
            primary_timeout_seconds=10,
        )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls, [10.0, 60.0, 10.0])

    def test_all_attempts_unavailable_fail_closed_after_bounded_retries(self):
        calls = []

        def usage_fetcher(timeout):
            calls.append(timeout)
            raise ControlRoomUsageBridgeUnavailable("unavailable")

        with self.assertRaises(ControlRoomUsageBridgeUnavailable):
            fetch_with_cold_start_resilience(
                usage_fetcher=usage_fetcher,
                primary_timeout_seconds=10,
            )

        self.assertEqual(calls, [10.0, 60.0, 10.0])

    def test_misconfiguration_is_not_retried(self):
        calls = []

        def usage_fetcher(timeout):
            calls.append(timeout)
            raise ControlRoomUsageBridgeMisconfigured("bad config")

        with self.assertRaises(ControlRoomUsageBridgeMisconfigured):
            fetch_with_cold_start_resilience(
                usage_fetcher=usage_fetcher,
                primary_timeout_seconds=10,
            )

        self.assertEqual(calls, [10.0])

    def test_invalid_primary_timeout_fails_before_fetch(self):
        calls = []

        for primary in (0, -1, 61, "bad"):
            with self.subTest(primary=primary):
                with self.assertRaises(ControlRoomUsageBridgeMisconfigured):
                    fetch_with_cold_start_resilience(
                        usage_fetcher=lambda timeout: calls.append(timeout),
                        primary_timeout_seconds=primary,
                    )

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
