from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from app.operations.persistent_store import (
    PersistentOperationsStoreMisconfigured,
    PersistentOperationsStoreUnavailable,
    initialize_persistent_operations_store,
    record_operational_event,
)


DATABASE_URL = "postgresql://user:password@example.com/sportabase"


class _Cursor:
    def __init__(self, calls):
        self.calls = calls
        self.closed = False

    def execute(self, statement, params=None):
        self.calls.append((statement, params))

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self):
        self.calls = []
        self.cursor_instance = _Cursor(self.calls)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class PersistentOperationsStoreTests(unittest.TestCase):
    def test_empty_database_url_disables_store_without_connecting(self):
        calls = []

        initialized = initialize_persistent_operations_store(
            database_url="",
            connect_factory=lambda *args: calls.append(args),
        )
        event_id = record_operational_event(
            database_url="",
            service_name="sportabase-api",
            component="analysis",
            event_type="analysis.completed",
            status="success",
            connect_factory=lambda *args: calls.append(args),
        )

        self.assertIs(initialized, False)
        self.assertIsNone(event_id)
        self.assertEqual(calls, [])

    def test_invalid_database_url_fails_closed_before_network(self):
        calls = []

        for url in (
            "sqlite:///tmp/test.db",
            "http://example.com/database",
            "postgresql://example.com",
            "postgresql:///sportabase",
            "postgresql://example.com/sportabase#fragment",
        ):
            with self.subTest(url=url):
                with self.assertRaises(PersistentOperationsStoreMisconfigured):
                    initialize_persistent_operations_store(
                        database_url=url,
                        connect_factory=lambda *args: calls.append(args),
                    )

        self.assertEqual(calls, [])

    def test_initialization_creates_schema_and_indexes(self):
        connection = _Connection()
        connect_calls = []

        def connect_factory(url, timeout_seconds):
            connect_calls.append((url, timeout_seconds))
            return connection

        result = initialize_persistent_operations_store(
            database_url=DATABASE_URL,
            timeout_seconds=7,
            connect_factory=connect_factory,
        )

        self.assertIs(result, True)
        self.assertEqual(connect_calls, [(DATABASE_URL, 7.0)])
        self.assertGreaterEqual(len(connection.calls), 6)
        executed_sql = "\n".join(call[0] for call in connection.calls)
        self.assertIn("sportabase_operational_events", executed_sql)
        self.assertIn("idx_operational_events_time", executed_sql)
        self.assertIn("idx_operational_events_component_time", executed_sql)
        self.assertEqual(connection.commits, 1)
        self.assertEqual(connection.rollbacks, 0)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertTrue(connection.closed)

    def test_record_event_is_structured_and_redacts_sensitive_details(self):
        connection = _Connection()
        occurred_at = datetime(2026, 8, 21, 17, 30, tzinfo=timezone.utc)
        secret = "super-secret-value"

        event_id = record_operational_event(
            database_url=DATABASE_URL,
            service_name="sportabase-api",
            component="content_pipeline",
            event_type="analysis.completed",
            status="success",
            mode="article",
            source_key="example.com",
            correlation_id="request-123",
            duration_ms=1250,
            details={
                "cache_hit": False,
                "nested": {
                    "token": secret,
                    "safe": "kept",
                },
                "client_key": secret,
            },
            occurred_at=occurred_at,
            event_id="event-123",
            connect_factory=lambda *_: connection,
        )

        self.assertEqual(event_id, "event-123")
        self.assertEqual(len(connection.calls), 1)
        statement, params = connection.calls[0]
        self.assertIn("INSERT INTO sportabase_operational_events", statement)
        self.assertIn("ON CONFLICT (id) DO NOTHING", statement)
        self.assertEqual(params[0], "event-123")
        self.assertEqual(params[1], occurred_at)
        self.assertEqual(params[2], "sportabase-api")
        self.assertEqual(params[3], "content_pipeline")
        self.assertEqual(params[4], "analysis.completed")
        self.assertEqual(params[5], "success")
        self.assertEqual(params[6], "article")
        self.assertEqual(params[7], "example.com")
        self.assertEqual(params[8], "request-123")
        self.assertEqual(params[9], 1250)

        details = json.loads(params[10])
        self.assertEqual(details["nested"]["safe"], "kept")
        self.assertEqual(details["nested"]["token"], "[redacted]")
        self.assertEqual(details["client_key"], "[redacted]")
        self.assertNotIn(secret, params[10])
        self.assertEqual(connection.commits, 1)
        self.assertTrue(connection.closed)

    def test_oversized_details_are_replaced_with_bounded_metadata(self):
        connection = _Connection()

        record_operational_event(
            database_url=DATABASE_URL,
            service_name="sportabase-api",
            component="content_pipeline",
            event_type="analysis.completed",
            status="success",
            details={"text": "x" * 5000},
            maximum_details_bytes=256,
            connect_factory=lambda *_: connection,
        )

        _, params = connection.calls[0]
        details = json.loads(params[10])
        self.assertIs(details["details_truncated"], True)
        self.assertGreater(details["encoded_bytes"], 256)
        self.assertLessEqual(len(params[10].encode("utf-8")), 256)

    def test_naive_timestamp_is_rejected_before_network(self):
        calls = []

        with self.assertRaises(PersistentOperationsStoreMisconfigured):
            record_operational_event(
                database_url=DATABASE_URL,
                service_name="sportabase-api",
                component="analysis",
                event_type="analysis.completed",
                status="success",
                occurred_at=datetime(2026, 8, 21, 17, 30),
                connect_factory=lambda *args: calls.append(args),
            )

        self.assertEqual(calls, [])

    def test_connection_failure_is_wrapped_without_echoing_database_url(self):
        with self.assertRaises(PersistentOperationsStoreUnavailable) as caught:
            initialize_persistent_operations_store(
                database_url=DATABASE_URL,
                connect_factory=lambda *_: (_ for _ in ()).throw(
                    RuntimeError(DATABASE_URL)
                ),
            )

        self.assertNotIn(DATABASE_URL, str(caught.exception))

    def test_write_failure_rolls_back_and_closes(self):
        class BrokenCursor(_Cursor):
            def execute(self, statement, params=None):
                raise RuntimeError("write failed")

        connection = _Connection()
        connection.cursor_instance = BrokenCursor(connection.calls)

        with self.assertRaises(PersistentOperationsStoreUnavailable):
            record_operational_event(
                database_url=DATABASE_URL,
                service_name="sportabase-api",
                component="analysis",
                event_type="analysis.completed",
                status="success",
                connect_factory=lambda *_: connection,
            )

        self.assertEqual(connection.commits, 0)
        self.assertEqual(connection.rollbacks, 1)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
