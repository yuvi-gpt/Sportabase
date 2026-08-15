import copy
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

from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)

from app.db.connection import (
    connect_database,
)

from app.db.migrations import (
    initialize_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.adjudication_history import (
    persist_adjudication_state_revision,
)

from app.intelligence.correction_memory_history import (
    load_automatic_memory_candidate,
    process_automatic_correction_memory,
)


class AutomaticCorrectionMemoryHistoryTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(
                self.temp_dir.name
            )
            / "correction-memory.db"
        )

        initialize_database(
            self.connection_factory,
            SCHEMA,
        )

        conn = self.connection_factory()

        try:
            for claim_id in (
                "claim-1",
                "claim-2",
            ):
                conn.execute(
                    """
                    INSERT INTO intelligence_claims (
                      id,
                      canonical_key,
                      subject_key,
                      canonical_text,
                      claim_type,
                      first_seen_at,
                      last_seen_at,
                      metadata_json
                    )
                    VALUES (
                      ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        claim_id,
                        claim_id,
                        (
                            f"subject-{claim_id}"
                        ),
                        (
                            f"Canonical {claim_id}"
                        ),
                        "assertion",
                        (
                            "2026-08-15T05:00:00+00:00"
                        ),
                        (
                            "2026-08-15T05:00:00+00:00"
                        ),
                        "{}",
                    ),
                )

            conn.commit()

        finally:
            conn.close()

    def tearDown(
        self,
    ):
        self.temp_dir.cleanup()

    def connection_factory(
        self,
    ):
        return connect_database(
            self.db_path
        )

    def count(
        self,
        table,
    ):
        conn = self.connection_factory()

        try:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            )

        finally:
            conn.close()

    def judgment(
        self,
        *,
        claim_id,
        value,
        trusted,
    ):
        if trusted:
            evaluator_id = (
                "authority-record-v1"
            )
            evaluator_family = (
                "authority_record"
            )
            derivation_mode = (
                "machine_verified"
            )
            basis = (
                "direct_authority_record"
            )
            training = True
            suffix = "trusted"
        else:
            evaluator_id = (
                "semantic-v1"
            )
            evaluator_family = (
                "semantic_model"
            )
            derivation_mode = (
                "model_assisted"
            )
            basis = (
                "direct_authority_record"
            )
            training = False
            suffix = "model"

        return {
            "run_id": (
                f"{claim_id}-{suffix}-run"
            ),
            "evaluator_id": evaluator_id,
            "evaluator_family": (
                evaluator_family
            ),
            "derivation_mode": (
                derivation_mode
            ),
            "judgments": [
                {
                    "id": (
                        f"{claim_id}-{suffix}"
                    ),
                    "field": (
                        "authority_class"
                    ),
                    "value": value,
                    "confidence": 0.99,
                    "evaluator_id": (
                        evaluator_id
                    ),
                    "evaluator_family": (
                        evaluator_family
                    ),
                    "basis_class": basis,
                    "evidence_ids": [
                        (
                            f"{claim_id}-"
                            f"{suffix}-evidence"
                        )
                    ],
                    "training_eligible": (
                        training
                    ),
                }
            ],
        }

    def adjudication(
        self,
        *,
        claim_id,
        value=None,
        trusted=False,
    ):
        runs = []

        if value is not None:
            runs = [
                self.judgment(
                    claim_id=claim_id,
                    value=value,
                    trusted=trusted,
                )
            ]

        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=runs,
            )
        )

    def build_pair(
        self,
        *,
        claim_id,
        previous_value="indirect",
        current_value="direct",
        previous_empty=False,
    ):
        previous_adjudication = (
            self.adjudication(
                claim_id=claim_id,
            )
            if previous_empty
            else self.adjudication(
                claim_id=claim_id,
                value=previous_value,
                trusted=False,
            )
        )

        current_adjudication = (
            self.adjudication(
                claim_id=claim_id,
                value=current_value,
                trusted=True,
            )
        )

        previous = (
            build_adjudication_state_revision(
                adjudication=(
                    previous_adjudication
                ),
                as_of=(
                    "2026-08-15T05:00:00Z"
                ),
                trigger_type=(
                    "initial_evaluation"
                ),
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
                    "evaluator_refresh"
                ),
                previous_revision=(
                    previous
                ),
            )
        )

        return (
            previous,
            current,
        )

    def persist_pair(
        self,
        *,
        claim_id,
        previous_value="indirect",
        current_value="direct",
        previous_empty=False,
    ):
        previous, current = (
            self.build_pair(
                claim_id=claim_id,
                previous_value=(
                    previous_value
                ),
                current_value=(
                    current_value
                ),
                previous_empty=(
                    previous_empty
                ),
            )
        )

        persist_adjudication_state_revision(
            revision=previous,
            recorded_at=(
                "2026-08-15T05:01:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        persist_adjudication_state_revision(
            revision=current,
            recorded_at=(
                "2026-08-15T06:01:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        return (
            previous,
            current,
        )

    def process(
        self,
        previous,
        current,
    ):
        return (
            process_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
                recorded_at=(
                    "2026-08-15T06:02:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

    def test_schema_tables_exist(
        self,
    ):
        conn = self.connection_factory()

        try:
            names = {
                row[
                    "name"
                ]
                for row
                in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

        finally:
            conn.close()

        self.assertIn(
            "automatic_correction_events",
            names,
        )

        self.assertIn(
            "automatic_memory_candidates",
            names,
        )

    def test_genuine_correction_persists_case_memory(
        self,
    ):
        previous, current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        result = self.process(
            previous,
            current,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "persisted",
        )

        self.assertEqual(
            self.count(
                "automatic_correction_events"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "automatic_memory_candidates"
            ),
            1,
        )

        candidate = result[
            "memory"
        ][
            "memory_candidates"
        ][0]

        self.assertEqual(
            candidate[
                "status"
            ],
            "case_memory",
        )

        self.assertEqual(
            candidate[
                "support_count"
            ],
            1,
        )

    def test_replay_is_idempotent(
        self,
    ):
        previous, current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        first = self.process(
            previous,
            current,
        )

        second = self.process(
            previous,
            current,
        )

        self.assertEqual(
            second[
                "status"
            ],
            "replayed",
        )

        self.assertEqual(
            self.count(
                "automatic_correction_events"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "automatic_memory_candidates"
            ),
            1,
        )

        self.assertEqual(
            first[
                "memory"
            ][
                "memory_candidates"
            ][0][
                "id"
            ],
            second[
                "memory"
            ][
                "memory_candidates"
            ][0][
                "id"
            ],
        )

    def test_second_distinct_claim_promotes_pattern_candidate(
        self,
    ):
        first_previous, first_current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        first = self.process(
            first_previous,
            first_current,
        )

        second_previous, second_current = (
            self.persist_pair(
                claim_id="claim-2"
            )
        )

        second = self.process(
            second_previous,
            second_current,
        )

        candidate = second[
            "memory"
        ][
            "memory_candidates"
        ][0]

        self.assertEqual(
            candidate[
                "status"
            ],
            "pattern_candidate",
        )

        self.assertEqual(
            candidate[
                "support_count"
            ],
            2,
        )

        self.assertEqual(
            candidate[
                "supporting_claim_ids"
            ],
            [
                "claim-1",
                "claim-2",
            ],
        )

        loaded = (
            load_automatic_memory_candidate(
                candidate_id=(
                    candidate[
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            loaded[
                "status"
            ],
            "pattern_candidate",
        )

        self.assertEqual(
            first[
                "memory"
            ][
                "memory_candidates"
            ][0][
                "id"
            ],
            candidate[
                "id"
            ],
        )

    def test_same_claim_replay_does_not_inflate_support(
        self,
    ):
        previous, current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        self.process(
            previous,
            current,
        )

        result = self.process(
            previous,
            current,
        )

        candidate = result[
            "memory"
        ][
            "memory_candidates"
        ][0]

        self.assertEqual(
            candidate[
                "support_count"
            ],
            1,
        )

        self.assertEqual(
            candidate[
                "supporting_claim_ids"
            ],
            [
                "claim-1"
            ],
        )

    def test_resolution_without_previous_value_is_not_correction(
        self,
    ):
        previous, current = (
            self.persist_pair(
                claim_id="claim-1",
                previous_empty=True,
            )
        )

        result = self.process(
            previous,
            current,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "no_correction",
        )

        self.assertEqual(
            self.count(
                "automatic_correction_events"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "automatic_memory_candidates"
            ),
            0,
        )

    def test_unpersisted_revision_pair_is_rejected(
        self,
    ):
        previous, current = (
            self.build_pair(
                claim_id="claim-1"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be persisted",
        ):
            self.process(
                previous,
                current,
            )

    def test_tampered_revision_is_rejected(
        self,
    ):
        previous, current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        tampered = copy.deepcopy(
            current
        )

        tampered[
            "fields"
        ][
            "authority_class"
        ][
            "state"
        ][
            "value"
        ] = "tampered"

        with self.assertRaisesRegex(
            ValueError,
            "does not match persisted history",
        ):
            self.process(
                previous,
                tampered,
            )

    def test_candidate_never_becomes_active_global_rule(
        self,
    ):
        first_previous, first_current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        self.process(
            first_previous,
            first_current,
        )

        second_previous, second_current = (
            self.persist_pair(
                claim_id="claim-2"
            )
        )

        result = self.process(
            second_previous,
            second_current,
        )

        candidate = result[
            "memory"
        ][
            "memory_candidates"
        ][0]

        self.assertEqual(
            candidate[
                "status"
            ],
            "pattern_candidate",
        )

        self.assertFalse(
            candidate[
                "eligible_for_automatic_global_rule"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "automatic_global_rule_promotion_forbidden"
            ]
        )

    def test_correction_memory_does_not_touch_live_merit(
        self,
    ):
        previous, current = (
            self.persist_pair(
                claim_id="claim-1"
            )
        )

        self.process(
            previous,
            current,
        )

        self.assertEqual(
            self.count(
                "analysis_snapshots"
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
