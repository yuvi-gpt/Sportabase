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


class IntelligenceReporterIdentityTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "reporter-identity-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_identity_key_is_normalized(
        self,
    ):
        first = (
            main.reporter_id_for_identity_key(
                " Social|X|Reporter-A "
            )
        )

        second = (
            main.reporter_id_for_identity_key(
                "social|x|reporter-a"
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            len(first),
            64,
        )

    def test_different_identity_keys_are_distinct(
        self,
    ):
        first = (
            main.reporter_id_for_identity_key(
                "social|x|reporter-a"
            )
        )

        second = (
            main.reporter_id_for_identity_key(
                "social|x|reporter-b"
            )
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_same_name_does_not_force_same_identity(
        self,
    ):
        first = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    "social|x|alex-one"
                ),
                display_name="Alex Smith",
            )
        )

        second = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    "social|x|alex-two"
                ),
                display_name="Alex Smith",
            )
        )

        self.assertNotEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            first["display_name"],
            second["display_name"],
        )

    def test_reporter_upsert_reuses_identity(
        self,
    ):
        first = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    "social|x|reporter-a"
                ),
                display_name="Reporter A",
                seen_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
                metadata={
                    "language": "en",
                },
            )
        )

        second = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    " SOCIAL|X|REPORTER-A "
                ),
                display_name=(
                    "Reporter A Updated"
                ),
                seen_at=(
                    "2026-08-12T12:00:00+00:00"
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
            second["identity_key"],
            "social|x|reporter-a",
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
            second["display_name"],
            "Reporter A Updated",
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
                    FROM intelligence_reporters
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