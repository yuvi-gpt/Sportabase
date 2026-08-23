import copy
import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.analysis.negative_merit_calibration_dataset import (
    NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION,
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION,
)

from evals.negative_merit_resolved_corpus import (
    NEGATIVE_MERIT_RESOLVED_CORPUS_REPORT_VERSION,
    NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES,
    NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION,
    corpus_template,
    evaluate_negative_merit_resolved_corpus,
)


class NegativeMeritResolvedCorpusEvalTests(
    unittest.TestCase
):
    @staticmethod
    def corpus(
        classes=None,
    ):
        classes = (
            list(
                classes
            )
            if classes is not None
            else sorted(
                NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES
            )
        )

        cases = []

        for index, observation_class in enumerate(
            classes
        ):
            cases.append(
                {
                    "version": (
                        NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
                    ),
                    "origin": (
                        "real_world"
                    ),
                    "machine_verified": True,
                    "id": (
                        "corpus-case-"
                        + str(
                            index
                        )
                    ),
                    "claim_id": (
                        "claim-"
                        + str(
                            index
                        )
                    ),
                    "observation_class": (
                        observation_class
                    ),
                }
            )

        return {
            "version": (
                NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION
            ),
            "corpus_id": (
                "negative-merit-real-world-v1"
            ),
            "frozen_at": (
                "2026-08-23T11:30:00Z"
            ),
            "cases": cases,
        }

    @staticmethod
    def dataset_for_cases(
        cases,
        *,
        numeric_penalty_authorized=False,
        live_negative_merit_authorized=False,
        penalty_weight_selected=False,
    ):
        observations = []
        class_counts = {}

        for case in cases:
            observation_class = (
                case[
                    "observation_class"
                ]
            )

            class_counts[
                observation_class
            ] = (
                class_counts.get(
                    observation_class,
                    0,
                )
                + 1
            )

            resolved = (
                observation_class
                == (
                    "resolved_against_claim_observation"
                )
            )

            observations.append(
                {
                    "id": (
                        case[
                            "id"
                        ]
                    ),
                    "claim_id": (
                        case[
                            "claim_id"
                        ]
                    ),
                    "observation_class": (
                        observation_class
                    ),
                    "resolution_status": (
                        "resolved_against_claim"
                        if resolved
                        else "unresolved"
                    ),
                    "legacy_total": (
                        75.0
                        + len(
                            observations
                        )
                    ),
                }
            )

        resolved_count = sum(
            1
            for observation in observations
            if observation[
                "resolution_status"
            ]
            == "resolved_against_claim"
        )

        return {
            "version": (
                NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION
            ),
            "status": (
                "measurement_ready"
            ),
            "case_count": len(
                observations
            ),
            "observations": (
                observations
            ),
            "score_distribution": {
                "overall": {
                    "count": len(
                        observations
                    ),
                },
                "resolved_against_claim": {
                    "count": (
                        resolved_count
                    ),
                },
                "by_class": {
                    observation_class: {
                        "count": count
                    }
                    for observation_class, count
                    in class_counts.items()
                },
            },
            "calibration": {
                "penalty_weight_selected": (
                    penalty_weight_selected
                ),
                "numeric_penalty_authorized": (
                    numeric_penalty_authorized
                ),
                "live_negative_merit_authorized": (
                    live_negative_merit_authorized
                ),
                "canonical_outcome_verifier_available": True,
                "canonical_outcome_labels_available": (
                    resolved_count > 0
                ),
                "resolved_against_claim_case_count": (
                    resolved_count
                ),
                "blockers": [
                    "numeric_penalty_not_calibrated"
                ],
            },
            "policy": {
                "dataset_does_not_authorize_release": True,
            },
        }

    def builder(
        self,
        *,
        numeric_penalty_authorized=False,
        live_negative_merit_authorized=False,
        penalty_weight_selected=False,
    ):
        def _builder(
            *,
            cases,
        ):
            return self.dataset_for_cases(
                cases,
                numeric_penalty_authorized=(
                    numeric_penalty_authorized
                ),
                live_negative_merit_authorized=(
                    live_negative_merit_authorized
                ),
                penalty_weight_selected=(
                    penalty_weight_selected
                ),
            )

        return _builder

    def test_complete_required_population_passes(
        self,
    ):
        report = (
            evaluate_negative_merit_resolved_corpus(
                corpus=(
                    self.corpus()
                ),
                dataset_builder=(
                    self.builder()
                ),
            )
        )

        self.assertEqual(
            report[
                "version"
            ],
            NEGATIVE_MERIT_RESOLVED_CORPUS_REPORT_VERSION,
        )

        self.assertEqual(
            report[
                "status"
            ],
            "pass",
        )

        self.assertEqual(
            report[
                "corpus"
            ][
                "resolved_against_claim_case_count"
            ],
            1,
        )

        self.assertEqual(
            report[
                "corpus"
            ][
                "missing_required_classes"
            ],
            [],
        )

        self.assertTrue(
            report[
                "calibration"
            ][
                "corpus_complete_for_measurement"
            ]
        )

        self.assertFalse(
            report[
                "calibration"
            ][
                "numeric_penalty_authorized"
            ]
        )

        self.assertFalse(
            report[
                "calibration"
            ][
                "live_negative_merit_authorized"
            ]
        )

        self.assertEqual(
            len(
                report[
                    "corpus"
                ][
                    "corpus_digest"
                ]
            ),
            64,
        )

        self.assertEqual(
            len(
                report[
                    "report_digest"
                ]
            ),
            64,
        )

    def test_missing_control_population_is_incomplete(
        self,
    ):
        classes = (
            set(
                NEGATIVE_MERIT_RESOLVED_CORPUS_REQUIRED_CLASSES
            )
            - {
                (
                    "exclusive_no_"
                    "corroboration_control"
                ),
            }
        )

        report = (
            evaluate_negative_merit_resolved_corpus(
                corpus=(
                    self.corpus(
                        classes
                    )
                ),
                dataset_builder=(
                    self.builder()
                ),
            )
        )

        self.assertEqual(
            report[
                "status"
            ],
            "incomplete",
        )

        self.assertIn(
            (
                "exclusive_no_"
                "corroboration_control"
            ),
            report[
                "corpus"
            ][
                "missing_required_classes"
            ],
        )

    def test_numeric_penalty_authorization_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "cannot authorize scoring changes",
        ):
            evaluate_negative_merit_resolved_corpus(
                corpus=(
                    self.corpus()
                ),
                dataset_builder=(
                    self.builder(
                        numeric_penalty_authorized=True
                    )
                ),
            )

    def test_live_negative_merit_authorization_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "cannot authorize scoring changes",
        ):
            evaluate_negative_merit_resolved_corpus(
                corpus=(
                    self.corpus()
                ),
                dataset_builder=(
                    self.builder(
                        live_negative_merit_authorized=True
                    )
                ),
            )

    def test_selected_penalty_weight_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "cannot authorize scoring changes",
        ):
            evaluate_negative_merit_resolved_corpus(
                corpus=(
                    self.corpus()
                ),
                dataset_builder=(
                    self.builder(
                        penalty_weight_selected=True
                    )
                ),
            )

    def test_stale_observation_contract_is_rejected(
        self,
    ):
        corpus = self.corpus()

        corpus[
            "cases"
        ][
            0
        ][
            "version"
        ] = (
            "negative-merit-calibration-observation-v1"
        )

        with self.assertRaisesRegex(
            ValueError,
            "unsupported observation version",
        ):
            evaluate_negative_merit_resolved_corpus(
                corpus=corpus,
                dataset_builder=(
                    self.builder()
                ),
            )

    def test_synthetic_case_origin_is_rejected(
        self,
    ):
        corpus = self.corpus()

        corpus[
            "cases"
        ][
            0
        ][
            "origin"
        ] = (
            "synthetic_policy_fixture"
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be marked real_world",
        ):
            evaluate_negative_merit_resolved_corpus(
                corpus=corpus,
                dataset_builder=(
                    self.builder()
                ),
            )

    def test_corpus_digest_stable_for_mapping_order(
        self,
    ):
        left = self.corpus()
        right = copy.deepcopy(
            left
        )

        right = {
            "cases": right[
                "cases"
            ],
            "frozen_at": right[
                "frozen_at"
            ],
            "corpus_id": right[
                "corpus_id"
            ],
            "version": right[
                "version"
            ],
        }

        left_report = (
            evaluate_negative_merit_resolved_corpus(
                corpus=left,
                dataset_builder=(
                    self.builder()
                ),
            )
        )

        right_report = (
            evaluate_negative_merit_resolved_corpus(
                corpus=right,
                dataset_builder=(
                    self.builder()
                ),
            )
        )

        self.assertEqual(
            left_report[
                "corpus"
            ][
                "corpus_digest"
            ],
            right_report[
                "corpus"
            ][
                "corpus_digest"
            ],
        )

    def test_empty_template_is_explicitly_not_evaluable(
        self,
    ):
        template = corpus_template()

        self.assertEqual(
            template[
                "version"
            ],
            NEGATIVE_MERIT_RESOLVED_CORPUS_VERSION,
        )

        self.assertEqual(
            template[
                "cases"
            ],
            [],
        )

        self.assertTrue(
            template[
                "policy"
            ][
                "synthetic_cases_forbidden_in_frozen_corpus"
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "ID is required",
        ):
            evaluate_negative_merit_resolved_corpus(
                corpus=template,
                dataset_builder=(
                    self.builder()
                ),
            )


if __name__ == "__main__":
    unittest.main()
