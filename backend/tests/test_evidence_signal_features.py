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


class EvidenceSignalFeatureTests(
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
                        "status":
                            "unresolved",
                        "observed_at":
                            "2026-08-12T10:00:00+00:00",
                    },
                    {
                        "id": "source-observation-2",
                        "source_id": "source-2",
                        "subject_key": "case-1",
                        "observation_type":
                            "report",
                        "status":
                            "confirmed",
                        "observed_at":
                            "2026-08-12T11:00:00+00:00",
                    },
                ],
                reporter_observations=[
                    {
                        "id":
                            "reporter-observation-1",
                        "reporter_id":
                            "reporter-1",
                        "source_id":
                            "source-1",
                        "subject_key":
                            "case-1",
                        "observation_type":
                            "report",
                        "status":
                            "confirmed",
                        "observed_at":
                            "2026-08-12T11:30:00+00:00",
                    },
                ],
                evidence_records=[
                    {
                        "id": "evidence-1",
                        "evidence_key":
                            "key-1",
                        "evidence_type":
                            "official_statement",
                        "subject_key":
                            "case-1",
                        "canonical_url":
                            "https://example.com/official",
                        "verification_status":
                            "verified",
                        "observed_at":
                            "2026-08-12T12:00:00+00:00",
                    },
                    {
                        "id": "evidence-2",
                        "evidence_key":
                            "key-2",
                        "evidence_type":
                            "independent_report",
                        "subject_key":
                            "case-1",
                        "canonical_url":
                            "https://other.example/report",
                        "verification_status":
                            "unverified",
                        "observed_at":
                            "2026-08-12T09:00:00+00:00",
                    },
                    {
                        "id": "evidence-3",
                        "evidence_key":
                            "key-3",
                        "evidence_type":
                            "primary_document",
                        "subject_key":
                            "case-1",
                        "reference_key":
                            "DOC-1",
                        "verification_status":
                            "verified",
                        "observed_at":
                            "2026-08-12T12:30:00+00:00",
                    },
                ],
                evidence_links=[
                    {
                        "id": "link-1",
                        "evidence_id":
                            "evidence-1",
                        "story_id":
                            "story-1",
                        "relationship_type":
                            "supports",
                    },
                    {
                        "id": "link-2",
                        "evidence_id":
                            "evidence-2",
                        "story_id":
                            "story-1",
                        "relationship_type":
                            "contradicts",
                    },
                    {
                        "id": "link-3",
                        "evidence_id":
                            "evidence-3",
                        "story_id":
                            "story-1",
                        "relationship_type":
                            "supports",
                    },
                ],
            )
        )

    def test_raw_counts_are_correct(
        self,
    ):
        features = (
            main.build_evidence_signal_features(
                self.make_bundle()
            )
        )

        self.assertEqual(
            features["version"],
            main.EVIDENCE_FEATURE_VERSION,
        )

        self.assertEqual(
            features["policy_version"],
            main.EVIDENCE_SIGNAL_POLICY_VERSION,
        )

        self.assertEqual(
            features["counts"][
                "story_relationship_types"
            ],
            {
                "confirms": 1,
                "reports": 1,
            },
        )

        self.assertEqual(
            features["counts"][
                "observation_statuses"
            ],
            {
                "confirmed": 2,
                "unresolved": 1,
            },
        )

        self.assertEqual(
            features["counts"][
                "verification_statuses"
            ],
            {
                "unverified": 1,
                "verified": 2,
            },
        )

        self.assertEqual(
            features["counts"][
                "evidence_relationship_types"
            ],
            {
                "contradicts": 1,
                "published_by": 0,
                "supports": 2,
            },
        )

    def test_known_types_are_counted(
        self,
    ):
        features = (
            main.build_evidence_signal_features(
                self.make_bundle()
            )
        )

        self.assertEqual(
            features["counts"][
                "observation_types"
            ],
            {
                "report": 3,
            },
        )

        self.assertEqual(
            features["counts"][
                "evidence_types"
            ],
            {
                "independent_report": 1,
                "official_statement": 1,
                "primary_document": 1,
                "quote": 0,
            },
        )

    def test_unknown_values_are_not_counted(
        self,
    ):
        bundle = self.make_bundle()

        bundle["evidence_links"].append(
            {
                "id": "link-unknown",
                "evidence_id":
                    "evidence-1",
                "target_type":
                    "story",
                "target_id":
                    "story-1",
                "relationship_type":
                    "partially_supports",
                "confidence": None,
            }
        )

        bundle[
            "source_observations"
        ].append(
            {
                "id":
                    "observation-unknown",
                "source_id":
                    "source-3",
                "media_item_id": "",
                "story_id":
                    "story-1",
                "subject_key":
                    "case-1",
                "observation_type":
                    "analysis",
                "status":
                    "disputed",
                "claim_summary": "",
                "provenance_url": "",
                "confidence": None,
                "observed_at":
                    "2026-08-12T13:00:00+00:00",
            }
        )

        features = (
            main.build_evidence_signal_features(
                bundle
            )
        )

        self.assertEqual(
            features["counts"][
                "evidence_relationship_types"
            ]["supports"],
            2,
        )

        self.assertEqual(
            features["counts"][
                "observation_types"
            ]["report"],
            3,
        )

        self.assertEqual(
            features["unknown"][
                "evidence_relationship_types"
            ],
            [
                "partially_supports"
            ],
        )

        self.assertEqual(
            features["unknown"][
                "observation_types"
            ],
            [
                "analysis"
            ],
        )

        self.assertEqual(
            features["unknown"][
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
            main.build_evidence_signal_features(
                bundle
            )
        )

        bundle["story_links"].reverse()
        bundle["source_observations"].reverse()
        bundle["evidence_records"].reverse()
        bundle["evidence_links"].reverse()

        second = (
            main.build_evidence_signal_features(
                bundle
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_empty_bundle_returns_zero_counts(
        self,
    ):
        features = (
            main.build_evidence_signal_features(
                {}
            )
        )

        self.assertTrue(
            all(
                value == 0
                for category
                in features[
                    "counts"
                ].values()
                for value
                in category.values()
            )
        )

        self.assertTrue(
            all(
                not values
                for values
                in features[
                    "unknown"
                ].values()
            )
        )

    def test_bundle_must_be_dictionary(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_evidence_signal_features(
                []
            )

    def test_features_do_not_contain_scores(
        self,
    ):
        features = (
            main.build_evidence_signal_features(
                self.make_bundle()
            )
        )

        forbidden = {
            "score",
            "merit_score",
            "weight",
            "weighted_score",
            "badge",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                features.keys()
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
