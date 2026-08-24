import inspect
import sys
import unittest

from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main

from app.services import (
    analysis_handlers,
)


class AnalysisHandlersModuleTests(
    unittest.TestCase
):
    def test_public_route_signatures_remain_small(
        self,
    ):
        self.assertEqual(
            list(
                inspect.signature(
                    main.analyze
                ).parameters
            ),
            [
                "req",
                "request",
            ],
        )

        self.assertEqual(
            list(
                inspect.signature(
                    main.analyze_video
                ).parameters
            ),
            [
                "req",
                "request",
            ],
        )

    def test_article_wrapper_delegates(
        self,
    ):
        sentinel = object()

        with patch.object(
            main,
            "_analyze_article_handler_impl",
            return_value=sentinel,
        ) as implementation:
            result = main.analyze(
                object(),
                object(),
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "request_client_key"
            ],
            main.request_client_key,
        )

        self.assertIs(
            kwargs[
                "run_article_ai_strategy"
            ],
            main.run_article_ai_strategy,
        )

        self.assertIs(
            kwargs[
                "AnalyzeResponse"
            ],
            main.AnalyzeResponse,
        )

        self.assertIs(
            kwargs[
                "persist_analysis_snapshot"
            ],
            main.persist_analysis_snapshot,
        )

        self.assertIs(
            kwargs[
                "apply_certified_live_merit"
            ],
            main.apply_certified_live_merit,
        )

        self.assertIs(
            kwargs[
                "live_merit_release_cache_token"
            ],
            main.live_merit_release_cache_token,
        )

        self.assertIs(
            kwargs[
                "apply_certified_live_negative_merit"
            ],
            main.apply_certified_live_negative_merit,
        )

        self.assertIs(
            kwargs[
                "live_negative_merit_release_cache_token"
            ],
            main.live_negative_merit_release_cache_token,
        )

        self.assertEqual(
            kwargs[
                "MERIT_SCORE_RELEASE_CERTIFICATE_PATH"
            ],
            main.MERIT_SCORE_RELEASE_CERTIFICATE_PATH,
        )

        self.assertEqual(
            kwargs[
                "NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_PATH"
            ],
            main.NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_PATH,
        )

        self.assertEqual(
            kwargs[
                "LIVE_NEGATIVE_MERIT_ENABLED"
            ],
            main.LIVE_NEGATIVE_MERIT_ENABLED,
        )

    def test_video_wrapper_delegates(
        self,
    ):
        sentinel = object()

        with patch.object(
            main,
            "_analyze_video_handler_impl",
            return_value=sentinel,
        ) as implementation:
            result = main.analyze_video(
                object(),
                object(),
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "request_client_key"
            ],
            main.request_client_key,
        )

        self.assertIs(
            kwargs[
                "ai_video_claim_readout"
            ],
            main.ai_video_claim_readout,
        )

        self.assertIs(
            kwargs[
                "VideoAnalyzeResponse"
            ],
            main.VideoAnalyzeResponse,
        )

    def test_service_dependencies_are_explicit(
        self,
    ):
        article = inspect.signature(
            analysis_handlers
            .analyze_article_impl
        )

        video = inspect.signature(
            analysis_handlers
            .analyze_video_impl
        )

        for name in (
            "request_client_key",
            "clean_html",
            "make_analysis_cache_key",
            "AnalyzeResponse",
            "apply_certified_live_merit",
            "live_merit_release_cache_token",
            "LIVE_MERIT_ENABLED",
            "MERIT_SCORE_RELEASE_CERTIFICATE_PATH",
            "apply_certified_live_negative_merit",
            "live_negative_merit_release_cache_token",
            "LIVE_NEGATIVE_MERIT_ENABLED",
            "NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_PATH",
            "badge",
        ):
            self.assertIn(
                name,
                article.parameters,
            )

            self.assertEqual(
                article.parameters[
                    name
                ].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )

        for name in (
            "request_client_key",
            "make_analysis_cache_key",
            "VideoAnalyzeResponse",
        ):
            self.assertIn(
                name,
                video.parameters,
            )

            self.assertEqual(
                video.parameters[
                    name
                ].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )

    def test_service_has_no_route_registration(
        self,
    ):
        source = Path(
            analysis_handlers.__file__
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "@app.",
            source,
        )

        self.assertNotIn(
            "from app.main",
            source,
        )

        self.assertNotIn(
            "from app import main",
            source,
        )

    def test_analysis_routes_remain_registered(
        self,
    ):
        paths = (
            main.app.openapi()[
                "paths"
            ]
        )

        self.assertIn(
            "/analyze",
            paths,
        )

        self.assertIn(
            "post",
            paths[
                "/analyze"
            ],
        )

        self.assertIn(
            "/analyze/video",
            paths,
        )

        self.assertIn(
            "post",
            paths[
                "/analyze/video"
            ],
        )


if __name__ == "__main__":
    unittest.main()
