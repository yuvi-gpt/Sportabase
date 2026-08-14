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


from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
)
from app.services.corroboration_discovery import (
    CORROBORATION_CANDIDATE_COLLECTION_VERSION,
    CORROBORATION_SEARCH_PLAN_VERSION,
)
from app.services.corroboration_graph import (
    CORROBORATION_GRAPH_PLAN_VERSION,
)
from app.services.corroboration_materialization import (
    CORROBORATION_GRAPH_MATERIALIZATION_VERSION,
)
from app.services.corroboration_pipeline import (
    CORROBORATION_PIPELINE_VERSION,
    run_claim_corroboration_pipeline,
)
from app.services.corroboration_semantics import (
    CORROBORATION_SEMANTIC_BATCH_VERSION,
)


class CorroborationPipelineTests(
    unittest.TestCase
):
    def setUp(self):
        self.claim = {
            "id": "claim-1",
            "canonical_key": (
                "transfer|alpha|beta|agreement"
            ),
            "subject_key": (
                "transfer|alpha|beta"
            ),
            "claim_type": "assertion",
            "canonical_text": (
                "Player Alpha has agreed "
                "to join Club Beta."
            ),
        }

        self.media_item_id = (
            "media-1"
        )

        self.source_url = (
            "https://origin.example/story"
        )

        self.news_api_key = (
            "test-news-key"
        )

        self.gemini_client = (
            object()
        )

        self.gemini_generator = (
            object()
        )

        self.connection_factory = (
            object()
        )

    def harness(self):
        calls = []
        captured = {}

        def search_plan_builder(
            **kwargs,
        ):
            calls.append(
                "search_plan"
            )
            captured[
                "search_plan"
            ] = kwargs

            return {
                "version": (
                    CORROBORATION_SEARCH_PLAN_VERSION
                ),
                "claim_id": "claim-1",
                "status": "searchable",
                "queries": [],
            }

        def candidate_collector(
            **kwargs,
        ):
            calls.append(
                "candidate_collection"
            )
            captured[
                "candidate_collection"
            ] = kwargs

            return {
                "version": (
                    CORROBORATION_CANDIDATE_COLLECTION_VERSION
                ),
                "claim_id": "claim-1",
                "status": "resolved",
                "resolved_candidates": [],
            }

        def semantic_batch_assessor(
            **kwargs,
        ):
            calls.append(
                "semantic_batch"
            )
            captured[
                "semantic_batch"
            ] = kwargs

            return {
                "version": (
                    CORROBORATION_SEMANTIC_BATCH_VERSION
                ),
                "claim_id": "claim-1",
                "status": "assessed",
                "candidate_assessments": [],
            }

        def graph_plan_builder(
            **kwargs,
        ):
            calls.append(
                "graph_plan"
            )
            captured[
                "graph_plan"
            ] = kwargs

            return {
                "version": (
                    CORROBORATION_GRAPH_PLAN_VERSION
                ),
                "claim_id": "claim-1",
                "status": (
                    "no_materializable_actions"
                ),
                "actions": [],
            }

        def graph_materializer(
            **kwargs,
        ):
            calls.append(
                "materialization"
            )
            captured[
                "materialization"
            ] = kwargs

            return {
                "version": (
                    CORROBORATION_GRAPH_MATERIALIZATION_VERSION
                ),
                "claim_id": "claim-1",
                "status": (
                    "no_materializable_actions"
                ),
                "results": [],
            }

        def evidence_loader(
            **kwargs,
        ):
            calls.append(
                "evidence"
            )
            captured[
                "evidence"
            ] = kwargs

            return {
                "version": (
                    EVIDENCE_ANALYSIS_BUNDLE_VERSION
                ),
                "marker": (
                    "refreshed-evidence"
                ),
            }

        stages = {
            "search_plan_builder": (
                search_plan_builder
            ),
            "candidate_collector": (
                candidate_collector
            ),
            "semantic_batch_assessor": (
                semantic_batch_assessor
            ),
            "graph_plan_builder": (
                graph_plan_builder
            ),
            "graph_materializer": (
                graph_materializer
            ),
            "evidence_loader": (
                evidence_loader
            ),
        }

        return (
            calls,
            captured,
            stages,
        )

    def run_pipeline(
        self,
        *,
        stages,
        claim=None,
        media_item_id=None,
        freshness="pw",
        max_candidates=8,
        results_per_query=20,
        max_assessments=8,
    ):
        return (
            run_claim_corroboration_pipeline(
                claim=(
                    self.claim
                    if claim is None
                    else claim
                ),
                media_item_id=(
                    self.media_item_id
                    if media_item_id is None
                    else media_item_id
                ),
                source_url=(
                    self.source_url
                ),
                news_api_key=(
                    self.news_api_key
                ),
                normalize_url=(
                    lambda value: value
                ),
                domain_resolver=(
                    lambda value: (
                        "example.com"
                    )
                ),
                fetch_article=(
                    lambda value: value
                ),
                extract_article=(
                    lambda value: value
                ),
                gemini_client=(
                    self.gemini_client
                ),
                gemini_client_key=(
                    "client-key"
                ),
                gemini_generator=(
                    self.gemini_generator
                ),
                connection_factory=(
                    self.connection_factory
                ),
                freshness=freshness,
                max_candidates=(
                    max_candidates
                ),
                results_per_query=(
                    results_per_query
                ),
                max_assessments=(
                    max_assessments
                ),
                **stages,
            )
        )

    def test_pipeline_runs_stages_in_order(
        self,
    ):
        (
            calls,
            _,
            stages,
        ) = self.harness()

        result = self.run_pipeline(
            stages=stages,
        )

        self.assertEqual(
            calls,
            [
                "search_plan",
                "candidate_collection",
                "semantic_batch",
                "graph_plan",
                "materialization",
                "evidence",
            ],
        )

        self.assertEqual(
            result["version"],
            CORROBORATION_PIPELINE_VERSION,
        )

        self.assertEqual(
            result["status"],
            "completed",
        )

        self.assertEqual(
            result["outcome"],
            "no_materializable_actions",
        )

        self.assertEqual(
            result["claim_id"],
            "claim-1",
        )

        self.assertEqual(
            result["media_item_id"],
            "media-1",
        )

        self.assertEqual(
            result[
                "stages"
            ][
                "evidence_bundle"
            ][
                "marker"
            ],
            "refreshed-evidence",
        )

    def test_pipeline_forwards_provider_and_limits(
        self,
    ):
        (
            _,
            captured,
            stages,
        ) = self.harness()

        self.run_pipeline(
            stages=stages,
            freshness="pm",
            max_candidates=5,
            results_per_query=7,
            max_assessments=4,
        )

        search = captured[
            "search_plan"
        ]

        self.assertIs(
            search["claim"],
            self.claim,
        )

        self.assertEqual(
            search["source_url"],
            self.source_url,
        )

        self.assertEqual(
            search["freshness"],
            "pm",
        )

        collection = captured[
            "candidate_collection"
        ]

        self.assertEqual(
            collection["api_key"],
            self.news_api_key,
        )

        self.assertEqual(
            collection[
                "max_candidates"
            ],
            5,
        )

        self.assertEqual(
            collection[
                "results_per_query"
            ],
            7,
        )

        semantic = captured[
            "semantic_batch"
        ]

        self.assertIs(
            semantic["client"],
            self.gemini_client,
        )

        self.assertEqual(
            semantic["client_key"],
            "client-key",
        )

        self.assertIs(
            semantic["generator"],
            self.gemini_generator,
        )

        self.assertEqual(
            semantic[
                "max_assessments"
            ],
            4,
        )

        evidence = captured[
            "evidence"
        ]

        self.assertEqual(
            evidence[
                "media_item_id"
            ],
            "media-1",
        )

        self.assertIs(
            evidence[
                "connection_factory"
            ],
            self.connection_factory,
        )

    def test_pipeline_preserves_conservative_policy(
        self,
    ):
        (
            _,
            _,
            stages,
        ) = self.harness()

        result = self.run_pipeline(
            stages=stages,
        )

        policy = result[
            "policy"
        ]

        self.assertTrue(
            policy[
                "search_is_discovery_only"
            ]
        )

        self.assertTrue(
            policy[
                "semantic_assessment_does_"
                "not_establish_independence"
            ]
        )

        self.assertTrue(
            policy[
                "materialization_does_not_"
                "create_independence_assertions"
            ]
        )

        self.assertTrue(
            policy[
                "pipeline_does_not_decide_"
                "corroboration"
            ]
        )

        self.assertTrue(
            policy[
                "pipeline_has_no_merit_effect"
            ]
        )

        self.assertTrue(
            policy[
                "evidence_is_reloaded_after_"
                "materialization"
            ]
        )

    def test_pipeline_requires_claim_id(
        self,
    ):
        (
            calls,
            _,
            stages,
        ) = self.harness()

        with self.assertRaisesRegex(
            ValueError,
            "claim ID is required",
        ):
            self.run_pipeline(
                stages=stages,
                claim={
                    "id": "",
                },
            )

        self.assertEqual(
            calls,
            [],
        )

    def test_pipeline_requires_media_item_id(
        self,
    ):
        (
            calls,
            _,
            stages,
        ) = self.harness()

        with self.assertRaisesRegex(
            ValueError,
            "media item ID is required",
        ):
            self.run_pipeline(
                stages=stages,
                media_item_id="",
            )

        self.assertEqual(
            calls,
            [],
        )

    def test_pipeline_rejects_stage_version_mismatch(
        self,
    ):
        (
            calls,
            _,
            stages,
        ) = self.harness()

        def bad_search_plan(
            **kwargs,
        ):
            calls.append(
                "bad_search_plan"
            )

            return {
                "version": (
                    "corroboration-search-plan-v999"
                ),
                "claim_id": "claim-1",
                "status": "searchable",
            }

        stages[
            "search_plan_builder"
        ] = bad_search_plan

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            self.run_pipeline(
                stages=stages,
            )

        self.assertEqual(
            calls,
            [
                "bad_search_plan",
            ],
        )

    def test_pipeline_rejects_stage_claim_mismatch(
        self,
    ):
        (
            calls,
            _,
            stages,
        ) = self.harness()

        def bad_collection(
            **kwargs,
        ):
            calls.append(
                "bad_collection"
            )

            return {
                "version": (
                    CORROBORATION_CANDIDATE_COLLECTION_VERSION
                ),
                "claim_id": (
                    "different-claim"
                ),
                "status": "resolved",
                "resolved_candidates": [],
            }

        stages[
            "candidate_collector"
        ] = bad_collection

        with self.assertRaisesRegex(
            ValueError,
            "claim ID does not match",
        ):
            self.run_pipeline(
                stages=stages,
            )

        self.assertEqual(
            calls,
            [
                "search_plan",
                "bad_collection",
            ],
        )

    def test_pipeline_propagates_failure_and_stops(
        self,
    ):
        (
            calls,
            _,
            stages,
        ) = self.harness()

        def failing_semantics(
            **kwargs,
        ):
            calls.append(
                "failing_semantics"
            )

            raise RuntimeError(
                "semantic boom"
            )

        stages[
            "semantic_batch_assessor"
        ] = failing_semantics

        with self.assertRaisesRegex(
            RuntimeError,
            "semantic boom",
        ):
            self.run_pipeline(
                stages=stages,
            )

        self.assertEqual(
            calls,
            [
                "search_plan",
                "candidate_collection",
                "failing_semantics",
            ],
        )


if __name__ == "__main__":
    unittest.main()
