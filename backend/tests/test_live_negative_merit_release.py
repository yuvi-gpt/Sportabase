import copy
import json
import sys
import tempfile
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


from app.analysis.negative_merit import (
    NEGATIVE_MERIT_SHADOW_VERSION,
)

from app.services.live_negative_merit_release import (
    LIVE_NEGATIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT,
    LIVE_NEGATIVE_MERIT_RELEASE_RUNTIME_VERSION,
    apply_certified_live_negative_merit,
    live_negative_merit_release_cache_token,
)

from app.services.negative_merit_runtime import (
    NEGATIVE_MERIT_RUNTIME_VERSION,
)


CERTIFICATE_PATH = (
    BACKEND_DIR
    / "data"
    / "negative_merit_score_release_certificate.json"
)


class LiveNegativeMeritReleaseTests(
    unittest.TestCase
):
    @staticmethod
    def score(
        total=72,
    ):
        return {
            "total": total,
            "badge": (
                f"badge-{total}"
            ),
            "components": {
                "legacy_component": 1,
            },
            "calculation": {
                "legacy_total": total,
                "final_total": total,
            },
            "reasons": [
                "Legacy Merit reason."
            ],
        }

    @staticmethod
    def negative_result(
        *,
        authority=True,
        semantics=True,
        eligible=True,
        status=(
            "negative_evidence_"
            "calibration_eligible"
        ),
    ):
        return {
            "version": (
                NEGATIVE_MERIT_RUNTIME_VERSION
            ),
            "mode": "shadow",
            "status": status,
            "claim_id": "claim-1",
            "provider_call_performed": False,
            "live_merit_effect_enabled": False,
            "claim_truth_established": False,
            "policy": {
                "no_network_calls": True,
                "no_gemini_calls": True,
                "absence_of_corroboration_is_not_false": True,
                "semantic_contradiction_alone_cannot_change_merit": True,
                "direct_authority_alone_is_not_calibration_eligible": True,
                "machine_verified_semantics_are_required_for_calibration": True,
                "live_negative_merit_is_disabled": True,
            },
            "shadow": {
                "version": (
                    NEGATIVE_MERIT_SHADOW_VERSION
                ),
                "mode": "shadow",
                "claim_id": "claim-1",
                "signal": (
                    "verified_authority_machine_"
                    "semantic_contradiction"
                    if (
                        authority
                        and semantics
                    )
                    else (
                        "no_certified_negative_evidence"
                    )
                ),
                "severity_class": (
                    "two_gate_negative_"
                    "evidence_candidate"
                    if (
                        authority
                        and semantics
                    )
                    else "none"
                ),
                "evidence_gates": {
                    "direct_authority_contradiction_lineage": (
                        authority
                    ),
                    "machine_verified_contradiction_semantics": (
                        semantics
                    ),
                    "both_required": True,
                    "claim_truth_established": False,
                },
                "proposed": {
                    "adjustment": 0.0,
                    "shadow_total": 72.0,
                    "eligible_for_penalty_calibration": (
                        eligible
                    ),
                },
                "live": {
                    "score_effect_enabled": False,
                    "total": 72.0,
                },
                "policy": {
                    "absence_of_corroboration_is_not_negative_evidence": True,
                    "single_source_exclusive_is_not_penalized": True,
                    "publisher_or_aggregator_contradiction_is_not_certified_here": True,
                    "model_only_contradiction_never_changes_merit": True,
                    "verified_direct_authority_lineage_is_required": True,
                    "machine_verified_contradiction_semantics_required_for_calibration": True,
                    "authority_lineage_alone_is_not_calibration_eligible": True,
                    "semantic_verification_alone_is_not_calibration_eligible": True,
                    "recorded_contradiction_is_not_permanent_truth": True,
                    "semantic_contradiction_is_not_objective_falsity": True,
                    "numeric_negative_weight_requires_calibration": True,
                    "live_negative_merit_is_disabled": True,
                },
            },
        }

    @staticmethod
    def badge(
        total,
    ):
        return (
            f"badge-{total}"
        )

    def test_two_gate_evidence_applies_certified_minus_fifteen(
        self,
    ):
        result = (
            apply_certified_live_negative_merit(
                enabled=True,
                score=(
                    self.score(
                        72
                    )
                ),
                negative_merit_result=(
                    self.negative_result()
                ),
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            LIVE_NEGATIVE_MERIT_RELEASE_RUNTIME_VERSION,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "applied",
        )

        self.assertTrue(
            result[
                "score_effect_applied"
            ]
        )

        self.assertEqual(
            result[
                "adjustment"
            ],
            LIVE_NEGATIVE_MERIT_RELEASE_CERTIFIED_ADJUSTMENT,
        )

        self.assertEqual(
            result[
                "input_total"
            ],
            72,
        )

        self.assertEqual(
            result[
                "live_total"
            ],
            57,
        )

        self.assertEqual(
            result[
                "score"
            ][
                "total"
            ],
            57,
        )

    def test_positive_merit_composition_is_preserved(
        self,
    ):
        score = self.score(
            78
        )

        score[
            "components"
        ][
            "certified_corroboration_overlay"
        ] = 6.0

        score[
            "calculation"
        ][
            "legacy_total_before_certified_corroboration"
        ] = 72

        score[
            "calculation"
        ][
            "certified_corroboration_adjustment"
        ] = 6.0

        result = (
            apply_certified_live_negative_merit(
                enabled=True,
                score=score,
                negative_merit_result=(
                    self.negative_result()
                ),
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        live_score = result[
            "score"
        ]

        self.assertEqual(
            live_score[
                "total"
            ],
            63,
        )

        self.assertEqual(
            live_score[
                "components"
            ][
                "certified_corroboration_overlay"
            ],
            6.0,
        )

        self.assertEqual(
            live_score[
                "components"
            ][
                "certified_negative_merit_adjustment"
            ],
            -15.0,
        )

        self.assertEqual(
            live_score[
                "calculation"
            ][
                "legacy_total_before_certified_corroboration"
            ],
            72,
        )

        self.assertEqual(
            live_score[
                "calculation"
            ][
                "total_before_certified_negative_merit"
            ],
            78,
        )

        self.assertEqual(
            live_score[
                "calculation"
            ][
                "final_total"
            ],
            63,
        )

    def test_negative_release_clamps_at_zero(
        self,
    ):
        result = (
            apply_certified_live_negative_merit(
                enabled=True,
                score=(
                    self.score(
                        10
                    )
                ),
                negative_merit_result=(
                    self.negative_result()
                ),
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        self.assertEqual(
            result[
                "score"
            ][
                "total"
            ],
            0,
        )

    def test_disabled_release_preserves_exact_score(
        self,
    ):
        original = self.score(
            72
        )

        result = (
            apply_certified_live_negative_merit(
                enabled=False,
                score=original,
                negative_merit_result=(
                    self.negative_result()
                ),
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )

        self.assertEqual(
            result[
                "score"
            ],
            original,
        )

    def test_authority_only_never_penalizes(
        self,
    ):
        original = self.score(
            72
        )

        result = (
            apply_certified_live_negative_merit(
                enabled=True,
                score=original,
                negative_merit_result=(
                    self.negative_result(
                        authority=True,
                        semantics=False,
                        eligible=False,
                        status=(
                            "no_certified_negative_evidence"
                        ),
                    )
                ),
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )

        self.assertEqual(
            result[
                "score"
            ],
            original,
        )

    def test_semantic_only_never_penalizes(
        self,
    ):
        original = self.score(
            72
        )

        result = (
            apply_certified_live_negative_merit(
                enabled=True,
                score=original,
                negative_merit_result=(
                    self.negative_result(
                        authority=False,
                        semantics=True,
                        eligible=False,
                        status=(
                            "no_certified_negative_evidence"
                        ),
                    )
                ),
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )

        self.assertEqual(
            result[
                "score"
            ],
            original,
        )

    def test_missing_negative_evidence_never_penalizes(
        self,
    ):
        original = self.score(
            72
        )

        result = (
            apply_certified_live_negative_merit(
                enabled=True,
                score=original,
                negative_merit_result={
                    "version": (
                        NEGATIVE_MERIT_RUNTIME_VERSION
                    ),
                    "mode": "shadow",
                    "status": (
                        "no_certified_negative_evidence"
                    ),
                    "claim_id": "claim-1",
                    "provider_call_performed": False,
                    "live_merit_effect_enabled": False,
                    "claim_truth_established": False,
                },
                certificate_path=(
                    CERTIFICATE_PATH
                ),
                badge_resolver=(
                    self.badge
                ),
            )
        )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )

        self.assertEqual(
            result[
                "score"
            ],
            original,
        )

    def test_tampered_certificate_preserves_score(
        self,
    ):
        original = self.score(
            72
        )

        certificate = json.loads(
            CERTIFICATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        certificate[
            "certified_adjustment"
        ] = -99.0

        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(
                    temp
                )
                / "tampered.json"
            )

            path.write_text(
                json.dumps(
                    certificate
                ),
                encoding="utf-8",
            )

            result = (
                apply_certified_live_negative_merit(
                    enabled=True,
                    score=original,
                    negative_merit_result=(
                        self.negative_result()
                    ),
                    certificate_path=path,
                    badge_resolver=(
                        self.badge
                    ),
                )
            )

        self.assertFalse(
            result[
                "score_effect_applied"
            ]
        )

        self.assertEqual(
            result[
                "score"
            ],
            original,
        )

    def test_cache_token_tracks_certificate_state(
        self,
    ):
        authorized = (
            live_negative_merit_release_cache_token(
                enabled=True,
                certificate_path=(
                    CERTIFICATE_PATH
                ),
            )
        )

        disabled = (
            live_negative_merit_release_cache_token(
                enabled=False,
                certificate_path=(
                    CERTIFICATE_PATH
                ),
            )
        )

        self.assertNotEqual(
            authorized,
            disabled,
        )

        self.assertEqual(
            len(
                authorized
            ),
            64,
        )


if __name__ == "__main__":
    unittest.main()
