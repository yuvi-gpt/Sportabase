import hashlib
import sys
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


class IntelligenceStoryIdentityTests(
    unittest.TestCase
):
    def test_canonical_key_is_normalized(
        self,
    ):
        first = main.story_id_for_canonical_key(
            " Transfer | Player-A | Club-B "
        )

        second = main.story_id_for_canonical_key(
            "transfer   |   player-a   |   club-b"
        )

        self.assertEqual(
            first,
            second,
        )

    def test_different_canonical_keys_are_distinct(
        self,
    ):
        first = main.story_id_for_canonical_key(
            "transfer|player-a|club-b"
        )

        second = main.story_id_for_canonical_key(
            "transfer|player-a|club-c"
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_story_identity_uses_story_namespace(
        self,
    ):
        canonical_key = (
            "transfer|player-a|club-b"
        )

        expected = hashlib.sha256(
            (
                "story|"
                + canonical_key
            ).encode("utf-8")
        ).hexdigest()

        self.assertEqual(
            main.story_id_for_canonical_key(
                canonical_key
            ),
            expected,
        )

    def test_empty_canonical_key_is_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            main.story_id_for_canonical_key(
                "   "
            )


if __name__ == "__main__":
    unittest.main()
