from __future__ import annotations

import sqlite3
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace

from app.db.schema import SCHEMA
from app.services import gemini_capacity
from evals import golden_live_budget


class _FakeResponse:
    def __init__(self, text="{}", usage=None):
        self.text = text
        self.usage_metadata = usage


class _FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response or _FakeResponse()
        self.error = error
        self.calls = []

    def generate_content(self, *, model, contents):
        self.calls.append(
            {
                "model": model,
                "contents": contents,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class _FakeClient:
    def __init__(self, response=None, error=None):
        self.models = _FakeModels(
            response=response,
            error=error,
        )


def _usage_db():
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "usage.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return tmp, path


class TestBudgetContract(unittest.TestCase):
    def test_default_budget_is_twelve(self):
        tmp, path = _usage_db()
        try:
            generator = (
                golden_live_budget
                .BudgetedGeminiGenerator(
                    usage_connection_factory=(
                        golden_live_budget
                        .sqlite_connection_factory(path)
                    )
                )
            )
            self.assertEqual(
                generator.max_calls,
                12,
            )
        finally:
            tmp.cleanup()

    def test_hard_max_is_twelve(self):
        self.assertEqual(
            golden_live_budget
            .HARD_MAX_PROVIDER_CALLS,
            12,
        )

    def test_budget_above_hard_max_rejected(self):
        tmp, path = _usage_db()
        try:
            with self.assertRaises(
                golden_live_budget
                .MultimodalGoldenLiveInputError
            ):
                (
                    golden_live_budget
                    .BudgetedGeminiGenerator(
                        usage_connection_factory=(
                            golden_live_budget
                            .sqlite_connection_factory(path)
                        ),
                        max_calls=13,
                    )
                )
        finally:
            tmp.cleanup()

    def test_zero_budget_blocks_before_provider(self):
        tmp, path = _usage_db()
        try:
            client = _FakeClient()
            generator = (
                golden_live_budget
                .BudgetedGeminiGenerator(
                    usage_connection_factory=(
                        golden_live_budget
                        .sqlite_connection_factory(path)
                    ),
                    max_calls=0,
                )
            )
            with self.assertRaises(
                golden_live_budget
                .MultimodalGoldenLiveBudgetExceeded
            ):
                generator(
                    client=client,
                    client_key="eval34b:test",
                    mode="fusion",
                    model="gemini-test",
                    contents="never sent",
                )
            self.assertEqual(
                client.models.calls,
                [],
            )
        finally:
            tmp.cleanup()

    def test_one_call_uses_real_capacity_ledger(self):
        tmp, path = _usage_db()
        try:
            usage = SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=5,
                thoughts_token_count=3,
                cached_content_token_count=2,
                total_token_count=18,
            )
            client = _FakeClient(
                response=_FakeResponse(
                    usage=usage
                )
            )
            generator = (
                golden_live_budget
                .BudgetedGeminiGenerator(
                    usage_connection_factory=(
                        golden_live_budget
                        .sqlite_connection_factory(path)
                    ),
                    max_calls=1,
                )
            )
            response = generator(
                client=client,
                client_key="eval34b:test",
                mode="fusion",
                model="gemini-test",
                contents="hello",
            )
            self.assertIs(
                response,
                client.models.response,
            )
            self.assertEqual(
                len(client.models.calls),
                1,
            )
            summary = generator.summary()
            self.assertEqual(
                summary["call_count"],
                1,
            )
            self.assertEqual(
                summary["prompt_tokens"],
                10,
            )
            self.assertEqual(
                summary["total_tokens"],
                18,
            )
            self.assertEqual(
                summary["cached_tokens"],
                2,
            )
            self.assertGreater(
                summary["call_log"][0]["usage_id"],
                0,
            )

            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT * FROM gemini_usage "
                    "WHERE cache_hit=0 "
                    "AND inflight_join=0"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "success")
            self.assertEqual(row["prompt_tokens"], 10)
            self.assertEqual(row["output_tokens"], 5)
            self.assertEqual(row["thought_tokens"], 3)
            self.assertEqual(row["total_tokens"], 18)
        finally:
            tmp.cleanup()

    def test_call_log_never_contains_prompt_or_client_key(self):
        tmp, path = _usage_db()
        try:
            client = _FakeClient()
            generator = (
                golden_live_budget
                .BudgetedGeminiGenerator(
                    usage_connection_factory=(
                        golden_live_budget
                        .sqlite_connection_factory(path)
                    ),
                    max_calls=1,
                )
            )
            generator(
                client=client,
                client_key="eval34b:secret-bucket",
                mode="fusion",
                model="gemini-test",
                contents="super-secret-prompt",
            )
            safe = generator.summary()["call_log"]
            serialized = repr(safe)
            self.assertNotIn(
                "super-secret-prompt",
                serialized,
            )
            self.assertNotIn(
                "secret-bucket",
                serialized,
            )
            self.assertNotIn(
                "contents",
                serialized,
            )
            self.assertNotIn(
                "client_key",
                safe[0],
            )
        finally:
            tmp.cleanup()

    def test_capacity_snapshot_accepts_empty_twelve_call_envelope(self):
        tmp, path = _usage_db()
        try:
            snapshot = (
                golden_live_budget
                .capacity_snapshot(
                    usage_connection_factory=(
                        golden_live_budget
                        .sqlite_connection_factory(path)
                    ),
                    model="gemini-3.5-flash",
                    client_keys=(
                        "eval34b:one",
                        "eval34b:two",
                        "eval34b:three",
                    ),
                    required_calls=12,
                    max_calls_per_client=4,
                )
            )
            self.assertTrue(snapshot["ready"])
            self.assertGreaterEqual(
                snapshot["global_remaining"],
                12,
            )
            self.assertGreaterEqual(
                snapshot["model_remaining"],
                12,
            )
        finally:
            tmp.cleanup()

    def test_capacity_snapshot_fails_when_global_headroom_is_below_twelve(self):
        tmp, path = _usage_db()
        try:
            factory = (
                golden_live_budget
                .sqlite_connection_factory(path)
            )
            day = gemini_capacity.provider_usage_day()
            conn = factory()
            try:
                for index in range(5):
                    conn.execute(
                        """
                        INSERT INTO gemini_usage (
                          created_at, usage_day, provider_day,
                          client_key, mode, model, status,
                          cache_hit, inflight_join
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 'success', 0, 0)
                        """,
                        (
                            "2026-08-17T00:00:00+00:00",
                            "2026-08-17",
                            day,
                            "other-" + str(index),
                            "test",
                            "gemini-3.5-flash",
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

            snapshot = (
                golden_live_budget
                .capacity_snapshot(
                    usage_connection_factory=factory,
                    model="gemini-3.5-flash",
                    client_keys=(
                        "eval34b:one",
                        "eval34b:two",
                        "eval34b:three",
                    ),
                    required_calls=12,
                    max_calls_per_client=4,
                )
            )
            self.assertFalse(snapshot["ready"])
            self.assertIn(
                "insufficient_global_provider_day_capacity",
                snapshot["failures"],
            )
        finally:
            tmp.cleanup()

    def test_capacity_snapshot_preserves_pair_fair_share(self):
        tmp, path = _usage_db()
        try:
            snapshot = (
                golden_live_budget
                .capacity_snapshot(
                    usage_connection_factory=(
                        golden_live_budget
                        .sqlite_connection_factory(path)
                    ),
                    model="gemini-3.5-flash",
                    client_keys=(
                        "eval34b:one",
                        "eval34b:two",
                        "eval34b:three",
                    ),
                    required_calls=12,
                    max_calls_per_client=4,
                )
            )
            self.assertEqual(
                snapshot["client_daily_call_cap"],
                8,
            )
            self.assertTrue(
                all(
                    remaining >= 4
                    for remaining in snapshot[
                        "client_remaining"
                    ].values()
                )
            )
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
