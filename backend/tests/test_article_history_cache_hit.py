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
from app.services.article_intelligence_public import (
    ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
)


class ArticleHistoryCacheHitTests(
    unittest.TestCase
):
    def make_request(self):
        req = main.AnalyzeRequest(
            title="Club confirms major signing",
            url=(
                "https://example.com/"
                "confirmed-signing"
            ),
            text=(
                "The club officially confirmed "
                "the signing in a statement after "
                "the player completed a medical "
                "and signed a long-term contract."
            ),
            max_bullets=3,
        )

        request = SimpleNamespace(
            headers={
                "x-sportabase-client-id":
                    "history-cache-test",
            },
            client=SimpleNamespace(
                host="127.0.0.1"
            ),
        )

        return req, request

    def cached_payload(
        self,
        req,
    ):
        return {
            "url": req.url,
            "title": req.title,
            "tldr": [
                "The club confirmed the signing."
            ],
            "merit_score": 81,
            "badge": "High Merit",
            "debug": {
                "cache": {
                    "hit": True,
                }
            },
        }

    def test_cache_hit_links_existing_snapshot(
        self,
    ):
        req, request = self.make_request()

        cache_content = (
            f"{req.title}\n"
            f"{main.clean_html(req.text)}"
        )

        expected_hash = (
            main.analysis_content_hash(
                cache_content
            )
        )

        expected_live_merit_cache_token = (
            main.live_merit_release_cache_token(
                enabled=(
                    main.LIVE_MERIT_ENABLED
                ),
                certificate_path=(
                    main.MERIT_SCORE_RELEASE_CERTIFICATE_PATH
                ),
            )
        )

        expected_live_negative_merit_cache_token = (
            main.live_negative_merit_release_cache_token(
                enabled=(
                    main.LIVE_NEGATIVE_MERIT_ENABLED
                ),
                certificate_path=(
                    main.NEGATIVE_MERIT_SCORE_RELEASE_CERTIFICATE_PATH
                ),
            )
        )

        expected_cache_key = (
            main.make_analysis_cache_key(
                mode="article",
                url=req.url,
                content=cache_content,
                variant=(
                    f"max_bullets:{req.max_bullets}"
                    "|intelligence_shadow:"
                    f"{int(main.INTELLIGENCE_SHADOW_ENABLED)}"
                    "|public_intelligence:"
                    f"{ARTICLE_INTELLIGENCE_PUBLIC_VERSION}"
                    "|live_merit:"
                    f"{expected_live_merit_cache_token}"
                    "|live_negative_merit:"
                    f"{expected_live_negative_merit_cache_token}"
                ),
                context_hash=(
                    "media-context-hash"
                ),
            )
        )

        expected_client_key = (
            main.request_client_key(
                request
            )
        )

        with patch(
            "app.main.get_cached_analysis",
            return_value=self.cached_payload(req),
        ) as mock_get_cached, patch(
            "app.main.record_analysis_cache_hit",
        ) as mock_cache_hit, patch(
            "app.main.upsert_media_item",
            return_value={
                "id": "media-cache-test",
            },
        ) as mock_upsert, patch(
            "app.main.load_evidence_analysis_state_for_media_item",
            return_value={
                "bundle": {},
                "context_hash": "media-context-hash",
            },
        ) as mock_context_hash, patch(
            "app.main.find_analysis_snapshot",
            return_value={
                "id": 42,
            },
        ) as mock_find, patch(
            "app.main.record_user_history",
        ) as mock_history, patch(
            "app.main.persist_analysis_snapshot",
        ) as mock_persist:
            response = main.analyze(
                req,
                request,
            )

        self.assertEqual(
            response.merit_score,
            81,
        )

        mock_get_cached.assert_called_once_with(
            expected_cache_key
        )

        mock_cache_hit.assert_called_once_with(
            expected_client_key,
            "article",
        )

        mock_upsert.assert_called_once_with(
            url=req.url,
            mode="article",
            title=req.title,
            content_hash=expected_hash,
        )

        mock_context_hash.assert_called_once_with(
            media_item_id=(
                main.media_item_id_for_url(
                    req.url
                )
            ),
        )

        mock_find.assert_called_once_with(
            media_item_id="media-cache-test",
            mode="article",
            content_hash=expected_hash,
            context_hash="media-context-hash",
        )

        mock_history.assert_called_once_with(
            client_key=expected_client_key,
            media_item_id="media-cache-test",
            snapshot_id=42,
        )

        mock_persist.assert_not_called()

    def test_cache_hit_without_snapshot_records_interaction(
        self,
    ):
        req, request = self.make_request()

        expected_client_key = (
            main.request_client_key(
                request
            )
        )

        with patch(
            "app.main.get_cached_analysis",
            return_value=self.cached_payload(req),
        ), patch(
            "app.main.record_analysis_cache_hit",
        ), patch(
            "app.main.upsert_media_item",
            return_value={
                "id": "media-no-snapshot",
            },
        ), patch(
            "app.main.load_evidence_analysis_state_for_media_item",
            return_value={
                "bundle": {},
                "context_hash": "media-context-hash",
            },
        ), patch(
            "app.main.find_analysis_snapshot",
            return_value=None,
        ), patch(
            "app.main.record_user_history",
        ) as mock_history, patch(
            "app.main.persist_analysis_snapshot",
        ) as mock_persist:
            response = main.analyze(
                req,
                request,
            )

        self.assertEqual(
            response.merit_score,
            81,
        )

        mock_history.assert_called_once_with(
            client_key=expected_client_key,
            media_item_id="media-no-snapshot",
            snapshot_id=None,
        )

        mock_persist.assert_not_called()

    def test_cache_hit_history_failure_does_not_block_response(
        self,
    ):
        req, request = self.make_request()

        with patch(
            "app.main.get_cached_analysis",
            return_value=self.cached_payload(req),
        ), patch(
            "app.main.record_analysis_cache_hit",
        ), patch(
            "app.main.load_evidence_analysis_state_for_media_item",
            return_value={
                "bundle": {},
                "context_hash": "media-context-hash",
            },
        ), patch(
            "app.main.upsert_media_item",
            side_effect=RuntimeError(
                "history unavailable"
            ),
        ), patch(
            "app.main.find_analysis_snapshot",
        ) as mock_find, patch(
            "app.main.record_user_history",
        ) as mock_history, patch(
            "app.main.persist_analysis_snapshot",
        ) as mock_persist, patch(
            "builtins.print",
        ):
            response = main.analyze(
                req,
                request,
            )

        self.assertEqual(
            response.merit_score,
            81,
        )

        mock_find.assert_not_called()
        mock_history.assert_not_called()
        mock_persist.assert_not_called()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
