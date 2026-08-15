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


from fastapi import (
    HTTPException,
)


from app import reviewer_app

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
    record_review_queue_item,
)


class LocalReviewerAppTests(
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
            / "reviewer.db"
        )

        self.original_db_path = (
            reviewer_app.REVIEW_DB_PATH
        )

        self.original_token = (
            reviewer_app.REVIEWER_SESSION_TOKEN
        )

        reviewer_app.REVIEW_DB_PATH = (
            self.db_path
        )

        reviewer_app.REVIEWER_SESSION_TOKEN = (
            "test-review-token"
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
                    "2026-08-15T05:00:00Z"
                ),
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.evidence = (
            record_evidence(
                evidence_type=(
                    "claim_evidence_snapshot"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                claim_summary=(
                    "Model-assisted "
                    "claim evidence."
                ),
                observed_at=(
                    "2026-08-15T05:01:00Z"
                ),
                reference_key=(
                    "snapshot-reviewer:"
                    "content-reviewer"
                ),
                verification_status=(
                    "unverified"
                ),
                metadata={
                    "derivation": {
                        "mode": (
                            "model_assisted"
                        )
                    },
                    "review": {
                        "status": "draft"
                    },
                },
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
                "2026-08-15T05:01:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        adjudication = (
            build_multi_evaluator_adjudication(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                evaluator_runs=[
                    {
                        "run_id": (
                            "semantic-run"
                        ),
                        "evaluator_id": (
                            "semantic-v1"
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
                                    "semantic-stance"
                                ),
                                "field": "stance",
                                "value": "supports",
                                "confidence": 0.96,
                                "evaluator_id": (
                                    "semantic-v1"
                                ),
                                "evaluator_family": (
                                    "semantic_model"
                                ),
                                "basis_class": (
                                    "model_inference"
                                ),
                                "evidence_ids": [
                                    self.evidence[
                                        "id"
                                    ]
                                ],
                                "training_eligible": (
                                    False
                                ),
                            }
                        ],
                    },
                    {
                        "run_id": (
                            "graph-run"
                        ),
                        "evaluator_id": (
                            "graph-v1"
                        ),
                        "evaluator_family": (
                            "provenance_graph"
                        ),
                        "derivation_mode": (
                            "machine_verified"
                        ),
                        "judgments": [
                            {
                                "id": (
                                    "graph-stance"
                                ),
                                "field": "stance",
                                "value": (
                                    "contradicts"
                                ),
                                "confidence": 0.97,
                                "evaluator_id": (
                                    "graph-v1"
                                ),
                                "evaluator_family": (
                                    "provenance_graph"
                                ),
                                "basis_class": (
                                    "provenance_graph"
                                ),
                                "evidence_ids": [
                                    self.evidence[
                                        "id"
                                    ]
                                ],
                                "training_eligible": (
                                    False
                                ),
                            }
                        ],
                    },
                ],
            )
        )

        packet = (
            build_adjudication_review_queue(
                adjudication=(
                    adjudication
                ),
                evidence_id=(
                    self.evidence[
                        "id"
                    ]
                ),
            )
        )

        self.review = (
            record_review_queue_item(
                item=(
                    packet[
                        "items"
                    ][0]
                ),
                recorded_at=(
                    "2026-08-15T05:02:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "review"
            ]
        )

    def tearDown(
        self,
    ):
        reviewer_app.REVIEW_DB_PATH = (
            self.original_db_path
        )

        reviewer_app.REVIEWER_SESSION_TOKEN = (
            self.original_token
        )

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

    def resolution_body(
        self,
    ):
        return (
            reviewer_app.ReviewResolutionRequest(
                value="supports",
                reason=(
                    "Reviewer inspected "
                    "the exact evidence."
                ),
                corrected_by="Yuvraj",
                corrected_at=(
                    "2026-08-15T10:40:00+05:30"
                ),
                scope="case_only",
            )
        )

    def test_loopback_ipv4_is_allowed(
        self,
    ):
        self.assertTrue(
            reviewer_app.is_loopback_host(
                "127.0.0.1"
            )
        )

    def test_loopback_ipv6_and_localhost_are_allowed(
        self,
    ):
        self.assertTrue(
            reviewer_app.is_loopback_host(
                "::1"
            )
        )

        self.assertTrue(
            reviewer_app.is_loopback_host(
                "localhost"
            )
        )

    def test_non_loopback_is_rejected(
        self,
    ):
        self.assertFalse(
            reviewer_app.is_loopback_host(
                "192.168.1.50"
            )
        )

        self.assertFalse(
            reviewer_app.is_loopback_host(
                "example.com"
            )
        )

    def test_required_routes_are_registered(
        self,
    ):
        paths = {
            route.path
            for route
            in reviewer_app.app.routes
        }

        self.assertIn(
            "/",
            paths,
        )

        self.assertIn(
            "/api/health",
            paths,
        )

        self.assertIn(
            "/api/reviews",
            paths,
        )

        self.assertIn(
            "/api/reviews/{review_id}",
            paths,
        )

        self.assertIn(
            (
                "/api/reviews/"
                "{review_id}/resolve"
            ),
            paths,
        )

    def test_home_injects_token_and_has_no_external_assets(
        self,
    ):
        response = (
            reviewer_app.reviewer_home()
        )

        body = (
            response.body.decode(
                "utf-8"
            )
        )

        self.assertIn(
            '"test-review-token"',
            body,
        )

        self.assertNotIn(
            "__SPORTABASE_REVIEWER_TOKEN__",
            body,
        )

        self.assertNotIn(
            "https://",
            body,
        )

        self.assertNotIn(
            "http://",
            body,
        )

    def test_api_list_returns_review_summary(
        self,
    ):
        result = (
            reviewer_app.api_list_reviews(
                status="pending",
                claim_id="",
                limit=100,
            )
        )

        self.assertEqual(
            result[
                "count"
            ],
            1,
        )

        item = result[
            "items"
        ][0]

        self.assertEqual(
            item[
                "queue_reason"
            ],
            "contested",
        )

        self.assertEqual(
            item[
                "field"
            ],
            "stance",
        )

        self.assertEqual(
            item[
                "judgment_count"
            ],
            2,
        )

    def test_api_detail_includes_claim_evidence_and_votes(
        self,
    ):
        result = (
            reviewer_app.api_get_review(
                self.review[
                    "id"
                ]
            )
        )

        self.assertEqual(
            result[
                "claim"
            ][
                "canonical_text"
            ],
            (
                "Player A will join Team A."
            ),
        )

        self.assertEqual(
            result[
                "evidence"
            ][
                "verification_status"
            ],
            "unverified",
        )

        self.assertEqual(
            len(
                result[
                    "votes"
                ]
            ),
            2,
        )

        self.assertEqual(
            {
                vote[
                    "value"
                ]
                for vote
                in result[
                    "votes"
                ]
            },
            {
                "supports",
                "contradicts",
            },
        )

    def test_missing_detail_returns_404(
        self,
    ):
        with self.assertRaises(
            HTTPException
        ) as context:
            reviewer_app.api_get_review(
                "missing-review"
            )

        self.assertEqual(
            context.exception.status_code,
            404,
        )

    def test_resolve_rejects_wrong_token(
        self,
    ):
        with self.assertRaises(
            HTTPException
        ) as context:
            reviewer_app.api_resolve_review(
                self.review[
                    "id"
                ],
                self.resolution_body(),
                x_sportabase_reviewer_token=(
                    "wrong-token"
                ),
            )

        self.assertEqual(
            context.exception.status_code,
            403,
        )

    def test_resolve_accepts_correct_token(
        self,
    ):
        result = (
            reviewer_app.api_resolve_review(
                self.review[
                    "id"
                ],
                self.resolution_body(),
                x_sportabase_reviewer_token=(
                    "test-review-token"
                ),
            )
        )

        self.assertEqual(
            result[
                "item"
            ][
                "review"
            ][
                "status"
            ],
            "resolved",
        )

        self.assertEqual(
            result[
                "resolution"
            ][
                "correction"
            ][
                "value"
            ],
            "supports",
        )

        self.assertTrue(
            result[
                "resolution"
            ][
                "policy"
            ][
                "resolution_does_not_change_live_merit"
            ]
        )

    def test_health_is_local_only_and_reports_database(
        self,
    ):
        result = (
            reviewer_app.api_health()
        )

        self.assertTrue(
            result[
                "local_only"
            ]
        )

        self.assertEqual(
            Path(
                result[
                    "db_path"
                ]
            ),
            self.db_path.resolve(),
        )

    def test_resolved_item_leaves_pending_view(
        self,
    ):
        reviewer_app.api_resolve_review(
            self.review[
                "id"
            ],
            self.resolution_body(),
            x_sportabase_reviewer_token=(
                "test-review-token"
            ),
        )

        pending = (
            reviewer_app.api_list_reviews(
                status="pending",
                claim_id="",
                limit=100,
            )
        )

        resolved = (
            reviewer_app.api_list_reviews(
                status="resolved",
                claim_id="",
                limit=100,
            )
        )

        self.assertEqual(
            pending[
                "count"
            ],
            0,
        )

        self.assertEqual(
            resolved[
                "count"
            ],
            1,
        )


if __name__ == "__main__":
    unittest.main()
