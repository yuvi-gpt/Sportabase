import tempfile
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


from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)

from app.analysis.review_queue import (
    build_adjudication_review_queue,
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

from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)

from app.intelligence.evidence import (
    record_evidence,
)

from app.intelligence.reviews import (
    list_review_queue_items,
    record_review_queue_item,
    resolve_review_queue_item,
)


class ReviewQueuePersistenceTests(
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
            / "review-queue.db"
        )

        initialize_database(
            self.connection_factory,
            SCHEMA,
        )

        self.claim = (
            upsert_intelligence_claim(
                canonical_key=(
                    "transfer|player-a|"
                    "team-a|join"
                ),
                subject_key=(
                    "transfer|player-a|team-a"
                ),
                canonical_text=(
                    "Player A will join Team A."
                ),
                seen_at=(
                    "2026-08-15T04:00:00Z"
                ),
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        evidence_result = (
            record_evidence(
                evidence_type=(
                    "claim_evidence_snapshot"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-15T04:01:00Z"
                ),
                reference_key=(
                    "snapshot-1:content-1"
                ),
                verification_status=(
                    "unverified"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.evidence = (
            evidence_result[
                "evidence"
            ]
        )

        record_claim_link(
            claim_id=(
                self.claim[
                    "id"
                ]
            ),
            evidence_id=(
                self.evidence[
                    "id"
                ]
            ),
            relationship_type=(
                "aligned_to"
            ),
            observed_at=(
                "2026-08-15T04:01:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

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

    @staticmethod
    def normalize_url(
        value,
    ):
        return str(
            value or ""
        ).strip()

    def judgment(
        self,
        *,
        row_id="model-stance",
        value="supports",
        confidence=0.95,
        evaluator_id="model",
        evaluator_family="semantic_model",
    ):
        return {
            "id": row_id,
            "field": "stance",
            "value": value,
            "confidence": confidence,
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "basis_class": (
                "model_inference"
            ),
            "evidence_ids": [
                self.evidence[
                    "id"
                ]
            ],
            "training_eligible": False,
        }

    def unresolved_packet(
        self,
        *,
        confidence=0.95,
    ):
        result = (
            build_multi_evaluator_adjudication(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                evaluator_runs=[
                    {
                        "run_id": "model-run",
                        "evaluator_id": "model",
                        "evaluator_family": (
                            "semantic_model"
                        ),
                        "derivation_mode": (
                            "model_assisted"
                        ),
                        "judgments": [
                            self.judgment(
                                confidence=(
                                    confidence
                                )
                            )
                        ],
                    }
                ],
            )
        )

        return (
            build_adjudication_review_queue(
                adjudication=result,
                evidence_id=(
                    self.evidence[
                        "id"
                    ]
                ),
            )
        )

    def contested_packet(
        self,
    ):
        result = (
            build_multi_evaluator_adjudication(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                evaluator_runs=[
                    {
                        "run_id": "model-run",
                        "evaluator_id": "model",
                        "evaluator_family": (
                            "semantic_model"
                        ),
                        "derivation_mode": (
                            "model_assisted"
                        ),
                        "judgments": [
                            self.judgment()
                        ],
                    },
                    {
                        "run_id": "graph-run",
                        "evaluator_id": "graph",
                        "evaluator_family": (
                            "provenance_graph"
                        ),
                        "derivation_mode": (
                            "machine_verified"
                        ),
                        "judgments": [
                            {
                                **self.judgment(
                                    row_id=(
                                        "graph-stance"
                                    ),
                                    value=(
                                        "contradicts"
                                    ),
                                    confidence=0.96,
                                    evaluator_id="graph",
                                    evaluator_family=(
                                        "provenance_graph"
                                    ),
                                ),
                                "basis_class": (
                                    "provenance_graph"
                                ),
                            }
                        ],
                    },
                ],
            )
        )

        return (
            build_adjudication_review_queue(
                adjudication=result,
                evidence_id=(
                    self.evidence[
                        "id"
                    ]
                ),
            )
        )

    def test_schema_contains_review_queue_table(
        self,
    ):
        conn = self.connection_factory()

        try:
            row = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'review_queue_items'
                """
            ).fetchone()

        finally:
            conn.close()

        self.assertIsNotNone(
            row
        )

    def test_review_item_persists_as_pending(
        self,
    ):
        item = (
            self.unresolved_packet()[
                "items"
            ][0]
        )

        result = (
            record_review_queue_item(
                item=item,
                recorded_at=(
                    "2026-08-15T04:10:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertTrue(
            result[
                "created"
            ]
        )

        self.assertEqual(
            result[
                "review"
            ][
                "status"
            ],
            "pending",
        )

        self.assertEqual(
            result[
                "review"
            ][
                "claim_id"
            ],
            self.claim[
                "id"
            ],
        )

    def test_exact_replay_is_idempotent(
        self,
    ):
        item = (
            self.unresolved_packet()[
                "items"
            ][0]
        )

        first = (
            record_review_queue_item(
                item=item,
                recorded_at=(
                    "2026-08-15T04:10:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        second = (
            record_review_queue_item(
                item=item,
                recorded_at=(
                    "2026-08-15T04:10:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertTrue(
            first[
                "created"
            ]
        )

        self.assertFalse(
            second[
                "created"
            ]
        )

        self.assertEqual(
            first[
                "review"
            ][
                "id"
            ],
            second[
                "review"
            ][
                "id"
            ],
        )

    def test_unlinked_evidence_is_rejected(
        self,
    ):
        second_evidence = (
            record_evidence(
                evidence_type=(
                    "claim_evidence_snapshot"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-15T04:02:00Z"
                ),
                reference_key=(
                    "snapshot-2:content-2"
                ),
                verification_status=(
                    "unverified"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "evidence"
            ]
        )

        packet = (
            build_adjudication_review_queue(
                adjudication=(
                    build_multi_evaluator_adjudication(
                        claim_id=(
                            self.claim[
                                "id"
                            ]
                        ),
                        evaluator_runs=[
                            {
                                "run_id": (
                                    "model-run"
                                ),
                                "evaluator_id": (
                                    "model"
                                ),
                                "evaluator_family": (
                                    "semantic_model"
                                ),
                                "derivation_mode": (
                                    "model_assisted"
                                ),
                                "judgments": [
                                    self.judgment()
                                ],
                            }
                        ],
                    )
                ),
                evidence_id=(
                    second_evidence[
                        "id"
                    ]
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "not linked",
        ):
            record_review_queue_item(
                item=(
                    packet[
                        "items"
                    ][0]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

    def test_queue_lists_highest_priority_first(
        self,
    ):
        unresolved = (
            self.unresolved_packet()[
                "items"
            ][0]
        )

        contested = (
            self.contested_packet()[
                "items"
            ][0]
        )

        record_review_queue_item(
            item=unresolved,
            recorded_at=(
                "2026-08-15T04:10:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        record_review_queue_item(
            item=contested,
            recorded_at=(
                "2026-08-15T04:11:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        rows = list_review_queue_items(
            connection_factory=(
                self.connection_factory
            )
        )

        self.assertEqual(
            [
                row[
                    "queue_reason"
                ]
                for row
                in rows
            ],
            [
                "contested",
                "unresolved",
            ],
        )

    def test_resolution_outputs_existing_correction_contract(
        self,
    ):
        item = (
            self.unresolved_packet()[
                "items"
            ][0]
        )

        review = (
            record_review_queue_item(
                item=item,
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "review"
            ]
        )

        result = (
            resolve_review_queue_item(
                review_id=(
                    review[
                        "id"
                    ]
                ),
                value="supports",
                reason=(
                    "Reviewer confirmed "
                    "the source supports "
                    "this exact claim."
                ),
                corrected_by="Yuvraj",
                corrected_at=(
                    "2026-08-15T10:15:00+05:30"
                ),
                scope="case_only",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "review"
            ][
                "status"
            ],
            "resolved",
        )

        self.assertEqual(
            result[
                "correction"
            ],
            {
                "value": "supports",
                "reason": (
                    "Reviewer confirmed "
                    "the source supports "
                    "this exact claim."
                ),
                "corrected_by": (
                    "Yuvraj"
                ),
                "corrected_at": (
                    "2026-08-15T10:15:00+05:30"
                ),
                "scope": (
                    "case_only"
                ),
            },
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "automatic_history_is_preserved"
            ]
        )

    def test_exact_resolution_replay_is_idempotent(
        self,
    ):
        review = (
            record_review_queue_item(
                item=(
                    self.unresolved_packet()[
                        "items"
                    ][0]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "review"
            ]
        )

        kwargs = {
            "review_id": (
                review[
                    "id"
                ]
            ),
            "value": "supports",
            "reason": "Reviewed.",
            "corrected_by": "Reviewer",
            "corrected_at": (
                "2026-08-15T10:20:00+05:30"
            ),
            "scope": "case_only",
            "connection_factory": (
                self.connection_factory
            ),
        }

        first = (
            resolve_review_queue_item(
                **kwargs
            )
        )

        second = (
            resolve_review_queue_item(
                **kwargs
            )
        )

        self.assertTrue(
            first[
                "changed"
            ]
        )

        self.assertFalse(
            second[
                "changed"
            ]
        )

    def test_conflicting_second_resolution_is_rejected(
        self,
    ):
        review = (
            record_review_queue_item(
                item=(
                    self.unresolved_packet()[
                        "items"
                    ][0]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "review"
            ]
        )

        resolve_review_queue_item(
            review_id=(
                review[
                    "id"
                ]
            ),
            value="supports",
            reason="Reviewed.",
            corrected_by="Reviewer",
            corrected_at=(
                "2026-08-15T10:20:00+05:30"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "different correction",
        ):
            resolve_review_queue_item(
                review_id=(
                    review[
                        "id"
                    ]
                ),
                value="contradicts",
                reason="Changed mind.",
                corrected_by="Reviewer",
                corrected_at=(
                    "2026-08-15T10:21:00+05:30"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

    def test_resolved_item_leaves_pending_queue(
        self,
    ):
        review = (
            record_review_queue_item(
                item=(
                    self.unresolved_packet()[
                        "items"
                    ][0]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "review"
            ]
        )

        resolve_review_queue_item(
            review_id=(
                review[
                    "id"
                ]
            ),
            value="supports",
            reason="Reviewed.",
            corrected_by="Reviewer",
            corrected_at=(
                "2026-08-15T10:20:00+05:30"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        pending = (
            list_review_queue_items(
                status="pending",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        resolved = (
            list_review_queue_items(
                status="resolved",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            pending,
            [],
        )

        self.assertEqual(
            len(
                resolved
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
