from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.operations.persistent_runtime import (
    PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
    build_persistent_operations_event_recorder,
    build_persistent_operations_startup_handler,
)
from app.operations.persistent_store import (
    PersistentOperationsStoreMisconfigured,
    PersistentOperationsStoreUnavailable,
)


class PersistentOperationsRuntimeTests(unittest.TestCase):
    def _app(self):
        return SimpleNamespace(state=SimpleNamespace())

    def test_disabled_store_marks_runtime_disabled(self):
        app = self._app()
        calls = []

        handler = build_persistent_operations_startup_handler(
            app=app,
            database_url="",
            timeout_seconds=10,
            initializer=lambda **kwargs: calls.append(kwargs) or False,
        )

        status = handler()

        self.assertEqual(status, "disabled")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["database_url"], "")
        self.assertEqual(calls[0]["timeout_seconds"], 10)
        self.assertEqual(
            getattr(app.state, PERSISTENT_OPERATIONS_STATE_ATTRIBUTE),
            "disabled",
        )

    def test_ready_store_marks_runtime_ready(self):
        app = self._app()

        handler = build_persistent_operations_startup_handler(
            app=app,
            database_url="postgresql://example.com/sportabase",
            timeout_seconds=7,
            initializer=lambda **_: True,
        )

        self.assertEqual(handler(), "ready")
        self.assertEqual(
            getattr(app.state, PERSISTENT_OPERATIONS_STATE_ATTRIBUTE),
            "ready",
        )

    def test_transient_store_outage_does_not_abort_product_startup(self):
        app = self._app()

        def unavailable(**_):
            raise PersistentOperationsStoreUnavailable("temporary outage")

        handler = build_persistent_operations_startup_handler(
            app=app,
            database_url="postgresql://example.com/sportabase",
            timeout_seconds=10,
            initializer=unavailable,
        )

        self.assertEqual(handler(), "unavailable")
        self.assertEqual(
            getattr(app.state, PERSISTENT_OPERATIONS_STATE_ATTRIBUTE),
            "unavailable",
        )

    def test_misconfiguration_still_fails_startup(self):
        app = self._app()

        def misconfigured(**_):
            raise PersistentOperationsStoreMisconfigured("bad configuration")

        handler = build_persistent_operations_startup_handler(
            app=app,
            database_url="bad-url",
            timeout_seconds=10,
            initializer=misconfigured,
        )

        with self.assertRaises(PersistentOperationsStoreMisconfigured):
            handler()

        self.assertFalse(
            hasattr(app.state, PERSISTENT_OPERATIONS_STATE_ATTRIBUTE)
        )

    def test_ready_runtime_recorder_forwards_store_configuration(self):
        app = self._app()
        setattr(
            app.state,
            PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
            "ready",
        )
        calls = []

        recorder = build_persistent_operations_event_recorder(
            app=app,
            database_url="postgresql://example.com/sportabase",
            service_name="sportabase-api",
            timeout_seconds=4,
            recorder=lambda **kwargs: calls.append(kwargs) or "event-1",
        )

        event_id = recorder(
            component="content_pipeline",
            event_type="analysis.completed",
            status="success",
            mode="article",
        )

        self.assertEqual(event_id, "event-1")
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["database_url"],
            "postgresql://example.com/sportabase",
        )
        self.assertEqual(calls[0]["service_name"], "sportabase-api")
        self.assertEqual(calls[0]["timeout_seconds"], 4)
        self.assertEqual(calls[0]["component"], "content_pipeline")

    def test_disabled_or_unavailable_runtime_skips_event_writes(self):
        for state in ("disabled", "unavailable"):
            app = self._app()
            setattr(
                app.state,
                PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
                state,
            )
            calls = []
            recorder = build_persistent_operations_event_recorder(
                app=app,
                database_url="postgresql://example.com/sportabase",
                service_name="sportabase-api",
                timeout_seconds=4,
                recorder=lambda **kwargs: calls.append(kwargs),
            )

            with self.subTest(state=state):
                self.assertIsNone(
                    recorder(
                        component="content_pipeline",
                        event_type="analysis.completed",
                        status="success",
                    )
                )
                self.assertEqual(calls, [])

    def test_runtime_write_outage_trips_fail_open_state(self):
        app = self._app()
        setattr(
            app.state,
            PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
            "ready",
        )
        calls = []

        def unavailable(**kwargs):
            calls.append(kwargs)
            raise PersistentOperationsStoreUnavailable("temporary outage")

        recorder = build_persistent_operations_event_recorder(
            app=app,
            database_url="postgresql://example.com/sportabase",
            service_name="sportabase-api",
            timeout_seconds=4,
            recorder=unavailable,
        )

        self.assertIsNone(
            recorder(
                component="content_pipeline",
                event_type="analysis.completed",
                status="success",
            )
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            getattr(app.state, PERSISTENT_OPERATIONS_STATE_ATTRIBUTE),
            "unavailable",
        )

        self.assertIsNone(
            recorder(
                component="content_pipeline",
                event_type="analysis.completed",
                status="success",
            )
        )
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
