from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.content import capture_inbox as implementation
from app.operations.telemetry_context import (
    invoke_with_operational_event_recorder,
)
from app.services import browser_capture_inbox as facade


class BrowserCaptureInboxServiceFacadeTests(unittest.TestCase):
    def test_legacy_attributes_still_proxy_to_content_engine(self):
        self.assertIs(
            facade.store_browser_capture,
            implementation.store_browser_capture,
        )
        self.assertEqual(
            facade.BROWSER_CAPTURE_INBOX_VERSION,
            implementation.BROWSER_CAPTURE_INBOX_VERSION,
        )

    def test_http_wrapper_records_successful_job_enqueue(self):
        events = []
        req = SimpleNamespace(
            capture={
                "payload": {
                    "platform": "web",
                    "surface": "article",
                }
            },
            short_video_threshold_seconds=180.0,
        )

        def fake_execute(**kwargs):
            enqueue = kwargs["automation_enqueue"]
            result = enqueue(
                capture_record_id="private-capture-id",
                analysis_version="analysis-v1",
                scoring_version="score-v1",
                connection_factory=lambda: None,
            )
            self.assertEqual(result["status"], "enqueued")
            return "response"

        def fake_enqueue(**_):
            return {
                "status": "enqueued",
                "job_id": "private-job-id",
                "capture_record_id": "private-capture-id",
                "job_status": "pending",
                "attempts": 0,
                "max_attempts": 4,
            }

        with patch.object(
            facade._implementation,
            "execute_browser_capture_http",
            side_effect=fake_execute,
        ):
            result = invoke_with_operational_event_recorder(
                handler=facade.execute_browser_capture_http,
                recorder=lambda **event: events.append(event),
                kwargs={
                    "req": req,
                    "connection_factory": lambda: None,
                    "response_model": object,
                    "automation_enqueue": fake_enqueue,
                    "analysis_version": "analysis-v1",
                    "scoring_version": "score-v1",
                },
            )

        self.assertEqual(result, "response")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "job.enqueued")
        self.assertEqual(events[0]["mode"], "article")
        self.assertNotIn("job_id", events[0]["details"])
        self.assertNotIn("capture_record_id", events[0]["details"])

    def test_http_wrapper_preserves_enqueue_exception(self):
        req = SimpleNamespace(
            capture={
                "payload": {
                    "platform": "x",
                    "surface": "post",
                }
            },
            short_video_threshold_seconds=180.0,
        )

        def fake_execute(**kwargs):
            return kwargs["automation_enqueue"]()

        def broken_enqueue(**_):
            raise RuntimeError("queue failure")

        with patch.object(
            facade._implementation,
            "execute_browser_capture_http",
            side_effect=fake_execute,
        ):
            with self.assertRaises(RuntimeError):
                facade.execute_browser_capture_http(
                    req=req,
                    connection_factory=lambda: None,
                    response_model=object,
                    automation_enqueue=broken_enqueue,
                )


if __name__ == "__main__":
    unittest.main()
