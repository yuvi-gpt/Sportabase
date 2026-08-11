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


class SnapshotContextPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "context-persistence-test.db"
        )

        main.init_db()

        self.media_item = (
            main.upsert_media_item(
                url=(
                    "https://example.com/"
                    "developing-transfer"
                ),
                mode="article",
                title="Developing transfer",
                content_hash="stable-content",
            )
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_same_context_reuses_snapshot(
        self,
    ):
        first = (
            main.persist_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash=(
                    "evidence-context-a"
                ),
                response={
                    "merit_score": 54,
                },
                merit_score=54,
            )
        )

        second = (
            main.persist_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash=(
                    "evidence-context-a"
                ),
                response={
                    "merit_score": 54,
                },
                merit_score=54,
            )
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

        self.assertEqual(
            first["snapshot"][
                "context_hash"
            ],
            "evidence-context-a",
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

    def test_changed_context_creates_snapshot(
        self,
    ):
        first = (
            main.persist_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash=(
                    "one-report-only"
                ),
                response={
                    "merit_score": 54,
                },
                merit_score=54,
            )
        )

        second = (
            main.persist_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash=(
                    "club-plus-two-sources"
                ),
                response={
                    "merit_score": 82,
                },
                merit_score=82,
            )
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
            first["snapshot"][
                "content_hash"
            ],
            second["snapshot"][
                "content_hash"
            ],
        )

        self.assertNotEqual(
            first["snapshot"][
                "context_hash"
            ],
            second["snapshot"][
                "context_hash"
            ],
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

    def test_find_snapshot_respects_context(
        self,
    ):
        persisted = (
            main.persist_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash="context-one",
                response={
                    "merit_score": 63,
                },
                merit_score=63,
            )
        )

        matching = (
            main.find_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash="context-one",
            )
        )

        mismatched = (
            main.find_analysis_snapshot(
                media_item_id=(
                    self.media_item["id"]
                ),
                mode="article",
                content_hash="stable-content",
                context_hash="context-two",
            )
        )

        self.assertIsNotNone(
            matching
        )

        self.assertEqual(
            matching["id"],
            persisted["snapshot"]["id"],
        )

        self.assertEqual(
            matching["context_hash"],
            "context-one",
        )

        self.assertIsNone(
            mismatched
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )