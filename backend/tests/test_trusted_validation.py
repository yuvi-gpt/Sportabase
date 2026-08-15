import json
import sqlite3
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


from app.analysis.adjudication_state import (
    build_adjudication_state_revision,
)

from app.analysis.corpus_expansion import (
    build_validation_corpus_expansion,
)

from app.analysis.merit_release import (
    MERIT_LIVE_RELEASE_GATE_VERSION,
    build_merit_live_release_gate,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
    build_multi_evaluator_adjudication,
)

from app.analysis.trusted_validation import (
    TRUSTED_HOLDOUT_CASE_VERSION,
    TRUSTED_VALIDATION_BUNDLE_VERSION,
    build_trusted_holdout_cases,
    build_trusted_validation_bundle,
    validation_partition_for_claim,
)

from app.services.validation_dataset_runtime import (
    PERSISTED_VALIDATION_DATASET_RUNTIME_VERSION,
    build_persisted_validation_bundle,
)


VERIFIED_VALUES = {
    "source_role": "direct_source",
    "authority_class": "direct",
    "reliability_class": "established",
    "provenance_class": "primary",
    "stance": "supports",
    "independence_status": "established",
}


TRUSTED_BASIS = {
    "source_role": "canonical_resolution",
    "authority_class": "direct_authority_record",
    "reliability_class": "structured_fact",
    "provenance_class": "canonical_resolution",
    "stance": "direct_authority_record",
    "independence_status": "provenance_graph",
}


class TrustedValidationTests(
    unittest.TestCase
):
    def claim_ids(
        self,
        *,
        partition,
        count,
    ):
        output = []

        number = 1

        while len(
            output
        ) < count:
            candidate = (
                f"{partition}-claim-{number}"
            )

            if (
                validation_partition_for_claim(
                    candidate
                )
                == partition
            ):
                output.append(
                    candidate
                )

            number += 1

        return output

    def evaluator_run(
        self,
        *,
        claim_id,
        values,
        trusted,
        training_eligible=False,
        family=None,
        suffix=None,
        evidence_id=None,
        confidence=0.95,
    ):
        if trusted:
            family = (
                family
                or "machine_reference"
            )

            evaluator_id = (
                family
                + "-v1"
            )

            derivation_mode = (
                "machine_verified"
            )

            suffix = (
                suffix
                or "trusted"
            )

        else:
            family = (
                family
                or "semantic_model"
            )

            evaluator_id = (
                family
                + "-v1"
            )

            derivation_mode = (
                "model_assisted"
            )

            suffix = (
                suffix
                or "model"
            )

        judgments = []

        for field, value in values.items():
            judgments.append(
                {
                    "id": (
                        f"{claim_id}-{suffix}-"
                        f"{field}"
                    ),
                    "field": field,
                    "value": value,
                    "confidence": (
                        confidence
                    ),
                    "evaluator_id": (
                        evaluator_id
                    ),
                    "evaluator_family": (
                        family
                    ),
                    "basis_class": (
                        TRUSTED_BASIS[
                            field
                        ]
                        if trusted
                        else "model_inference"
                    ),
                    "evidence_ids": (
                        [
                            evidence_id
                        ]
                        if evidence_id
                        else [
                            f"{claim_id}-"
                            f"{suffix}-evidence"
                        ]
                    ),
                    "training_eligible": (
                        training_eligible
                    ),
                }
            )

        return {
            "run_id": (
                f"{claim_id}-{suffix}-run"
            ),
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                family
            ),
            "derivation_mode": (
                derivation_mode
            ),
            "judgments": judgments,
        }

    def pair(
        self,
        *,
        claim_id,
        baseline_values,
        verified_values,
        trusted_training,
        evidence_id,
        baseline_confidence=0.95,
    ):
        baseline = (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    self.evaluator_run(
                        claim_id=claim_id,
                        values=baseline_values,
                        trusted=False,
                        family=(
                            "semantic_model"
                        ),
                        suffix=(
                            "baseline-primary"
                        ),
                        confidence=(
                            baseline_confidence
                        ),
                    ),
                    self.evaluator_run(
                        claim_id=claim_id,
                        values=baseline_values,
                        trusted=False,
                        family=(
                            "semantic_peer"
                        ),
                        suffix=(
                            "baseline-peer"
                        ),
                        confidence=(
                            baseline_confidence
                        ),
                    ),
                ],
            )
        )

        previous = (
            build_adjudication_state_revision(
                adjudication=baseline,
                as_of=(
                    "2026-08-15T05:00:00Z"
                ),
                trigger_type=(
                    "initial_evaluation"
                ),
            )
        )

        trusted = (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    self.evaluator_run(
                        claim_id=claim_id,
                        values=verified_values,
                        trusted=True,
                        training_eligible=(
                            trusted_training
                        ),
                        evidence_id=(
                            evidence_id
                        ),
                        confidence=0.99,
                    )
                ],
            )
        )

        current = (
            build_adjudication_state_revision(
                adjudication=trusted,
                as_of=(
                    "2026-08-15T06:00:00Z"
                ),
                trigger_type=(
                    "evidence_verified"
                ),
                trigger_evidence_ids=[
                    evidence_id
                ],
                previous_revision=(
                    previous
                ),
            )
        )

        return (
            previous,
            current,
        )

    def test_machine_verified_training_false_does_not_train(
        self,
    ):
        claim_id = "training-safety"

        run = self.evaluator_run(
            claim_id=claim_id,
            values={
                "authority_class": "direct",
            },
            trusted=True,
            training_eligible=False,
            evidence_id="verified-1",
            confidence=0.99,
        )

        result = (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    run
                ],
            )
        )

        field = result[
            "fields"
        ][
            "authority_class"
        ]

        self.assertEqual(
            field[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertFalse(
            field[
                "reference_gate"
            ][
                "training_reference_allowed"
            ]
        )

        self.assertEqual(
            field[
                "reference_gate"
            ][
                "trusted_hard_reference_judgment_ids"
            ],
            [],
        )

    def test_machine_verified_validation_does_not_require_training(
        self,
    ):
        claim_id = (
            self.claim_ids(
                partition="holdout",
                count=1,
            )[0]
        )

        evidence_id = (
            claim_id
            + "-verified"
        )

        previous, current = (
            self.pair(
                claim_id=claim_id,
                baseline_values=(
                    VERIFIED_VALUES
                ),
                verified_values=(
                    VERIFIED_VALUES
                ),
                trusted_training=False,
                evidence_id=(
                    evidence_id
                ),
            )
        )

        cases = (
            build_trusted_holdout_cases(
                previous_revision=previous,
                current_revision=current,
                verified_evidence_ids=[
                    evidence_id
                ],
            )
        )

        self.assertEqual(
            len(cases),
            6,
        )

        self.assertEqual(
            {
                case[
                    "field"
                ]
                for case
                in cases
            },
            set(
                MULTI_EVALUATOR_FIELDS
            ),
        )

        self.assertTrue(
            all(
                case[
                    "validation_only"
                ]
                for case
                in cases
            )
        )

        self.assertTrue(
            all(
                case[
                    "version"
                ]
                == (
                    TRUSTED_HOLDOUT_CASE_VERSION
                )
                for case
                in cases
            )
        )

    def test_unverified_evidence_cannot_validate_holdout(
        self,
    ):
        claim_id = (
            self.claim_ids(
                partition="holdout",
                count=1,
            )[0]
        )

        evidence_id = (
            claim_id
            + "-verified"
        )

        previous, current = (
            self.pair(
                claim_id=claim_id,
                baseline_values=(
                    VERIFIED_VALUES
                ),
                verified_values=(
                    VERIFIED_VALUES
                ),
                trusted_training=False,
                evidence_id=(
                    evidence_id
                ),
            )
        )

        cases = (
            build_trusted_holdout_cases(
                previous_revision=previous,
                current_revision=current,
                verified_evidence_ids=[],
            )
        )

        self.assertEqual(
            cases,
            [],
        )

    def test_model_assisted_run_cannot_be_holdout_truth(
        self,
    ):
        claim_id = "model-only"

        evidence_id = (
            claim_id
            + "-verified"
        )

        baseline = (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    self.evaluator_run(
                        claim_id=claim_id,
                        values=(
                            VERIFIED_VALUES
                        ),
                        trusted=False,
                        suffix="baseline",
                    )
                ],
            )
        )

        previous = (
            build_adjudication_state_revision(
                adjudication=baseline,
                as_of=(
                    "2026-08-15T05:00:00Z"
                ),
                trigger_type=(
                    "initial_evaluation"
                ),
            )
        )

        current_adjudication = (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    self.evaluator_run(
                        claim_id=claim_id,
                        values=(
                            VERIFIED_VALUES
                        ),
                        trusted=False,
                        suffix="later-model",
                        evidence_id=(
                            evidence_id
                        ),
                        confidence=0.99,
                    )
                ],
            )
        )

        current = (
            build_adjudication_state_revision(
                adjudication=(
                    current_adjudication
                ),
                as_of=(
                    "2026-08-15T06:00:00Z"
                ),
                trigger_type=(
                    "evidence_verified"
                ),
                trigger_evidence_ids=[
                    evidence_id
                ],
                previous_revision=(
                    previous
                ),
            )
        )

        cases = (
            build_trusted_holdout_cases(
                previous_revision=previous,
                current_revision=current,
                verified_evidence_ids=[
                    evidence_id
                ],
            )
        )

        self.assertEqual(
            cases,
            [],
        )

    def test_partition_is_stable_and_disjoint(
        self,
    ):
        ids = [
            f"claim-{number}"
            for number
            in range(
                1,
                101,
            )
        ]

        first = {
            claim_id: (
                validation_partition_for_claim(
                    claim_id
                )
            )
            for claim_id
            in ids
        }

        second = {
            claim_id: (
                validation_partition_for_claim(
                    claim_id
                )
            )
            for claim_id
            in reversed(
                ids
            )
        }

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            set(
                first.values()
            ),
            {
                "calibration",
                "holdout",
            },
        )

    def complete_corpus(
        self,
    ):
        sports = [
            "american_football",
            "baseball",
            "basketball",
            "cricket",
            "football",
            "ice_hockey",
            "motorsport",
            "tennis",
        ]

        records = [
            {
                "id": (
                    "record-"
                    + sport
                ),
                "origin_type": (
                    "external_dataset"
                ),
                "data_family": (
                    "structured_sports_data"
                ),
                "dataset_name": (
                    sport
                    + "-validation"
                ),
                "external_record_id": (
                    "record-1"
                ),
                "sport_key": sport,
                "payload_hash": (
                    "hash-"
                    + sport
                ),
                "ingested_at": (
                    "2026-08-15T06:00:00+00:00"
                ),
            }
            for sport
            in sports
        ]

        return (
            build_validation_corpus_expansion(
                records=records,
                target_records_per_sport=1,
            )
        )

    def test_revision_derived_bundle_can_reach_gate(
        self,
    ):
        calibration_claims = (
            self.claim_ids(
                partition="calibration",
                count=5,
            )
        )

        holdout_claims = (
            self.claim_ids(
                partition="holdout",
                count=5,
            )
        )

        revisions = []

        verified_evidence_ids = []

        # Five correct-but-overconfident authority
        # predictions establish a conservative shadow
        # calibration target. With Laplace smoothing,
        # 5/5 confirmed cases map 0.95 to 6/7 ~= 0.857,
        # which remains above the auto_silver threshold.
        for claim_id in calibration_claims:
            evidence_id = (
                claim_id
                + "-verified"
            )

            verified_evidence_ids.append(
                evidence_id
            )

            previous, current = (
                self.pair(
                    claim_id=claim_id,
                    baseline_values={
                        "authority_class": (
                            "direct"
                        ),
                    },
                    verified_values={
                        "authority_class": (
                            "direct"
                        ),
                    },
                    trusted_training=True,
                    evidence_id=(
                        evidence_id
                    ),
                )
            )

            revisions.extend(
                [
                    previous,
                    current,
                ]
            )

        # Holdout is assigned before outcomes are
        # examined. It covers all six fields.
        # Under calibration v2, perfect calibration
        # evidence moves a 0.95 authority confidence
        # upward. The synthetic holdout therefore
        # keeps the authority value correct so the
        # higher confidence must improve holdout
        # calibration without changing the decision.
        for claim_id in holdout_claims:
            evidence_id = (
                claim_id
                + "-verified"
            )

            verified_evidence_ids.append(
                evidence_id
            )

            baseline_values = dict(
                VERIFIED_VALUES
            )

            previous, current = (
                self.pair(
                    claim_id=claim_id,
                    baseline_values=(
                        baseline_values
                    ),
                    verified_values=(
                        VERIFIED_VALUES
                    ),
                    trusted_training=False,
                    evidence_id=(
                        evidence_id
                    ),
                )
            )

            revisions.extend(
                [
                    previous,
                    current,
                ]
            )

        bundle = (
            build_trusted_validation_bundle(
                revisions=revisions,
                verified_evidence_ids=(
                    verified_evidence_ids
                ),
            )
        )

        self.assertEqual(
            bundle[
                "version"
            ],
            TRUSTED_VALIDATION_BUNDLE_VERSION,
        )

        self.assertEqual(
            bundle[
                "summary"
            ][
                "calibration_claim_count"
            ],
            5,
        )

        self.assertEqual(
            bundle[
                "summary"
            ][
                "shadow_ready_profile_count"
            ],
            2,
        )

        self.assertEqual(
            bundle[
                "summary"
            ][
                "holdout_claim_count"
            ],
            5,
        )

        self.assertEqual(
            bundle[
                "summary"
            ][
                "missing_holdout_fields"
            ],
            [],
        )

        self.assertGreater(
            bundle[
                "summary"
            ][
                "shadow_adjustment_count"
            ],
            0,
        )

        calibration_ids = {
            case[
                "claim_id"
            ]
            for case
            in bundle[
                "calibration"
            ][
                "cases"
            ]
        }

        holdout_ids = {
            case[
                "claim_id"
            ]
            for case
            in bundle[
                "holdout_cases"
            ]
        }

        self.assertFalse(
            calibration_ids
            & holdout_ids
        )

        gate = (
            build_merit_live_release_gate(
                request_live=True,
                calibration=(
                    bundle[
                        "calibration"
                    ]
                ),
                holdout_cases=(
                    bundle[
                        "holdout_cases"
                    ]
                ),
                shadow_results=(
                    bundle[
                        "shadow_results"
                    ]
                ),
                corpus_expansion=(
                    self.complete_corpus()
                ),
            )
        )

        # This is a synthetic reachability test,
        # not a production authorization.
        self.assertEqual(
            gate[
                "version"
            ],
            MERIT_LIVE_RELEASE_GATE_VERSION,
        )

        self.assertEqual(
            gate[
                "version"
            ],
            "merit-live-release-gate-v4",
        )

        self.assertEqual(
            gate[
                "blockers"
            ],
            [],
        )

        self.assertTrue(
            gate[
                "live_merit_authorized"
            ]
        )

    def test_persisted_runtime_reads_without_writing(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            path = (
                Path(temp)
                / "validation.db"
            )

            connection = sqlite3.connect(
                str(path)
            )

            try:
                connection.execute(
                    """
                    CREATE TABLE
                    adjudication_state_revisions (
                        id TEXT PRIMARY KEY,
                        claim_id TEXT NOT NULL,
                        as_of TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        revision_json TEXT NOT NULL
                    )
                    """
                )

                connection.execute(
                    """
                    CREATE TABLE
                    evidence_records (
                        id TEXT PRIMARY KEY,
                        verification_status TEXT NOT NULL
                    )
                    """
                )

                connection.commit()

            finally:
                connection.close()

            def factory():
                conn = sqlite3.connect(
                    str(path)
                )

                conn.row_factory = (
                    sqlite3.Row
                )

                return conn

            result = (
                build_persisted_validation_bundle(
                    connection_factory=(
                        factory
                    )
                )
            )

            self.assertEqual(
                result[
                    "version"
                ],
                (
                    PERSISTED_VALIDATION_DATASET_RUNTIME_VERSION
                ),
            )

            self.assertEqual(
                result[
                    "summary"
                ][
                    "persisted_revision_count"
                ],
                0,
            )

            self.assertEqual(
                result[
                    "summary"
                ][
                    "verified_evidence_count"
                ],
                0,
            )

            self.assertEqual(
                result[
                    "bundle"
                ][
                    "holdout_cases"
                ],
                [],
            )


if __name__ == "__main__":
    unittest.main()
