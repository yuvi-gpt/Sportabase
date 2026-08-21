from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from app.operations.pipeline_runtime import (
    PIPELINE_OPERATIONAL_TELEMETRY_VERSION,
    execute_browser_capture_with_operational_telemetry,
)


class PersistentPipelineRuntimeTests(unittest.TestCase):
    def _request(
        self,
        *,
        source_url="https://www.example.com/story?id=secret",
        platform="web",
        surface="article",
    ):
        return SimpleNamespace(
            capture={
                "source_url": source_url,
                "payload": {
                    "platform": platform,
                    "surface": surface,
                    "title": "Private title must not enter telemetry",
                    "body": "Private body must not enter telemetry",
                },
                "actor": {
                    "handle": "private-handle",
                },
            }
        )

    def test_stored_capture_emits_minimized_success_event(self):
        events = []
        clock_values = iter([10.0, 10.125])

        response = execute_browser_capture_with_operational_telemetry(
            handler=lambda _: {
                "capture_inbox_status": "stored",
                "capture_persisted": True,
                "capture_record_id": "must-not-be-recorded",
            },
            req=self._request(),
            event_recorder=lambda **event: events.append(event),
            clock=lambda: next(clock_values),
        )

        self.assertTrue(response["capture_persisted"])
        self.assertEqual(len(events), 1)

        event = events[0]
        self.assertEqual(event["component"], "content_pipeline")
        self.assertEqual(event["event_type"], "capture.processed")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["mode"], "article")
        self.assertEqual(event["source_key"], "example.com")
        self.assertEqual(event["duration_ms"], 125)
        self.assertEqual(event["details"]["capture_inbox_status"], "stored")
        self.assertIs(event["details"]["capture_persisted"], True)
        self.assertEqual(event["details"]["platform"], "web")
        self.assertEqual(event["details"]["platform_surface"], "article")
        self.assertEqual(
            event["details"]["telemetry_version"],
            PIPELINE_OPERATIONAL_TELEMETRY_VERSION,
        )

        encoded = json.dumps(event, sort_keys=True)
        self.assertNotIn("?id=secret", encoded)
        self.assertNotIn("Private title", encoded)
        self.assertNotIn("Private body", encoded)
        self.assertNotIn("private-handle", encoded)
        self.assertNotIn("must-not-be-recorded", encoded)

    def test_capture_inbox_statuses_map_to_operator_statuses(self):
        cases = {
            "stored": "success",
            "replayed": "success",
            "disabled": "skipped",
            "oversize": "rejected",
            "unavailable": "degraded",
            "": "unknown",
        }

        for inbox_status, expected_status in cases.items():
            with self.subTest(inbox_status=inbox_status):
                events = []
                clock_values = iter([1.0, 1.0])

                execute_browser_capture_with_operational_telemetry(
                    handler=lambda _, value=inbox_status: {
                        "capture_inbox_status": value,
                        "capture_persisted": False,
                    },
                    req=self._request(),
                    event_recorder=lambda **event: events.append(event),
                    clock=lambda: next(clock_values),
                )

                self.assertEqual(events[0]["status"], expected_status)

    def test_video_capture_is_classified_without_storing_raw_url(self):
        events = []
        clock_values = iter([4.0, 4.01])

        execute_browser_capture_with_operational_telemetry(
            handler=lambda _: {
                "capture_inbox_status": "stored",
                "capture_persisted": True,
            },
            req=self._request(
                source_url="https://youtube.com/watch?v=private",
                platform="youtube",
                surface="video",
            ),
            event_recorder=lambda **event: events.append(event),
            clock=lambda: next(clock_values),
        )

        self.assertEqual(events[0]["mode"], "video")
        self.assertEqual(events[0]["source_key"], "youtube.com")
        self.assertNotIn("watch", json.dumps(events[0]))
        self.assertNotIn("private", json.dumps(events[0]))

    def test_handler_failure_emits_exception_class_and_reraises(self):
        events = []
        clock_values = iter([20.0, 20.2])

        class CaptureFailure(RuntimeError):
            pass

        def fail(_):
            raise CaptureFailure("private failure detail")

        with self.assertRaises(CaptureFailure):
            execute_browser_capture_with_operational_telemetry(
                handler=fail,
                req=self._request(),
                event_recorder=lambda **event: events.append(event),
                clock=lambda: next(clock_values),
            )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_type"], "capture.failed")
        self.assertEqual(event["status"], "error")
        self.assertEqual(event["details"]["error_type"], "CaptureFailure")
        self.assertNotIn("private failure detail", json.dumps(event))

    def test_telemetry_failure_never_breaks_capture_response(self):
        clock_values = iter([30.0, 30.1])

        def broken_recorder(**_):
            raise RuntimeError("telemetry offline")

        response = execute_browser_capture_with_operational_telemetry(
            handler=lambda _: {
                "capture_inbox_status": "stored",
                "capture_persisted": True,
            },
            req=self._request(),
            event_recorder=broken_recorder,
            clock=lambda: next(clock_values),
        )

        self.assertIs(response["capture_persisted"], True)

    def test_missing_recorder_is_a_noop(self):
        clock_values = iter([40.0, 40.0])

        response = execute_browser_capture_with_operational_telemetry(
            handler=lambda _: {
                "capture_inbox_status": "disabled",
                "capture_persisted": False,
            },
            req=self._request(),
            event_recorder=None,
            clock=lambda: next(clock_values),
        )

        self.assertEqual(response["capture_inbox_status"], "disabled")


if __name__ == "__main__":
    unittest.main()
