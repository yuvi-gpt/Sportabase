from __future__ import annotations

import unittest

from app.operations.job_runtime import (
    JOB_OPERATIONAL_TELEMETRY_VERSION,
    record_browser_capture_job_enqueued,
    record_browser_capture_job_result,
)
from app.operations.telemetry_context import (
    current_operational_event_recorder,
    invoke_with_operational_event_recorder,
)


class PersistentJobTelemetryTests(unittest.TestCase):
    def test_version_is_v1(self):
        self.assertEqual(
            JOB_OPERATIONAL_TELEMETRY_VERSION,
            "sportabase-job-operational-telemetry-v1",
        )

    def test_enqueue_records_only_operational_metadata(self):
        events = []

        record_browser_capture_job_enqueued(
            event_recorder=lambda **event: events.append(event),
            result={
                "status": "enqueued",
                "job_id": "private-job-id",
                "capture_record_id": "private-capture-id",
                "job_status": "pending",
                "attempts": 0,
                "max_attempts": 4,
            },
            platform="web",
            platform_surface="article",
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["component"], "automation_jobs")
        self.assertEqual(event["event_type"], "job.enqueued")
        self.assertEqual(event["status"], "queued")
        self.assertEqual(event["mode"], "article")
        self.assertEqual(event["details"]["platform"], "web")
        self.assertEqual(event["details"]["platform_surface"], "article")
        self.assertNotIn("job_id", event["details"])
        self.assertNotIn("capture_record_id", event["details"])

    def test_existing_enqueue_is_not_double_counted(self):
        events = []

        record_browser_capture_job_enqueued(
            event_recorder=lambda **event: events.append(event),
            result={
                "status": "existing",
                "job_status": "pending",
            },
            platform="web",
            platform_surface="article",
        )

        self.assertEqual(events, [])

    def test_malformed_enqueue_counters_cannot_break_product_path(self):
        events = []

        record_browser_capture_job_enqueued(
            event_recorder=lambda **event: events.append(event),
            result={
                "status": "enqueued",
                "job_status": "pending",
                "attempts": "not-an-int",
                "max_attempts": object(),
            },
        )

        self.assertEqual(events[0]["details"]["attempts"], 0)
        self.assertEqual(events[0]["details"]["max_attempts"], 0)

    def test_retry_result_records_retry_without_error_detail(self):
        events = []

        record_browser_capture_job_result(
            event_recorder=lambda **event: events.append(event),
            result={
                "status": "retry_scheduled",
                "retry_delay_seconds": 20,
                "job": {
                    "id": "private-job-id",
                    "capture_record_id": "private-capture-id",
                    "status": "pending",
                    "attempts": 2,
                    "max_attempts": 4,
                    "last_outcome": "provider_unavailable",
                    "error_type": "ProviderUnavailable",
                    "error_detail": "secret raw provider message",
                },
            },
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_type"], "job.retry_scheduled")
        self.assertEqual(event["status"], "retrying")
        self.assertEqual(event["details"]["retry_delay_seconds"], 20)
        self.assertEqual(event["details"]["error_type"], "ProviderUnavailable")
        self.assertNotIn("error_detail", event["details"])
        self.assertNotIn("id", event["details"])
        self.assertNotIn("capture_record_id", event["details"])

    def test_completed_result_records_execution_mode(self):
        events = []

        record_browser_capture_job_result(
            event_recorder=lambda **event: events.append(event),
            result={
                "status": "completed",
                "execution_mode": "article_history_merit",
                "job": {
                    "status": "completed",
                    "attempts": 1,
                    "max_attempts": 4,
                    "last_outcome": "completed_shadow",
                },
                "result": {
                    "claim_ids": ["private-claim-id"],
                },
            },
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_type"], "job.completed")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["mode"], "article")
        self.assertEqual(
            event["details"]["execution_mode"],
            "article_history_merit",
        )
        self.assertNotIn("claim_ids", event["details"])

    def test_failed_result_records_error_class_only(self):
        events = []

        record_browser_capture_job_result(
            event_recorder=lambda **event: events.append(event),
            result={
                "status": "failed",
                "job": {
                    "status": "failed",
                    "attempts": 4,
                    "max_attempts": 4,
                    "last_outcome": "retry_exhausted:provider_unavailable",
                    "error_type": "ProviderUnavailable",
                    "error_detail": "do not persist this",
                },
            },
        )

        self.assertEqual(events[0]["event_type"], "job.failed")
        self.assertEqual(events[0]["status"], "error")
        self.assertEqual(
            events[0]["details"]["error_type"],
            "ProviderUnavailable",
        )
        self.assertNotIn("error_detail", events[0]["details"])

    def test_recorder_failure_is_fail_open(self):
        def broken(**_):
            raise RuntimeError("telemetry unavailable")

        result = record_browser_capture_job_enqueued(
            event_recorder=broken,
            result={
                "status": "enqueued",
                "job_status": "pending",
            },
        )
        self.assertIsNone(result)

    def test_request_context_is_scoped_and_reset(self):
        seen = []

        def recorder(**_):
            return None

        def handler(value):
            seen.append(current_operational_event_recorder())
            return value

        self.assertIsNone(current_operational_event_recorder())

        result = invoke_with_operational_event_recorder(
            handler=handler,
            recorder=recorder,
            args=("ok",),
        )

        self.assertEqual(result, "ok")
        self.assertIs(seen[0], recorder)
        self.assertIsNone(current_operational_event_recorder())

    def test_request_context_resets_after_handler_error(self):
        def recorder(**_):
            return None

        def handler():
            self.assertIs(current_operational_event_recorder(), recorder)
            raise ValueError("expected")

        with self.assertRaises(ValueError):
            invoke_with_operational_event_recorder(
                handler=handler,
                recorder=recorder,
            )

        self.assertIsNone(current_operational_event_recorder())


if __name__ == "__main__":
    unittest.main()
