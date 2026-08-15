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


from app.analysis.validation_snapshot import (
    CLAIM_EVIDENCE_SNAPSHOT_VERSION,
    SNAPSHOT_AVAILABILITY_BASES,
    SNAPSHOT_AVAILABILITY_PRECISIONS,
    SNAPSHOT_CAPTURE_METHODS,
    SNAPSHOT_CAPTURE_STATUSES,
    SNAPSHOT_CAPTURE_TIME_BASES,
    SNAPSHOT_CAPTURE_TIME_PRECISIONS,
    SNAPSHOT_DERIVATION_MODES,
    SNAPSHOT_INDEPENDENCE_STATUSES,
    build_claim_evidence_snapshot,
)


class ClaimEvidenceSnapshotTests(
    unittest.TestCase
):
    def observation(
        self,
        *,
        row_id="observation-1",
        actor_id="reporter-1",
        source_role="privileged_reporter",
        authority_class="none",
        reliability_class="elite_specialist",
        provenance_class="firsthand_reporting",
        stance="supports",
        independence_status="unknown",
        depends_on=None,
        published_at=(
            "2026-08-14T09:55:00+00:00"
        ),
        observed_at=(
            "2026-08-14T10:00:00+00:00"
        ),
        availability=None,
        capture_method="direct_http",
        capture_status="captured",
        captured_at=(
            "2026-08-15T00:00:00+00:00"
        ),
        capture_time=None,
        content_sha256=(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        ),
        capture_note="Deterministic test capture.",
    ):
        if depends_on is None:
            depends_on = []

        return {
            "id": row_id,
            "actor_id": actor_id,
            "source_url": (
                "https://example.com/"
                + row_id
            ),
            "source_role": source_role,
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
                independence_status
            ),
            "depends_on_observation_ids": (
                depends_on
            ),
            "published_at": (
                published_at
            ),
            "observed_at": (
                observed_at
            ),
            "availability": (
                availability
            ),
            "capture": {
                "method": (
                    capture_method
                ),
                "status": (
                    capture_status
                ),
                "captured_at": (
                    captured_at
                ),
                "time": (
                    capture_time
                ),
                "content_sha256": (
                    content_sha256
                ),
                "note": (
                    capture_note
                ),
            },
        }

    def case(
        self,
        observations,
        *,
        review=None,
        outcome=None,
        derivation=None,
        as_of=(
            "2026-08-14T11:00:00+00:00"
        ),
    ):
        if review is None:
            review = {
                "status": "draft",
                "reviewer": "",
                "reviewed_at": "",
                "rationale": "",
            }

        if outcome is None:
            outcome = {}

        return {
            "version": (
                CLAIM_EVIDENCE_SNAPSHOT_VERSION
            ),
            "id": "case-1",
            "claim_id": "claim-1",
            "claim_text": (
                "Driver will join Team A."
            ),
            "as_of": (
                as_of
            ),
            "observations": observations,
            "review": review,
            "derivation": (
                derivation
            ),
            "outcome": outcome,
        }

    def build(
        self,
        observations,
        **kwargs,
    ):
        return (
            build_claim_evidence_snapshot(
                self.case(
                    observations,
                    **kwargs,
                )
            )
        )

    def test_version_and_independence_vocabulary(
        self,
    ):
        self.assertEqual(
            CLAIM_EVIDENCE_SNAPSHOT_VERSION,
            "claim-evidence-snapshot-v1",
        )

        self.assertEqual(
            set(
                SNAPSHOT_INDEPENDENCE_STATUSES
            ),
            {
                "established",
                "not_established",
                "unknown",
                "not_applicable",
            },
        )

        self.assertIn(
            "official_search_index_snapshot",
            SNAPSHOT_CAPTURE_METHODS,
        )

        self.assertIn(
            "archive_snapshot",
            SNAPSHOT_CAPTURE_METHODS,
        )

        self.assertIn(
            "partial",
            SNAPSHOT_CAPTURE_STATUSES,
        )

        self.assertIn(
            "unavailable",
            SNAPSHOT_CAPTURE_STATUSES,
        )

        self.assertEqual(
            set(
                SNAPSHOT_CAPTURE_TIME_PRECISIONS
            ),
            {
                "timestamp",
                "date",
                "unknown",
            },
        )

        self.assertIn(
            "legacy_captured_at",
            SNAPSHOT_CAPTURE_TIME_BASES,
        )

        self.assertIn(
            "review_session_date",
            SNAPSHOT_CAPTURE_TIME_BASES,
        )

        self.assertEqual(
            set(
                SNAPSHOT_AVAILABILITY_PRECISIONS
            ),
            {
                "timestamp",
                "date",
                "unknown",
            },
        )

        self.assertIn(
            "official_release_date",
            SNAPSHOT_AVAILABILITY_BASES,
        )

        self.assertIn(
            "legacy_observed_at",
            SNAPSHOT_AVAILABILITY_BASES,
        )

        self.assertEqual(
            set(
                SNAPSHOT_DERIVATION_MODES
            ),
            {
                "machine_verified",
                "model_assisted",
                "manual_draft",
                "mixed",
                "unknown",
            },
        )

    def test_snapshot_derivation_defaults_to_unknown(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ]
        )

        self.assertEqual(
            result[
                "derivation"
            ],
            {
                "mode": "unknown",
                "producer": "",
                "producer_version": "",
                "evidence_ids": [],
                "note": "",
            },
        )

    def test_machine_verified_derivation_requires_audit_lineage(
        self,
    ):
        incomplete = [
            {
                "mode": "machine_verified",
                "producer": "",
                "producer_version": "v1",
                "evidence_ids": [
                    "observation-1",
                ],
            },
            {
                "mode": "machine_verified",
                "producer": (
                    "authority-pipeline"
                ),
                "producer_version": "",
                "evidence_ids": [
                    "observation-1",
                ],
            },
            {
                "mode": "machine_verified",
                "producer": (
                    "authority-pipeline"
                ),
                "producer_version": "v1",
                "evidence_ids": [],
            },
        ]

        for derivation in incomplete:
            with self.subTest(
                derivation=derivation
            ):
                with self.assertRaises(
                    ValueError
                ):
                    self.build(
                        [
                            self.observation()
                        ],
                        derivation=(
                            derivation
                        ),
                    )

    def test_machine_verified_derivation_is_preserved(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ],
            derivation={
                "mode": (
                    "machine_verified"
                ),
                "producer": (
                    "authority-pipeline"
                ),
                "producer_version": (
                    "authority-pipeline-v1"
                ),
                "evidence_ids": [
                    "observation-1",
                ],
                "note": (
                    "Required source identity "
                    "and evidence fields were "
                    "machine verified."
                ),
            },
        )

        self.assertEqual(
            result[
                "derivation"
            ][
                "mode"
            ],
            "machine_verified",
        )

        self.assertEqual(
            result[
                "derivation"
            ][
                "evidence_ids"
            ],
            [
                "observation-1",
            ],
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "machine_verified_derivation_requires_evidence_lineage"
            ]
        )

    def test_primary_stakeholder_statement_confirms_snapshot(
        self,
    ):
        result = self.build(
            [
                self.observation(
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
                    independence_status=(
                        "not_applicable"
                    ),
                )
            ]
        )

        authority = result[
            "authority_assessment"
        ]

        self.assertEqual(
            authority[
                "confirmation_state"
            ],
            "stakeholder_confirmed",
        )

        self.assertTrue(
            authority[
                "stakeholder_confirmation_established"
            ]
        )

    def test_official_institution_is_institutional_not_stakeholder(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    actor_id="sport-body",
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
                    independence_status=(
                        "not_applicable"
                    ),
                )
            ]
        )

        authority = result[
            "authority_assessment"
        ]

        self.assertEqual(
            authority[
                "confirmation_state"
            ],
            "institutionally_confirmed",
        )

        self.assertFalse(
            authority[
                "stakeholder_confirmation_established"
            ]
        )

    def test_elite_reporter_remains_unconfirmed(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ]
        )

        self.assertEqual(
            result[
                "authority_assessment"
            ][
                "confirmation_state"
            ],
            "reported_unconfirmed",
        )

    def test_opposing_stakeholders_are_contested(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    row_id="team",
                    actor_id="team",
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
                    independence_status=(
                        "not_applicable"
                    ),
                ),
                self.observation(
                    row_id="driver",
                    actor_id="driver",
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
                    stance="contradicts",
                    independence_status=(
                        "not_applicable"
                    ),
                    observed_at=(
                        "2026-08-14T10:05:00+00:00"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result[
                "authority_assessment"
            ][
                "confirmation_state"
            ],
            "stakeholder_contested",
        )

    def test_observation_after_as_of_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "after the snapshot as_of",
        ):
            self.build(
                [
                    self.observation(
                        observed_at=(
                            "2026-08-14T12:00:00+00:00"
                        )
                    )
                ]
            )

    def test_publication_after_as_of_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "publication occurs after",
        ):
            self.build(
                [
                    self.observation(
                        published_at=(
                            "2026-08-14T12:00:00+00:00"
                        )
                    )
                ]
            )

    def test_dependency_blocks_independence_established(
        self,
    ):
        first = self.observation(
            row_id="origin"
        )

        second = self.observation(
            row_id="dependent",
            depends_on=[
                "origin"
            ],
            independence_status=(
                "established"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "recorded dependencies",
        ):
            self.build(
                [
                    first,
                    second,
                ]
            )

    def test_unknown_dependency_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "unknown dependency",
        ):
            self.build(
                [
                    self.observation(
                        depends_on=[
                            "missing"
                        ],
                        independence_status=(
                            "not_established"
                        ),
                    )
                ]
            )

    def test_recorded_dependency_is_preserved(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    row_id="origin"
                ),
                self.observation(
                    row_id="dependent",
                    depends_on=[
                        "origin"
                    ],
                    independence_status=(
                        "not_established"
                    ),
                    observed_at=(
                        "2026-08-14T10:05:00+00:00"
                    ),
                ),
            ]
        )

        dependent = [
            row
            for row in result[
                "observations"
            ]
            if row["id"]
            == "dependent"
        ][0]

        self.assertEqual(
            dependent[
                "depends_on_observation_ids"
            ],
            [
                "origin"
            ],
        )

    def test_conflicting_duplicate_observation_is_rejected(
        self,
    ):
        first = self.observation(
            row_id="same"
        )

        second = {
            **first,
            "stance": "contradicts",
        }

        with self.assertRaisesRegex(
            ValueError,
            "conflicting duplicate",
        ):
            self.build(
                [
                    first,
                    second,
                ]
            )

    def test_legacy_observed_at_derives_timestamp_availability(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ]
        )

        availability = result[
            "observations"
        ][0][
            "availability"
        ]

        self.assertEqual(
            availability[
                "precision"
            ],
            "timestamp",
        )

        self.assertEqual(
            availability[
                "basis"
            ],
            "legacy_observed_at",
        )

        self.assertEqual(
            availability[
                "value"
            ],
            "2026-08-14T10:00:00Z",
        )

    def test_date_only_availability_preserves_date_precision(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    observed_at="",
                    published_at="",
                    availability={
                        "precision": "date",
                        "value": "2024-02-01",
                        "basis": (
                            "official_release_date"
                        ),
                    },
                )
            ],
            as_of=(
                "2024-02-01T23:59:59Z"
            ),
        )

        observation = result[
            "observations"
        ][0]

        self.assertEqual(
            observation[
                "observed_at"
            ],
            "",
        )

        self.assertEqual(
            observation[
                "published_at"
            ],
            "",
        )

        self.assertEqual(
            observation[
                "availability"
            ],
            {
                "precision": "date",
                "value": "2024-02-01",
                "basis": (
                    "official_release_date"
                ),
            },
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "date_precision_does_not_invent_clock_time"
            ]
        )

    def test_date_availability_after_snapshot_date_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "availability date occurs after",
        ):
            self.build(
                [
                    self.observation(
                        observed_at="",
                        published_at="",
                        availability={
                            "precision": "date",
                            "value": "2024-02-01",
                            "basis": (
                                "official_release_date"
                            ),
                        },
                    )
                ],
                as_of=(
                    "2024-01-31T23:59:59Z"
                ),
            )

    def test_timestamp_availability_is_normalized(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    observed_at="",
                    published_at="",
                    availability={
                        "precision": (
                            "timestamp"
                        ),
                        "value": (
                            "2024-02-01T12:00:00+05:30"
                        ),
                        "basis": (
                            "published_timestamp"
                        ),
                    },
                )
            ],
            as_of=(
                "2024-02-01T23:59:59Z"
            ),
        )

        self.assertEqual(
            result[
                "observations"
            ][0][
                "availability"
            ][
                "value"
            ],
            "2024-02-01T06:30:00Z",
        )

    def test_invalid_date_availability_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "must be YYYY-MM-DD",
        ):
            self.build(
                [
                    self.observation(
                        observed_at="",
                        published_at="",
                        availability={
                            "precision": "date",
                            "value": "2024-02-99",
                            "basis": (
                                "official_release_date"
                            ),
                        },
                    )
                ]
            )

    def test_approved_snapshot_requires_known_availability(
        self,
    ):
        review = {
            "status": "approved",
            "reviewer": "Human Reviewer",
            "reviewed_at": (
                "2026-08-15T01:00:00Z"
            ),
            "rationale": (
                "Reviewed source authority, "
                "temporal availability, "
                "provenance, and capture."
            ),
        }

        with self.assertRaisesRegex(
            ValueError,
            "known evidence availability",
        ):
            self.build(
                [
                    self.observation(
                        observed_at="",
                        published_at="",
                        availability={
                            "precision": (
                                "unknown"
                            ),
                            "value": "",
                            "basis": "unknown",
                        },
                    )
                ],
                review=review,
            )

    def test_capture_metadata_is_preserved(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    capture_method=(
                        "official_search_index_snapshot"
                    ),
                    capture_status="partial",
                    capture_note=(
                        "Direct HTTP unavailable; "
                        "official indexed text captured."
                    ),
                )
            ]
        )

        capture = result[
            "observations"
        ][0][
            "capture"
        ]

        self.assertEqual(
            capture["method"],
            "official_search_index_snapshot",
        )

        self.assertEqual(
            capture["status"],
            "partial",
        )

        self.assertEqual(
            capture["content_sha256"],
            (
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
        )

        self.assertIn(
            "Direct HTTP unavailable",
            capture["note"],
        )

    def test_retrospective_capture_may_postdate_as_of(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    captured_at=(
                        "2026-08-15T00:00:00Z"
                    ),
                )
            ]
        )

        capture = result[
            "observations"
        ][0][
            "capture"
        ]

        self.assertEqual(
            capture[
                "captured_at"
            ],
            "2026-08-15T00:00:00Z",
        )

        self.assertEqual(
            capture[
                "time"
            ],
            {
                "precision": "timestamp",
                "value": (
                    "2026-08-15T00:00:00Z"
                ),
                "basis": (
                    "legacy_captured_at"
                ),
            },
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "retrospective_capture_may_postdate_snapshot_as_of"
            ]
        )

    def test_capture_date_precision_is_preserved(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    captured_at="",
                    capture_time={
                        "precision": "date",
                        "value": "2026-08-15",
                        "basis": (
                            "review_session_date"
                        ),
                    },
                )
            ]
        )

        capture = result[
            "observations"
        ][0][
            "capture"
        ]

        self.assertEqual(
            capture[
                "captured_at"
            ],
            "",
        )

        self.assertEqual(
            capture[
                "time"
            ],
            {
                "precision": "date",
                "value": "2026-08-15",
                "basis": (
                    "review_session_date"
                ),
            },
        )

    def test_capture_date_may_postdate_historical_as_of(
        self,
    ):
        result = self.build(
            [
                self.observation(
                    observed_at="",
                    published_at="",
                    availability={
                        "precision": "date",
                        "value": "2024-02-01",
                        "basis": (
                            "official_release_date"
                        ),
                    },
                    captured_at="",
                    capture_time={
                        "precision": "date",
                        "value": "2026-08-15",
                        "basis": (
                            "review_session_date"
                        ),
                    },
                )
            ],
            as_of=(
                "2024-02-01T23:59:59Z"
            ),
        )

        self.assertEqual(
            result[
                "observations"
            ][0][
                "capture"
            ][
                "time"
            ][
                "value"
            ],
            "2026-08-15",
        )

    def test_unknown_capture_time_with_explanation_can_be_approved(
        self,
    ):
        review = {
            "status": "approved",
            "reviewer": "Human Reviewer",
            "reviewed_at": (
                "2026-08-15T01:00:00Z"
            ),
            "rationale": (
                "Reviewed authority, provenance, "
                "availability, and capture."
            ),
        }

        result = self.build(
            [
                self.observation(
                    captured_at="",
                    capture_time={
                        "precision": "unknown",
                        "value": "",
                        "basis": "unknown",
                    },
                    capture_note=(
                        "The exact retrospective "
                        "capture time was not preserved."
                    ),
                )
            ],
            review=review,
        )

        capture = result[
            "observations"
        ][0][
            "capture"
        ]

        self.assertEqual(
            capture[
                "time"
            ][
                "precision"
            ],
            "unknown",
        )

        self.assertEqual(
            result[
                "review"
            ][
                "status"
            ],
            "approved",
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "approval_does_not_require_fabricated_capture_timestamp"
            ]
        )

    def test_unknown_capture_time_without_explanation_blocks_approval(
        self,
    ):
        review = {
            "status": "approved",
            "reviewer": "Human Reviewer",
            "reviewed_at": (
                "2026-08-15T01:00:00Z"
            ),
            "rationale": (
                "Reviewed authority, provenance, "
                "availability, and capture."
            ),
        }

        with self.assertRaisesRegex(
            ValueError,
            "unknown capture time requires",
        ):
            self.build(
                [
                    self.observation(
                        captured_at="",
                        capture_time={
                            "precision": "unknown",
                            "value": "",
                            "basis": "unknown",
                        },
                        capture_note="",
                    )
                ],
                review=review,
            )

    def test_invalid_capture_date_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "must be YYYY-MM-DD",
        ):
            self.build(
                [
                    self.observation(
                        captured_at="",
                        capture_time={
                            "precision": "date",
                            "value": "2026-08-99",
                            "basis": (
                                "review_session_date"
                            ),
                        },
                    )
                ]
            )

    def test_conflicting_legacy_and_explicit_capture_time_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "conflicts with captured_at",
        ):
            self.build(
                [
                    self.observation(
                        captured_at=(
                            "2026-08-15T00:00:00Z"
                        ),
                        capture_time={
                            "precision": "timestamp",
                            "value": (
                                "2026-08-15T01:00:00Z"
                            ),
                            "basis": (
                                "capture_timestamp"
                            ),
                        },
                    )
                ]
            )

    def test_invalid_capture_sha256_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "64-character hexadecimal SHA-256",
        ):
            self.build(
                [
                    self.observation(
                        content_sha256="not-a-hash",
                    )
                ]
            )

    def test_approved_snapshot_requires_auditable_capture(
        self,
    ):
        cases = [
            (
                {
                    "capture_method": "unknown",
                },
                "known capture method",
            ),
            (
                {
                    "capture_status": "unavailable",
                },
                "captured or partial evidence",
            ),
            (
                {
                    "content_sha256": "",
                },
                "requires content_sha256",
            ),
        ]

        review = {
            "status": "approved",
            "reviewer": "Human Reviewer",
            "reviewed_at": (
                "2026-08-15T01:00:00Z"
            ),
            "rationale": (
                "Reviewed authority, provenance, "
                "timing, and capture metadata."
            ),
        }

        for overrides, message in cases:
            with self.subTest(
                overrides=overrides
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    message,
                ):
                    self.build(
                        [
                            self.observation(
                                **overrides
                            )
                        ],
                        review=review,
                    )

    def test_approved_snapshot_requires_human_review_metadata(
        self,
    ):
        incomplete_reviews = [
            {
                "status": "approved",
                "reviewer": "",
                "reviewed_at": (
                    "2026-08-14T12:00:00+00:00"
                ),
                "rationale": "Reviewed.",
            },
            {
                "status": "approved",
                "reviewer": "Reviewer",
                "reviewed_at": "",
                "rationale": "Reviewed.",
            },
            {
                "status": "approved",
                "reviewer": "Reviewer",
                "reviewed_at": (
                    "2026-08-14T12:00:00+00:00"
                ),
                "rationale": "",
            },
        ]

        for review in incomplete_reviews:
            with self.subTest(
                review=review
            ):
                with self.assertRaises(
                    ValueError
                ):
                    self.build(
                        [
                            self.observation()
                        ],
                        review=review,
                    )

    def test_valid_approved_snapshot_is_preserved(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ],
            review={
                "status": "approved",
                "reviewer": "Human Reviewer",
                "reviewed_at": (
                    "2026-08-14T12:00:00+00:00"
                ),
                "rationale": (
                    "Reviewed source role, "
                    "provenance, and timing."
                ),
            },
        )

        self.assertEqual(
            result["review"]["status"],
            "approved",
        )

        self.assertEqual(
            result[
                "review"
            ][
                "reviewer"
            ],
            "Human Reviewer",
        )

    def test_later_outcome_does_not_change_historical_authority(
        self,
    ):
        first = self.build(
            [
                self.observation()
            ],
            outcome={
                "status": "eventually_true"
            },
        )

        second = self.build(
            [
                self.observation()
            ],
            outcome={
                "status": "eventually_false"
            },
        )

        self.assertEqual(
            first[
                "authority_assessment"
            ],
            second[
                "authority_assessment"
            ],
        )

        self.assertNotEqual(
            first["outcome"],
            second["outcome"],
        )

    def test_input_order_is_stable(
        self,
    ):
        rows = [
            self.observation(
                row_id="later",
                observed_at=(
                    "2026-08-14T10:05:00+00:00"
                ),
            ),
            self.observation(
                row_id="earlier",
                observed_at=(
                    "2026-08-14T10:00:00+00:00"
                ),
            ),
        ]

        first = self.build(
            rows
        )

        second = self.build(
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

    def test_invalid_source_url_is_rejected(
        self,
    ):
        row = self.observation()
        row["source_url"] = "not-a-url"

        with self.assertRaisesRegex(
            ValueError,
            "absolute HTTP",
        ):
            self.build(
                [row]
            )

    def test_snapshot_does_not_claim_truth_or_change_merit(
        self,
    ):
        result = self.build(
            [
                self.observation()
            ]
        )

        forbidden = {
            "truth",
            "true",
            "false",
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
                "snapshot_does_not_change_live_merit"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "later_outcomes_do_not_relabel_historical_snapshot"
            ]
        )


if __name__ == "__main__":
    unittest.main()
