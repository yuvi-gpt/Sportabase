import unittest

from app import main
from app.models import api as api_models
from app.services import browser_ingestion


OBSERVED = "2026-08-16T12:00:00Z"


def x_capture():
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://x.com/Reporter/"
            "status/123456789"
        ),
        "observed_at": OBSERVED,
        "extraction_method": "browser_dom",
        "payload": {
            "platform": "x",
            "surface": "post",
            "container_kind": "post",
            "canonical_url": (
                "https://x.com/Reporter/"
                "status/123456789"
            ),
            "body": (
                "Arsenal agree a deal."
            ),
        },
        "actor": {
            "handle": "Reporter"
        },
    }


def youtube_capture():
    return {
        "version": "browser-capture-v1",
        "source_url": (
            "https://youtube.com/"
            "shorts/abcDEF12345"
        ),
        "observed_at": OBSERVED,
        "extraction_method": (
            "browser_dom+"
            "youtube_transcript"
        ),
        "payload": {
            "platform": "youtube",
            "surface": "short",
            "container_kind": "media",
            "title": "Match reaction",
            "transcript": (
                "Existing transcript"
            ),
            "media": [
                {
                    "component_id": (
                        "video:0"
                    ),
                    "media_kind": "video",
                    "media_url": (
                        "https://cdn.example/"
                        "video.mp4"
                    ),
                    "duration_seconds": 44,
                    "has_audio": True,
                }
            ],
        },
    }


class BrowserCaptureArtifactRuntimeTests(
    unittest.TestCase
):
    def test_browser_preview_returns_artifact_manifest_for_same_item(
        self,
    ):
        preview = (
            browser_ingestion
            .preview_browser_capture(
                x_capture()
            )
        )

        self.assertEqual(
            preview[
                "artifact_manifest"
            ][
                "version"
            ],
            "multimodal-artifact-model-v1",
        )

        self.assertEqual(
            preview[
                "artifact_manifest"
            ][
                "item_id"
            ],
            preview[
                "item"
            ][
                "item_id"
            ],
        )


    def test_text_only_browser_capture_materializes_ready_text_artifact(
        self,
    ):
        preview = (
            browser_ingestion
            .preview_browser_capture(
                x_capture()
            )
        )

        artifacts = preview[
            "artifact_manifest"
        ][
            "artifacts"
        ]

        self.assertEqual(
            len(artifacts),
            1,
        )

        self.assertEqual(
            artifacts[0][
                "artifact_kind"
            ],
            "text_component",
        )

        self.assertEqual(
            artifacts[0][
                "payload"
            ][
                "text"
            ],
            "Arsenal agree a deal.",
        )


    def test_youtube_capture_materializes_schedule_without_retranscribing_existing_transcript(
        self,
    ):
        preview = (
            browser_ingestion
            .preview_browser_capture(
                youtube_capture()
            )
        )

        manifest = preview[
            "artifact_manifest"
        ]

        kinds = {
            artifact[
                "artifact_kind"
            ]
            for artifact
            in manifest[
                "artifacts"
            ]
        }

        operations = {
            work[
                "operation"
            ]
            for work
            in manifest[
                "work_units"
            ]
        }

        self.assertIn(
            "frame_sampling_schedule",
            kinds,
        )

        self.assertIn(
            "video_frame_extract",
            operations,
        )

        self.assertIn(
            "ocr",
            operations,
        )

        self.assertNotIn(
            "transcription",
            operations,
        )

        schedule = next(
            artifact
            for artifact
            in manifest[
                "artifacts"
            ]
            if artifact[
                "artifact_kind"
            ]
            == "frame_sampling_schedule"
        )

        self.assertEqual(
            schedule[
                "payload"
            ][
                "sample_limit"
            ],
            6,
        )


    def test_api_response_exposes_artifact_manifest_without_db_or_gemini(
        self,
    ):
        original_gemini = (
            main
            .generate_gemini_content
        )

        original_db_conn = (
            main.db_conn
        )

        def forbidden(
            *_args,
            **_kwargs,
        ):
            raise AssertionError(
                "Artifact preview must "
                "not use Gemini or DB."
            )

        try:
            main.generate_gemini_content = (
                forbidden
            )

            main.db_conn = (
                forbidden
            )

            response = (
                main
                .browser_capture_preview(
                    api_models
                    .BrowserCaptureRequest(
                        capture=(
                            youtube_capture()
                        )
                    )
                )
            )

        finally:
            main.generate_gemini_content = (
                original_gemini
            )

            main.db_conn = (
                original_db_conn
            )

        self.assertIsInstance(
            response,
            api_models
            .BrowserCaptureResponse,
        )

        self.assertEqual(
            response.artifact_manifest[
                "version"
            ],
            "multimodal-artifact-model-v1",
        )

        self.assertEqual(
            response.artifact_manifest[
                "item_id"
            ],
            response.item[
                "item_id"
            ],
        )


if __name__ == "__main__":
    unittest.main()