import json
import sys
import tempfile
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
from app.analysis.merit_evaluation import (
    MERIT_CORROBORATION_GOLDEN_CASE_VERSION,
)
from app.analysis.merit_goldens import (
    MERIT_CORROBORATION_CURATION_VERSION,
    MERIT_CORROBORATION_GOLDEN_DATASET_VERSION,
    load_merit_corroboration_golden_dataset,
    select_approved_real_world_golden_cases,
    validate_merit_corroboration_golden_dataset,
)
from app.analysis.validation_snapshot import (
    CLAIM_EVIDENCE_SNAPSHOT_VERSION,
)


class MeritCorroborationGoldenDatasetTests(
    unittest.TestCase
):
    def state(
        self,
        *,
        status=(
            "support_independence_unknown"
        ),
        established=False,
        contested=False,
        independent=False,
    ):
        return {
            "version": (
                CLAIM_CORROBORATION_POLICY_VERSION
            ),
            "claims": [
                {
                    "claim_id": (
                        "claim-1"
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
                    "supporting_source_ids": [
                        "source-a",
                        "source-b",
                    ],
                },
            ],
        }

    def snapshot(
        self,
        *,
        source_urls=None,
    ):
        if source_urls is None:
            source_urls = [
                "https://a.example/story",
            ]

        observations = []

        for index, source_url in enumerate(
            source_urls
        ):
            observations.append(
                {
                    "id": (
                        f"snapshot-observation-"
                        f"{index + 1}"
                    ),
                    "actor_id": (
                        f"source-actor-"
                        f"{index + 1}"
                    ),
                    "source_url": (
                        source_url
                    ),
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
                        "2026-08-14T03:45:00Z"
                    ),
                    "observed_at": (
                        "2026-08-14T04:00:00Z"
                    ),
                    "capture": {
                        "method": (
                            "direct_http"
                        ),
                        "status": (
                            "captured"
                        ),
                        "captured_at": (
                            "2026-08-15T00:00:00Z"
                        ),
                        "content_sha256": (
                            format(
                                index + 1,
                                "064x",
                            )
                        ),
                        "note": (
                            "Deterministic golden "
                            "fixture capture."
                        ),
                    },
                }
            )

        return {
            "version": (
                CLAIM_EVIDENCE_SNAPSHOT_VERSION
            ),
            "id": (
                "snapshot-case-1"
            ),
            "claim_id": (
                "claim-1"
            ),
            "claim_text": (
                "A reviewed sports claim."
            ),
            "as_of": (
                "2026-08-14T04:15:00Z"
            ),
            "observations": (
                observations
            ),
            "review": {
                "status": (
                    "approved"
                ),
                "reviewer": (
                    "Yuvraj"
                ),
                "reviewed_at": (
                    "2026-08-14T10:00:00+05:30"
                ),
                "rationale": (
                    "Human-reviewed authority, "
                    "provenance, timing, and "
                    "source relationships."
                ),
            },
            "outcome": {},
        }

    def case(
        self,
        *,
        case_id="case-1",
        origin="real_world",
        review_status="approved",
        reviewer="Yuvraj",
        reviewed_at=(
            "2026-08-14T10:00:00+05:30"
        ),
        source_urls=None,
        label_basis=(
            "Manually reviewed source "
            "provenance and reporting basis."
        ),
        signal=(
            "support_independence_unknown"
        ),
        authority_state=(
            "reported_unconfirmed"
        ),
        state=None,
    ):
        if source_urls is None:
            source_urls = [
                "https://a.example/story",
            ]

        return {
            "version": (
                MERIT_CORROBORATION_GOLDEN_CASE_VERSION
            ),
            "evidence_snapshot": (
                self.snapshot(
                    source_urls=source_urls
                )
            ),
            "id": (
                case_id
            ),
            "claim_id": (
                "claim-1"
            ),
            "legacy_score": {
                "total": 60,
                "components": {
                    "corroboration": 4,
                },
            },
            "corroboration_state": (
                self.state()
                if state is None
                else state
            ),
            "expectations": {
                "signal": (
                    signal
                ),
                "authority_state": (
                    authority_state
                ),
                "adjustment": 0,
                "live_total": 60,
                "shadow_total": 60,
            },
            "curation": {
                "version": (
                    MERIT_CORROBORATION_CURATION_VERSION
                ),
                "origin": (
                    origin
                ),
                "review_status": (
                    review_status
                ),
                "reviewer": (
                    reviewer
                ),
                "reviewed_at": (
                    reviewed_at
                ),
                "source_urls": (
                    source_urls
                ),
                "label_basis": (
                    label_basis
                ),
            },
        }

    def dataset(
        self,
        cases,
        *,
        version=None,
    ):
        return {
            "version": (
                MERIT_CORROBORATION_GOLDEN_DATASET_VERSION
                if version is None
                else version
            ),
            "cases": (
                cases
            ),
        }

    def test_checked_in_dataset_has_real_world_drafts_and_is_not_ready(
        self,
    ):
        path = (
            BACKEND_DIR
            / "data"
            / "merit_corroboration_goldens.json"
        )

        result = (
            load_merit_corroboration_golden_dataset(
                path
            )
        )

        self.assertEqual(
            result["status"],
            "awaiting_curated_cases",
        )

        self.assertEqual(
            result["counts"]["cases"],
            4,
        )

        self.assertEqual(
            result["counts"]["real_world"],
            4,
        )

        self.assertEqual(
            result["counts"]["draft"],
            4,
        )

        self.assertEqual(
            result["counts"][
                "approved_real_world"
            ],
            0,
        )

        self.assertEqual(
            result["counts"][
                "evaluation_eligible"
            ],
            0,
        )

        self.assertFalse(
            result[
                "evaluation_ready"
            ]
        )

        self.assertFalse(
            result[
                "live_enablement_authorized"
            ]
        )


    def test_checked_in_drafts_preserve_human_approval_gate(
        self,
    ):
        path = (
            BACKEND_DIR
            / "data"
            / "merit_corroboration_goldens.json"
        )

        result = (
            load_merit_corroboration_golden_dataset(
                path
            )
        )

        expected_ids = {
            (
                "2025-doncic-lakers-"
                "two-primary-sources"
            ),
            (
                "2024-hamilton-ferrari-"
                "independence-unknown"
            ),
            (
                "2024-klopp-liverpool-"
                "announcement-dependency"
            ),
            (
                "2024-hamilton-ferrari-"
                "single-primary-source"
            ),
        }

        actual_ids = {
            case["id"]
            for case in result["cases"]
        }

        self.assertEqual(
            actual_ids,
            expected_ids,
        )

        self.assertEqual(
            result[
                "approved_real_world_cases"
            ],
            [],
        )

        for case in result["cases"]:
            curation = case[
                "curation"
            ]

            self.assertEqual(
                curation["origin"],
                "real_world",
            )

            self.assertEqual(
                curation[
                    "review_status"
                ],
                "draft",
            )

            self.assertEqual(
                curation["reviewer"],
                "",
            )

            self.assertEqual(
                curation["reviewed_at"],
                "",
            )

            self.assertTrue(
                curation["source_urls"]
            )

            self.assertTrue(
                curation["label_basis"]
            )

    def test_approved_real_world_case_is_evaluation_eligible(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(),
            ]
        )

        result = (
            validate_merit_corroboration_golden_dataset(
                dataset
            )
        )

        self.assertEqual(
            result["status"],
            "ready_for_evaluation",
        )

        self.assertEqual(
            result["counts"][
                "approved_real_world"
            ],
            1,
        )

        self.assertEqual(
            result["counts"][
                "evaluation_eligible"
            ],
            1,
        )

    def test_approved_real_world_case_requires_expected_authority_state(
        self,
    ):
        case = self.case()

        del case[
            "expectations"
        ][
            "authority_state"
        ]

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "requires an expected authority state",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_expected_authority_state_must_be_supported(
        self,
    ):
        case = self.case(
            authority_state=(
                "magically_confirmed"
            )
        )

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "authority state is unsupported",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_expected_authority_state_must_match_snapshot(
        self,
    ):
        case = self.case(
            authority_state=(
                "stakeholder_confirmed"
            )
        )

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not match",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_stakeholder_confirmation_can_coexist_with_no_corroboration_boost(
        self,
    ):
        case = self.case(
            signal=(
                "no_verified_corroboration_boost"
            ),
            authority_state=(
                "stakeholder_confirmed"
            ),
        )

        case[
            "evidence_snapshot"
        ][
            "observations"
        ][0].update(
            {
                "actor_id": "team-a",
                "source_role": (
                    "primary_stakeholder"
                ),
                "authority_class": (
                    "direct"
                ),
                "reliability_class": (
                    "not_applicable"
                ),
                "provenance_class": (
                    "direct_statement"
                ),
                "independence_status": (
                    "not_applicable"
                ),
            }
        )

        dataset = self.dataset(
            [case]
        )

        result = (
            validate_merit_corroboration_golden_dataset(
                dataset
            )
        )

        validated = result[
            "approved_real_world_cases"
        ][0]

        self.assertEqual(
            validated[
                "expectations"
            ][
                "signal"
            ],
            "no_verified_corroboration_boost",
        )

        self.assertEqual(
            validated[
                "expectations"
            ][
                "authority_state"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            validated[
                "evidence_snapshot"
            ][
                "authority_assessment"
            ][
                "confirmation_state"
            ],
            "stakeholder_confirmed",
        )

    def test_approved_real_world_case_requires_evidence_snapshot(
        self,
    ):
        case = self.case()

        del case[
            "evidence_snapshot"
        ]

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "time-bounded evidence snapshot",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_evidence_snapshot_claim_must_match_golden_claim(
        self,
    ):
        case = self.case()

        case[
            "evidence_snapshot"
        ][
            "claim_id"
        ] = "different-claim"

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "claim ID must match",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_approved_golden_requires_approved_snapshot(
        self,
    ):
        case = self.case()

        case[
            "evidence_snapshot"
        ][
            "review"
        ] = {
            "status": "draft",
            "reviewer": "",
            "reviewed_at": "",
            "rationale": "",
        }

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "requires an approved evidence snapshot",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_snapshot_reviewer_must_match_golden_reviewer(
        self,
    ):
        case = self.case()

        case[
            "evidence_snapshot"
        ][
            "review"
        ][
            "reviewer"
        ] = "Different Reviewer"

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "reviewer must match",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_snapshot_sources_must_match_golden_sources(
        self,
    ):
        case = self.case()

        case[
            "evidence_snapshot"
        ][
            "observations"
        ][0][
            "source_url"
        ] = (
            "https://different.example/story"
        )

        dataset = self.dataset(
            [case]
        )

        with self.assertRaisesRegex(
            ValueError,
            "source URLs must match",
        ):
            validate_merit_corroboration_golden_dataset(
                dataset
            )

    def test_draft_real_world_case_is_excluded(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    review_status="draft",
                    reviewer="",
                    reviewed_at="",
                ),
            ]
        )

        selected = (
            select_approved_real_world_golden_cases(
                dataset
            )
        )

        self.assertEqual(
            selected,
            [],
        )

    def test_synthetic_case_cannot_count_as_real_world_validation(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    origin="synthetic_policy",
                ),
            ]
        )

        result = (
            validate_merit_corroboration_golden_dataset(
                dataset
            )
        )

        self.assertEqual(
            result["counts"][
                "synthetic_policy"
            ],
            1,
        )

        self.assertEqual(
            result["counts"][
                "approved_real_world"
            ],
            0,
        )

        self.assertFalse(
            result[
                "evaluation_ready"
            ]
        )

    def test_duplicate_case_ids_are_rejected(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    case_id="duplicate"
                ),
                self.case(
                    case_id="duplicate"
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be unique",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_approved_real_world_case_requires_reviewer(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    reviewer=""
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "reviewer is required",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_approved_real_world_case_requires_timezone_review_time(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    reviewed_at=(
                        "2026-08-14T10:00:00"
                    )
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "must include a timezone",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_real_world_case_requires_source_provenance(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    source_urls=[]
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "at least one source URL",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_verified_case_requires_two_unique_sources(
        self,
    ):
        verified_state = self.state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
        )

        dataset = self.dataset(
            [
                self.case(
                    signal=(
                        "verified_corroboration"
                    ),
                    state=(
                        verified_state
                    ),
                    source_urls=[
                        "https://a.example/story",
                    ],
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "at least two",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_duplicate_source_urls_do_not_fake_two_sources(
        self,
    ):
        verified_state = self.state(
            status=(
                "corroboration_established"
            ),
            established=True,
            independent=True,
        )

        dataset = self.dataset(
            [
                self.case(
                    signal=(
                        "verified_corroboration"
                    ),
                    state=(
                        verified_state
                    ),
                    source_urls=[
                        "https://A.EXAMPLE/story/",
                        "https://a.example/story",
                    ],
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be unique",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_invalid_source_url_is_rejected(
        self,
    ):
        dataset = self.dataset(
            [
                self.case(
                    source_urls=[
                        "not-a-url",
                    ]
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "absolute HTTP",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )

    def test_wrong_dataset_version_is_rejected(
        self,
    ):
        dataset = self.dataset(
            [],
            version=(
                "merit-goldens-v999"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "Unsupported",
        ):
            (
                validate_merit_corroboration_golden_dataset(
                    dataset
                )
            )


if __name__ == "__main__":
    unittest.main()
