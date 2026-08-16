import unittest

from app.services import (
    browser_ingestion,
)


OBSERVED = (
    "2026-08-16T12:00:00Z"
)


class BrowserIngestionTests(
    unittest.TestCase
):
    def test_x_browser_capture_normalizes_through_multimodal_spine(
        self,
    ):
        result = (
            browser_ingestion
            .ingest_browser_capture(
                {
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

                        "metadata": {
                            (
                                "browser_"
                                "acquisition_"
                                "version"
                            ): (
                                "platform-"
                                "acquisition-v1"
                            )
                        },
                    },

                    "actor": {
                        "handle": (
                            "Reporter"
                        )
                    },
                }
            )
        )

        self.assertEqual(
            result.item.item_id,
            "x:123456789",
        )

        self.assertEqual(
            result.item.actor.handle,
            "Reporter",
        )

        self.assertEqual(
            (
                result
                .processing_plan
                .semantic_text_component_ids
            ),
            (
                "body",
            ),
        )


    def test_youtube_browser_capture_reuses_transcript_and_video_plan(
        self,
    ):
        result = (
            browser_ingestion
            .ingest_browser_capture(
                {
                    "version": (
                        "browser-capture-v1"
                    ),

                    "source_url": (
                        "https://youtube.com/"
                        "shorts/"
                        "abcDEF12345"
                    ),

                    "observed_at": (
                        OBSERVED
                    ),

                    "extraction_method": (
                        "browser_dom+"
                        "youtube_transcript"
                    ),

                    "payload": {
                        "platform": (
                            "youtube"
                        ),

                        "surface": (
                            "short"
                        ),

                        "container_kind": (
                            "media"
                        ),

                        "title": (
                            "Match reaction"
                        ),

                        "transcript": (
                            "Existing transcript"
                        ),

                        "media": [
                            {
                                "component_id": (
                                    "video:0"
                                ),

                                "media_kind": (
                                    "video"
                                ),

                                "media_url": (
                                    "https://cdn."
                                    "example/v.mp4"
                                ),

                                "duration_seconds": (
                                    44
                                ),
                            }
                        ],
                    },
                }
            )
        )

        self.assertEqual(
            (
                result
                .processing_plan
                .short_video_component_ids
            ),
            (
                "video:0",
            ),
        )

        self.assertEqual(
            (
                result
                .processing_plan
                .transcription_component_ids
            ),
            (),
        )


    def test_generic_article_browser_capture_preserves_article_mode(
        self,
    ):
        item = (
            browser_ingestion
            .normalize_browser_capture(
                {
                    "version": (
                        "browser-capture-v1"
                    ),

                    "source_url": (
                        "https://example.com/"
                        "story?utm_source=x"
                    ),

                    "observed_at": (
                        OBSERVED
                    ),

                    "extraction_method": (
                        "browser_dom+"
                        "article_extractor"
                    ),

                    "payload": {
                        "platform": (
                            "web"
                        ),

                        "surface": (
                            "article"
                        ),

                        "container_kind": (
                            "article"
                        ),

                        "canonical_url": (
                            "https://example.com/"
                            "story"
                        ),

                        "title": (
                            "Article title"
                        ),

                        "body": (
                            "Existing article "
                            "extractor content."
                        ),
                    },
                }
            )
        )

        self.assertEqual(
            item.platform,
            "web",
        )

        self.assertEqual(
            item.platform_surface,
            "article",
        )

        self.assertEqual(
            item.container_kind,
            "article",
        )


    def test_capture_wrapper_rejects_unknown_version_and_fields(
        self,
    ):
        base = {
            "version": (
                "browser-capture-v1"
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

        wrong_version = dict(
            base
        )

        wrong_version[
            "version"
        ] = "wrong"

        with self.assertRaises(
            ValueError
        ):
            (
                browser_ingestion
                .normalize_browser_capture(
                    wrong_version
                )
            )

        unknown_field = dict(
            base
        )

        unknown_field[
            "authority"
        ] = "official"

        with self.assertRaises(
            ValueError
        ):
            (
                browser_ingestion
                .normalize_browser_capture(
                    unknown_field
                )
            )


    def test_capture_rejects_non_browser_method_and_missing_timestamp(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            (
                browser_ingestion
                .normalize_browser_capture(
                    {
                        "version": (
                            "browser-capture-v1"
                        ),

                        "source_url": (
                            "https://x.com/a/"
                            "status/111111"
                        ),

                        "observed_at": (
                            OBSERVED
                        ),

                        "extraction_method": (
                            "official_api"
                        ),

                        "payload": {
                            "text": "A"
                        },
                    }
                )
            )

        with self.assertRaises(
            ValueError
        ):
            (
                browser_ingestion
                .normalize_browser_capture(
                    {
                        "version": (
                            "browser-capture-v1"
                        ),

                        "source_url": (
                            "https://x.com/a/"
                            "status/111111"
                        ),

                        "observed_at": "",

                        "extraction_method": (
                            "browser_dom"
                        ),

                        "payload": {
                            "text": "A"
                        },
                    }
                )
            )


    def test_nested_semantic_smuggling_is_rejected_by_locked_multimodal_spine(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            (
                browser_ingestion
                .normalize_browser_capture(
                    {
                        "version": (
                            "browser-capture-v1"
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
                            "text": "A",

                            "metadata": {
                                "nested": {
                                    "authority": (
                                        "official"
                                    )
                                }
                            },
                        },
                    }
                )
            )


if __name__ == "__main__":
    unittest.main()
