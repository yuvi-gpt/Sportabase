import inspect
import sys
import unittest

from pathlib import Path
from types import SimpleNamespace
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
                "persist_article_intelligence_baseline"
            ],
            main.persist_article_intelligence_baseline,
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

        self.assertEqual(
            kwargs[
                "MERIT_SCORE_RELEASE_CERTIFICATE_PATH"
            ],
            main.MERIT_SCORE_RELEASE_CERTIFICATE_PATH,
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

        for name in (
            "analysis_content_hash",
            "persist_analysis_snapshot",
            "record_user_history",
            "upsert_media_item",
        ):
            self.assertIs(kwargs[name], getattr(main, name))

    def test_video_cache_hit_persists_and_exposes_exact_snapshot_internally(self):
        request = SimpleNamespace(state=SimpleNamespace())
        req = main.VideoAnalyzeRequest(
            title="Saved video",
            transcript="A sufficiently useful transcript",
            url="https://youtube.com/watch?v=saved",
            transcript_metadata={},
        )
        cached = main.VideoAnalyzeResponse(
            content_type="analysis", claim="A claim", evidence_used=["Evidence"],
            logic_check="Logic", hype_check="Hype", evidence_score=70,
            logic_score=65, verdict="supported",
        ).model_dump()

        with patch.object(main, "request_client_key", return_value="account-owner"), \
             patch.object(main, "get_cached_analysis", return_value=cached), \
             patch.object(main, "record_analysis_cache_hit"), \
             patch.object(main, "upsert_media_item", return_value={"id": "video-media"}), \
             patch.object(main, "persist_analysis_snapshot", return_value={"snapshot": {"id": 91}, "created": True}) as persist, \
             patch.object(main, "record_user_history") as history, \
             patch.object(main, "ai_video_claim_readout") as provider:
            response = main.analyze_video(req, request)

        self.assertEqual(response.evidence_score, 70)
        self.assertEqual(request.state.analysis_snapshot_id, 91)
        persist.assert_called_once()
        history.assert_called_once_with(client_key="account-owner", media_item_id="video-media", snapshot_id=91)
        provider.assert_not_called()

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
