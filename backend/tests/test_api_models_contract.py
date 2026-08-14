import sys
import unittest

from pathlib import Path

from pydantic import ValidationError


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main
from app.models import api as api_models


class ApiModelExtractionContractTests(
    unittest.TestCase
):
    def test_main_reexports_extracted_models(
        self,
    ):
        names = (
            "IngestResponse",
            "Story",
            "AnalyzeRequest",
            "AnalyzeResponse",
            "VideoAnalyzeRequest",
            "VideoAnalyzeResponse",
            "ContentResolveRequest",
            "ContentResolveResponse",
        )

        for name in names:
            with self.subTest(
                name=name
            ):
                self.assertIs(
                    getattr(
                        main,
                        name,
                    ),
                    getattr(
                        api_models,
                        name,
                    ),
                )

    def test_analyze_request_contract_preserved(
        self,
    ):
        request = (
            api_models.AnalyzeRequest(
                title="Transfer update",
                url=(
                    "https://example.com/"
                    "transfer"
                ),
                text=(
                    "A sufficiently long sports "
                    "article body used to verify "
                    "the existing API model "
                    "contract remains unchanged."
                ),
                max_bullets=4,
            )
        )

        self.assertEqual(
            request.max_bullets,
            4,
        )

    def test_analyze_request_validation_preserved(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            api_models.AnalyzeRequest(
                title="Hi",
                url="https://example.com/x",
                text=(
                    "This body is long enough "
                    "for the text constraint but "
                    "the title is intentionally "
                    "too short for validation."
                ),
            )

    def test_video_metadata_default_is_not_shared(
        self,
    ):
        first = (
            api_models.VideoAnalyzeRequest(
                transcript="one"
            )
        )

        second = (
            api_models.VideoAnalyzeRequest(
                transcript="two"
            )
        )

        first.transcript_metadata[
            "confidence"
        ] = 0.8

        self.assertEqual(
            second.transcript_metadata,
            {},
        )

    def test_content_resolve_literal_contract_preserved(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            (
                api_models
                .ContentResolveResponse(
                    url=(
                        "https://example.com/a"
                    ),
                    normalized_url=(
                        "https://example.com/a"
                    ),
                    source="podcast",
                    mode="article",
                    content="content",
                    content_characters=7,
                )
            )

    def test_analyze_response_defaults_are_not_shared(
        self,
    ):
        kwargs = {
            "url": (
                "https://example.com/a"
            ),
            "title": "Article",
            "tldr": ["Summary"],
            "merit_score": 70,
            "badge": "High Merit",
        }

        first = (
            api_models.AnalyzeResponse(
                **kwargs
            )
        )

        second = (
            api_models.AnalyzeResponse(
                **kwargs
            )
        )

        first.reasons.append(
            "reason"
        )

        self.assertEqual(
            second.reasons,
            [],
        )

    def test_story_defaults_preserved(
        self,
    ):
        story = api_models.Story(
            id="story-1",
            source="Example",
            sport="football",
            title="Example story",
            link=(
                "https://example.com/story"
            ),
            created_at=(
                "2026-08-14T00:00:00Z"
            ),
        )

        self.assertEqual(
            story.summary,
            "",
        )

        self.assertEqual(
            story.tldr,
            [],
        )

        self.assertEqual(
            story.merit_score,
            0,
        )

        self.assertEqual(
            story.badge,
            "Unverified Rumor",
        )

    def test_openapi_keeps_core_model_schemas(
        self,
    ):
        schema = main.app.openapi()

        schemas = (
            schema
            .get(
                "components",
                {},
            )
            .get(
                "schemas",
                {},
            )
        )

        for name in (
            "AnalyzeRequest",
            "AnalyzeResponse",
            "VideoAnalyzeRequest",
            "VideoAnalyzeResponse",
            "ContentResolveRequest",
            "ContentResolveResponse",
        ):
            with self.subTest(
                name=name
            ):
                self.assertIn(
                    name,
                    schemas,
                )


if __name__ == "__main__":
    unittest.main()
