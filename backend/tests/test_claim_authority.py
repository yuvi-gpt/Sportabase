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


from app.analysis.authority import (
    CLAIM_AUTHORITY_POLICY_VERSION,
    CLAIM_CONFIRMATION_STATES,
    CLAIM_PROVENANCE_CLASSES,
    CLAIM_RELIABILITY_CLASSES,
    CLAIM_SOURCE_ROLES,
    build_claim_authority_assessment,
)


class ClaimAuthorityTests(
    unittest.TestCase
):
    def row(
        self,
        *,
        row_id="observation-1",
        actor_id="actor-1",
        source_role="publisher",
        authority_class="none",
        reliability_class="established",
        provenance_class="firsthand_reporting",
        stance="supports",
        observed_at="2026-08-14T10:00:00+00:00",
    ):
        return {
            "id": row_id,
            "claim_id": "claim-1",
            "actor_id": actor_id,
            "source_role": source_role,
            "authority_class": authority_class,
            "reliability_class": reliability_class,
            "provenance_class": provenance_class,
            "stance": stance,
            "observed_at": observed_at,
        }

    def assess(
        self,
        rows,
    ):
        return (
            build_claim_authority_assessment(
                claim_id="claim-1",
                observations=rows,
            )
        )

    def test_version_and_vocabularies(
        self,
    ):
        self.assertEqual(
            CLAIM_AUTHORITY_POLICY_VERSION,
            "claim-authority-v1",
        )

        self.assertIn(
            "primary_stakeholder",
            CLAIM_SOURCE_ROLES,
        )

        self.assertIn(
            "official_institution",
            CLAIM_SOURCE_ROLES,
        )

        self.assertIn(
            "privileged_reporter",
            CLAIM_SOURCE_ROLES,
        )

        self.assertIn(
            "elite_specialist",
            CLAIM_RELIABILITY_CLASSES,
        )

        self.assertIn(
            "direct_statement",
            CLAIM_PROVENANCE_CLASSES,
        )

        self.assertIn(
            "stakeholder_contested",
            CLAIM_CONFIRMATION_STATES,
        )

    def test_primary_stakeholder_direct_statement_confirms(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    actor_id="ferrari",
                    source_role="primary_stakeholder",
                    authority_class="direct",
                    reliability_class="not_applicable",
                    provenance_class="direct_statement",
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "stakeholder_confirmed",
        )

        self.assertTrue(
            result[
                "stakeholder_confirmation_established"
            ]
        )

    def test_official_institution_is_distinct(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    actor_id="formula1",
                    source_role="official_institution",
                    authority_class="institutional",
                    reliability_class="established",
                    provenance_class=(
                        "direct_official_reporting"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "institutionally_confirmed",
        )

        self.assertFalse(
            result[
                "stakeholder_confirmation_established"
            ]
        )

        self.assertTrue(
            result[
                "institutional_confirmation_established"
            ]
        )

    def test_elite_reporter_remains_unconfirmed(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    actor_id="elite-reporter",
                    source_role="privileged_reporter",
                    authority_class="none",
                    reliability_class="elite_specialist",
                    provenance_class="firsthand_reporting",
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "reported_unconfirmed",
        )

    def test_multiple_elite_reporters_do_not_create_official_confirmation(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    row_id="reporter-1",
                    actor_id="reporter-a",
                    source_role="privileged_reporter",
                    authority_class="none",
                    reliability_class="elite_specialist",
                    provenance_class="firsthand_reporting",
                ),
                self.row(
                    row_id="reporter-2",
                    actor_id="reporter-b",
                    source_role="privileged_reporter",
                    authority_class="none",
                    reliability_class="elite_specialist",
                    provenance_class="firsthand_reporting",
                    observed_at=(
                        "2026-08-14T10:05:00+00:00"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "reported_unconfirmed",
        )

        self.assertEqual(
            result["counts"]["reporting_support"],
            2,
        )

    def test_opposing_primary_stakeholders_are_contested(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    row_id="alpine",
                    actor_id="alpine",
                    source_role="primary_stakeholder",
                    authority_class="direct",
                    reliability_class="not_applicable",
                    provenance_class="direct_statement",
                    stance="supports",
                ),
                self.row(
                    row_id="piastri",
                    actor_id="piastri",
                    source_role="primary_stakeholder",
                    authority_class="direct",
                    reliability_class="not_applicable",
                    provenance_class="direct_statement",
                    stance="contradicts",
                    observed_at=(
                        "2026-08-14T10:05:00+00:00"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "stakeholder_contested",
        )

        self.assertTrue(
            result["contradiction_present"]
        )

    def test_reporter_contradiction_does_not_erase_stakeholder_confirmation(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    row_id="club",
                    actor_id="club",
                    source_role="primary_stakeholder",
                    authority_class="direct",
                    reliability_class="not_applicable",
                    provenance_class="direct_statement",
                    stance="supports",
                ),
                self.row(
                    row_id="reporter",
                    actor_id="reporter",
                    source_role="privileged_reporter",
                    authority_class="none",
                    reliability_class="elite_specialist",
                    provenance_class="firsthand_reporting",
                    stance="contradicts",
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "stakeholder_confirmed",
        )

        self.assertTrue(
            result["contradiction_present"]
        )

    def test_single_stakeholder_contradiction_is_preserved(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    actor_id="player",
                    source_role="primary_stakeholder",
                    authority_class="direct",
                    reliability_class="not_applicable",
                    provenance_class="direct_statement",
                    stance="contradicts",
                ),
            ]
        )

        self.assertEqual(
            result["confirmation_state"],
            "stakeholder_contradicted",
        )

    def test_invalid_primary_stakeholder_authority_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "require direct authority",
        ):
            self.assess(
                [
                    self.row(
                        source_role="primary_stakeholder",
                        authority_class="institutional",
                    ),
                ]
            )

    def test_invalid_reporter_authority_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "cannot claim stakeholder",
        ):
            self.assess(
                [
                    self.row(
                        source_role="privileged_reporter",
                        authority_class="direct",
                    ),
                ]
            )

    def test_input_order_is_stable(
        self,
    ):
        rows = [
            self.row(
                row_id="b",
                actor_id="reporter-b",
                source_role="privileged_reporter",
                authority_class="none",
                reliability_class="elite_specialist",
                provenance_class="firsthand_reporting",
                observed_at=(
                    "2026-08-14T10:05:00+00:00"
                ),
            ),
            self.row(
                row_id="a",
                actor_id="reporter-a",
                source_role="privileged_reporter",
                authority_class="none",
                reliability_class="elite_specialist",
                provenance_class="firsthand_reporting",
                observed_at=(
                    "2026-08-14T10:00:00+00:00"
                ),
            ),
        ]

        first = self.assess(
            rows
        )

        second = self.assess(
            list(
                reversed(
                    rows
                )
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_assessment_does_not_claim_truth_corroboration_or_merit(
        self,
    ):
        result = self.assess(
            [
                self.row(
                    actor_id="ferrari",
                    source_role="primary_stakeholder",
                    authority_class="direct",
                    reliability_class="not_applicable",
                    provenance_class="direct_statement",
                ),
            ]
        )

        forbidden = {
            "truth",
            "true",
            "false",
            "corroborated",
            "corroboration",
            "independent",
            "merit",
            "merit_score",
            "score",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                result.keys()
            )
        )

    def test_mixed_claims_are_rejected(
        self,
    ):
        row = self.row()
        row["claim_id"] = "other-claim"

        with self.assertRaisesRegex(
            ValueError,
            "cannot mix different claims",
        ):
            self.assess(
                [row]
            )


if __name__ == "__main__":
    unittest.main()
