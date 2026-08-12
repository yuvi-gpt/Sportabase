import sqlite3
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


class StoryMediaLinkPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "story-media-link-test.db"
        )

        main.init_db()

        self.story = (
            main.upsert_intelligence_story(
                canonical_key=(
                    "transfer|player-a|club-b"
                ),
                seen_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        self.media = main.upsert_media_item(
            url=(
                "https://example.com/"
                "player-a-club-b"
            ),
            mode="article",
            title=(
                "Player A linked with Club B"
            ),
            content_hash="content-hash-1",
            seen_at=(
                "2026-08-12T10:05:00+00:00"
            ),
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_identical_link_is_idempotent(
        self,
    ):
        first = main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type="reports",
            confidence=0.8,
            linked_at=(
                "2026-08-12T10:10:00+00:00"
            ),
        )

        second = main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type="reports",
            confidence=0.8,
            linked_at=(
                "2026-08-12T10:10:00+00:00"
            ),
        )

        self.assertEqual(
            first,
            second,
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM story_media_links
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_existing_edge_updates_current_state(
        self,
    ):
        first = main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type="reports",
            confidence=0.6,
            linked_at=(
                "2026-08-12T10:10:00+00:00"
            ),
        )

        second = main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type="confirms",
            confidence=0.9,
            linked_at=(
                "2026-08-12T12:00:00+00:00"
            ),
        )

        self.assertEqual(
            first["story_id"],
            second["story_id"],
        )

        self.assertEqual(
            first["media_item_id"],
            second["media_item_id"],
        )

        self.assertEqual(
            second["relationship_type"],
            "confirms",
        )

        self.assertEqual(
            second["confidence"],
            0.9,
        )

        self.assertEqual(
            second["linked_at"],
            "2026-08-12T10:10:00+00:00",
        )

    def test_relationship_type_is_normalized(
        self,
    ):
        link = main.link_media_item_to_story(
            story_id=self.story["id"],
            media_item_id=self.media["id"],
            relationship_type=" REPORTS ",
            confidence=0.5,
        )

        self.assertEqual(
            link["relationship_type"],
            "reports",
        )

    def test_invalid_confidence_is_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            main.link_media_item_to_story(
                story_id=self.story["id"],
                media_item_id=self.media["id"],
                confidence=1.1,
            )

    def test_foreign_keys_are_enforced(
        self,
    ):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.link_media_item_to_story(
                story_id="missing-story",
                media_item_id=self.media["id"],
            )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.link_media_item_to_story(
                story_id=self.story["id"],
                media_item_id="missing-media",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
