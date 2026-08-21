from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.operations import job_worker_runtime
from app.workflows import browser_capture_automation


class FakeApp:
    def __init__(self):
        self.handlers = []

    def add_event_handler(self, event, handler):
        self.handlers.append((event, handler))


class PersistentJobWorkerRuntimeTests(unittest.TestCase):
    def setUp(self):
        job_worker_runtime.stop_persistent_job_worker(
            join_timeout_seconds=0.1
        )

    def tearDown(self):
        job_worker_runtime.stop_persistent_job_worker(
            join_timeout_seconds=0.1
        )

    @staticmethod
    def disabled_env(key, default=None):
        if key == browser_capture_automation.BROWSER_CAPTURE_AUTOMATION_FLAG:
            return "0"
        return default

    def test_version_is_v1(self):
        self.assertEqual(
            job_worker_runtime.PERSISTENT_JOB_WORKER_RUNTIME_VERSION,
            "sportabase-persistent-job-worker-runtime-v1",
        )

    def test_disabled_worker_never_initializes_provider(self):
        provider_calls = []

        result = job_worker_runtime.start_persistent_job_worker(
            connection_factory=lambda: None,
            analysis_version="analysis-v1",
            scoring_version="score-v1",
            gemini_client_factory=lambda: provider_calls.append(True),
            gemini_generator=lambda *args, **kwargs: None,
            env_getter=self.disabled_env,
        )

        self.assertEqual(result["status"], "disabled")
        self.assertEqual(provider_calls, [])

    def test_lifecycle_registration_uses_fastapi_compatibility_hooks(self):
        app = FakeApp()

        result = job_worker_runtime.register_persistent_job_worker_lifecycle(
            app=app,
            connection_factory=lambda: None,
            analysis_version="analysis-v1",
            scoring_version="score-v1",
            gemini_client_factory=lambda: None,
            gemini_generator=lambda *args, **kwargs: None,
            env_getter=self.disabled_env,
        )

        self.assertEqual(result["status"], "registered")
        self.assertEqual(
            [event for event, _ in app.handlers],
            ["startup", "shutdown"],
        )
        self.assertEqual(app.handlers[0][1]()["status"], "disabled")
        self.assertEqual(app.handlers[1][1]()["status"], "stopped")

    def test_reconcile_event_is_aggregate_and_privacy_minimized(self):
        events = []

        job_worker_runtime._emit_reconcile_event(
            lambda **event: events.append(event),
            {
                "status": "reconciled",
                "created": 3,
                "examined": 8,
                "capture_record_ids": ["private-id"],
            },
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_type"], "job.reconciled")
        self.assertEqual(event["details"]["created"], 3)
        self.assertEqual(event["details"]["examined"], 8)
        self.assertNotIn("capture_record_ids", event["details"])

    def test_reconcile_event_failure_is_fail_open(self):
        def broken(**_):
            raise RuntimeError("telemetry down")

        job_worker_runtime._emit_reconcile_event(
            broken,
            {"created": 1, "examined": 1},
        )

    def test_enabled_start_uses_instrumented_worker_thread(self):
        class FakeThread:
            def __init__(self, *, target, args, name, daemon):
                self.target = target
                self.args = args
                self.name = name
                self.daemon = daemon
                self.started = False

            def start(self):
                self.started = True

            def is_alive(self):
                return self.started

            def join(self, timeout=None):
                self.started = False

        def enabled_env(key, default=None):
            if key == browser_capture_automation.BROWSER_CAPTURE_AUTOMATION_FLAG:
                return "1"
            if key == browser_capture_automation.BROWSER_CAPTURE_AUTOMATION_POLL_SECONDS:
                return "3"
            return default

        with patch.object(
            job_worker_runtime.threading,
            "Thread",
            FakeThread,
        ):
            result = job_worker_runtime.start_persistent_job_worker(
                connection_factory=lambda: SimpleNamespace(),
                analysis_version="analysis-v1",
                scoring_version="score-v1",
                gemini_client_factory=lambda: None,
                gemini_generator=lambda *args, **kwargs: None,
                env_getter=enabled_env,
            )

            self.assertEqual(result["status"], "started")
            thread = job_worker_runtime._WORKER_THREAD
            self.assertIsNotNone(thread)
            self.assertEqual(
                thread.name,
                "sportabase-persistent-job-worker",
            )
            self.assertTrue(thread.daemon)

            stopped = job_worker_runtime.stop_persistent_job_worker(
                join_timeout_seconds=0.1
            )
            self.assertEqual(stopped["status"], "stopped")


if __name__ == "__main__":
    unittest.main()
