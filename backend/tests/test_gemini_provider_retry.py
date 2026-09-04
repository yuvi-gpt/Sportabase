import threading
import time
import sqlite3
import tempfile
import unittest

import httpx

from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from pathlib import Path
from types import SimpleNamespace

from app.ai import generation
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA


class ProviderStatusError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(f"provider status {code}")


class RetryHarness:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.provider_calls = []
        self.reservations = []
        self.rows = []
        self.joins = []
        self.sleeps = []
        self.inflight_calls = {}
        self.inflight_lock = threading.Lock()

        harness = self

        class Models:
            def generate_content(self, *, model, contents):
                harness.provider_calls.append(
                    (model, contents)
                )
                outcome = harness.outcomes.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

        self.client = SimpleNamespace(
            models=Models()
        )

    def reserve(self, **kwargs):
        usage_id = len(self.reservations) + 1
        self.reservations.append(
            (usage_id, kwargs)
        )
        return usage_id

    def finish(self, usage_id, status, response=None, **kwargs):
        self.rows.append(
            {
                "usage_id": usage_id,
                "status": status,
                "response": response,
                **kwargs,
            }
        )

    def generate(self, **overrides):
        kwargs = {
            "client": self.client,
            "client_key": "client",
            "mode": "article_tldr",
            "model": "gemini-3.5-flash",
            "contents": "same prompt",
            "inflight_lock": self.inflight_lock,
            "inflight_calls": self.inflight_calls,
            "fingerprint_resolver": (
                generation.gemini_request_fingerprint
            ),
            "reserve_call": self.reserve,
            "finish_call": self.finish,
            "classify_failure": (
                generation.classify_gemini_failure
            ),
            "record_join": (
                lambda **kwargs: self.joins.append(
                    kwargs
                )
            ),
            "sleep_func": self.sleeps.append,
        }
        kwargs.update(overrides)
        return generation.generate_gemini_content(
            **kwargs
        )


class GeminiProviderRetryTests(unittest.TestCase):
    def test_normal_success_is_one_accounted_attempt(self):
        response = SimpleNamespace(text="ok")
        harness = RetryHarness([response])

        result = harness.generate()

        self.assertIs(result, response)
        self.assertEqual(len(harness.reservations), 1)
        self.assertEqual(len(harness.provider_calls), 1)
        self.assertEqual(
            [row["status"] for row in harness.rows],
            ["success"],
        )
        self.assertEqual(harness.sleeps, [])

    def test_selected_5xx_recovers_with_independent_attempts(self):
        expected_types = {
            500: "provider_error",
            502: "provider_error",
            503: "provider_capacity",
            504: "provider_error",
        }

        for code, failure_type in expected_types.items():
            with self.subTest(code=code):
                response = SimpleNamespace(text="ok")
                harness = RetryHarness(
                    [ProviderStatusError(code), response]
                )

                result = harness.generate()

                self.assertIs(result, response)
                self.assertEqual(
                    len(harness.provider_calls),
                    2,
                )
                self.assertEqual(
                    [row["usage_id"] for row in harness.rows],
                    [1, 2],
                )
                self.assertEqual(
                    [row["status"] for row in harness.rows],
                    ["failed", "success"],
                )
                self.assertEqual(
                    harness.rows[0]["failure_status_code"],
                    code,
                )
                self.assertEqual(
                    harness.rows[0]["failure_type"],
                    failure_type,
                )
                self.assertEqual(harness.sleeps, [1.0])
                self.assertEqual(
                    harness.provider_calls[0],
                    harness.provider_calls[1],
                )

    def test_timeout_and_connect_error_recover_once(self):
        request = httpx.Request(
            "POST",
            "https://example.invalid",
        )
        cases = (
            (
                httpx.TimeoutException(
                    "timeout",
                    request=request,
                ),
                "timeout",
            ),
            (
                httpx.ConnectError(
                    "connect",
                    request=request,
                ),
                "network",
            ),
        )

        for error, failure_type in cases:
            with self.subTest(error=type(error).__name__):
                harness = RetryHarness(
                    [error, SimpleNamespace(text="ok")]
                )

                harness.generate()

                self.assertEqual(
                    len(harness.provider_calls),
                    2,
                )
                self.assertEqual(
                    harness.rows[0]["failure_type"],
                    failure_type,
                )
                self.assertEqual(
                    [row["status"] for row in harness.rows],
                    ["failed", "success"],
                )
                self.assertEqual(harness.sleeps, [1.0])

    def test_retry_exhaustion_stops_after_two_attempts(self):
        first = ProviderStatusError(503)
        terminal = ProviderStatusError(500)
        harness = RetryHarness([first, terminal])

        with self.assertRaises(ProviderStatusError) as caught:
            harness.generate()

        self.assertIs(caught.exception, terminal)
        self.assertEqual(len(harness.provider_calls), 2)
        self.assertEqual(len(harness.reservations), 2)
        self.assertEqual(
            [row["status"] for row in harness.rows],
            ["failed", "failed"],
        )
        self.assertEqual(harness.sleeps, [1.0])

    def test_non_retryable_failures_stop_after_one_attempt(self):
        request = httpx.Request(
            "POST",
            "https://example.invalid",
        )
        cases = (
            ProviderStatusError(429),
            ProviderStatusError(400),
            ProviderStatusError(401),
            ProviderStatusError(403),
            RuntimeError("unknown"),
            RuntimeError("503 service unavailable"),
            httpx.ReadError("read", request=request),
            httpx.WriteError("write", request=request),
        )

        for error in cases:
            with self.subTest(error=type(error).__name__):
                harness = RetryHarness([error])

                with self.assertRaises(type(error)):
                    harness.generate()

                self.assertEqual(
                    len(harness.provider_calls),
                    1,
                )
                self.assertEqual(len(harness.rows), 1)
                self.assertEqual(
                    harness.rows[0]["status"],
                    "failed",
                )
                self.assertEqual(harness.sleeps, [])

        rate_limit = RetryHarness(
            [ProviderStatusError(429)]
        )
        with self.assertRaises(ProviderStatusError):
            rate_limit.generate()
        self.assertEqual(
            rate_limit.rows[0]["failure_status_code"],
            429,
        )
        self.assertEqual(
            rate_limit.rows[0]["failure_type"],
            "rate_limit",
        )

    def test_initial_local_capacity_failure_never_dispatches(self):
        local_error = HTTPException(
            status_code=429,
            detail="local capacity",
        )
        harness = RetryHarness([])

        with self.assertRaises(HTTPException) as caught:
            harness.generate(
                reserve_call=lambda **kwargs: (
                    (_ for _ in ()).throw(local_error)
                )
            )

        self.assertIs(caught.exception, local_error)
        self.assertEqual(harness.provider_calls, [])
        self.assertEqual(harness.rows, [])
        self.assertEqual(harness.sleeps, [])

    def test_retry_reservation_failure_cannot_refinalize_first_row(self):
        local_error = HTTPException(
            status_code=429,
            detail="retry capacity exhausted",
        )
        harness = RetryHarness(
            [ProviderStatusError(503)]
        )
        reservation_count = 0

        def reserve(**kwargs):
            nonlocal reservation_count
            reservation_count += 1
            if reservation_count == 2:
                raise local_error
            return 41

        with self.assertRaises(HTTPException) as caught:
            harness.generate(reserve_call=reserve)

        self.assertIs(caught.exception, local_error)
        self.assertEqual(len(harness.provider_calls), 1)
        self.assertEqual(harness.sleeps, [1.0])
        self.assertEqual(
            harness.rows,
            [
                {
                    "usage_id": 41,
                    "status": "failed",
                    "response": None,
                    "latency_ms": harness.rows[0]["latency_ms"],
                    "failure_status_code": 503,
                    "failure_type": "provider_capacity",
                    "failure_detail": harness.rows[0]["failure_detail"],
                }
            ],
        )

    def test_finalization_failure_prevents_retry(self):
        accounting_error = RuntimeError(
            "ledger unavailable"
        )
        harness = RetryHarness(
            [ProviderStatusError(503)]
        )

        with self.assertRaises(RuntimeError) as caught:
            harness.generate(
                finish_call=lambda *args, **kwargs: (
                    (_ for _ in ()).throw(
                        accounting_error
                    )
                )
            )

        self.assertIs(caught.exception, accounting_error)
        self.assertEqual(len(harness.provider_calls), 1)
        self.assertEqual(len(harness.reservations), 1)
        self.assertEqual(harness.sleeps, [])


class GeminiProviderRetryInflightTests(unittest.TestCase):
    def _run_pair(self, outcomes):
        harness = RetryHarness(outcomes)
        original_generate = (
            harness.client.models.generate_content
        )
        provider_entered = threading.Event()
        release_provider = threading.Event()
        first_call = True

        def controlled_generate(*, model, contents):
            nonlocal first_call
            if first_call:
                first_call = False
                provider_entered.set()
                release_provider.wait(timeout=2.0)
            return original_generate(
                model=model,
                contents=contents,
            )

        harness.client.models.generate_content = (
            controlled_generate
        )
        results = []
        errors = []

        def invoke():
            try:
                results.append(harness.generate())
            except Exception as error:
                errors.append(error)

        leader = threading.Thread(target=invoke)
        follower = threading.Thread(target=invoke)
        leader.start()
        self.assertTrue(provider_entered.wait(timeout=2.0))
        follower.start()
        time.sleep(0.05)
        release_provider.set()
        leader.join(timeout=2.0)
        follower.join(timeout=2.0)

        self.assertFalse(leader.is_alive())
        self.assertFalse(follower.is_alive())
        return harness, results, errors

    def test_follower_joins_retry_then_success(self):
        response = SimpleNamespace(text="ok")
        harness, results, errors = self._run_pair(
            [ProviderStatusError(503), response]
        )

        self.assertEqual(errors, [])
        self.assertEqual(results, [response, response])
        self.assertEqual(len(harness.provider_calls), 2)
        self.assertEqual(len(harness.reservations), 2)
        self.assertEqual(
            harness.joins,
            [
                {
                    "client_key": "client",
                    "mode": "article_tldr",
                    "model": "gemini-3.5-flash",
                    "succeeded": True,
                }
            ],
        )

    def test_follower_receives_terminal_retry_failure(self):
        terminal = ProviderStatusError(503)
        harness, results, errors = self._run_pair(
            [ProviderStatusError(503), terminal]
        )

        self.assertEqual(results, [])
        self.assertEqual(len(errors), 2)
        self.assertTrue(
            all(error is terminal for error in errors)
        )
        self.assertEqual(len(harness.provider_calls), 2)
        self.assertEqual(len(harness.reservations), 2)
        self.assertEqual(
            [row["status"] for row in harness.rows],
            ["failed", "failed"],
        )
        self.assertEqual(
            harness.joins[0]["succeeded"],
            False,
        )


class GeminiProviderRetryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="sportabase-retry-ledger-"
        )
        self.path = Path(self.tmp.name) / "usage.db"
        initialize_database(self.connect, SCHEMA)
        self.now = datetime(
            2026,
            9,
            4,
            12,
            0,
            tzinfo=timezone.utc,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def connect(self):
        conn = sqlite3.connect(
            str(self.path),
            timeout=30.0,
        )
        conn.row_factory = sqlite3.Row
        return conn

    def reserve(self, *, global_cap=10):
        attempt = 0

        def reserve_call(**kwargs):
            nonlocal attempt
            current = self.now + timedelta(
                seconds=attempt * 16
            )
            attempt += 1
            return generation.reserve_gemini_call(
                kwargs["client_key"],
                kwargs["mode"],
                kwargs["model"],
                usage_day_resolver=(
                    lambda: "2026-09-04"
                ),
                connection_factory=self.connect,
                expire_reservations=(
                    lambda conn, **expire_kwargs: (
                        generation
                        .expire_stale_gemini_reservations(
                            conn,
                            reservation_timeout_seconds=900,
                            **expire_kwargs,
                        )
                    )
                ),
                global_daily_call_cap=global_cap,
                client_daily_call_cap=global_cap,
                estimated_prompt_tokens=kwargs[
                    "estimated_prompt_tokens"
                ],
                now=current,
            )

        return reserve_call

    def finish(self, *args, **kwargs):
        return generation.finish_gemini_call(
            *args,
            **kwargs,
            usage_counter=(
                generation.usage_metadata_counts
            ),
            connection_factory=self.connect,
        )

    def rows(self):
        conn = self.connect()
        try:
            return conn.execute(
                """
                SELECT
                  id,
                  status,
                  failure_status_code,
                  failure_type,
                  cache_hit,
                  inflight_join
                FROM gemini_usage
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

    def test_transient_retry_uses_two_real_usage_rows(self):
        response = SimpleNamespace(
            text="ok",
            usage_metadata={
                "prompt_token_count": 4,
                "total_token_count": 5,
            },
        )
        harness = RetryHarness(
            [ProviderStatusError(503), response]
        )

        harness.generate(
            reserve_call=self.reserve(),
            finish_call=self.finish,
        )

        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [row["status"] for row in rows],
            ["failed", "success"],
        )
        self.assertEqual(
            rows[0]["failure_status_code"],
            503,
        )
        self.assertEqual(
            rows[0]["failure_type"],
            "provider_capacity",
        )
        self.assertTrue(
            all(
                row["cache_hit"] == 0
                and row["inflight_join"] == 0
                for row in rows
            )
        )

    def test_failed_attempt_consumes_cap_and_retry_cannot_overwrite_it(self):
        harness = RetryHarness(
            [ProviderStatusError(503)]
        )

        with self.assertRaises(HTTPException) as caught:
            harness.generate(
                reserve_call=self.reserve(
                    global_cap=1
                ),
                finish_call=self.finish,
            )

        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(len(harness.provider_calls), 1)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "failed")
        self.assertEqual(
            rows[0]["failure_status_code"],
            503,
        )
        self.assertEqual(
            rows[0]["failure_type"],
            "provider_capacity",
        )


if __name__ == "__main__":
    unittest.main()
