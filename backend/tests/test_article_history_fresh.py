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


class ArticleHistoryFreshTests(
    unittest.TestCase
):
    def make_request(self):
        req = main.AnalyzeRequest(
            title="Club confirms major signing",
            url=(
                "https://example.com/"
                "fresh-confirmed-signing"
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
                    "fresh-history-test",
            },
            client=SimpleNamespace(
                host="127.0.0.1"
            ),
        )

        return req, request

    def analysis_patches(self):
        return (
            patch(
                "app.main.get_cached_analysis",
                return_value=None,
            ),
            patch(
                "app.main.detect_content_language",
                return_value={
                    "detected_language": "English",
                    "mixed_language": False,
                },
            ),
            patch(
                "app.main.detect_article_type",
                return_value={
                    "primary_type":
                        "transfer_confirmation",
                    "label":
                        "Transfer Confirmation",
                    "subtype":
                        "official_confirmation",
                    "confidence": 0.95,
                    "signals": [
                        "Official announcement."
                    ],
                },
            ),
            patch(
                "app.main.run_article_ai_strategy",
                return_value={
                    "ai_type_info": {},
                    "single_pass_result": {
                        "bullets": [
                            "The club confirmed "
                            "the signing."
                        ],
                        "ui_labels": {},
                    },
                    "used_single_pass": False,
                },
            ),
            patch(
                "app.main.merit_score",
                return_value={
                    "total": 84,
                    "badge": "High Merit",
                    "reasons": [
                        "Official confirmation."
                    ],
                    "components": {
                        "source": 20.0,
                    },
                    "calculation": {
                        "raw_total": 84.0,
                        "final_total": 84,
                    },
                },
            ),
        )

    def test_fresh_analysis_persists_before_cache(
        self,
    ):
        req, request = self.make_request()

        cleaned_text = main.clean_html(
            req.text
        )

        cache_content = (
            f"{req.title}\n"
            f"{cleaned_text}"
        )

        expected_hash = (
            main.analysis_content_hash(
                cache_content
            )
        )

        expected_client_key = (
            main.request_client_key(
                request
            )
        )

        order = []

        def upsert_side_effect(**kwargs):
            order.append("media")
            return {
                "id": "fresh-media",
            }

        def snapshot_side_effect(**kwargs):
            order.append("snapshot")
            return {
                "snapshot": {
                    "id": 51,
                },
                "created": True,
            }

        def history_side_effect(**kwargs):
            order.append("history")
            return {}

        def cache_side_effect(**kwargs):
            order.append("cache")

        patches = self.analysis_patches()

        with patches[0], patches[1], patches[2], \
             patches[3], patches[4], patch(
                "app.main.upsert_media_item",
                side_effect=upsert_side_effect,
             ) as mock_upsert, patch(
                "app.main.expanded_evidence_context_hash_for_media_item",
                return_value="media-context-hash",
             ) as mock_context_hash, patch(
                "app.main.persist_analysis_snapshot",
                side_effect=snapshot_side_effect,
             ) as mock_snapshot, patch(
                "app.main.record_user_history",
                side_effect=history_side_effect,
             ) as mock_history, patch(
                "app.main.set_cached_analysis",
                side_effect=cache_side_effect,
             ) as mock_cache, patch(
                "app.main.find_analysis_snapshot",
             ) as mock_find:

            response = main.analyze(
                req,
                request,
            )

        self.assertEqual(
            response.merit_score,
            84,
        )

        self.assertEqual(
            order,
            [
                "media",
                "snapshot",
                "history",
                "cache",
            ],
        )

        mock_upsert.assert_called_once_with(
            url=req.url,
            mode="article",
            title=req.title,
            content_hash=expected_hash,
        )

        snapshot_kwargs = (
            mock_snapshot.call_args.kwargs
        )

        self.assertEqual(
            snapshot_kwargs[
                "media_item_id"
            ],
            "fresh-media",
        )

        self.assertEqual(
            snapshot_kwargs[
                "content_hash"
            ],
            expected_hash,
        )

        self.assertEqual(
            snapshot_kwargs[
                "context_hash"
            ],
            "media-context-hash",
        )

        mock_context_hash.assert_called_once_with(
            media_item_id="fresh-media",
        )

        self.assertEqual(
            snapshot_kwargs[
                "merit_score"
            ],
            84,
        )

        self.assertEqual(
            snapshot_kwargs[
                "article_type"
            ],
            "transfer_confirmation",
        )

        self.assertEqual(
            snapshot_kwargs[
                "response"
            ][
                "merit_score"
            ],
            84,
        )

        mock_history.assert_called_once_with(
            client_key=expected_client_key,
            media_item_id="fresh-media",
            snapshot_id=51,
        )

        mock_cache.assert_called_once()
        mock_find.assert_not_called()

    def test_reused_snapshot_is_linked_to_history(
        self,
    ):
        req, request = self.make_request()

        expected_client_key = (
            main.request_client_key(
                request
            )
        )

        patches = self.analysis_patches()

        with patches[0], patches[1], patches[2], \
             patches[3], patches[4], patch(
                "app.main.upsert_media_item",
                return_value={
                    "id": "reused-media",
                },
             ), patch(
                "app.main.expanded_evidence_context_hash_for_media_item",
                return_value="media-context-hash",
             ), patch(
                "app.main.persist_analysis_snapshot",
                return_value={
                    "snapshot": {
                        "id": 77,
                    },
                    "created": False,
                },
             ), patch(
                "app.main.record_user_history",
             ) as mock_history, patch(
                "app.main.set_cached_analysis",
             ) as mock_cache:

            response = main.analyze(
                req,
                request,
            )

        self.assertEqual(
            response.merit_score,
            84,
        )

        mock_history.assert_called_once_with(
            client_key=expected_client_key,
            media_item_id="reused-media",
            snapshot_id=77,
        )

        mock_cache.assert_called_once()

    def test_fresh_history_failure_does_not_block_response_or_cache(
        self,
    ):
        req, request = self.make_request()

        patches = self.analysis_patches()

        with patches[0], patches[1], patches[2], \
             patches[3], patches[4], patch(
                "app.main.upsert_media_item",
                side_effect=RuntimeError(
                    "history unavailable"
                ),
             ), patch(
                "app.main.persist_analysis_snapshot",
             ) as mock_snapshot, patch(
                "app.main.record_user_history",
             ) as mock_history, patch(
                "app.main.set_cached_analysis",
             ) as mock_cache, patch(
                "builtins.print",
             ):

            response = main.analyze(
                req,
                request,
            )

        self.assertEqual(
            response.merit_score,
            84,
        )

        mock_snapshot.assert_not_called()
        mock_history.assert_not_called()
        mock_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )