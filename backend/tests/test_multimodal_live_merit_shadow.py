from __future__ import annotations

import copy
import math
import unittest
from unittest import mock

from app.analysis import corroboration as corroboration_analysis
from app.analysis import merit as merit_analysis
from app.services import multimodal_corroboration_runtime
from app.services import multimodal_live_merit_shadow as runtime


CLAIM_ID = "claim-1"


def canonical_policy():
    return {
        "corroboration_requires_explicit_support":
            True,
        "corroboration_requires_established_independent_support":
            True,
        "source_diversity_alone_does_not_establish_corroboration":
            True,
        "absence_of_dependency_does_not_establish_corroboration":
            True,
        "evidence_only_support_does_not_establish_corroboration":
            True,
        "contradiction_does_not_erase_recorded_support":
            True,
        "corroboration_does_not_establish_truth":
            True,
    }


def runtime_policy():
    return {
        "model_stance_materializes_historical_support_only":
            True,
        "support_edge_does_not_establish_truth":
            True,
        "support_edge_does_not_establish_independence":
            True,
        "independence_requires_existing_direct_stakeholder_verifier":
            True,
        "requires_two_distinct_sources":
            True,
        "requires_two_distinct_verified_direct_stakeholders":
            True,
        "requires_origin_destination_role_pair":
            True,
        "recorded_cross_dependency_fails_closed":
            True,
        "source_domain_diversity_alone_is_not_independence":
            True,
        "model_output_is_not_independence_proof":
            True,
        "verified_independence_may_establish_corroboration":
            True,
        "establishes_truth":
            False,
        "live_merit_evaluated":
            False,
        "affects_live_merit":
            False,
    }


def claim_row(
    *,
    status="corroboration_established",
    established=True,
    independent=True,
    contested=False,
):
    return {
        "claim_id": CLAIM_ID,
        "canonical_key": "claim-key",
        "subject_key": "club|arsenal",
        "status": status,
        "corroboration_established":
            established,
        "contested":
            contested,
        "contradiction_present":
            contested,
        "support_status":
            (
                "verified_independent_support"
                if independent
                else "multi_source_support_independence_unknown"
            ),
        "stance_status":
            (
                "contested"
                if contested
                else "support_only"
            ),
        "independent_support_established":
            independent,
        "supporting_source_ids": [
            "source-a",
            "source-b",
        ],
        "recorded_support_dependency_ids": [],
        "counts": {
            "supporting_observations": 2,
            "supporting_evidence": 0,
            "distinct_supporting_sources": 2,
            "recorded_support_dependencies": 0,
            "contradictions": (
                1
                if contested
                else 0
            ),
        },
    }


def corroboration_result(
    row=None,
):
    row = copy.deepcopy(
        row
        or claim_row()
    )

    return {
        "version": (
            multimodal_corroboration_runtime
            .MULTIMODAL_CORROBORATION_RUNTIME_VERSION
        ),
        "status": (
            "verified_direct_stakeholder_corroboration"
        ),
        "claim_id": CLAIM_ID,
        "left_media_item_id": "media-a",
        "right_media_item_id": "media-b",
        "left_observation_id": "obs-a",
        "right_observation_id": "obs-b",
        "support_state": {},
        "corroboration_state": {
            "version": (
                corroboration_analysis
                .CLAIM_CORROBORATION_POLICY_VERSION
            ),
            "status_vocabulary": [],
            "policy": canonical_policy(),
            "claims": [
                row,
            ],
        },
        "independent_support_established": bool(
            row[
                "independent_support_established"
            ]
        ),
        "corroboration_established": bool(
            row[
                "corroboration_established"
            ]
        ),
        "contested": bool(
            row["contested"]
        ),
        "policy": runtime_policy(),
    }


def legacy_score(total=64.0):
    return {
        "total": total,
        "breakdown": {
            "source": 20,
            "language": 15,
        },
        "reason": "legacy",
    }


class MultimodalLiveMeritShadowTests(
    unittest.TestCase
):
    def evaluate(
        self,
        *,
        result=None,
        score=None,
    ):
        return (
            runtime
            .evaluate_multimodal_live_merit_shadow(
                corroboration_result=(
                    result
                    or corroboration_result()
                ),
                legacy_score=(
                    score
                    or legacy_score()
                ),
            )
        )

    def test_verified_corroboration_proposes_locked_six_point_boost(self):
        result = self.evaluate()

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            6.0,
        )

        self.assertEqual(
            result[
                "proposed_shadow_total"
            ],
            70.0,
        )

    def test_live_score_remains_exact_legacy_score(self):
        score = legacy_score()

        result = self.evaluate(
            score=score
        )

        self.assertEqual(
            result["live_score"],
            score,
        )

        self.assertEqual(
            result[
                "overlay"
            ][
                "live"
            ][
                "total"
            ],
            score["total"],
        )

        self.assertFalse(
            result[
                "overlay"
            ][
                "live"
            ][
                "score_effect_enabled"
            ]
        )

    def test_shadow_runtime_does_not_mutate_inputs(self):
        corr = corroboration_result()
        score = legacy_score()

        corr_before = copy.deepcopy(corr)
        score_before = copy.deepcopy(score)

        self.evaluate(
            result=corr,
            score=score,
        )

        self.assertEqual(
            corr,
            corr_before,
        )

        self.assertEqual(
            score,
            score_before,
        )

    def test_shadow_total_caps_at_one_hundred(self):
        result = self.evaluate(
            score=legacy_score(
                98.0
            )
        )

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            6.0,
        )

        self.assertEqual(
            result[
                "proposed_shadow_total"
            ],
            100.0,
        )

    def test_contested_corroboration_is_neutral(self):
        row = claim_row(
            contested=True,
        )

        result = self.evaluate(
            result=(
                corroboration_result(
                    row
                )
            )
        )

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            0.0,
        )

    def test_unknown_independence_is_neutral(self):
        row = claim_row(
            status="support_independence_unknown",
            established=False,
            independent=False,
        )

        result = self.evaluate(
            result=(
                corroboration_result(
                    row
                )
            )
        )

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            0.0,
        )

    def test_recorded_dependency_is_neutral(self):
        row = claim_row(
            status=(
                "recorded_support_dependency_present"
            ),
            established=False,
            independent=False,
        )

        row[
            "recorded_support_dependency_ids"
        ] = [
            "dependency-1"
        ]

        row[
            "counts"
        ][
            "recorded_support_dependencies"
        ] = 1

        result = self.evaluate(
            result=(
                corroboration_result(
                    row
                )
            )
        )

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            0.0,
        )

    def test_no_explicit_support_is_neutral(self):
        row = claim_row(
            status="no_explicit_support",
            established=False,
            independent=False,
        )

        result = self.evaluate(
            result=(
                corroboration_result(
                    row
                )
            )
        )

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            0.0,
        )

    def test_shadow_boost_flag_tracks_overlay_only(self):
        positive = self.evaluate()

        negative = self.evaluate(
            result=(
                corroboration_result(
                    claim_row(
                        status=(
                            "support_independence_unknown"
                        ),
                        established=False,
                        independent=False,
                    )
                )
            )
        )

        self.assertTrue(
            positive[
                "shadow_boost_eligible_under_overlay"
            ]
        )

        self.assertFalse(
            negative[
                "shadow_boost_eligible_under_overlay"
            ]
        )

    def test_policy_explicitly_forbids_live_enablement(self):
        result = self.evaluate()

        policy = result[
            "policy"
        ]

        self.assertTrue(
            policy[
                "shadow_only"
            ]
        )

        self.assertTrue(
            policy[
                "no_live_release_invocation"
            ]
        )

        self.assertTrue(
            policy[
                "no_certificate_consumption"
            ]
        )

        self.assertFalse(
            policy[
                "live_enablement_authorized"
            ]
        )

        self.assertFalse(
            policy[
                "score_effect_applied"
            ]
        )

        self.assertFalse(
            policy[
                "affects_live_merit"
            ]
        )

    def test_wrong_corroboration_runtime_version_is_rejected(self):
        corr = corroboration_result()
        corr["version"] = "wrong"

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_missing_claim_id_is_rejected(self):
        corr = corroboration_result()
        corr["claim_id"] = ""

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_missing_runtime_policy_is_rejected(self):
        corr = corroboration_result()
        corr["policy"] = None

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_missing_runtime_safety_marker_is_rejected(self):
        corr = corroboration_result()

        corr[
            "policy"
        ][
            "model_output_is_not_independence_proof"
        ] = False

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_truth_enabled_in_input_is_rejected(self):
        corr = corroboration_result()

        corr[
            "policy"
        ][
            "establishes_truth"
        ] = True

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_prior_live_merit_evaluation_is_rejected(self):
        corr = corroboration_result()

        corr[
            "policy"
        ][
            "live_merit_evaluated"
        ] = True

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_prior_live_merit_effect_is_rejected(self):
        corr = corroboration_result()

        corr[
            "policy"
        ][
            "affects_live_merit"
        ] = True

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_wrong_canonical_corroboration_version_is_rejected(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "version"
        ] = "wrong"

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_missing_canonical_policy_is_rejected(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "policy"
        ] = {}

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_non_list_canonical_claims_are_rejected(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "claims"
        ] = {}

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_missing_canonical_claim_row_is_rejected(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "claims"
        ] = []

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_duplicate_canonical_claim_rows_are_rejected(self):
        corr = corroboration_result()

        row = copy.deepcopy(
            corr[
                "corroboration_state"
            ][
                "claims"
            ][0]
        )

        corr[
            "corroboration_state"
        ][
            "claims"
        ].append(row)

        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                result=corr
            )

    def test_top_level_corroboration_flag_must_match_state(self):
        corr = corroboration_result()
        corr[
            "corroboration_established"
        ] = False

        with self.assertRaises(
            runtime.ShadowIntegrityError
        ):
            self.evaluate(
                result=corr
            )

    def test_top_level_independence_flag_must_match_state(self):
        corr = corroboration_result()
        corr[
            "independent_support_established"
        ] = False

        with self.assertRaises(
            runtime.ShadowIntegrityError
        ):
            self.evaluate(
                result=corr
            )

    def test_top_level_contested_flag_must_match_state(self):
        corr = corroboration_result()
        corr[
            "contested"
        ] = True

        with self.assertRaises(
            runtime.ShadowIntegrityError
        ):
            self.evaluate(
                result=corr
            )

    def test_canonical_status_must_match_established_flag(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "claims"
        ][0][
            "status"
        ] = "support_independence_unknown"

        with self.assertRaises(
            runtime.ShadowIntegrityError
        ):
            self.evaluate(
                result=corr
            )

    def test_corroboration_requires_independent_support(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "claims"
        ][0][
            "independent_support_established"
        ] = False

        corr[
            "independent_support_established"
        ] = False

        with self.assertRaises(
            runtime.ShadowIntegrityError
        ):
            self.evaluate(
                result=corr
            )

    def test_contested_and_contradiction_flags_must_match(self):
        corr = corroboration_result()

        corr[
            "corroboration_state"
        ][
            "claims"
        ][0][
            "contradiction_present"
        ] = True

        with self.assertRaises(
            runtime.ShadowIntegrityError
        ):
            self.evaluate(
                result=corr
            )

    def test_legacy_score_must_be_mapping(self):
        with self.assertRaises(
            runtime.ShadowInputError
        ):
            (
                runtime
                .evaluate_multimodal_live_merit_shadow(
                    corroboration_result=(
                        corroboration_result()
                    ),
                    legacy_score=64,
                )
            )

    def test_boolean_legacy_total_is_rejected(self):
        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                score={
                    "total": True
                }
            )

    def test_nan_legacy_total_is_rejected(self):
        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                score={
                    "total": math.nan
                }
            )

    def test_infinite_legacy_total_is_rejected(self):
        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                score={
                    "total": math.inf
                }
            )

    def test_negative_legacy_total_is_rejected(self):
        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                score={
                    "total": -1
                }
            )

    def test_legacy_total_above_one_hundred_is_rejected(self):
        with self.assertRaises(
            runtime.ShadowInputError
        ):
            self.evaluate(
                score={
                    "total": 101
                }
            )

    def test_overlay_version_mismatch_fails_closed(self):
        bad = (
            merit_analysis
            .build_merit_corroboration_overlay(
                corroboration_state=(
                    corroboration_result()[
                        "corroboration_state"
                    ]
                ),
                legacy_score=(
                    legacy_score()
                ),
                claim_id="claim-1",
            )
        )

        bad["version"] = "wrong"

        with mock.patch.object(
            runtime.merit_analysis,
            "build_merit_corroboration_overlay",
            return_value=bad,
        ):
            with self.assertRaises(
                runtime.ShadowIntegrityError
            ):
                self.evaluate()

    def test_overlay_live_score_mutation_fails_closed(self):
        score = legacy_score()

        bad = (
            merit_analysis
            .build_merit_corroboration_overlay(
                corroboration_state=(
                    corroboration_result()[
                        "corroboration_state"
                    ]
                ),
                legacy_score=score,
                claim_id="claim-1",
            )
        )

        bad[
            "live"
        ][
            "total"
        ] = 70

        with mock.patch.object(
            runtime.merit_analysis,
            "build_merit_corroboration_overlay",
            return_value=bad,
        ):
            with self.assertRaises(
                runtime.ShadowIntegrityError
            ):
                self.evaluate(
                    score=score
                )

    def test_overlay_score_effect_true_fails_closed(self):
        bad = (
            merit_analysis
            .build_merit_corroboration_overlay(
                corroboration_state=(
                    corroboration_result()[
                        "corroboration_state"
                    ]
                ),
                legacy_score=(
                    legacy_score()
                ),
                claim_id="claim-1",
            )
        )

        bad[
            "live"
        ][
            "score_effect_enabled"
        ] = True

        with mock.patch.object(
            runtime.merit_analysis,
            "build_merit_corroboration_overlay",
            return_value=bad,
        ):
            with self.assertRaises(
                runtime.ShadowIntegrityError
            ):
                self.evaluate()

    def test_overlay_adjustment_above_locked_max_fails_closed(self):
        bad = (
            merit_analysis
            .build_merit_corroboration_overlay(
                corroboration_state=(
                    corroboration_result()[
                        "corroboration_state"
                    ]
                ),
                legacy_score=(
                    legacy_score()
                ),
                claim_id="claim-1",
            )
        )

        bad[
            "proposed"
        ][
            "adjustment"
        ] = 7.0

        with mock.patch.object(
            runtime.merit_analysis,
            "build_merit_corroboration_overlay",
            return_value=bad,
        ):
            with self.assertRaises(
                runtime.ShadowIntegrityError
            ):
                self.evaluate()

    def test_only_target_claim_is_scored_when_state_has_other_claims(self):
        corr = corroboration_result(
            claim_row(
                status="support_independence_unknown",
                established=False,
                independent=False,
            )
        )

        other = claim_row()
        other["claim_id"] = "other-claim"

        corr[
            "corroboration_state"
        ][
            "claims"
        ].append(
            other
        )

        result = self.evaluate(
            result=corr
        )

        self.assertEqual(
            result[
                "proposed_adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            result[
                "overlay"
            ][
                "claim_id"
            ],
            "claim-1",
        )


if __name__ == "__main__":
    unittest.main()
