from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import unittest

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.services import gemini_capacity
from app.services import gemini_runtime
from app.services import usage_reporting


_CAPACITY_ENV_KEYS = (
    "SPORTABASE_GEMINI_PROVIDER_RPM",
    "SPORTABASE_GEMINI_DISPATCH_RPM",
    "SPORTABASE_GEMINI_PROVIDER_TPM",
    "SPORTABASE_GEMINI_USABLE_TPM",
    "SPORTABASE_GEMINI_PROVIDER_RPD",
    "SPORTABASE_GEMINI_RPD_RESERVE",
    "SPORTABASE_GEMINI_MAX_ESTIMATED_INPUT_TOKENS",
    "SPORTABASE_GEMINI_MAX_PACING_WAIT_SECONDS",
)


@contextmanager
def capacity_env(**values):
    previous = {
        key: os.environ.get(key)
        for key in _CAPACITY_ENV_KEYS
    }
    try:
        for key in _CAPACITY_ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in values.items():
            os.environ[key] = str(value)
        yield
    finally:
        for key in _CAPACITY_ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in previous.items():
            if value is not None:
                os.environ[key] = value


def factory_for(path: Path):
    def factory():
        conn = sqlite3.connect(
            str(path),
            timeout=30.0,
        )
        conn.row_factory = sqlite3.Row
        return conn

    return factory


def expire_for(conn, **kwargs):
    return gemini_runtime.expire_stale_gemini_reservations(
        conn,
        reservation_timeout_seconds=900,
        **kwargs,
    )


def reserve_at(
    *,
    factory,
    now,
    client="client-a",
    model="gemini-2.5-flash",
    estimate=100,
    global_cap=100,
    client_cap=100,
):
    return gemini_runtime.reserve_gemini_call(
        client,
        "test",
        model,
        usage_day_resolver=lambda: now.date().isoformat(),
        connection_factory=factory,
        expire_reservations=expire_for,
        global_daily_call_cap=global_cap,
        client_daily_call_cap=client_cap,
        estimated_prompt_tokens=estimate,
        now=now,
    )


class _TempDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="sportabase-capacity-test-"
        )
        self.db_path = Path(self.tmp.name) / "capacity.db"
        self.factory = factory_for(self.db_path)
        initialize_database(
            self.factory,
            SCHEMA,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def row_count(self):
        conn = self.factory()
        try:
            return int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM gemini_usage
                    WHERE cache_hit = 0
                      AND inflight_join = 0
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()


class GeminiCapacitySchemaTests(_TempDatabaseTest):
    def test_schema_contains_provider_capacity_columns(self):
        conn = self.factory()
        try:
            columns = {
                str(row["name"])
                for row in conn.execute(
                    "PRAGMA table_info(gemini_usage)"
                ).fetchall()
            }
        finally:
            conn.close()

        self.assertIn("provider_day", columns)
        self.assertIn(
            "estimated_prompt_tokens",
            columns,
        )

    def test_capacity_indexes_exist_after_migration(self):
        conn = self.factory()
        try:
            indexes = {
                str(row["name"])
                for row in conn.execute(
                    "PRAGMA index_list(gemini_usage)"
                ).fetchall()
            }
        finally:
            conn.close()

        self.assertIn(
            "idx_gemini_usage_model_provider_day",
            indexes,
        )
        self.assertIn(
            "idx_gemini_usage_model_created_at",
            indexes,
        )

    def test_migration_is_idempotent(self):
        initialize_database(
            self.factory,
            SCHEMA,
        )
        initialize_database(
            self.factory,
            SCHEMA,
        )

        conn = self.factory()
        try:
            columns = [
                str(row["name"])
                for row in conn.execute(
                    "PRAGMA table_info(gemini_usage)"
                ).fetchall()
            ]
        finally:
            conn.close()

        self.assertEqual(
            columns.count("provider_day"),
            1,
        )
        self.assertEqual(
            columns.count(
                "estimated_prompt_tokens"
            ),
            1,
        )


class GeminiCapacityReservationTests(_TempDatabaseTest):
    def test_reservation_persists_provider_day_and_estimate(self):
        now = datetime(
            2026,
            8,
            17,
            6,
            0,
            tzinfo=timezone.utc,
        )

        usage_id = reserve_at(
            factory=self.factory,
            now=now,
            estimate=321,
        )

        conn = self.factory()
        try:
            row = conn.execute(
                """
                SELECT
                  provider_day,
                  estimated_prompt_tokens,
                  model
                FROM gemini_usage
                WHERE id = ?
                """,
                (usage_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            row["provider_day"],
            "2026-08-16",
        )
        self.assertEqual(
            row["estimated_prompt_tokens"],
            321,
        )
        self.assertEqual(
            row["model"],
            "gemini-2.5-flash",
        )

    def test_model_daily_reserve_allows_sixteen_and_blocks_seventeenth(self):
        start = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        with capacity_env():
            for index in range(16):
                reserve_at(
                    factory=self.factory,
                    now=(
                        start
                        + timedelta(
                            seconds=index * 16
                        )
                    ),
                    estimate=100,
                )

            with self.assertRaises(
                HTTPException
            ) as caught:
                reserve_at(
                    factory=self.factory,
                    now=(
                        start
                        + timedelta(
                            seconds=16 * 16
                        )
                    ),
                    estimate=100,
                )

        self.assertEqual(
            caught.exception.status_code,
            429,
        )
        self.assertIn(
            "daily provider reserve",
            str(caught.exception.detail),
        )
        self.assertEqual(
            self.row_count(),
            16,
        )

    def test_different_models_have_separate_provider_rpd_buckets(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        first = reserve_at(
            factory=self.factory,
            now=now,
            model="gemini-a",
        )
        second = reserve_at(
            factory=self.factory,
            now=now,
            model="gemini-b",
        )

        self.assertNotEqual(
            first,
            second,
        )
        self.assertEqual(
            self.row_count(),
            2,
        )

    def test_global_fairness_cap_prevents_model_pooling(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        reserve_at(
            factory=self.factory,
            now=now,
            client="a",
            model="gemini-a",
            global_cap=2,
        )
        reserve_at(
            factory=self.factory,
            now=now,
            client="b",
            model="gemini-b",
            global_cap=2,
        )

        with self.assertRaises(
            HTTPException
        ) as caught:
            reserve_at(
                factory=self.factory,
                now=now,
                client="c",
                model="gemini-c",
                global_cap=2,
            )

        self.assertEqual(
            caught.exception.status_code,
            429,
        )
        self.assertIn(
            "beta AI capacity",
            str(caught.exception.detail),
        )

    def test_client_fairness_cap_spans_models(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        reserve_at(
            factory=self.factory,
            now=now,
            client="same-client",
            model="gemini-a",
            client_cap=1,
        )

        with self.assertRaises(
            HTTPException
        ) as caught:
            reserve_at(
                factory=self.factory,
                now=now,
                client="same-client",
                model="gemini-b",
                client_cap=1,
            )

        self.assertEqual(
            caught.exception.status_code,
            429,
        )
        self.assertIn(
            "fair-share",
            str(caught.exception.detail),
        )

    def test_same_model_immediate_second_call_is_paced_without_reservation(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        reserve_at(
            factory=self.factory,
            now=now,
        )

        with self.assertRaises(
            gemini_capacity.GeminiCapacityPacingRequired
        ) as caught:
            reserve_at(
                factory=self.factory,
                now=now + timedelta(seconds=1),
            )

        self.assertEqual(
            caught.exception.reason,
            "rpm",
        )
        self.assertGreater(
            caught.exception.wait_seconds,
            13.0,
        )
        self.assertEqual(
            self.row_count(),
            1,
        )

    def test_same_model_is_allowed_after_dispatch_interval(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        reserve_at(
            factory=self.factory,
            now=now,
        )
        reserve_at(
            factory=self.factory,
            now=now + timedelta(seconds=16),
        )

        self.assertEqual(
            self.row_count(),
            2,
        )

    def test_tpm_soft_limit_paces_before_provider_reservation(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        with capacity_env(
            SPORTABASE_GEMINI_PROVIDER_TPM=250,
            SPORTABASE_GEMINI_USABLE_TPM=100,
            SPORTABASE_GEMINI_MAX_ESTIMATED_INPUT_TOKENS=100,
        ):
            reserve_at(
                factory=self.factory,
                now=now,
                estimate=60,
            )

            with self.assertRaises(
                gemini_capacity.GeminiCapacityPacingRequired
            ) as caught:
                reserve_at(
                    factory=self.factory,
                    now=now + timedelta(seconds=16),
                    estimate=60,
                )

        self.assertEqual(
            caught.exception.reason,
            "tpm",
        )
        self.assertEqual(
            self.row_count(),
            1,
        )

    def test_request_above_estimated_input_guard_is_rejected_before_insert(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        with self.assertRaises(
            HTTPException
        ) as caught:
            reserve_at(
                factory=self.factory,
                now=now,
                estimate=50_001,
            )

        self.assertEqual(
            caught.exception.status_code,
            429,
        )
        self.assertEqual(
            self.row_count(),
            0,
        )

    def test_cache_hit_and_inflight_join_do_not_consume_provider_capacity(self):
        for index in range(30):
            gemini_runtime.record_analysis_cache_hit(
                f"cache-{index}",
                "article",
                connection_factory=self.factory,
                usage_day_resolver=lambda: "2026-08-17",
            )
            gemini_runtime.record_inflight_gemini_join(
                client_key=f"join-{index}",
                mode="article",
                model="gemini-2.5-flash",
                succeeded=True,
                connection_factory=self.factory,
                usage_day_resolver=lambda: "2026-08-17",
            )

        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        reserve_at(
            factory=self.factory,
            now=now,
            global_cap=1,
            client_cap=1,
        )

        self.assertEqual(
            self.row_count(),
            1,
        )

    def test_finish_reconciles_estimate_to_exact_prompt_tokens(self):
        now = datetime(
            2026,
            8,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        )

        usage_id = reserve_at(
            factory=self.factory,
            now=now,
            estimate=1_000,
        )

        response = SimpleNamespace(
            usage_metadata={
                "prompt_token_count": 7,
                "candidates_token_count": 5,
                "thoughts_token_count": 3,
                "total_token_count": 15,
            }
        )

        counts = gemini_runtime.finish_gemini_call(
            usage_id,
            "success",
            response,
            usage_counter=(
                gemini_runtime
                .usage_metadata_counts
            ),
            connection_factory=self.factory,
        )

        conn = self.factory()
        try:
            row = conn.execute(
                """
                SELECT
                  status,
                  estimated_prompt_tokens,
                  prompt_tokens,
                  total_tokens
                FROM gemini_usage
                WHERE id = ?
                """,
                (usage_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            counts["prompt_tokens"],
            7,
        )
        self.assertEqual(
            row["status"],
            "success",
        )
        self.assertEqual(
            row["estimated_prompt_tokens"],
            1_000,
        )
        self.assertEqual(
            row["prompt_tokens"],
            7,
        )
        self.assertEqual(
            row["total_tokens"],
            15,
        )

    def test_admin_usage_reports_provider_day_capacity_separately_from_utc_analytics(self):
        now = datetime(
            2026,
            8,
            17,
            6,
            0,
            tzinfo=timezone.utc,
        )

        reserve_at(
            factory=self.factory,
            now=now,
            estimate=100,
            global_cap=16,
            client_cap=8,
        )

        def derived(summary):
            return usage_reporting.usage_derived_metrics(
                summary,
                input_cost_per_million_usd=0.0,
                output_cost_per_million_usd=0.0,
                global_daily_call_cap=16,
            )

        def savings(summary):
            return usage_reporting.usage_savings_metrics(
                summary,
                input_cost_per_million_usd=0.0,
                output_cost_per_million_usd=0.0,
            )

        def mode_metrics(summary):
            return usage_reporting.usage_mode_metrics(
                summary,
                derived_metrics_resolver=derived,
                savings_metrics_resolver=savings,
            )

        summary = usage_reporting.admin_usage_summary(
            days=1,
            connection_factory=self.factory,
            usage_day_resolver=lambda: "2026-08-17",
            expire_reservations=expire_for,
            derived_metrics_resolver=derived,
            mode_metrics_resolver=mode_metrics,
            scope_savings_resolver=(
                usage_reporting
                .usage_scope_savings_summary
            ),
            reservation_timeout_seconds=900,
            global_daily_call_cap=16,
            client_daily_call_cap=8,
            input_cost_per_million_usd=0.0,
            output_cost_per_million_usd=0.0,
            provider_day_resolver=lambda: "2026-08-16",
            capacity_policy_resolver=(
                gemini_capacity
                .capacity_policy_for_model
            ),
        )

        provider = summary[
            "provider_capacity"
        ]

        self.assertEqual(
            summary["usage_day_utc"],
            "2026-08-17",
        )
        self.assertEqual(
            provider["provider_day"],
            "2026-08-16",
        )
        self.assertEqual(
            provider["provider_timezone"],
            "America/Los_Angeles",
        )
        self.assertEqual(
            provider["provider_attempts"],
            1,
        )
        self.assertEqual(
            provider["global_calls_remaining"],
            15,
        )
        self.assertEqual(
            provider["highest_client_calls_remaining"],
            7,
        )
        self.assertEqual(
            provider["by_model"][0]["usable_rpd"],
            16,
        )
        self.assertEqual(
            provider["by_model"][0]["rpd_remaining"],
            15,
        )


class GeminiCapacityGenerationTests(unittest.TestCase):
    def test_generate_waits_out_internal_pacing_then_calls_provider_once(self):
        calls = []
        sleeps = []

        class Models:
            def generate_content(self, *, model, contents):
                calls.append(
                    (model, contents)
                )
                return SimpleNamespace(
                    usage_metadata={
                        "prompt_token_count": 3,
                        "total_token_count": 4,
                    }
                )

        client = SimpleNamespace(
            models=Models()
        )

        attempts = {"count": 0}

        def reserve_call(**kwargs):
            attempts["count"] += 1
            self.assertGreater(
                kwargs[
                    "estimated_prompt_tokens"
                ],
                0,
            )
            if attempts["count"] == 1:
                raise (
                    gemini_capacity
                    .GeminiCapacityPacingRequired(
                        wait_seconds=1.25,
                        reason="rpm",
                    )
                )
            return 9

        finished = []

        def finish_call(*args, **kwargs):
            finished.append(
                (args, kwargs)
            )

        result = gemini_runtime.generate_gemini_content(
            client=client,
            client_key="client",
            mode="article",
            model="gemini-2.5-flash",
            contents="hello",
            inflight_lock=threading.Lock(),
            inflight_calls={},
            fingerprint_resolver=(
                gemini_runtime
                .gemini_request_fingerprint
            ),
            reserve_call=reserve_call,
            finish_call=finish_call,
            classify_failure=(
                gemini_runtime
                .classify_gemini_failure
            ),
            record_join=lambda **kwargs: None,
            sleep_func=sleeps.append,
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            sleeps,
            [1.25],
        )
        self.assertEqual(
            attempts["count"],
            2,
        )
        self.assertEqual(
            len(calls),
            1,
        )
        self.assertEqual(
            len(finished),
            1,
        )

    def test_generate_stops_before_provider_when_pacing_wait_exceeds_budget(self):
        provider_calls = []

        class Models:
            def generate_content(self, *, model, contents):
                provider_calls.append(1)
                return SimpleNamespace()

        def reserve_call(**kwargs):
            raise (
                gemini_capacity
                .GeminiCapacityPacingRequired(
                    wait_seconds=76.0,
                    reason="rpm",
                )
            )

        with capacity_env():
            with self.assertRaises(
                HTTPException
            ) as caught:
                gemini_runtime.generate_gemini_content(
                    client=SimpleNamespace(
                        models=Models()
                    ),
                    client_key="client",
                    mode="article",
                    model="gemini-2.5-flash",
                    contents="hello",
                    inflight_lock=threading.Lock(),
                    inflight_calls={},
                    fingerprint_resolver=(
                        gemini_runtime
                        .gemini_request_fingerprint
                    ),
                    reserve_call=reserve_call,
                    finish_call=lambda *args, **kwargs: None,
                    classify_failure=(
                        gemini_runtime
                        .classify_gemini_failure
                    ),
                    record_join=lambda **kwargs: None,
                    sleep_func=lambda seconds: None,
                )

        self.assertEqual(
            caught.exception.status_code,
            429,
        )
        self.assertEqual(
            provider_calls,
            [],
        )

    def test_provider_503_still_classifies_as_capacity_not_quota(self):
        error = RuntimeError(
            "503 service unavailable"
        )

        result = (
            gemini_runtime
            .classify_gemini_failure(
                error
            )
        )

        self.assertEqual(
            result["failure_status_code"],
            503,
        )
        self.assertEqual(
            result["failure_type"],
            "provider_capacity",
        )


class GeminiCapacityLegacyMigrationTests(unittest.TestCase):
    def test_old_provider_rows_are_backfilled_to_pacific_provider_day(self):
        with tempfile.TemporaryDirectory(
            prefix="sportabase-capacity-legacy-"
        ) as tmp:
            path = Path(tmp) / "legacy.db"
            factory = factory_for(path)

            conn = factory()
            try:
                conn.execute(
                    """
                    CREATE TABLE gemini_usage (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      created_at TEXT NOT NULL,
                      usage_day TEXT NOT NULL,
                      client_key TEXT NOT NULL,
                      mode TEXT NOT NULL,
                      model TEXT NOT NULL,
                      status TEXT NOT NULL,
                      prompt_tokens INTEGER NOT NULL DEFAULT 0,
                      output_tokens INTEGER NOT NULL DEFAULT 0,
                      thought_tokens INTEGER NOT NULL DEFAULT 0,
                      total_tokens INTEGER NOT NULL DEFAULT 0,
                      cache_hit INTEGER NOT NULL DEFAULT 0,
                      inflight_join INTEGER NOT NULL DEFAULT 0,
                      latency_ms INTEGER NOT NULL DEFAULT 0,
                      failure_status_code INTEGER,
                      failure_type TEXT NOT NULL DEFAULT '',
                      failure_detail TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO gemini_usage (
                      created_at,
                      usage_day,
                      client_key,
                      mode,
                      model,
                      status
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "2026-08-17T06:00:00+00:00",
                        "2026-08-17",
                        "legacy-client",
                        "video_analysis",
                        "gemini-2.5-flash",
                        "success",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            initialize_database(
                factory,
                SCHEMA,
            )

            conn = factory()
            try:
                row = conn.execute(
                    """
                    SELECT
                      provider_day,
                      estimated_prompt_tokens
                    FROM gemini_usage
                    WHERE client_key = 'legacy-client'
                    """
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(
            row["provider_day"],
            "2026-08-16",
        )
        self.assertEqual(
            row["estimated_prompt_tokens"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
