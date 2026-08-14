import json
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


class IntelligenceStoryPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "story-persistence-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_story_upsert_reuses_identity(
        self,
    ):
        first = main.upsert_intelligence_story(
            canonical_key=(
                "transfer|player-a|club-b"
            ),
            canonical_title=(
                "Player A linked with Club B"
            ),
            status="developing",
            seen_at=(
                "2026-08-12T10:00:00+00:00"
            ),
            metadata={
                "sport": "football",
            },
        )

        second = main.upsert_intelligence_story(
            canonical_key=(
                " TRANSFER|PLAYER-A|CLUB-B "
            ),
            canonical_title=(
                "Club B advances for Player A"
            ),
            status="confirmed",
            seen_at=(
                "2026-08-12T12:00:00+00:00"
            ),
            metadata={
                "competition": "league",
            },
        )

        self.assertEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            second["canonical_key"],
            "transfer|player-a|club-b",
        )

        self.assertEqual(
            second["first_seen_at"],
            "2026-08-12T10:00:00+00:00",
        )

        self.assertEqual(
            second["last_seen_at"],
            "2026-08-12T12:00:00+00:00",
        )

        self.assertEqual(
            second["canonical_title"],
            "Club B advances for Player A",
        )

        self.assertEqual(
            second["status"],
            "confirmed",
        )

        self.assertEqual(
            json.loads(
                second["metadata_json"]
            ),
            {
                "competition": "league",
            },
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM intelligence_stories
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_empty_descriptive_update_preserves_data(
        self,
    ):
        first = main.upsert_intelligence_story(
            canonical_key=(
                "transfer|player-a|club-b"
            ),
            canonical_title=(
                "Player A linked with Club B"
            ),
            status="developing",
            seen_at=(
                "2026-08-12T10:00:00+00:00"
            ),
            metadata={
                "sport": "football",
            },
        )

        second = main.upsert_intelligence_story(
            canonical_key=(
                "transfer|player-a|club-b"
            ),
            canonical_title="",
            status="developing",
            seen_at=(
                "2026-08-12T11:00:00+00:00"
            ),
            metadata={},
        )

        self.assertEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            second["canonical_title"],
            "Player A linked with Club B",
        )

        self.assertEqual(
            json.loads(
                second["metadata_json"]
            ),
            {
                "sport": "football",
            },
        )

        self.assertEqual(
            second["first_seen_at"],
            "2026-08-12T10:00:00+00:00",
        )

        self.assertEqual(
            second["last_seen_at"],
            "2026-08-12T11:00:00+00:00",
        )

    def test_different_story_keys_are_distinct(
        self,
    ):
        first = main.upsert_intelligence_story(
            canonical_key=(
                "transfer|player-a|club-b"
            ),
        )

        second = main.upsert_intelligence_story(
            canonical_key=(
                "transfer|player-a|club-c"
            ),
        )

        self.assertNotEqual(
            first["id"],
            second["id"],
        )

    def test_empty_canonical_key_is_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            main.upsert_intelligence_story(
                canonical_key="   ",
            )

    def test_empty_status_is_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            main.upsert_intelligence_story(
                canonical_key=(
                    "transfer|player-a|club-b"
                ),
                status="   ",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
