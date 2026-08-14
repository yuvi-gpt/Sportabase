import inspect
import json
import sys
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import (
    Mock,
    patch,
)


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main

from app.services.video_analysis import (
    ai_video_claim_readout_impl,
)


def payload():
    return {
        "detected_language":
            "English",
        "languages": [
            "English"
        ],
        "mixed_language":
            False,
        "language_confidence":
            0.98,
        "transcript_confidence":
            0.94,
        "uncertain_corrections":
            [],
        "content_type":
            "sports_analysis",
        "localized_content_type":
            "Sports Analysis",
        "localized_verdict":
            "Well-Supported Analysis",
        "ui_labels":
            {},
        "claim":
            (
                "Mercedes has shown strong "
                "overall race pace."
            ),
        "evidence_used": [
            (
                "The presenter compares "
                "qualifying pace and race pace."
            ),
            (
                "Tyre degradation figures are "
                "used as supporting evidence."
            ),
        ],
        "logic_check":
            (
                "The evidence is connected "
                "to the central argument."
            ),
        "hype_check":
            (
                "The presentation is energetic "
                "without materially overstating "
                "the evidence."
            ),
        "evidence_score":
            82,
        "logic_score":
            84,
        "verdict":
            "well_supported_analysis",
    }


def transcript():
    return (
        "The presenter compares Mercedes "
        "qualifying pace, race pace, tyre "
        "degradation, strategy, and results "
        "across several races. "
    ) * 12


def run_success():
    calls = []

    def generator(**kwargs):
        calls.append(
            kwargs
        )

        return SimpleNamespace(
            text=json.dumps(
                payload()
            )
        )

    result = (
        ai_video_claim_readout_impl(
            title=(
                "Mercedes race pace analysis"
            ),
            transcript=transcript(),
            url=(
                "https://youtube.com/"
                "watch?v=module-test"
            ),
            client_key=(
                "unit-test-client"
            ),
            client_factory=(
                lambda: object()
            ),
            generator=generator,
        )
    )

    return result, calls


class VideoAnalysisModuleTests(
    unittest.TestCase
):
    def test_service_implementation_is_distinct_from_main_wrapper(
        self,
    ):
        self.assertIsNot(
            main.ai_video_claim_readout,
            ai_video_claim_readout_impl,
        )

    def test_main_wrapper_injects_main_runtime_dependencies(
        self,
    ):
        with (
            patch.object(
                main,
                "_ai_video_claim_readout_impl",
                return_value={
                    "ok": True
                },
            ) as implementation,
            patch.object(
                main,
                "gemini_client",
                return_value=None,
            ) as client_factory,
            patch.object(
                main,
                "generate_gemini_content",
            ) as generator,
        ):
            result = (
                main.ai_video_claim_readout(
                    title="Test",
                    transcript="Transcript",
                    url=(
                        "https://youtube.com/"
                        "watch?v=wrapper"
                    ),
                    client_key="client",
                )
            )

        self.assertEqual(
            result,
            {
                "ok": True
            },
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "client_factory"
            ],
            client_factory,
        )

        self.assertIs(
            kwargs[
                "generator"
            ],
            generator,
        )

    def test_missing_client_returns_ai_unavailable(
        self,
    ):
        result = (
            ai_video_claim_readout_impl(
                title="Test",
                transcript="Transcript",
                client_key="client",
                client_factory=(
                    lambda: None
                ),
                generator=Mock(),
            )
        )

        self.assertEqual(
            result[
                "verdict"
            ],
            "ai_unavailable",
        )

        self.assertFalse(
            result[
                "debug"
            ][
                "ai_enabled"
            ]
        )

    def test_missing_client_never_calls_generator(
        self,
    ):
        generator = Mock()

        ai_video_claim_readout_impl(
            title="Test",
            transcript="Transcript",
            client_key="client",
            client_factory=(
                lambda: None
            ),
            generator=generator,
        )

        generator.assert_not_called()

    def test_injected_generator_uses_video_mode(
        self,
    ):
        _result, calls = (
            run_success()
        )

        self.assertEqual(
            len(calls),
            1,
        )

        self.assertEqual(
            calls[0][
                "mode"
            ],
            "video_analysis",
        )

        self.assertEqual(
            calls[0][
                "model"
            ],
            "gemini-3.5-flash",
        )

    def test_successful_payload_survives_extraction(
        self,
    ):
        result, _calls = (
            run_success()
        )

        self.assertEqual(
            result[
                "content_type"
            ],
            "sports_analysis",
        )

        self.assertEqual(
            result[
                "verdict"
            ],
            "well_supported_analysis",
        )

        self.assertIn(
            "Mercedes",
            result[
                "claim"
            ],
        )

        self.assertEqual(
            result[
                "evidence_score"
            ],
            82,
        )

    def test_provider_capacity_failure_remains_classified(
        self,
    ):
        def generator(**_kwargs):
            raise RuntimeError(
                "503 service unavailable"
            )

        result = (
            ai_video_claim_readout_impl(
                title="Test",
                transcript=transcript(),
                client_key="client",
                client_factory=(
                    lambda: object()
                ),
                generator=generator,
            )
        )

        self.assertEqual(
            result[
                "verdict"
            ],
            "analysis_failed",
        )

        self.assertEqual(
            result[
                "debug"
            ][
                "error_code"
            ],
            "provider_capacity",
        )

    def test_service_has_no_direct_main_provider_dependency(
        self,
    ):
        source = inspect.getsource(
            ai_video_claim_readout_impl
        )

        self.assertNotIn(
            "gemini_client()",
            source,
        )

        self.assertNotIn(
            "generate_gemini_content(",
            source,
        )

        self.assertIn(
            "client_factory()",
            source,
        )

        self.assertIn(
            "generator(",
            source,
        )


if __name__ == "__main__":
    unittest.main()
