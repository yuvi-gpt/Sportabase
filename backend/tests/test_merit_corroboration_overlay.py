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


from app.analysis.corroboration import (
    CLAIM_CORROBORATION_POLICY_VERSION,
)
from app.analysis.merit import (
    MERIT_CORROBORATION_OVERLAY_VERSION,
    MERIT_CORROBORATION_SHADOW_MAX_BOOST,
    build_merit_corroboration_overlay,
)


class MeritCorroborationOverlayTests(
    unittest.TestCase
):
    def legacy_score(
        self,
        *,
        total=60,
        legacy_corroboration=4,
    ):
        return {
            "total": (
                total
            ),
            "badge": (
                "Developing"
            ),
            "reasons": [],
            "components": {
                "source_score": 8,
                "evidence_quality": 10,
                "specificity": 8,
                "language_reliability": 14,
                "article_type": 6,
                "corroboration": (
                    legacy_corroboration
                ),
                "impact": 3,
                "type_fit": 7,
            },
            "calculation": {
                "final_total": (
                    total
                ),
            },
        }

    def claim_state(
        self,
        *,
        status=(
            "support_independence_unknown"
        ),
        established=False,
        contested=False,
        independent=False,
        source_ids=None,
        claim_id="claim-1",
    ):
        return {
            "claim_id": (
                claim_id
            ),
            "canonical_key": (
                "transfer|alpha|beta|agreement"
            ),
            "subject_key": (
                "transfer|alpha|beta"
            ),
            "status": (
                status
            ),
            "corroboration_established": (
                established
            ),
            "contested": (
                contested
            ),
            "contradiction_present": (
                contested
            ),
            (
                "independent_support_"
                "established"
            ): (
                independent
            ),
            "supporting_source_ids": (
                source_ids
                if source_ids is not None
                else [
                    "source-a",
                    "source-b",
                ]
            ),
            "counts": {
                "supporting_observations": 2,
                "distinct_supporting_sources": (
                    len(
                        source_ids
                        if source_ids is not None
                        else [
                            "source-a",
                            "source-b",
                        ]
                    )
                ),
            },
        }

    def corroboration_state(
        self,
        claim=None,
        *,
        version=None,
    ):
        return {
            "version": (
                CLAIM_CORROBORATION_POLICY_VERSION
                if version is None
                else version
            ),
            "claims": [
                (
                    self.claim_state()
                    if claim is None
                    else claim
                ),
            ],
        }

    def build(
        self,
        *,
        legacy=None,
        claim=None,
        state=None,
        claim_id="claim-1",
    ):
        return (
            build_merit_corroboration_overlay(
                legacy_score=(
                    self.legacy_score()
                    if legacy is None
                    else legacy
                ),
                corroboration_state=(
                    self.corroboration_state(
                        claim
                    )
                    if state is None
                    else state
                ),
                claim_id=(
                    claim_id
                ),
            )
        )

    def test_verified_uncontested_corroboration_gets_shadow_boost(
        self,
    ):
        claim = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            contested=False,
            independent=True,
        )

        result = self.build(
            claim=claim,
        )

        self.assertEqual(
            result["version"],
            MERIT_CORROBORATION_OVERLAY_VERSION,
        )

        self.assertEqual(
            result["mode"],
            "shadow",
        )

        self.assertEqual(
            result["signal"],
            "verified_corroboration",
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "adjustment"
            ],
            MERIT_CORROBORATION_SHADOW_MAX_BOOST,
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "shadow_total"
            ],
            66.0,
        )

        self.assertEqual(
            result[
                "live"
            ][
                "total"
            ],
            60.0,
        )

        self.assertFalse(
            result[
                "live"
            ][
                "score_effect_enabled"
            ]
        )

    def test_source_count_does_not_scale_boost(
        self,
    ):
        two_sources = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
            source_ids=[
                "source-a",
                "source-b",
            ],
        )

        many_sources = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
            source_ids=[
                "source-a",
                "source-b",
                "source-c",
                "source-d",
                "source-e",
                "source-f",
            ],
        )

        first = self.build(
            claim=two_sources,
        )

        second = self.build(
            claim=many_sources,
        )

        self.assertEqual(
            first[
                "proposed"
            ][
                "adjustment"
            ],
            second[
                "proposed"
            ][
                "adjustment"
            ],
        )

        self.assertEqual(
            first[
                "proposed"
            ][
                "adjustment"
            ],
            MERIT_CORROBORATION_SHADOW_MAX_BOOST,
        )

    def test_legacy_lexical_corroboration_does_not_scale_overlay(
        self,
    ):
        claim = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
        )

        low_legacy = self.build(
            legacy=(
                self.legacy_score(
                    legacy_corroboration=0
                )
            ),
            claim=claim,
        )

        high_legacy = self.build(
            legacy=(
                self.legacy_score(
                    legacy_corroboration=12
                )
            ),
            claim=claim,
        )

        self.assertEqual(
            low_legacy[
                "proposed"
            ][
                "adjustment"
            ],
            high_legacy[
                "proposed"
            ][
                "adjustment"
            ],
        )

    def test_contested_corroboration_gets_no_boost(
        self,
    ):
        claim = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            contested=True,
            independent=True,
        )

        result = self.build(
            claim=claim,
        )

        self.assertEqual(
            result["signal"],
            (
                "verified_corroboration_"
                "contested"
            ),
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "shadow_total"
            ],
            60.0,
        )

    def test_independence_unknown_gets_no_boost(
        self,
    ):
        result = self.build()

        self.assertEqual(
            result["signal"],
            (
                "support_independence_"
                "unknown"
            ),
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

    def test_recorded_dependency_gets_no_boost_or_penalty(
        self,
    ):
        claim = self.claim_state(
            status=(
                "recorded_support_"
                "dependency_present"
            ),
            established=False,
            independent=False,
        )

        result = self.build(
            claim=claim,
        )

        self.assertEqual(
            result["signal"],
            (
                "support_dependency_present"
            ),
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            result[
                "live"
            ][
                "total"
            ],
            60.0,
        )

    def test_missing_external_support_never_reduces_legacy_score(
        self,
    ):
        claim = self.claim_state(
            status=(
                "no_explicit_support"
            ),
            established=False,
            independent=False,
            source_ids=[],
        )

        result = self.build(
            claim=claim,
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "shadow_total"
            ],
            result[
                "legacy"
            ][
                "total"
            ],
        )

        self.assertEqual(
            result[
                "live"
            ][
                "total"
            ],
            result[
                "legacy"
            ][
                "total"
            ],
        )

    def test_shadow_total_is_clamped_to_100(
        self,
    ):
        claim = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
        )

        result = self.build(
            legacy=(
                self.legacy_score(
                    total=98
                )
            ),
            claim=claim,
        )

        self.assertEqual(
            result[
                "proposed"
            ][
                "shadow_total"
            ],
            100.0,
        )

        self.assertEqual(
            result[
                "live"
            ][
                "total"
            ],
            98.0,
        )

    def test_established_corroboration_requires_independent_support(
        self,
    ):
        claim = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=False,
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "requires established "
                "independent support"
            ),
        ):
            self.build(
                claim=claim,
            )

    def test_status_and_established_flag_must_agree(
        self,
    ):
        claim = self.claim_state(
            status=(
                "support_independence_unknown"
            ),
            established=True,
            independent=True,
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "status and established "
                "flag disagree"
            ),
        ):
            self.build(
                claim=claim,
            )

    def test_rejects_wrong_corroboration_version(
        self,
    ):
        state = (
            self.corroboration_state(
                version=(
                    "claim-corroboration-v999"
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "Unsupported claim "
                "corroboration version"
            ),
        ):
            self.build(
                state=state,
            )

    def test_requires_exactly_one_target_claim(
        self,
    ):
        state = {
            "version": (
                CLAIM_CORROBORATION_POLICY_VERSION
            ),
            "claims": [
                self.claim_state(
                    claim_id=(
                        "other-claim"
                    )
                ),
            ],
        }

        with self.assertRaisesRegex(
            ValueError,
            "exactly one target claim",
        ):
            self.build(
                state=state,
            )

    def test_rejects_invalid_legacy_total(
        self,
    ):
        legacy = (
            self.legacy_score()
        )

        legacy[
            "total"
        ] = 101

        with self.assertRaisesRegex(
            ValueError,
            (
                "Legacy Merit total must "
                "be between 0 and 100"
            ),
        ):
            self.build(
                legacy=legacy,
            )

    def test_policy_requires_golden_set_before_enablement(
        self,
    ):
        claim = self.claim_state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
        )

        result = self.build(
            claim=claim,
        )

        policy = result[
            "policy"
        ]

        self.assertTrue(
            policy[
                "distinct_source_count_is_"
                "not_weighted"
            ]
        )

        self.assertTrue(
            policy[
                "live_merit_effect_is_disabled"
            ]
        )

        self.assertTrue(
            policy[
                "golden_set_validation_is_"
                "required_before_enablement"
            ]
        )


if __name__ == "__main__":
    unittest.main()
