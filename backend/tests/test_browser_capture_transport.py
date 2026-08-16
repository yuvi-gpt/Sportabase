import unittest

from fastapi import (
    HTTPException,
)

from pydantic import (
    ValidationError,
)

from app import main

from app.models import (
    api as api_models,
)

from app.services import (
    browser_ingestion,
)


OBSERVED = (
    "2026-08-16T12:00:00Z"
)


def x_capture():
    return {
        "version": (
            "browser-capture-v1"
        ),

        "source_url": (
            "https://x.com/"
            "Reporter/status/"
            "123456789"
        ),

        "observed_at": (
            OBSERVED
        ),

        "extraction_method": (
            "browser_dom"
        ),

        "payload": {
            "platform": (
                "x"
            ),

            "surface": (
                "post"
            ),

            "container_kind": (
                "post"
            ),

            "canonical_url": (
                "https://x.com/"
                "Reporter/status/"
                "123456789"
            ),

            "body": (
                "Arsenal agree "
                "a deal."
            ),
        },

        "actor": {
            "handle": (
                "Reporter"
            )
        },
    }


def video_capture(
    duration,
):
    return {
        "version": (
            "browser-capture-v1"
        ),

        "source_url": (
            "https://youtube.com/"
            "watch?v="
            "abcDEF12345"
        ),

        "observed_at": (
            OBSERVED
        ),

        "extraction_method": (
            "browser_dom"
        ),

        "payload": {
            "platform": (
                "youtube"
            ),

            "surface": (
                "video"
            ),

            "container_kind": (
                "media"
            ),

            "title": (
                "Video"
            ),

            "media": [
                {
                    "component_id": (
                        "video:0"
                    ),

                    "media_kind": (
                        "video"
                    ),

                    "duration_seconds": (
                        duration
                    ),
                }
            ],
        },
    }


class BrowserCaptureTransportTests(
    unittest.TestCase
):
    def test_preview_serializes_unified_item_and_processing_plan(
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
                "version"
            ],
            "browser-ingestion-v1",
        )

        self.assertEqual(
            preview[
                "item"
            ][
                "item_id"
            ],
            "x:123456789",
        )

        self.assertEqual(
            preview[
                "item"
            ][
                "actor"
            ][
                "handle"
            ],
            "Reporter",
        )

        self.assertEqual(
            preview[
                "processing_plan"
            ][
                "semantic_text_component_ids"
            ],
            (
                "body",
            ),
        )


    def test_preview_threshold_controls_video_strategy_without_changing_media_kind(
        self,
    ):
        preview = (
            browser_ingestion
            .preview_browser_capture(
                video_capture(
                    240
                ),

                short_video_threshold_seconds=(
                    300
                ),
            )
        )

        self.assertEqual(
            preview[
                "item"
            ][
                "media_components"
            ][0][
                "media_kind"
            ],
            "video",
        )

        self.assertEqual(
            preview[
                "processing_plan"
            ][
                "short_video_component_ids"
            ],
            (
                "video:0",
            ),
        )

        self.assertEqual(
            preview[
                "processing_plan"
            ][
                "long_video_component_ids"
            ],
            (),
        )


    def test_transport_response_does_not_create_truth_authority_or_merit_fields(
        self,
    ):
        preview = (
            browser_ingestion
            .preview_browser_capture(
                x_capture()
            )
        )

        encoded = str(
            preview
        ).lower()

        self.assertNotIn(
            "merit_score",
            encoded,
        )

        self.assertNotIn(
            "truth_status",
            encoded,
        )

        self.assertNotIn(
            "authority_score",
            encoded,
        )

        self.assertNotIn(
            "affects_merit_score",
            encoded,
        )


    def test_api_models_and_openapi_expose_browser_capture_contract(
        self,
    ):
        self.assertIs(
            main.BrowserCaptureRequest,
            (
                api_models
                .BrowserCaptureRequest
            ),
        )

        self.assertIs(
            main.BrowserCaptureResponse,
            (
                api_models
                .BrowserCaptureResponse
            ),
        )

        schema = (
            main.app.openapi()
        )

        self.assertIn(
            "/content/browser-capture",
            schema[
                "paths"
            ],
        )

        schemas = (
            schema[
                "components"
            ][
                "schemas"
            ]
        )

        self.assertIn(
            "BrowserCaptureRequest",
            schemas,
        )

        self.assertIn(
            "BrowserCaptureResponse",
            schemas,
        )

        with self.assertRaises(
            ValidationError
        ):
            (
                api_models
                .BrowserCaptureRequest(
                    capture=x_capture(),

                    short_video_threshold_seconds=(
                        0
                    ),
                )
            )


    def test_endpoint_preview_does_not_require_gemini_or_database_access(
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
            *args,
            **kwargs,
        ):
            raise AssertionError(
                "Browser capture preview "
                "must not use Gemini or DB."
            )

        try:
            main.generate_gemini_content = (
                forbidden
            )

            main.db_conn = (
                forbidden
            )

            response = (
                main.browser_capture_preview(
                    api_models
                    .BrowserCaptureRequest(
                        capture=x_capture()
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
            (
                api_models
                .BrowserCaptureResponse
            ),
        )

        self.assertEqual(
            response.item[
                "platform"
            ],
            "x",
        )


    def test_endpoint_maps_invalid_capture_to_422(
        self,
    ):
        request = (
            api_models
            .BrowserCaptureRequest(
                capture={
                    "version": (
                        "wrong"
                    ),

                    "source_url": (
                        "https://x.com/a/"
                        "status/111111"
                    ),

                    "observed_at": (
                        OBSERVED
                    ),

                    "extraction_method": (
                        "browser_dom"
                    ),

                    "payload": {
                        "text": "A"
                    },
                }
            )
        )

        with self.assertRaises(
            HTTPException
        ) as context:
            (
                main
                .browser_capture_preview(
                    request
                )
            )

        self.assertEqual(
            context.exception
            .status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main()
