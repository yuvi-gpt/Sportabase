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


class IntelligenceClaimPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "intelligence-claim-persistence.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_claim_id_is_deterministic_and_normalized(
        self,
    ):
        first = (
            main.claim_id_for_canonical_key(
                (
                    " Transfer|Player A|Club B|"
                    "Agreement Reached "
                )
            )
        )

        second = (
            main.claim_id_for_canonical_key(
                (
                    "transfer|player a|club b|"
                    "agreement reached"
                )
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_claim_identity_uses_claim_namespace(
        self,
    ):
        claim_id = (
            main.claim_id_for_canonical_key(
                "same-canonical-key"
            )
        )

        story_id = (
            main.story_id_for_canonical_key(
                "same-canonical-key"
            )
        )

        self.assertNotEqual(
            claim_id,
            story_id,
        )

    def test_claim_upsert_reuses_identity(
        self,
    ):
        first = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    " Transfer|Player A|Club B|"
                    "Agreement Reached "
                ),
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                canonical_text=(
                    "Agreement reached."
                ),
                claim_type="Assertion",
                metadata={
                    "origin": "manual",
                },
                seen_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )
        )

        second = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|player a|club b|"
                    "agreement reached"
                ),
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                canonical_text=(
                    "Club B reached an agreement "
                    "for Player A."
                ),
                claim_type="TRANSFER_STATE",
                seen_at=(
                    "2026-08-12T12:30:00+00:00"
                ),
            )
        )

        self.assertEqual(
            first["id"],
            second["id"],
        )

        self.assertEqual(
            second["canonical_key"],
            (
                "transfer|player a|club b|"
                "agreement reached"
            ),
        )

        self.assertEqual(
            second["canonical_text"],
            (
                "Club B reached an agreement "
                "for Player A."
            ),
        )

        self.assertEqual(
            second["claim_type"],
            "transfer_state",
        )

        self.assertEqual(
            second["first_seen_at"],
            "2026-08-12T12:00:00+00:00",
        )

        self.assertEqual(
            second["last_seen_at"],
            "2026-08-12T12:30:00+00:00",
        )

        self.assertEqual(
            second["metadata_json"],
            '{"origin": "manual"}',
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM intelligence_claims
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_empty_descriptive_update_preserves_text(
        self,
    ):
        main.upsert_intelligence_claim(
            canonical_key=(
                "transfer|a|b|medical"
            ),
            subject_key="transfer|a|b",
            canonical_text=(
                "A medical is scheduled."
            ),
            seen_at=(
                "2026-08-12T12:00:00+00:00"
            ),
        )

        updated = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|medical"
                ),
                subject_key="transfer|a|b",
                canonical_text="",
                seen_at=(
                    "2026-08-12T12:15:00+00:00"
                ),
            )
        )

        self.assertEqual(
            updated["canonical_text"],
            "A medical is scheduled.",
        )

    def test_subject_mismatch_is_rejected(
        self,
    ):
        main.upsert_intelligence_claim(
            canonical_key=(
                "transfer|a|b|agreement"
            ),
            subject_key="transfer|a|b",
            seen_at=(
                "2026-08-12T12:00:00+00:00"
            ),
        )

        with self.assertRaises(
            ValueError
        ):
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|agreement"
                ),
                subject_key="transfer|a|c",
                seen_at=(
                    "2026-08-12T12:10:00+00:00"
                ),
            )

    def test_different_claim_keys_are_distinct(
        self,
    ):
        agreement = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|agreement"
                ),
                subject_key="transfer|a|b",
                seen_at=(
                    "2026-08-12T12:00:00+00:00"
                ),
            )
        )

        medical = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|a|b|medical"
                ),
                subject_key="transfer|a|b",
                seen_at=(
                    "2026-08-12T12:05:00+00:00"
                ),
            )
        )

        self.assertNotEqual(
            agreement["id"],
            medical["id"],
        )

    def test_required_identity_fields_are_enforced(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.claim_id_for_canonical_key(
                "   "
            )

        with self.assertRaises(
            ValueError
        ):
            main.upsert_intelligence_claim(
                canonical_key="   ",
                subject_key="subject-1",
            )

        with self.assertRaises(
            ValueError
        ):
            main.upsert_intelligence_claim(
                canonical_key="claim-1",
                subject_key="   ",
            )

        with self.assertRaises(
            ValueError
        ):
            main.upsert_intelligence_claim(
                canonical_key="claim-1",
                subject_key="subject-1",
                claim_type="   ",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
