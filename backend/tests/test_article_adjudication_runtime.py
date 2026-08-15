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


from app.services.article_adjudication_runtime import (
    ARTICLE_ADJUDICATION_RUNTIME_VERSION,
    build_article_adjudication_evaluator_runs,
    run_article_adjudication_runtime,
)

from app.services.article_intelligence_shadow import (
    run_article_intelligence_shadow,
)

from app.services.intelligence_pipeline import (
    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
)


class ArticleAdjudicationRuntimeTests(
    unittest.TestCase
):
    def pipeline(
        self,
        *,
        support=True,
        contradiction=False,
        independent=False,
        dependency=False,
    ):
        support_links = (
            [
                {
                    "id": "support-link-1"
                }
            ]
            if support
            else []
        )

        contradiction_links = (
            [
                {
                    "id": "contradiction-link-1"
                }
            ]
            if contradiction
            else []
        )

        dependency_ids = (
            [
                "dependency-1"
            ]
            if dependency
            else []
        )

        independence_results = []

        if independent:
            independence_results = [
                {
                    "status": (
                        "materialized_verified_independence"
                    ),
                    "materialization": {
                        "verification_observed_at": (
                            "2026-08-15T08:00:00+00:00"
                        ),
                        "evidence": {
                            "id": (
                                "independence-evidence-1"
                            )
                        },
                    },
                }
            ]

        return {
            "version": (
                SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
            ),
            "status": "completed",
            "mode": "shadow",
            "claim_id": "claim-1",
            "live": {
                "merit_score_effect_enabled": False,
                "legacy_total": 72.0,
                "total": 72.0,
            },
            "stages": {
                "corroboration_resolution": {
                    "claim_id": "claim-1",
                    "target_claim": {
                        "claim_id": "claim-1",
                        "independent_support_established": (
                            independent
                        ),
                        "recorded_support_dependency_ids": (
                            dependency_ids
                        ),
                    },
                    "stages": {
                        "stance": {
                            "claims": [
                                {
                                    "claim_id": "claim-1",
                                    "support_links": (
                                        support_links
                                    ),
                                    "contradiction_links": (
                                        contradiction_links
                                    ),
                                }
                            ]
                        }
                    },
                },
                "independence_batch": {
                    "claim_id": "claim-1",
                    "results": (
                        independence_results
                    ),
                    "evidence_bundle": {
                        "source_observations": [
                            {
                                "observed_at": (
                                    "2026-08-15T07:00:00+00:00"
                                )
                            }
                        ],
                        "reporter_observations": [],
                        "evidence_records": [],
                    },
                },
            },
        }

    def test_version(
        self,
    ):
        self.assertEqual(
            ARTICLE_ADJUDICATION_RUNTIME_VERSION,
            "article-adjudication-runtime-v1",
        )

    def test_support_creates_stance_vote(
        self,
    ):
        runs = (
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=(
                    self.pipeline()
                ),
            )
        )

        judgments = [
            judgment
            for run in runs
            for judgment in run[
                "judgments"
            ]
        ]

        stance = [
            row
            for row in judgments
            if row[
                "field"
            ]
            == "stance"
        ]

        self.assertEqual(
            len(
                stance
            ),
            1,
        )

        self.assertEqual(
            stance[0][
                "value"
            ],
            "supports",
        )

    def test_support_and_contradiction_are_separate_votes(
        self,
    ):
        runs = (
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=(
                    self.pipeline(
                        contradiction=True
                    )
                ),
            )
        )

        stance_values = sorted(
            judgment[
                "value"
            ]
            for run in runs
            for judgment in run[
                "judgments"
            ]
            if judgment[
                "field"
            ]
            == "stance"
        )

        self.assertEqual(
            stance_values,
            [
                "contradicts",
                "supports",
            ],
        )

        families = {
            run[
                "evaluator_family"
            ]
            for run in runs
        }

        self.assertEqual(
            families,
            {
                "provenance_graph"
            },
        )

    def test_verified_independence_creates_established_vote(
        self,
    ):
        runs = (
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=(
                    self.pipeline(
                        independent=True
                    )
                ),
            )
        )

        rows = [
            judgment
            for run in runs
            for judgment in run[
                "judgments"
            ]
            if judgment[
                "field"
            ]
            == "independence_status"
        ]

        self.assertEqual(
            len(
                rows
            ),
            1,
        )

        self.assertEqual(
            rows[0][
                "value"
            ],
            "established",
        )

        self.assertEqual(
            rows[0][
                "evidence_ids"
            ],
            [
                "independence-evidence-1"
            ],
        )

    def test_recorded_dependency_creates_not_established_vote(
        self,
    ):
        runs = (
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=(
                    self.pipeline(
                        dependency=True
                    )
                ),
            )
        )

        rows = [
            judgment
            for run in runs
            for judgment in run[
                "judgments"
            ]
            if judgment[
                "field"
            ]
            == "independence_status"
        ]

        self.assertEqual(
            rows[0][
                "value"
            ],
            "not_established",
        )

    def test_unknown_independence_is_not_guessed(
        self,
    ):
        runs = (
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=(
                    self.pipeline()
                ),
            )
        )

        fields = {
            judgment[
                "field"
            ]
            for run in runs
            for judgment in run[
                "judgments"
            ]
        }

        self.assertNotIn(
            "independence_status",
            fields,
        )

    def test_graph_is_never_trusted_training_reference(
        self,
    ):
        runs = (
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=(
                    self.pipeline(
                        independent=True
                    )
                ),
            )
        )

        self.assertTrue(
            all(
                run[
                    "derivation_mode"
                ]
                == "mixed"
                for run in runs
            )
        )

        self.assertTrue(
            all(
                judgment[
                    "training_eligible"
                ]
                is False
                for run in runs
                for judgment in run[
                    "judgments"
                ]
            )
        )

    def test_initial_history_trigger(
        self,
    ):
        captured = {}

        def latest_loader(
            **kwargs
        ):
            return None

        def history_runner(
            **kwargs
        ):
            captured.update(
                kwargs
            )

            return {
                "status": "persisted",
                "revision": {
                    "revision_id": (
                        "revision-1"
                    ),
                    "transitions": [],
                },
                "persistence": {
                    "transition_count": 0
                },
            }

        result = (
            run_article_adjudication_runtime(
                claim={
                    "id": "claim-1"
                },
                pipeline=(
                    self.pipeline()
                ),
                as_of=(
                    "2026-08-15T06:00:00+00:00"
                ),
                connection_factory=(
                    lambda: None
                ),
                latest_loader=(
                    latest_loader
                ),
                history_runner=(
                    history_runner
                ),
            )
        )

        self.assertEqual(
            captured[
                "trigger_type"
            ],
            "initial_evaluation",
        )

        self.assertEqual(
            result[
                "revision_id"
            ],
            "revision-1",
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "does_not_change_live_merit"
            ]
            is False
        )

    def test_existing_history_uses_refresh_trigger(
        self,
    ):
        captured = {}

        def history_runner(
            **kwargs
        ):
            captured.update(
                kwargs
            )

            return {
                "status": "persisted",
                "revision": {
                    "revision_id": (
                        "revision-2"
                    ),
                    "transitions": [],
                },
                "persistence": {
                    "transition_count": 0
                },
            }

        result = (
            run_article_adjudication_runtime(
                claim={
                    "id": "claim-1"
                },
                pipeline=(
                    self.pipeline()
                ),
                as_of=(
                    "2026-08-15T06:00:00+00:00"
                ),
                connection_factory=(
                    lambda: None
                ),
                latest_loader=(
                    lambda **kwargs: {
                        "revision_id": (
                            "revision-1"
                        )
                    }
                ),
                history_runner=(
                    history_runner
                ),
            )
        )

        self.assertEqual(
            captured[
                "trigger_type"
            ],
            "evaluator_refresh",
        )

        self.assertEqual(
            result[
                "trigger_type"
            ],
            "evaluator_refresh",
        )

    def test_as_of_uses_latest_evidence_time(
        self,
    ):
        captured = {}

        def history_runner(
            **kwargs
        ):
            captured.update(
                kwargs
            )

            return {
                "status": "persisted",
                "revision": {
                    "revision_id": (
                        "revision-1"
                    ),
                    "transitions": [],
                },
                "persistence": {
                    "transition_count": 0
                },
            }

        run_article_adjudication_runtime(
            claim={
                "id": "claim-1"
            },
            pipeline=(
                self.pipeline(
                    independent=True
                )
            ),
            as_of=(
                "2026-08-15T06:00:00+00:00"
            ),
            connection_factory=(
                lambda: None
            ),
            latest_loader=(
                lambda **kwargs: None
            ),
            history_runner=(
                history_runner
            ),
        )

        self.assertEqual(
            captured[
                "as_of"
            ],
            "2026-08-15T08:00:00+00:00",
        )

    def test_wrong_pipeline_version_fails_closed(
        self,
    ):
        pipeline = (
            self.pipeline()
        )

        pipeline[
            "version"
        ] = "wrong"

        with self.assertRaisesRegex(
            ValueError,
            "current intelligence pipeline",
        ):
            build_article_adjudication_evaluator_runs(
                claim_id="claim-1",
                pipeline=pipeline,
            )

    def test_article_shadow_invokes_adjudication_runtime(
        self,
    ):
        calls = []

        def pipeline_runner(
            **kwargs
        ):
            result = (
                self.pipeline()
            )

            result[
                "stages"
            ][
                "merit_overlay"
            ] = {
                "signal": "unchanged",
                "proposed": {
                    "adjustment": 0.0,
                    "shadow_total": 72.0,
                },
            }

            result[
                "stages"
            ][
                "independence_plan"
            ] = {
                "counts": {
                    "verification_pairs": 0
                }
            }

            result[
                "stages"
            ][
                "corroboration_pipeline"
            ] = {
                "stages": {
                    "candidate_collection": {
                        "counts": {
                            "resolved": 0
                        }
                    }
                }
            }

            return result

        def adjudication_runner(
            **kwargs
        ):
            calls.append(
                kwargs
            )

            return {
                "version": (
                    ARTICLE_ADJUDICATION_RUNTIME_VERSION
                ),
                "status": "persisted",
                "claim_id": "claim-1",
                "revision_id": "revision-1",
                "transition_count": 0,
                "evaluator_run_count": 1,
                "fields_evaluated": [
                    "stance"
                ],
                "policy": {
                    "does_not_change_live_merit": True
                },
            }

        result = (
            run_article_intelligence_shadow(
                enabled=True,
                media_item_id="media-1",
                observed_at=(
                    "2026-08-15T06:00:00+00:00"
                ),
                title="Player joins Club",
                article_text="Body",
                url=(
                    "https://example.com/story"
                ),
                article_type=(
                    "transfer_report"
                ),
                type_confidence=0.9,
                legacy_score={
                    "total": 72,
                    "components": {},
                },
                news_api_key="key",
                normalize_url=(
                    lambda value: value
                ),
                fetch_article=(
                    lambda url: {}
                ),
                extract_article=(
                    lambda html: {}
                ),
                gemini_client=object(),
                gemini_client_key="client",
                gemini_generator=(
                    lambda **kwargs: None
                ),
                connection_factory=(
                    lambda: None
                ),
                seed_persister=(
                    lambda **kwargs: {
                        "claim": {
                            "id": "claim-1",
                            "canonical_text": (
                                "Player joins Club"
                            ),
                            "subject_key": (
                                "subject-1"
                            ),
                        }
                    }
                ),
                pipeline_runner=(
                    pipeline_runner
                ),
                adjudication_runner=(
                    adjudication_runner
                ),
            )
        )

        self.assertEqual(
            len(
                calls
            ),
            1,
        )

        self.assertEqual(
            calls[0][
                "claim"
            ][
                "id"
            ],
            "claim-1",
        )

        self.assertEqual(
            result[
                "adjudication"
            ][
                "revision_id"
            ],
            "revision-1",
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()
