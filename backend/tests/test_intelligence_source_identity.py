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


class IntelligenceSourceIdentityTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "source-identity-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_www_and_root_domain_share_source(
        self,
    ):
        first_url = (
            "https://www.espn.com/football/"
            "story/_/id/123/test"
            "?utm_source=one"
        )

        second_url = (
            "https://espn.com/football/"
            "another-story"
        )

        self.assertEqual(
            main.source_domain_for_url(
                first_url
            ),
            "espn.com",
        )

        self.assertEqual(
            main.source_key_for_url(
                first_url
            ),
            "publisher|espn.com",
        )

        self.assertEqual(
            main.source_key_for_url(
                first_url
            ),
            main.source_key_for_url(
                second_url
            ),
        )

        self.assertEqual(
            main.source_id_for_url(
                first_url
            ),
            main.source_id_for_url(
                second_url
            ),
        )

    def test_distinct_subdomain_stays_distinct(
        self,
    ):
        root = (
            main.source_key_for_url(
                "https://example.com/story"
            )
        )

        subdomain = (
            main.source_key_for_url(
                "https://news.example.com/story"
            )
        )

        self.assertEqual(
            root,
            "publisher|example.com",
        )

        self.assertEqual(
            subdomain,
            "publisher|news.example.com",
        )

        self.assertNotEqual(
            root,
            subdomain,
        )

    def test_source_type_is_part_of_identity(
        self,
    ):
        publisher_id = (
            main.source_id_for_url(
                "https://example.com/story",
                source_type="publisher",
            )
        )

        official_id = (
            main.source_id_for_url(
                "https://example.com/story",
                source_type="official",
            )
        )

        self.assertNotEqual(
            publisher_id,
            official_id,
        )

        self.assertEqual(
            main.source_key_for_url(
                "https://example.com/story",
                source_type="OFFICIAL",
            ),
            "official|example.com",
        )

    def test_source_upsert_reuses_identity(
        self,
    ):
        first = (
            main.upsert_intelligence_source(
                url=(
                    "https://www.espn.com/"
                    "football/story-one"
                ),
                display_name="ESPN",
                seen_at=(
                    "2026-08-11T10:00:00+00:00"
                ),
                metadata={
                    "language": "en",
                },
            )
        )

        second = (
            main.upsert_intelligence_source(
                url=(
                    "https://espn.com/"
                    "football/story-two"
                ),
                display_name="ESPN Football",
                publication_founded_at="1979",
                domain_registered_at=(
                    "1994-10-04"
                ),
                seen_at=(
                    "2026-08-11T12:00:00+00:00"
                ),
                metadata={
                    "region": "global",
                },
            )
        )

        self.assertEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            second["source_key"],
            "publisher|espn.com",
        )

        self.assertEqual(
            second["canonical_domain"],
            "espn.com",
        )

        self.assertEqual(
            second["first_seen_at"],
            "2026-08-11T10:00:00+00:00",
        )

        self.assertEqual(
            second["last_seen_at"],
            "2026-08-11T12:00:00+00:00",
        )

        self.assertEqual(
            second["display_name"],
            "ESPN Football",
        )

        self.assertEqual(
            second["publication_founded_at"],
            "1979",
        )

        self.assertEqual(
            second["domain_registered_at"],
            "1994-10-04",
        )

        self.assertEqual(
            json.loads(
                second["metadata_json"]
            ),
            {
                "region": "global",
            },
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM intelligence_sources
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )