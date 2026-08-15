import copy
import json
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


from app.analysis.model_assisted_baseline import (
    MODEL_ASSISTED_BASELINE_VERSION,
    build_model_assisted_baseline_evaluator_runs,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
    build_multi_evaluator_adjudication,
)

from app.analysis.observation_semantics import (
    normalize_claim_observation_semantics,
)


class ModelAssistedBaselineTests(
    unittest.TestCase
):
    CLAIM_ID = "claim-baseline-1"
    SOURCE_URL = (
        "https://example.com/"
        "transfer-report"
    )

    def raw_semantics(
        self,
        **overrides,
    ):
        data = {
            "claim_relevance": (
                "same_claim"
            ),
            "source_role": (
                "publisher"
            ),
            "authority_class": (
                "none"
            ),
            "reliability_class": (
                "elite_specialist"
            ),
            "provenance_class": (
                "firsthand_reporting"
            ),
            "stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_targets": [],
            "field_evidence": [
                (
                    "Publisher reports that "
                    "Player A will join Team A."
                )
            ],
            "source_role_confidence": 0.93,
            "authority_confidence": 0.97,
            "reliability_confidence": 0.99,
            "provenance_confidence": 0.91,
            "stance_confidence": 0.94,
            "dependency_confidence": 0.89,
        }

        data.update(
            overrides
        )

        return data

    def assessment(
        self,
        *,
        context=None,
    ):
        return (
            normalize_claim_observation_semantics(
                self.raw_semantics(),
                claim_id=self.CLAIM_ID,
                source_url=(
                    self.SOURCE_URL
                ),
                context=(
                    context
                    or {}
                ),
                evaluator_id=(
                    "semantic-model-v1"
                ),
            )
        )

    def test_builds_untrusted_baseline_runs_without_fabricating_missing_confidence(
        self,
    ):
        assessment = (
            self.assessment()
        )

        result = (
            build_model_assisted_baseline_evaluator_runs(
                semantic_assessment=(
                    assessment
                )
            )
        )

        self.assertEqual(
            result["version"],
            MODEL_ASSISTED_BASELINE_VERSION,
        )

        self.assertEqual(
            result["status"],
            "ready",
        )

        self.assertEqual(
            result["field_count"],
            6,
        )

        # Reliability is intentionally unknown
        # without empirical trusted context.
        self.assertEqual(
            result[
                "unscored_fields"
            ],
            [
                "reliability_class"
            ],
        )

        self.assertEqual(
            result[
                "scored_field_count"
            ],
            5,
        )

        self.assertEqual(
            len(
                result[
                    "evaluator_runs"
                ]
            ),
            1,
        )

        run = result[
            "evaluator_runs"
        ][0]

        self.assertEqual(
            run[
                "derivation_mode"
            ],
            "model_assisted",
        )

        for judgment in run[
            "judgments"
        ]:
            self.assertFalse(
                judgment[
                    "training_eligible"
                ]
            )

            self.assertEqual(
                judgment[
                    "evidence_ids"
                ],
                [],
            )

    def test_existing_multi_evaluator_engine_accepts_baseline_and_keeps_all_fields_untrusted(
        self,
    ):
        result = (
            build_model_assisted_baseline_evaluator_runs(
                semantic_assessment=(
                    self.assessment()
                )
            )
        )

        adjudication = (
            build_multi_evaluator_adjudication(
                claim_id=self.CLAIM_ID,
                evaluator_runs=(
                    result[
                        "evaluator_runs"
                    ]
                ),
            )
        )

        self.assertEqual(
            set(
                adjudication[
                    "fields"
                ].keys()
            ),
            set(
                MULTI_EVALUATOR_FIELDS
            ),
        )

        self.assertEqual(
            adjudication[
                "fields"
            ][
                "reliability_class"
            ][
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

        for field in (
            MULTI_EVALUATOR_FIELDS
        ):
            packet = (
                adjudication[
                    "fields"
                ][field]
            )

            self.assertFalse(
                packet[
                    "reference_gate"
                ][
                    "training_reference_allowed"
                ]
            )

            self.assertEqual(
                packet[
                    "reference_gate"
                ][
                    "trusted_hard_reference_judgment_ids"
                ],
                [],
            )

    def test_empirical_reliability_context_becomes_separate_untrusted_family(
        self,
    ):
        assessment = (
            self.assessment(
                context={
                    "known_reliability_class": (
                        "established"
                    ),
                }
            )
        )

        result = (
            build_model_assisted_baseline_evaluator_runs(
                semantic_assessment=(
                    assessment
                )
            )
        )

        self.assertEqual(
            result[
                "unscored_fields"
            ],
            [],
        )

        self.assertEqual(
            result[
                "scored_field_count"
            ],
            6,
        )

        families = {
            run[
                "evaluator_family"
            ]
            for run
            in result[
                "evaluator_runs"
            ]
        }

        self.assertEqual(
            families,
            {
                (
                    "observation_"
                    "semantic_model"
                ),
                (
                    "empirical_"
                    "reliability_context"
                ),
            },
        )

        adjudication = (
            build_multi_evaluator_adjudication(
                claim_id=self.CLAIM_ID,
                evaluator_runs=(
                    result[
                        "evaluator_runs"
                    ]
                ),
            )
        )

        reliability = (
            adjudication[
                "fields"
            ][
                "reliability_class"
            ]
        )

        # One evaluator family is intentionally
        # insufficient to create an adjudicated
        # reliability value. The empirical value
        # remains preserved as an untrusted judgment.
        self.assertEqual(
            reliability[
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

        self.assertEqual(
            reliability[
                "automatic"
            ][
                "value"
            ],
            "",
        )

        empirical_runs = [
            run
            for run
            in adjudication[
                "evaluators"
            ]
            if (
                run[
                    "evaluator_family"
                ]
                == (
                    "empirical_"
                    "reliability_context"
                )
            )
        ]

        self.assertEqual(
            len(
                empirical_runs
            ),
            1,
        )

        empirical_judgments = (
            empirical_runs[0][
                "judgments"
            ]
        )

        self.assertEqual(
            len(
                empirical_judgments
            ),
            1,
        )

        empirical = (
            empirical_judgments[0]
        )

        self.assertEqual(
            empirical[
                "field"
            ],
            "reliability_class",
        )

        self.assertEqual(
            empirical[
                "value"
            ],
            "established",
        )

        self.assertEqual(
            empirical[
                "confidence"
            ],
            1.0,
        )

        self.assertEqual(
            empirical[
                "basis_class"
            ],
            "structured_fact",
        )

        self.assertFalse(
            empirical[
                "training_eligible"
            ]
        )

        self.assertFalse(
            reliability[
                "reference_gate"
            ][
                "training_reference_allowed"
            ]
        )

    def test_rejects_training_eligible_model_judgment(
        self,
    ):
        assessment = (
            self.assessment()
        )

        tampered = copy.deepcopy(
            assessment
        )

        tampered[
            "field_judgments"
        ][0][
            "training_eligible"
        ] = True

        with self.assertRaises(
            ValueError
        ):
            (
                build_model_assisted_baseline_evaluator_runs(
                    semantic_assessment=(
                        tampered
                    )
                )
            )

    def test_rejects_self_validating_model_assessment(
        self,
    ):
        assessment = (
            self.assessment()
        )

        tampered = copy.deepcopy(
            assessment
        )

        tampered[
            "derivation"
        ][
            "self_validating"
        ] = True

        with self.assertRaises(
            ValueError
        ):
            (
                build_model_assisted_baseline_evaluator_runs(
                    semantic_assessment=(
                        tampered
                    )
                )
            )

    def test_rejects_prepersistence_evidence_claims(
        self,
    ):
        assessment = (
            self.assessment()
        )

        tampered = copy.deepcopy(
            assessment
        )

        tampered[
            "field_judgments"
        ][0][
            "evidence_ids"
        ] = [
            "not-yet-persisted"
        ]

        with self.assertRaises(
            ValueError
        ):
            (
                build_model_assisted_baseline_evaluator_runs(
                    semantic_assessment=(
                        tampered
                    )
                )
            )

    def test_output_is_deterministic(
        self,
    ):
        assessment = (
            self.assessment()
        )

        first = (
            build_model_assisted_baseline_evaluator_runs(
                semantic_assessment=(
                    assessment
                )
            )
        )

        second = (
            build_model_assisted_baseline_evaluator_runs(
                semantic_assessment=(
                    copy.deepcopy(
                        assessment
                    )
                )
            )
        )

        self.assertEqual(
            json.dumps(
                first,
                sort_keys=True,
            ),
            json.dumps(
                second,
                sort_keys=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()