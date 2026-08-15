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


from app.analysis.merit_evaluation import (
    MERIT_CORROBORATION_EVALUATION_VERSION,
    MERIT_CORROBORATION_GOLDEN_CASE_VERSION,
)
from app.analysis.merit_goldens import (
    MERIT_CORROBORATION_CURATION_VERSION,
    MERIT_CORROBORATION_GOLDEN_DATASET_VERSION,
)
from app.analysis.validation_snapshot import (
    CLAIM_EVIDENCE_SNAPSHOT_VERSION,
)
from app.analysis.merit_release import (
    MERIT_LIVE_RELEASE_GATE_VERSION,
    MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE,
    build_merit_live_release_gate,
)


class MeritLiveReleaseGateTests(
    unittest.TestCase
):
    def evidence_snapshot(
        self,
        *,
        index,
        urls,
    ):
        observations = []

        for position, url in enumerate(
            urls,
            start=1,
        ):
            observations.append(
                {
                    "id": (
                        "snapshot-observation-"
                        + str(index)
                        + "-"
                        + str(position)
                    ),
                    "actor_id": (
                        "fixture-source-"
                        + str(index)
                        + "-"
                        + str(position)
                    ),
                    "source_url": url,
                    "source_role": (
                        "publisher"
                    ),
                    "authority_class": (
                        "none"
                    ),
                    "reliability_class": (
                        "established"
                    ),
                    "provenance_class": (
                        "firsthand_reporting"
                    ),
                    "stance": (
                        "supports"
                    ),
                    "independence_status": (
                        "unknown"
                    ),
                    (
                        "depends_on_"
                        "observation_ids"
                    ): [],
                    "published_at": (
                        "2026-08-14T05:00:00Z"
                    ),
                    "observed_at": (
                        "2026-08-14T05:15:00Z"
                    ),
                }
            )

        return {
            "version": (
                CLAIM_EVIDENCE_SNAPSHOT_VERSION
            ),
            "id": (
                "release-snapshot-"
                + str(index)
            ),
            "claim_id": (
                "claim-"
                + str(index)
            ),
            "claim_text": (
                "Release-gate validation "
                "fixture claim "
                + str(index)
                + "."
            ),
            "as_of": (
                "2026-08-14T05:30:00Z"
            ),
            "observations": (
                observations
            ),
            "review": {
                "status": (
                    "approved"
                ),
                "reviewer": (
                    "reviewer"
                ),
                "reviewed_at": (
                    "2026-08-14T12:00:00+05:30"
                ),
                "rationale": (
                    "Release-gate fixture "
                    "with human-review metadata "
                    "and a time-bounded "
                    "evidence snapshot."
                ),
            },
            "outcome": {},
        }

    def case(
        self,
        *,
        index,
        signal,
        status="approved",
        origin="real_world",
    ):
        urls = [
            (
                "https://source"
                + str(index)
                + "a.example/story"
            )
        ]

        if signal in {
            "verified_corroboration",
            (
                "verified_corroboration_"
                "contested"
            ),
        }:
            urls.append(
                (
                    "https://source"
                    + str(index)
                    + "b.example/story"
                )
            )

        evidence_snapshot = None

        if (
            status == "approved"
            and origin == "real_world"
        ):
            evidence_snapshot = (
                self.evidence_snapshot(
                    index=index,
                    urls=urls,
                )
            )

        result = {
            "version": (
                MERIT_CORROBORATION_GOLDEN_CASE_VERSION
            ),
            "id": (
                "case-"
                + str(index)
            ),
            "claim_id": (
                "claim-"
                + str(index)
            ),
            "legacy_score": {},
            "corroboration_state": {},
            "expectations": {
                "signal": signal,
            },
            "curation": {
                "version": (
                    MERIT_CORROBORATION_CURATION_VERSION
                ),
                "origin": origin,
                "review_status": status,
                "reviewer": (
                    "reviewer"
                    if status == "approved"
                    and origin == "real_world"
                    else ""
                ),
                "reviewed_at": (
                    "2026-08-14T12:00:00+05:30"
                    if status == "approved"
                    and origin == "real_world"
                    else ""
                ),
                "source_urls": (
                    urls
                    if origin == "real_world"
                    else []
                ),
                "label_basis": (
                    "Human reviewed source "
                    "provenance and expected "
                    "corroboration state."
                    if origin == "real_world"
                    else ""
                ),
            },
        }

        if evidence_snapshot is not None:
            result[
                "evidence_snapshot"
            ] = evidence_snapshot

        return result

    def dataset(
        self,
        cases,
    ):
        return {
            "version": (
                MERIT_CORROBORATION_GOLDEN_DATASET_VERSION
            ),
            "cases": cases,
        }

    def approved_coverage_cases(
        self,
    ):
        return [
            self.case(
                index=index,
                signal=signal,
            )
            for index, signal in enumerate(
                MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE,
                start=1,
            )
        ]

    def passing_evaluation(
        self,
        *,
        cases,
    ):
        return {
            "version": (
                MERIT_CORROBORATION_EVALUATION_VERSION
            ),
            "status": "passed",
            "metrics": {
                "cases": len(
                    cases
                ),
                "expectations_passed": (
                    len(
                        cases
                    )
                ),
                "expectations_failed": 0,
                "safety_violations": 0,
                "live_score_changes": 0,
                "positive_adjustments": 1,
                "negative_adjustments": 0,
                (
                    "unverified_positive_"
                    "adjustments"
                ): 0,
                (
                    "contested_positive_"
                    "adjustments"
                ): 0,
                "invariance_groups_checked": 0,
                "invariance_failures": 0,
            },
            "cases": [],
            "invariance_groups": [],
            "enablement": {
                "live_enablement_authorized": (
                    False
                ),
            },
        }

    def test_version_constant(
        self,
    ):
        self.assertEqual(
            MERIT_LIVE_RELEASE_GATE_VERSION,
            "merit-live-release-gate-v1",
        )

    def test_draft_dataset_is_safe_when_live_not_requested(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    index=1,
                    signal=(
                        "verified_corroboration"
                    ),
                    status="draft",
                )
            ]
        )

        result = (
            build_merit_live_release_gate(
                dataset=dataset,
                request_live=False,
            )
        )

        self.assertTrue(
            result[
                "release_authorized"
            ]
        )

        self.assertFalse(
            result[
                "live_merit_authorized"
            ]
        )

        self.assertEqual(
            result["status"],
            "shadow_safe",
        )

    def test_draft_dataset_blocks_live_request(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    index=1,
                    signal=(
                        "verified_corroboration"
                    ),
                    status="draft",
                )
            ]
        )

        result = (
            build_merit_live_release_gate(
                dataset=dataset,
                request_live=True,
            )
        )

        self.assertFalse(
            result[
                "release_authorized"
            ]
        )

        self.assertIn(
            (
                "insufficient_approved_"
                "real_world_cases"
            ),
            result[
                "blockers"
            ],
        )

    def test_required_signal_coverage_is_explicit(
        self,
    ):
        self.assertEqual(
            set(
                MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE
            ),
            {
                "verified_corroboration",
                (
                    "verified_corroboration_"
                    "contested"
                ),
                (
                    "support_dependency_"
                    "present"
                ),
                (
                    "support_independence_"
                    "unknown"
                ),
                (
                    "no_verified_"
                    "corroboration_boost"
                ),
            },
        )

    def test_too_few_approved_cases_blocks_live(
        self,
    ):
        cases = (
            self.approved_coverage_cases()[
                :4
            ]
        )

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        cases
                    )
                ),
                request_live=True,
                minimum_approved_cases=5,
            )
        )

        self.assertIn(
            (
                "insufficient_approved_"
                "real_world_cases"
            ),
            result[
                "blockers"
            ],
        )

    def test_missing_signal_coverage_blocks_live(
        self,
    ):
        cases = [
            self.case(
                index=index,
                signal=(
                    "support_independence_unknown"
                ),
            )
            for index in range(
                1,
                6,
            )
        ]

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        cases
                    )
                ),
                request_live=True,
            )
        )

        self.assertIn(
            (
                "required_signal_"
                "coverage_missing"
            ),
            result[
                "blockers"
            ],
        )

        self.assertIn(
            "verified_corroboration",
            result[
                "missing_signal_coverage"
            ],
        )

    def test_complete_real_world_coverage_can_authorize_live(
        self,
    ):
        cases = (
            self.approved_coverage_cases()
        )

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        cases
                    )
                ),
                request_live=True,
                evaluator=(
                    self.passing_evaluation
                ),
            )
        )

        self.assertTrue(
            result[
                "release_authorized"
            ]
        )

        self.assertTrue(
            result[
                "live_merit_authorized"
            ]
        )

        self.assertEqual(
            result["status"],
            "live_authorized",
        )

    def test_eligible_dataset_does_not_go_live_without_request(
        self,
    ):
        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        self.approved_coverage_cases()
                    )
                ),
                request_live=False,
                evaluator=(
                    self.passing_evaluation
                ),
            )
        )

        self.assertTrue(
            result[
                "release_authorized"
            ]
        )

        self.assertFalse(
            result[
                "live_merit_authorized"
            ]
        )

    def test_failed_evaluation_blocks_live(
        self,
    ):
        def evaluator(
            *,
            cases,
        ):
            result = (
                self.passing_evaluation(
                    cases=cases
                )
            )

            result[
                "status"
            ] = "failed"

            result[
                "metrics"
            ][
                "expectations_failed"
            ] = 1

            return result

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        self.approved_coverage_cases()
                    )
                ),
                request_live=True,
                evaluator=evaluator,
            )
        )

        self.assertFalse(
            result[
                "release_authorized"
            ]
        )

        self.assertIn(
            "evaluation_not_passed",
            result[
                "blockers"
            ],
        )

    def test_safety_violation_blocks_live(
        self,
    ):
        def evaluator(
            *,
            cases,
        ):
            result = (
                self.passing_evaluation(
                    cases=cases
                )
            )

            result[
                "metrics"
            ][
                "safety_violations"
            ] = 1

            return result

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        self.approved_coverage_cases()
                    )
                ),
                request_live=True,
                evaluator=evaluator,
            )
        )

        self.assertIn(
            (
                "evaluation_safety_"
                "violations"
            ),
            result[
                "blockers"
            ],
        )

    def test_wrong_evaluation_version_blocks_live(
        self,
    ):
        def evaluator(
            *,
            cases,
        ):
            result = (
                self.passing_evaluation(
                    cases=cases
                )
            )

            result[
                "version"
            ] = "wrong"

            return result

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        self.approved_coverage_cases()
                    )
                ),
                request_live=True,
                evaluator=evaluator,
            )
        )

        self.assertIn(
            (
                "evaluation_version_"
                "invalid"
            ),
            result[
                "blockers"
            ],
        )

    def test_evaluator_exception_fails_closed(
        self,
    ):
        def evaluator(
            *,
            cases,
        ):
            raise RuntimeError(
                "evaluation unavailable"
            )

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        self.approved_coverage_cases()
                    )
                ),
                request_live=True,
                evaluator=evaluator,
            )
        )

        self.assertFalse(
            result[
                "release_authorized"
            ]
        )

        self.assertIn(
            "evaluation_error:RuntimeError",
            result[
                "blockers"
            ],
        )

    def test_synthetic_cases_never_satisfy_real_world_gate(
        self,
    ):
        cases = [
            self.case(
                index=index,
                signal=signal,
                origin="synthetic_policy",
                status="draft",
            )
            for index, signal in enumerate(
                MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE,
                start=1,
            )
        ]

        result = (
            build_merit_live_release_gate(
                dataset=(
                    self.dataset(
                        cases
                    )
                ),
                request_live=True,
            )
        )

        self.assertEqual(
            result[
                "approved_real_world_cases"
            ],
            0,
        )

        self.assertFalse(
            result[
                "release_authorized"
            ]
        )


if __name__ == "__main__":
    unittest.main()
