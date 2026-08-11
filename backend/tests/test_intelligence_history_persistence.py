import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main


class IntelligenceHistoryPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "history-persistence-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_tracking_variants_reuse_media_item(
        self,
    ):
        first = main.upsert_media_item(
            url=(
                "https://www.espn.com/football/"
                "story/_/id/12345/test-story"
                "?utm_source=first"
            ),
            mode="article",
            title="Original title",
            content_hash="hash-one",
            seen_at=(
                "2026-08-11T10:00:00+00:00"
            ),
        )

        second = main.upsert_media_item(
            url=(
                "https://www.espn.com/football/"
                "story/_/id/12345/test-story"
                "?utm_source=second"
            ),
            mode="article",
            title="Updated title",
            content_hash="hash-two",
            seen_at=(
                "2026-08-11T11:00:00+00:00"
            ),
        )

        self.assertEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            second["canonical_url"],
            (
                "https://www.espn.com/football/"
                "story/_/id/12345/test-story"
            ),
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM media_items
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_updated_content_updates_existing_media_item(
        self,
    ):
        first_seen = (
            "2026-08-11T10:00:00+00:00"
        )

        second_seen = (
            "2026-08-11T12:30:00+00:00"
        )

        first = main.upsert_media_item(
            url=(
                "https://example.com/"
                "developing-story"
            ),
            mode="article",
            title="Developing story",
            content_hash="content-hash-v1",
            seen_at=first_seen,
        )

        second = main.upsert_media_item(
            url=(
                "https://example.com/"
                "developing-story"
            ),
            mode="article",
            title="Developing story updated",
            content_hash="content-hash-v2",
            seen_at=second_seen,
        )

        self.assertEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            second["first_seen_at"],
            first_seen,
        )

        self.assertEqual(
            second["last_seen_at"],
            second_seen,
        )

        self.assertEqual(
            second["latest_content_hash"],
            "content-hash-v2",
        )

        self.assertEqual(
            second["title"],
            "Developing story updated",
        )

    def test_media_item_id_is_deterministic(
        self,
    ):
        first_id = (
            main.media_item_id_for_url(
                (
                    "https://example.com/story"
                    "?utm_source=one"
                )
            )
        )

        second_id = (
            main.media_item_id_for_url(
                (
                    "https://example.com/story"
                    "?utm_source=two"
                )
            )
        )

        self.assertEqual(
            first_id,
            second_id,
        )

        self.assertEqual(
            len(first_id),
            64,
        )

    def test_missing_required_identity_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.upsert_media_item(
                url="",
                mode="article",
                title="Test",
                content_hash="hash",
            )

        with self.assertRaises(
            ValueError
        ):
            main.upsert_media_item(
                url="https://example.com/story",
                mode="article",
                title="Test",
                content_hash="",
            )


    def test_identical_analysis_reuses_snapshot(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "same-analysis"
            ),
            mode="article",
            title="Same analysis",
            content_hash="same-hash",
            seen_at=(
                "2026-08-11T10:00:00+00:00"
            ),
        )

        first = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="same-hash",
            response={
                "merit_score": 61,
            },
            analyzed_at=(
                "2026-08-11T10:00:00+00:00"
            ),
            merit_score=61,
            badge="Developing",
        )

        second = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="same-hash",
            response={
                "merit_score": 61,
            },
            analyzed_at=(
                "2026-08-11T10:05:00+00:00"
            ),
            merit_score=61,
            badge="Developing",
        )

        self.assertTrue(
            first["created"]
        )

        self.assertFalse(
            second["created"]
        )

        self.assertEqual(
            first["snapshot"]["id"],
            second["snapshot"]["id"],
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM analysis_snapshots
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_changed_content_creates_new_snapshot(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "changing-analysis"
            ),
            mode="article",
            title="Changing analysis",
            content_hash="content-v1",
            seen_at=(
                "2026-08-11T10:00:00+00:00"
            ),
        )

        first = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="content-v1",
            response={
                "merit_score": 44,
            },
            analyzed_at=(
                "2026-08-11T10:00:00+00:00"
            ),
            merit_score=44,
            badge="Low Evidence",
        )

        main.upsert_media_item(
            url=(
                "https://example.com/"
                "changing-analysis"
            ),
            mode="article",
            title="Changing analysis updated",
            content_hash="content-v2",
            seen_at=(
                "2026-08-11T12:00:00+00:00"
            ),
        )

        second = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="content-v2",
            response={
                "merit_score": 71,
            },
            analyzed_at=(
                "2026-08-11T12:00:00+00:00"
            ),
            merit_score=71,
            badge="Substantial Signal",
        )

        self.assertTrue(
            first["created"]
        )

        self.assertTrue(
            second["created"]
        )

        self.assertNotEqual(
            first["snapshot"]["id"],
            second["snapshot"]["id"],
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM analysis_snapshots
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            2,
        )

    def test_scoring_version_change_creates_new_snapshot(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "versioned-analysis"
            ),
            mode="article",
            title="Versioned analysis",
            content_hash="stable-content",
            seen_at=(
                "2026-08-11T10:00:00+00:00"
            ),
        )

        first = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="stable-content",
            response={
                "merit_score": 58,
            },
            scoring_version=(
                "merit-v1-legacy"
            ),
            merit_score=58,
        )

        second = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="stable-content",
            response={
                "merit_score": 64,
            },
            scoring_version=(
                "merit-v2-evidence"
            ),
            merit_score=64,
        )

        self.assertTrue(
            first["created"]
        )

        self.assertTrue(
            second["created"]
        )

        self.assertNotEqual(
            first["snapshot"]["id"],
            second["snapshot"]["id"],
        )

        self.assertEqual(
            first["snapshot"]["content_hash"],
            second["snapshot"]["content_hash"],
        )

        self.assertNotEqual(
            first["snapshot"]["scoring_version"],
            second["snapshot"]["scoring_version"],
        )

    def test_same_client_updates_single_history_row(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "history-repeat"
            ),
            mode="article",
            title="History repeat",
            content_hash="history-hash",
            seen_at=(
                "2026-08-11T10:00:00+00:00"
            ),
        )

        snapshot = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="history-hash",
            response={
                "merit_score": 67,
            },
            analyzed_at=(
                "2026-08-11T10:00:00+00:00"
            ),
            merit_score=67,
        )

        first = main.record_user_history(
            client_key="client-one",
            media_item_id=media_item["id"],
            snapshot_id=(
                snapshot["snapshot"]["id"]
            ),
            analyzed_at=(
                "2026-08-11T10:00:00+00:00"
            ),
        )

        second = main.record_user_history(
            client_key="client-one",
            media_item_id=media_item["id"],
            snapshot_id=None,
            analyzed_at=(
                "2026-08-11T10:05:00+00:00"
            ),
        )

        self.assertEqual(
            first["first_analyzed_at"],
            "2026-08-11T10:00:00+00:00",
        )

        self.assertEqual(
            second["first_analyzed_at"],
            "2026-08-11T10:00:00+00:00",
        )

        self.assertEqual(
            second["last_analyzed_at"],
            "2026-08-11T10:05:00+00:00",
        )

        self.assertEqual(
            second["analysis_count"],
            2,
        )

        self.assertEqual(
            second["last_snapshot_id"],
            snapshot["snapshot"]["id"],
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM user_history
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_different_clients_share_media_but_not_history(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "shared-intelligence"
            ),
            mode="article",
            title="Shared intelligence",
            content_hash="shared-hash",
        )

        snapshot = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="shared-hash",
            response={
                "merit_score": 72,
            },
            merit_score=72,
        )

        first = main.record_user_history(
            client_key="client-alpha",
            media_item_id=media_item["id"],
            snapshot_id=(
                snapshot["snapshot"]["id"]
            ),
        )

        second = main.record_user_history(
            client_key="client-beta",
            media_item_id=media_item["id"],
            snapshot_id=(
                snapshot["snapshot"]["id"]
            ),
        )

        self.assertNotEqual(
            first["client_key"],
            second["client_key"],
        )

        self.assertEqual(
            first["media_item_id"],
            second["media_item_id"],
        )

        self.assertEqual(
            first["last_snapshot_id"],
            second["last_snapshot_id"],
        )

        conn = main.db_conn()

        try:
            media_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM media_items
                    """
                ).fetchone()[0]
            )

            snapshot_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM analysis_snapshots
                    """
                ).fetchone()[0]
            )

            history_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM user_history
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            media_count,
            1,
        )

        self.assertEqual(
            snapshot_count,
            1,
        )

        self.assertEqual(
            history_count,
            2,
        )

    def test_history_rejects_snapshot_from_other_media(
        self,
    ):
        first_media = main.upsert_media_item(
            url=(
                "https://example.com/"
                "first-media"
            ),
            mode="article",
            title="First media",
            content_hash="first-hash",
        )

        second_media = main.upsert_media_item(
            url=(
                "https://example.com/"
                "second-media"
            ),
            mode="article",
            title="Second media",
            content_hash="second-hash",
        )

        snapshot = main.persist_analysis_snapshot(
            media_item_id=first_media["id"],
            mode="article",
            content_hash="first-hash",
            response={
                "merit_score": 55,
            },
            merit_score=55,
        )

        with self.assertRaises(
            ValueError
        ):
            main.record_user_history(
                client_key="client-wrong-link",
                media_item_id=second_media["id"],
                snapshot_id=(
                    snapshot["snapshot"]["id"]
                ),
            )

        conn = main.db_conn()

        try:
            history_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM user_history
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            history_count,
            0,
        )

    def test_find_analysis_snapshot_returns_match(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "snapshot-lookup"
            ),
            mode="article",
            title="Snapshot lookup",
            content_hash="lookup-hash",
        )

        created = main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="lookup-hash",
            response={
                "merit_score": 63,
            },
            merit_score=63,
        )

        found = main.find_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="lookup-hash",
        )

        self.assertIsNotNone(
            found
        )

        self.assertEqual(
            found["id"],
            created["snapshot"]["id"],
        )

        self.assertEqual(
            found["merit_score"],
            63,
        )

    def test_find_analysis_snapshot_rejects_mismatch(
        self,
    ):
        media_item = main.upsert_media_item(
            url=(
                "https://example.com/"
                "snapshot-mismatch"
            ),
            mode="article",
            title="Snapshot mismatch",
            content_hash="stable-hash",
        )

        main.persist_analysis_snapshot(
            media_item_id=media_item["id"],
            mode="article",
            content_hash="stable-hash",
            response={
                "merit_score": 57,
            },
            merit_score=57,
        )

        wrong_content = (
            main.find_analysis_snapshot(
                media_item_id=media_item["id"],
                mode="article",
                content_hash="different-hash",
            )
        )

        wrong_scoring_version = (
            main.find_analysis_snapshot(
                media_item_id=media_item["id"],
                mode="article",
                content_hash="stable-hash",
                scoring_version=(
                    "merit-v999-test"
                ),
            )
        )

        self.assertIsNone(
            wrong_content
        )

        self.assertIsNone(
            wrong_scoring_version
        )

if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )