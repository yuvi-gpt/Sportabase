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


from app.analysis.adjudication_evaluators import (
    AUTHORITY_STATE_EVALUATOR_VERSION,
    build_authority_state_adjudication,
)

from app.analysis.merit_goldens import (
    load_merit_corroboration_golden_dataset,
)

from app.analysis.validation_snapshot import (
    CLAIM_EVIDENCE_SNAPSHOT_VERSION,
)


class AuthorityStateAdjudicationTests(
    unittest.TestCase
):
    def observation(
        self,
        *,
        row_id="observation-1",
        actor_id="team-a",
        source_role=(
            "primary_stakeholder"
        ),
        authority_class="direct",
        reliability_class=(
            "not_applicable"
        ),
        provenance_class=(
            "direct_statement"
        ),
        stance="supports",
        observed_at=(
            "2026-08-15T01:00:00Z"
        ),
    ):
        return {
            "id": row_id,
            "actor_id": (
                actor_id
            ),
            "source_url": (
                "https://example.com/"
                + row_id
            ),
            "source_role": (
                source_role
            ),
            "authority_class": (
                authority_class
            ),
            "reliability_class": (
                reliability_class
            ),
            "provenance_class": (
                provenance_class
            ),
            "stance": stance,
            "independence_status": (
                "not_applicable"
                if source_role
                in {
                    "primary_stakeholder",
                    "official_institution",
                }
                else "unknown"
            ),
            "depends_on_observation_ids": [],
            "published_at": "",
            "observed_at": (
                observed_at
            ),
        }

    def snapshot(
        self,
        observations,
    ):
        return {
            "version": (
                CLAIM_EVIDENCE_SNAPSHOT_VERSION
            ),
            "id": (
                "snapshot-1"
            ),
            "claim_id": (
                "claim-1"
            ),
            "claim_text": (
                "Player will join Team A."
            ),
            "as_of": (
                "2026-08-15T02:00:00Z"
            ),
            "observations": (
                observations
            ),
            "review": {
                "status": "draft",
                "reviewer": "",
                "reviewed_at": "",
                "rationale": "",
            },
            "outcome": {},
        }

    def build(
        self,
        observations,
        *,
        correction=None,
    ):
        return (
            build_authority_state_adjudication(
                evidence_snapshot=(
                    self.snapshot(
                        observations
                    )
                ),
                correction=(
                    correction
                ),
            )
        )

    def test_version(
        self,
    ):
        self.assertEqual(
            AUTHORITY_STATE_EVALUATOR_VERSION,
            "authority-state-evaluator-v1",
        )

    def test_direct_stakeholder_support_is_auto_gold(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "basis_class"
            ],
            "direct_authority_record",
        )

    def test_direct_stakeholder_contradiction_is_auto_gold(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    stance="contradicts",
                )
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_contradicted",
        )

    def test_opposing_stakeholders_produce_auto_gold_contested_state(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    row_id="team",
                    actor_id="team-a",
                    stance="supports",
                ),
                self.observation(
                    row_id="player",
                    actor_id="player-a",
                    stance="contradicts",
                    observed_at=(
                        "2026-08-15T01:05:00Z"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_contested",
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "evidence_ids"
            ],
            [
                "player",
                "team",
            ],
        )

    def test_direct_institutional_record_is_auto_gold(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    actor_id="league",
                    source_role=(
                        "official_institution"
                    ),
                    authority_class=(
                        "institutional"
                    ),
                    reliability_class=(
                        "established"
                    ),
                    provenance_class=(
                        "direct_official_reporting"
                    ),
                )
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "institutionally_confirmed",
        )

    def test_reporter_only_state_is_not_auto_gold(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    actor_id="reporter",
                    source_role=(
                        "privileged_reporter"
                    ),
                    authority_class="none",
                    reliability_class=(
                        "elite_specialist"
                    ),
                    provenance_class=(
                        "firsthand_reporting"
                    ),
                )
            ]
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "value"
            ],
            "reported_unconfirmed",
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "basis_class"
            ],
            "deterministic_rule",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

        self.assertEqual(
            result[
                "effective"
            ][
                "value"
            ],
            "",
        )

    def test_empty_authority_state_is_not_gold_from_absence(
        self,
    ):
        result = self.build(
            []
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "value"
            ],
            "unconfirmed",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

    def test_stored_derived_authority_is_ignored_and_recomputed(
        self,
    ):
        snapshot = self.snapshot(
            [
                self.observation()
            ]
        )

        snapshot[
            "authority_assessment"
        ] = {
            "confirmation_state": (
                "stakeholder_contradicted"
            )
        }

        result = (
            build_authority_state_adjudication(
                evidence_snapshot=(
                    snapshot
                )
            )
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

        self.assertTrue(
            result[
                "evaluator"
            ][
                "stored_derived_authority_is_not_trusted"
            ]
        )

    def test_manual_correction_preserves_automatic_reference(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ],
            correction={
                "value": (
                    "stakeholder_contested"
                ),
                "reason": (
                    "A second direct stakeholder "
                    "observation was missed."
                ),
                "corrected_by": (
                    "Reviewer"
                ),
                "corrected_at": (
                    "2026-08-15T08:45:00+05:30"
                ),
                "scope": (
                    "pattern_candidate"
                ),
            },
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            result[
                "effective"
            ][
                "value"
            ],
            "stakeholder_contested",
        )

        self.assertEqual(
            result[
                "learning_signal"
            ][
                "status"
            ],
            "pending_validation",
        )

        self.assertFalse(
            result[
                "learning_signal"
            ][
                "training_eligible"
            ]
        )

    def test_checked_in_ferrari_case_is_automatically_auto_gold_authority(
        self,
    ):
        dataset = (
            load_merit_corroboration_golden_dataset(
                BACKEND_DIR
                / "data"
                / "merit_corroboration_goldens.json"
            )
        )

        case = [
            row
            for row
            in dataset[
                "cases"
            ]
            if row[
                "id"
            ]
            == (
                "2024-hamilton-ferrari-"
                "single-primary-source"
            )
        ][0]

        self.assertEqual(
            case[
                "curation"
            ][
                "review_status"
            ],
            "draft",
        )

        result = (
            build_authority_state_adjudication(
                evidence_snapshot=(
                    case[
                        "evidence_snapshot"
                    ]
                )
            )
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            case[
                "expectations"
            ][
                "authority_state"
            ],
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "basis_class"
            ],
            "direct_authority_record",
        )

        self.assertEqual(
            result[
                "judgments"
            ][0][
                "evidence_ids"
            ],
            [
                (
                    "ferrari-team-statement-"
                    "2024-02-01"
                )
            ],
        )

    def test_evaluator_does_not_change_live_merit(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ]
        )

        forbidden = {
            "merit",
            "merit_score",
            "score_adjustment",
            "live_total",
            "shadow_total",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                result.keys()
            )
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "automatic_authority_adjudication_does_not_change_live_merit"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "automatic_authority_adjudication_does_not_establish_truth"
            ]
        )


if __name__ == "__main__":
    unittest.main()
