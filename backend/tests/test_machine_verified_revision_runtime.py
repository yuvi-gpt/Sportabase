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


from app import main

from app.analysis.trusted_validation import (
    validation_partition_for_claim,
)

from app.intelligence.adjudication_history import (
    re_adjudicate_claim,
)

from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
)

from app.intelligence.evidence import (
    record_evidence,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
    persist_machine_verified_reference_revision,
)

from app.services.validation_dataset_runtime import (
    build_persisted_validation_bundle,
)


class MachineVerifiedRevisionRuntimeTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.original_db_path = (
            main.DB_PATH
        )

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(
                self.temp_dir.name
            )
            / "machine-verified-runtime.db"
        )

        main.init_db()

    def tearDown(
        self,
    ):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    @staticmethod
    def normalize_url(
        value,
    ):
        return str(
            value or ""
        ).strip().lower()

    def claim_for_partition(
        self,
        partition,
    ):
        for index in range(
            10000
        ):
            canonical_key = (
                f"machine-runtime|"
                f"{partition}|"
                f"{index}"
            )

            claim_id = (
                claim_id_for_canonical_key(
                    canonical_key
                )
            )

            if (
                validation_partition_for_claim(
                    claim_id
                )
                != partition
            ):
                continue

            return (
                main.upsert_intelligence_claim(
                    canonical_key=(
                        canonical_key
                    ),
                    subject_key=(
                        "player-a|team-b"
                    ),
                    canonical_text=(
                        "Player A will join Team B."
                    ),
                    claim_type=(
                        "headline_assertion"
                    ),
                    seen_at=(
                        "2026-08-15T09:00:00Z"
                    ),
                )
            )

        raise AssertionError(
            "Unable to find claim partition."
        )

    def seed_model_baseline(
        self,
        partition,
        *,
        model_value="none",
        confidence=0.90,
    ):
        claim = (
            self.claim_for_partition(
                partition
            )
        )

        evidence = record_evidence(
            evidence_type=(
                "model_assisted_snapshot"
            ),
            subject_key=(
                claim[
                    "subject_key"
                ]
            ),
            observed_at=(
                "2026-08-15T09:30:00Z"
            ),
            claim_summary=(
                claim[
                    "canonical_text"
                ]
            ),
            reference_key=(
                "baseline:"
                + claim[
                    "id"
                ]
            ),
            verification_status=(
                "unverified"
            ),
            recorded_at=(
                "2026-08-15T09:31:00Z"
            ),
            metadata={
                "model_assisted": True,
                "truth_established": False,
            },
            normalize_url=(
                self.normalize_url
            ),
            connection_factory=(
                main.db_conn
            ),
        )[
            "evidence"
        ]

        record_claim_link(
            claim_id=(
                claim[
                    "id"
                ]
            ),
            evidence_id=(
                evidence[
                    "id"
                ]
            ),
            relationship_type=(
                "baseline_semantics"
            ),
            confidence=confidence,
            observed_at=(
                "2026-08-15T09:30:00Z"
            ),
            recorded_at=(
                "2026-08-15T09:31:00Z"
            ),
            metadata={
                "model_assisted": True,
            },
            connection_factory=(
                main.db_conn
            ),
        )

        run = {
            "run_id": (
                "model-run-"
                + claim[
                    "id"
                ]
            ),
            "evaluator_id": (
                "semantic-model-v1"
            ),
            "evaluator_family": (
                "semantic_model"
            ),
            "derivation_mode": (
                "model_assisted"
            ),
            "judgments": [
                {
                    "id": (
                        "model-authority-"
                        + claim[
                            "id"
                        ]
                    ),
                    "field": (
                        "authority_class"
                    ),
                    "value": (
                        model_value
                    ),
                    "confidence": (
                        confidence
                    ),
                    "evaluator_id": (
                        "semantic-model-v1"
                    ),
                    "evaluator_family": (
                        "semantic_model"
                    ),
                    "basis_class": (
                        "model_inference"
                    ),
                    "evidence_ids": [
                        evidence[
                            "id"
                        ]
                    ],
                    "training_eligible": False,
                },
            ],
        }

        baseline = (
            re_adjudicate_claim(
                claim_id=(
                    claim[
                        "id"
                    ]
                ),
                evaluator_runs=[
                    run
                ],
                as_of=(
                    "2026-08-15T10:00:00Z"
                ),
                trigger_type=(
                    "evidence_added"
                ),
                trigger_evidence_ids=[
                    evidence[
                        "id"
                    ]
                ],
                recorded_at=(
                    "2026-08-15T10:01:00Z"
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

        return (
            claim,
            baseline[
                "revision"
            ],
        )

    def verification(
        self,
        claim,
        *,
        basis_class=(
            "direct_authority_record"
        ),
        confidence=0.99,
    ):
        return (
            persist_machine_verified_reference_revision(
                claim_id=(
                    claim[
                        "id"
                    ]
                ),
                verification_evidence={
                    "observed_at": (
                        "2026-08-15T11:00:00Z"
                    ),
                    "reference_key": (
                        "verified:"
                        + claim[
                            "id"
                        ]
                    ),
                    "claim_summary": (
                        "Structured authority record "
                        "verifies source authority."
                    ),
                    "metadata": {
                        "fixture": (
                            "machine-verification"
                        ),
                    },
                },
                field_verifications=[
                    {
                        "field": (
                            "authority_class"
                        ),
                        "value": "direct",
                        "confidence": (
                            confidence
                        ),
                        "basis_class": (
                            basis_class
                        ),
                    },
                ],
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    main.db_conn
                ),
                recorded_at=(
                    "2026-08-15T11:01:00Z"
                ),
            )
        )

    def count(
        self,
        table,
    ):
        conn = main.db_conn()

        try:
            return int(
                conn.execute(
                    (
                        "SELECT COUNT(*) "
                        f"FROM {table}"
                    )
                ).fetchone()[0]
            )

        finally:
            conn.close()

    def test_calibration_partition_creates_training_eligible_hard_reference_and_case(
        self,
    ):
        claim, baseline = (
            self.seed_model_baseline(
                "calibration",
                model_value="none",
                confidence=0.90,
            )
        )

        result = (
            self.verification(
                claim
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            "persisted",
        )

        self.assertEqual(
            result[
                "partition"
            ],
            "calibration",
        )

        revision = (
            result[
                "revision"
            ]
        )

        self.assertEqual(
            revision[
                "previous_revision_id"
            ],
            baseline[
                "revision_id"
            ],
        )

        self.assertEqual(
            revision[
                "trigger"
            ][
                "type"
            ],
            "evidence_verified",
        )

        authority = (
            revision[
                "fields"
            ][
                "authority_class"
            ]
        )

        self.assertEqual(
            authority[
                "state"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            authority[
                "state"
            ][
                "value"
            ],
            "direct",
        )

        self.assertTrue(
            authority[
                "state"
            ][
                "training_reference_allowed"
            ]
        )

        machine = [
            run
            for run
            in revision[
                "adjudication"
            ][
                "evaluators"
            ]
            if (
                run[
                    "derivation_mode"
                ]
                == "machine_verified"
            )
        ]

        self.assertEqual(
            len(
                machine
            ),
            1,
        )

        self.assertTrue(
            machine[0][
                "judgments"
            ][0][
                "training_eligible"
            ]
        )

        model_values = [
            judgment[
                "value"
            ]
            for run
            in revision[
                "adjudication"
            ][
                "evaluators"
            ]
            if (
                run[
                    "evaluator_family"
                ]
                == "semantic_model"
            )
            for judgment
            in run[
                "judgments"
            ]
        ]

        self.assertEqual(
            model_values,
            [
                "none",
            ],
        )

        dataset = (
            build_persisted_validation_bundle(
                connection_factory=(
                    main.db_conn
                )
            )
        )

        summary = (
            dataset[
                "summary"
            ]
        )

        self.assertEqual(
            summary[
                "calibration_case_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "calibration_claim_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "holdout_case_count"
            ],
            0,
        )

    def test_holdout_partition_verifies_without_training(
        self,
    ):
        claim, baseline = (
            self.seed_model_baseline(
                "holdout",
                model_value="none",
                confidence=0.90,
            )
        )

        result = (
            self.verification(
                claim
            )
        )

        self.assertEqual(
            result[
                "partition"
            ],
            "holdout",
        )

        revision = (
            result[
                "revision"
            ]
        )

        authority = (
            revision[
                "fields"
            ][
                "authority_class"
            ]
        )

        self.assertEqual(
            authority[
                "state"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertFalse(
            authority[
                "state"
            ][
                "training_reference_allowed"
            ]
        )

        machine = [
            run
            for run
            in revision[
                "adjudication"
            ][
                "evaluators"
            ]
            if (
                run[
                    "derivation_mode"
                ]
                == "machine_verified"
            )
        ]

        self.assertFalse(
            machine[0][
                "judgments"
            ][0][
                "training_eligible"
            ]
        )

        dataset = (
            build_persisted_validation_bundle(
                connection_factory=(
                    main.db_conn
                )
            )
        )

        summary = (
            dataset[
                "summary"
            ]
        )

        self.assertEqual(
            summary[
                "calibration_case_count"
            ],
            0,
        )

        self.assertEqual(
            summary[
                "holdout_case_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "holdout_claim_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "holdout_field_coverage"
            ],
            [
                "authority_class",
            ],
        )

    def test_exact_replay_is_idempotent(
        self,
    ):
        claim, baseline = (
            self.seed_model_baseline(
                "calibration"
            )
        )

        first = (
            self.verification(
                claim
            )
        )

        second = (
            self.verification(
                claim
            )
        )

        self.assertEqual(
            first[
                "status"
            ],
            "persisted",
        )

        self.assertEqual(
            second[
                "status"
            ],
            "replayed",
        )

        self.assertEqual(
            first[
                "revision"
            ][
                "revision_id"
            ],
            second[
                "revision"
            ][
                "revision_id"
            ],
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            2,
        )

    def test_disallowed_basis_fails_before_verified_writes(
        self,
    ):
        claim, baseline = (
            self.seed_model_baseline(
                "calibration"
            )
        )

        before_evidence = (
            self.count(
                "evidence_records"
            )
        )

        before_links = (
            self.count(
                "claim_links"
            )
        )

        before_revisions = (
            self.count(
                "adjudication_state_revisions"
            )
        )

        with self.assertRaises(
            ValueError
        ):
            self.verification(
                claim,
                basis_class=(
                    "structured_fact"
                ),
            )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            before_evidence,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            before_links,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            before_revisions,
        )

    def test_caller_cannot_launder_training_eligibility(
        self,
    ):
        claim, baseline = (
            self.seed_model_baseline(
                "holdout"
            )
        )

        with self.assertRaises(
            ValueError
        ):
            (
                persist_machine_verified_reference_revision(
                    claim_id=(
                        claim[
                            "id"
                        ]
                    ),
                    verification_evidence={
                        "observed_at": (
                            "2026-08-15T11:00:00Z"
                        ),
                        "reference_key": (
                            "verified:"
                            + claim[
                                "id"
                            ]
                        ),
                    },
                    field_verifications=[
                        {
                            "field": (
                                "authority_class"
                            ),
                            "value": "direct",
                            "confidence": 0.99,
                            "basis_class": (
                                "direct_authority_record"
                            ),
                            "training_eligible": True,
                        },
                    ],
                    normalize_url=(
                        self.normalize_url
                    ),
                    connection_factory=(
                        main.db_conn
                    ),
                )
            )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            1,
        )

    def test_verification_must_be_later_than_baseline(
        self,
    ):
        claim, baseline = (
            self.seed_model_baseline(
                "calibration"
            )
        )

        with self.assertRaises(
            ValueError
        ):
            (
                persist_machine_verified_reference_revision(
                    claim_id=(
                        claim[
                            "id"
                        ]
                    ),
                    verification_evidence={
                        "observed_at": (
                            "2026-08-15T09:59:00Z"
                        ),
                        "reference_key": (
                            "verified-too-early:"
                            + claim[
                                "id"
                            ]
                        ),
                    },
                    field_verifications=[
                        {
                            "field": (
                                "authority_class"
                            ),
                            "value": "direct",
                            "confidence": 0.99,
                            "basis_class": (
                                "direct_authority_record"
                            ),
                        },
                    ],
                    normalize_url=(
                        self.normalize_url
                    ),
                    connection_factory=(
                        main.db_conn
                    ),
                )
            )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()