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


class EvidenceSignalPolicyTests(
    unittest.TestCase
):
    def make_bundle(self):
        return (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                story_links=[
                    {
                        "story_id": "story-1",
                        "relationship_type":
                            "reports",
                        "confidence": 0.8,
                    },
                    {
                        "story_id": "story-2",
                        "relationship_type":
                            "confirms",
                        "confidence": 0.9,
                    },
                ],
                source_observations=[
                    {
                        "id": "source-observation-1",
                        "source_id": "source-1",
                        "subject_key": "case-1",
                        "observation_type":
                            "report",
                        "status": "unresolved",
                        "observed_at":
                            "2026-08-12T10:00:00+00:00",
                    },
                ],
                reporter_observations=[
                    {
                        "id": "reporter-observation-1",
                        "reporter_id":
                            "reporter-1",
                        "subject_key": "case-1",
                        "observation_type":
                            "report",
                        "status": "confirmed",
                        "observed_at":
                            "2026-08-12T11:00:00+00:00",
                    },
                ],
                evidence_records=[
                    {
                        "id": "evidence-1",
                        "evidence_key": "key-1",
                        "evidence_type":
                            "official_statement",
                        "subject_key": "case-1",
                        "canonical_url":
                            "https://example.com/official",
                        "verification_status":
                            "verified",
                        "observed_at":
                            "2026-08-12T12:00:00+00:00",
                    },
                    {
                        "id": "evidence-2",
                        "evidence_key": "key-2",
                        "evidence_type":
                            "independent_report",
                        "subject_key": "case-1",
                        "canonical_url":
                            "https://other.example/report",
                        "verification_status":
                            "unverified",
                        "observed_at":
                            "2026-08-12T09:00:00+00:00",
                    },
                ],
                evidence_links=[
                    {
                        "id": "link-1",
                        "evidence_id":
                            "evidence-1",
                        "story_id": "story-1",
                        "relationship_type":
                            "supports",
                    },
                    {
                        "id": "link-2",
                        "evidence_id":
                            "evidence-2",
                        "story_id": "story-1",
                        "relationship_type":
                            "contradicts",
                    },
                ],
            )
        )

    def test_current_vocabulary_is_recognized(
        self,
    ):
        report = (
            main.inspect_evidence_signal_vocabulary(
                self.make_bundle()
            )
        )

        self.assertEqual(
            report["version"],
            main.EVIDENCE_SIGNAL_POLICY_VERSION,
        )

        self.assertTrue(
            all(
                not values
                for values
                in report["unknown"].values()
            )
        )

        self.assertEqual(
            report["recognized"][
                "evidence_relationship_types"
            ],
            [
                "contradicts",
                "supports",
            ],
        )

    def test_unknown_values_are_exposed(
        self,
    ):
        bundle = self.make_bundle()

        bundle["evidence_links"].append(
            {
                "id": "link-unknown",
                "evidence_id": "evidence-1",
                "target_type": "story",
                "target_id": "story-2",
                "relationship_type":
                    "partially_supports",
                "confidence": None,
            }
        )

        bundle[
            "source_observations"
        ].append(
            {
                "id": "observation-unknown",
                "source_id": "source-1",
                "media_item_id": "",
                "story_id": "story-1",
                "subject_key": "case-1",
                "observation_type":
                    "analysis",
                "status": "disputed",
                "claim_summary": "",
                "provenance_url": "",
                "confidence": None,
                "observed_at":
                    "2026-08-12T13:00:00+00:00",
            }
        )

        report = (
            main.inspect_evidence_signal_vocabulary(
                bundle
            )
        )

        self.assertEqual(
            report["unknown"][
                "evidence_relationship_types"
            ],
            [
                "partially_supports"
            ],
        )

        self.assertEqual(
            report["unknown"][
                "observation_types"
            ],
            [
                "analysis"
            ],
        )

        self.assertEqual(
            report["unknown"][
                "observation_statuses"
            ],
            [
                "disputed"
            ],
        )

    def test_input_order_is_stable(
        self,
    ):
        bundle = self.make_bundle()

        first = (
            main.inspect_evidence_signal_vocabulary(
                bundle
            )
        )

        bundle["story_links"].reverse()
        bundle["evidence_records"].reverse()
        bundle["evidence_links"].reverse()

        second = (
            main.inspect_evidence_signal_vocabulary(
                bundle
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_empty_bundle_is_safe(
        self,
    ):
        report = (
            main.inspect_evidence_signal_vocabulary(
                {}
            )
        )

        self.assertTrue(
            all(
                not values
                for values
                in report["recognized"].values()
            )
        )

        self.assertTrue(
            all(
                not values
                for values
                in report["unknown"].values()
            )
        )

    def test_bundle_must_be_dictionary(
        self,
    ):
        with self.assertRaises(ValueError):
            main.inspect_evidence_signal_vocabulary(
                []
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
