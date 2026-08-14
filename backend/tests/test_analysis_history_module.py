import hashlib
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
    analysis_history,
)


class AnalysisHistoryModuleTests(
    unittest.TestCase
):
    def test_media_id_module_uses_injected_normalizer(
        self,
    ):
        normalized = (
            "https://example.com/story"
        )

        result = (
            analysis_history
            .media_item_id_for_url(
                (
                    "https://example.com/story"
                    "?utm_source=test"
                ),
                normalize_url=(
                    lambda value: normalized
                ),
            )
        )

        expected = hashlib.sha256(
            (
                "media|"
                + normalized
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        self.assertEqual(
            result,
            expected,
        )

    def test_main_media_id_uses_main_normalizer(
        self,
    ):
        canonical = (
            "https://example.com/canonical"
        )

        with patch.object(
            main,
            "normalized_analysis_url",
            return_value=canonical,
        ) as normalizer:
            result = (
                main.media_item_id_for_url(
                    "https://example.com/raw"
                )
            )

        normalizer.assert_called_once_with(
            "https://example.com/raw"
        )

        self.assertEqual(
            result,
            hashlib.sha256(
                (
                    "media|"
                    + canonical
                ).encode(
                    "utf-8"
                )
            ).hexdigest(),
        )

    def test_main_upsert_injects_runtime_dependencies(
        self,
    ):
        sentinel = {
            "id": "media-1"
        }

        with patch.object(
            main,
            "_upsert_media_item_history_impl",
            return_value=sentinel,
        ) as impl:
            result = main.upsert_media_item(
                url=(
                    "https://example.com/story"
                ),
                mode="article",
                title="Story",
                content_hash="hash",
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertIs(
            kwargs["normalize_url"],
            main.normalized_analysis_url,
        )

        self.assertIs(
            kwargs["id_resolver"],
            main.media_item_id_for_url,
        )

        self.assertIs(
            kwargs["connection_factory"],
            main.db_conn,
        )

    def test_snapshot_lookup_injects_versions_and_database(
        self,
    ):
        with patch.object(
            main,
            "_find_analysis_snapshot_history_impl",
            return_value=None,
        ) as impl:
            result = (
                main.find_analysis_snapshot(
                    media_item_id="media-1",
                    mode="article",
                    content_hash="hash",
                )
            )

        self.assertIsNone(
            result
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertEqual(
            kwargs[
                "default_analysis_version"
            ],
            main.ANALYSIS_VERSION,
        )

        self.assertEqual(
            kwargs[
                "default_scoring_version"
            ],
            main.SCORING_VERSION,
        )

        self.assertIs(
            kwargs["connection_factory"],
            main.db_conn,
        )

    def test_snapshot_persistence_injects_runtime_dependencies(
        self,
    ):
        sentinel = {
            "snapshot": {
                "id": 1
            },
            "created": True,
        }

        with patch.object(
            main,
            "_persist_analysis_snapshot_history_impl",
            return_value=sentinel,
        ) as impl:
            result = (
                main.persist_analysis_snapshot(
                    media_item_id="media-1",
                    mode="article",
                    content_hash="hash",
                    response={
                        "merit_score": 70
                    },
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertEqual(
            kwargs[
                "default_analysis_version"
            ],
            main.ANALYSIS_VERSION,
        )

        self.assertEqual(
            kwargs[
                "default_scoring_version"
            ],
            main.SCORING_VERSION,
        )

        self.assertIs(
            kwargs["connection_factory"],
            main.db_conn,
        )

    def test_user_history_injects_database(
        self,
    ):
        sentinel = {
            "client_key": "client"
        }

        with patch.object(
            main,
            "_record_user_history_history_impl",
            return_value=sentinel,
        ) as impl:
            result = (
                main.record_user_history(
                    client_key="client",
                    media_item_id="media-1",
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        self.assertIs(
            (
                impl.call_args.kwargs[
                    "connection_factory"
                ]
            ),
            main.db_conn,
        )


if __name__ == "__main__":
    unittest.main()
