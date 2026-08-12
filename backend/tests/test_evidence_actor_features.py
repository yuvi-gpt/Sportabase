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


class EvidenceActorFeatureTests(
    unittest.TestCase
):
    def make_bundle(self):
        return (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
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
                    {
                        "id": "source-observation-2",
                        "source_id": "source-2",
                        "subject_key": "case-1",
                        "observation_type":
                            "report",
                        "status": "confirmed",
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
                    {
                        "id":
                            "reporter-observation-2",
                        "reporter_id":
                            "reporter-2",
                        "source_id":
                            "source-2",
                        "subject_key":
                            "case-2",
                        "observation_type":
                            "report",
                        "status":
                            "unresolved",
                        "observed_at":
                            "2026-08-12T12:00:00+00:00",
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
                            "case-3",
                        "canonical_url":
                            "https://example.com/official",
                        "verification_status":
                            "verified",
                        "observed_at":
                            "2026-08-12T12:30:00+00:00",
                    },
                ],
            )
        )

    def test_distinct_actor_counts_are_correct(
        self,
    ):
        features = (
            main.build_evidence_actor_features(
                self.make_bundle()
            )
        )

        self.assertEqual(
            features["version"],
            main.EVIDENCE_ACTOR_FEATURE_VERSION,
        )

        self.assertEqual(
            features["counts"],
            {
                "observation_sources": 2,
                "reporters": 2,
                "subjects": 3,
            },
        )

    def test_source_is_not_double_counted_across_observation_types(
        self,
    ):
        features = (
            main.build_evidence_actor_features(
                self.make_bundle()
            )
        )

        self.assertEqual(
            features["distinct"][
                "observation_source_ids"
            ],
            [
                "source-1",
                "source-2",
            ],
        )

        self.assertEqual(
            features["counts"][
                "observation_sources"
            ],
            2,
        )

    def test_reporter_ids_are_distinct(
        self,
    ):
        features = (
            main.build_evidence_actor_features(
                self.make_bundle()
            )
        )

        self.assertEqual(
            features["distinct"][
                "reporter_ids"
            ],
            [
                "reporter-1",
                "reporter-2",
            ],
        )

    def test_subjects_include_evidence_records(
        self,
    ):
        features = (
            main.build_evidence_actor_features(
                self.make_bundle()
            )
        )

        self.assertEqual(
            features["distinct"][
                "subject_keys"
            ],
            [
                "case-1",
                "case-2",
                "case-3",
            ],
        )

    def test_blank_identity_values_are_ignored(
        self,
    ):
        bundle = self.make_bundle()

        bundle[
            "source_observations"
        ].append(
            {
                "id": "blank-source",
                "source_id": "",
                "media_item_id": "",
                "story_id": "",
                "subject_key": "",
                "observation_type":
                    "report",
                "status": "unresolved",
                "claim_summary": "",
                "provenance_url": "",
                "confidence": None,
                "observed_at":
                    "2026-08-12T13:00:00+00:00",
            }
        )

        features = (
            main.build_evidence_actor_features(
                bundle
            )
        )

        self.assertEqual(
            features["counts"],
            {
                "observation_sources": 2,
                "reporters": 2,
                "subjects": 3,
            },
        )

    def test_input_order_is_stable(
        self,
    ):
        bundle = self.make_bundle()

        first = (
            main.build_evidence_actor_features(
                bundle
            )
        )

        bundle[
            "source_observations"
        ].reverse()

        bundle[
            "reporter_observations"
        ].reverse()

        bundle[
            "evidence_records"
        ].reverse()

        second = (
            main.build_evidence_actor_features(
                bundle
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_features_do_not_claim_independence_or_corroboration(
        self,
    ):
        features = (
            main.build_evidence_actor_features(
                self.make_bundle()
            )
        )

        forbidden = {
            "independent_sources",
            "independent_source_count",
            "corroboration",
            "corroborated",
            "corroboration_count",
            "score",
            "merit_score",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                features.keys()
            )
        )

    def test_bundle_must_be_dictionary(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_evidence_actor_features(
                []
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
