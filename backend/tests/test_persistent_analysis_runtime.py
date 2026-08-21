from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.operations.analysis_runtime import (
    ANALYSIS_OPERATIONAL_TELEMETRY_VERSION,
    execute_analysis_with_operational_telemetry,
)


class _Clock:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        if not self.values:
            raise AssertionError("clock exhausted")
        return self.values.pop(0)


class PersistentAnalysisRuntimeTests(unittest.TestCase):
    def test_article_success_emits_minimized_operational_event(self):
        response = SimpleNamespace(
            article_type="transfer_news",
            merit_score=84,
            debug={"cache": {"hit": True}},
        )
        events = []
        req = SimpleNamespace(
            url=(
                "https://www.Example.com/story?utm_source=private"
            )
        )

        result = execute_analysis_with_operational_telemetry(
            handler=lambda *_: response,
            req=req,
            request=object(),
            mode="article",
            event_recorder=lambda **event: events.append(event),
            clock=_Clock(10.0, 10.125),
        )

        self.assertIs(result, response)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["component"], "content_pipeline")
        self.assertEqual(event["event_type"], "analysis.completed")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["mode"], "article")
        self.assertEqual(event["source_key"], "example.com")
        self.assertEqual(event["duration_ms"], 125)
        self.assertEqual(event["details"]["cache_hit"], True)
        self.assertEqual(
            event["details"]["article_type"],
            "transfer_news",
        )
        self.assertEqual(event["details"]["merit_score"], 84)
        self.assertEqual(
            event["details"]["telemetry_version"],
            ANALYSIS_OPERATIONAL_TELEMETRY_VERSION,
        )
        serialized = repr(event)
        self.assertNotIn("utm_source", serialized)
        self.assertNotIn("private", serialized)

    def test_video_success_emits_verdict_without_raw_content(self):
        response = {
            "content_type": "claim_analysis",
            "verdict": "supported",
            "debug": {"cache": {"hit": False}},
            "claim": "sensitive raw claim text",
            "evidence_used": ["sensitive evidence text"],
        }
        events = []

        execute_analysis_with_operational_telemetry(
            handler=lambda *_: response,
            req=SimpleNamespace(url="https://video.example/path"),
            request=object(),
            mode="video",
            event_recorder=lambda **event: events.append(event),
            clock=_Clock(5.0, 5.04),
        )

        event = events[0]
        self.assertEqual(event["mode"], "video")
        self.assertEqual(event["source_key"], "video.example")
        self.assertEqual(event["duration_ms"], 40)
        self.assertEqual(event["details"]["cache_hit"], False)
        self.assertEqual(
            event["details"]["content_type"],
            "claim_analysis",
        )
        self.assertEqual(event["details"]["verdict"], "supported")
        serialized = repr(event)
        self.assertNotIn("sensitive raw claim text", serialized)
        self.assertNotIn("sensitive evidence text", serialized)

    def test_handler_failure_is_recorded_and_original_error_is_reraised(self):
        events = []
        secret_message = "provider failed with secret-token-value"

        def broken(*_):
            raise ValueError(secret_message)

        with self.assertRaisesRegex(ValueError, "provider failed"):
            execute_analysis_with_operational_telemetry(
                handler=broken,
                req=SimpleNamespace(url="https://example.com/story"),
                request=object(),
                mode="article",
                event_recorder=lambda **event: events.append(event),
                clock=_Clock(2.0, 2.25),
            )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["event_type"], "analysis.failed")
        self.assertEqual(event["status"], "error")
        self.assertEqual(event["duration_ms"], 250)
        self.assertEqual(event["details"]["error_type"], "ValueError")
        self.assertNotIn(secret_message, repr(event))

    def test_telemetry_failure_never_breaks_successful_analysis(self):
        response = SimpleNamespace(debug={})

        def broken_recorder(**_):
            raise RuntimeError("telemetry unavailable")

        result = execute_analysis_with_operational_telemetry(
            handler=lambda *_: response,
            req=SimpleNamespace(url="https://example.com/story"),
            request=object(),
            mode="article",
            event_recorder=broken_recorder,
            clock=_Clock(1.0, 1.01),
        )

        self.assertIs(result, response)

    def test_missing_recorder_is_a_zero_effect_path(self):
        response = object()

        result = execute_analysis_with_operational_telemetry(
            handler=lambda *_: response,
            req=SimpleNamespace(url="https://example.com/story"),
            request=object(),
            mode="article",
            event_recorder=None,
            clock=_Clock(1.0, 1.0),
        )

        self.assertIs(result, response)

    def test_non_callable_handler_is_rejected_before_clock_or_telemetry(self):
        events = []

        with self.assertRaises(TypeError):
            execute_analysis_with_operational_telemetry(
                handler=None,
                req=SimpleNamespace(url="https://example.com"),
                request=object(),
                mode="article",
                event_recorder=lambda **event: events.append(event),
                clock=lambda: (_ for _ in ()).throw(
                    AssertionError("clock should not run")
                ),
            )

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
