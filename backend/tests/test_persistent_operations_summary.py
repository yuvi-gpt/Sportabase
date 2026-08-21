from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.operations.persistent_store import (
    PersistentOperationsStoreMisconfigured,
    PersistentOperationsStoreUnavailable,
)
from app.operations.persistent_summary import (
    PERSISTENT_OPERATIONS_SUMMARY_VERSION,
    summarize_persistent_operations,
)


class FakeCursor:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.rows = []
        self.closed = False

    def execute(self, sql, params):
        if self.fail:
            raise RuntimeError("database unavailable")

        if "SELECT status, COUNT(*)" in sql:
            self.rows = [
                ("success", 7),
                ("error", 2),
                ("queued", 1),
            ]
        elif "SELECT component, event_type, status, COUNT(*)" in sql:
            self.rows = [
                ("content_pipeline", "capture.processed", "success", 2),
                ("content_pipeline", "analysis.completed", "success", 3),
                ("content_pipeline", "analysis.failed", "error", 1),
                ("automation_jobs", "job.enqueued", "queued", 1),
                ("automation_jobs", "job.completed", "success", 2),
                ("automation_jobs", "job.failed", "error", 1),
            ]
        elif "SELECT mode, COUNT(*)" in sql:
            self.rows = [
                ("article", 6),
                ("video", 2),
            ]
        elif "source_key" in sql and "MAX(occurred_at)" in sql:
            self.rows = [
                (
                    "example.com",
                    5,
                    4,
                    1,
                    datetime(2026, 8, 21, 18, 0, tzinfo=timezone.utc),
                ),
            ]
        else:
            raise AssertionError("Unexpected SQL")

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, *, fail=False):
        self.cursor_value = FakeCursor(fail=fail)
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


class PersistentOperationsSummaryTests(unittest.TestCase):
    def test_disabled_store_returns_explicit_disabled_summary(self):
        result = summarize_persistent_operations(
            database_url="",
            days=7,
        )

        self.assertEqual(result["state"], "disabled")
        self.assertEqual(result["total_events"], 0)
        self.assertEqual(result["source_health"], [])

    def test_ready_store_returns_bounded_aggregates(self):
        connection = FakeConnection()

        result = summarize_persistent_operations(
            database_url="postgresql://db.example/sportabase",
            days=7,
            now=datetime(2026, 8, 22, tzinfo=timezone.utc),
            connect_factory=lambda *_: connection,
        )

        self.assertEqual(
            result["version"],
            PERSISTENT_OPERATIONS_SUMMARY_VERSION,
        )
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["total_events"], 10)
        self.assertEqual(result["statuses"]["error"], 2)
        self.assertEqual(
            result["pipeline"]["analysis_completed"],
            3,
        )
        self.assertEqual(result["pipeline"]["analysis_failed"], 1)
        self.assertEqual(result["jobs"]["enqueued"], 1)
        self.assertEqual(result["jobs"]["completed"], 2)
        self.assertEqual(result["jobs"]["failed"], 1)
        self.assertEqual(result["modes"]["article"], 6)
        self.assertEqual(
            result["source_health"][0]["source_key"],
            "example.com",
        )
        self.assertEqual(result["source_health"][0]["failures"], 1)
        self.assertNotIn("details_json", result)
        self.assertTrue(connection.closed)
        self.assertTrue(connection.cursor_value.closed)

    def test_invalid_days_fail_closed(self):
        with self.assertRaises(PersistentOperationsStoreMisconfigured):
            summarize_persistent_operations(
                database_url="postgresql://db.example/sportabase",
                days=31,
            )

    def test_naive_clock_is_rejected(self):
        with self.assertRaises(PersistentOperationsStoreMisconfigured):
            summarize_persistent_operations(
                database_url="postgresql://db.example/sportabase",
                days=7,
                now=datetime(2026, 8, 22),
                connect_factory=lambda *_: FakeConnection(),
            )

    def test_query_failure_is_classified_unavailable(self):
        connection = FakeConnection(fail=True)

        with self.assertRaises(PersistentOperationsStoreUnavailable):
            summarize_persistent_operations(
                database_url="postgresql://db.example/sportabase",
                days=7,
                now=datetime(2026, 8, 22, tzinfo=timezone.utc),
                connect_factory=lambda *_: connection,
            )

        self.assertTrue(connection.closed)
        self.assertTrue(connection.cursor_value.closed)


if __name__ == "__main__":
    unittest.main()
