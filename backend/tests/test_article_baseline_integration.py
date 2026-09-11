import copy
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


from app.analysis.model_assisted_baseline import (
    build_model_assisted_baseline_evaluator_runs,
)

from app.analysis.observation_semantics import (
    normalize_claim_observation_semantics,
)

from app.db.schema import SCHEMA

from app.intelligence.analysis_result_context import (
    build_analysis_result_context,
)

from app.services.analysis_history import (
    media_item_id_for_url,
    upsert_media_item,
)

from app.services.article_intelligence_baseline import (
    persist_article_intelligence_baseline,
)

from app.services.article_adjudication_runtime import (
    ARTICLE_ADJUDICATION_RUNTIME_VERSION,
    run_article_adjudication_runtime,
)

from app.services.article_intelligence_shadow import (
    run_article_intelligence_shadow,
)

from app.services.intelligence_pipeline import (
    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
)

from app.services.model_assisted_baseline_runtime import (
    MODEL_ASSISTED_BASELINE_RUNTIME_VERSION,
    persist_model_assisted_baseline_revision,
)

from app.services.snapshot_persistence import (
    MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION,
)

from app.services.content_resolution import (
    normalized_analysis_url,
)


class ArticleBaselineIntegrationTests(
    unittest.TestCase
):
    @staticmethod
    def normalize_url(
        value,
    ):
        return str(
            value or ""
        ).strip().lower()

    def base_shadow_kwargs(
        self,
    ):
        return {
            "enabled": True,
            "media_item_id": "media-1",
            "observed_at": (
                "2026-08-15T08:00:00+00:00"
            ),
            "title": (
                "Player A set to join Team B"
            ),
            "article_text": (
                "Publisher reports that "
                "Player A is set to join Team B."
            ),
            "url": (
                "https://example.com/story"
            ),
            "article_type": (
                "transfer_report"
            ),
            "type_confidence": 0.9,
            "legacy_score": {
                "total": 70,
                "components": {},
            },
            "news_api_key": "fake-key",
            "normalize_url": (
                self.normalize_url
            ),
            "fetch_article": (
                lambda url: {}
            ),
            "extract_article": (
                lambda html: {}
            ),
            "gemini_client": object(),
            "gemini_client_key": (
                "client"
            ),
            "gemini_generator": (
                lambda **kwargs: None
            ),
            "connection_factory": (
                lambda: None
            ),
        }

    @staticmethod
    def pipeline():
        return {
            "version": (
                SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
            ),
            "status": "completed",
            "mode": "shadow",
            "claim_id": "claim-1",
            "live": {
                "merit_score_effect_enabled": False,
                "legacy_total": 70.0,
                "total": 70.0,
            },
            "stages": {
                "merit_overlay": {
                    "signal": "",
                    "proposed": {
                        "adjustment": 0.0,
                        "shadow_total": 70.0,
                    },
                },
                "independence_plan": {
                    "counts": {
                        "verification_pairs": 0,
                    },
                },
                "corroboration_pipeline": {
                    "stages": {
                        "candidate_collection": {
                            "counts": {
                                "resolved": 0,
                            },
                        },
                    },
                },
            },
        }

    def test_article_shadow_passes_primary_baseline_runs_into_adjudication(
        self,
    ):
        calls = []
        captured = {}

        baseline_run = {
            "run_id": "baseline-run",
            "evaluator_id": "semantic-v1",
            "evaluator_family": (
                "observation_semantic_model"
            ),
            "derivation_mode": (
                "model_assisted"
            ),
            "judgments": [],
        }

        def seed_persister(
            **kwargs,
        ):
            calls.append(
                "seed"
            )

            return {
                "claim": {
                    "id": "claim-1",
                    "canonical_key": "claim-key",
                    "subject_key": "subject-1",
                    "canonical_text": (
                        "Player A set to join Team B"
                    ),
                    "claim_type": (
                        "headline_assertion"
                    ),
                },
                "source": {
                    "id": "source-1",
                },
            }

        def semantic_assessor(
            **kwargs,
        ):
            calls.append(
                "semantic"
            )

            return {
                "status": "assessed",
                "assessment": {
                    "placeholder": True,
                },
            }

        def snapshot_builder(
            **kwargs,
        ):
            calls.append(
                "snapshot"
            )

            return {
                "status": "assembled",
                "claim_id": "claim-1",
            }

        def baseline_runtime_runner(
            **kwargs,
        ):
            calls.append(
                "baseline"
            )

            return {
                "version": (
                    MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
                ),
                "status": "persisted",
                "bound_evaluator_runs": [
                    baseline_run
                ],
            }

        def pipeline_runner(
            **kwargs,
        ):
            calls.append(
                "pipeline"
            )

            return self.pipeline()

        def adjudication_runner(
            **kwargs,
        ):
            calls.append(
                "adjudication"
            )

            captured[
                "additional"
            ] = kwargs[
                "additional_evaluator_runs"
            ]

            return {
                "version": (
                    ARTICLE_ADJUDICATION_RUNTIME_VERSION
                ),
                "status": "persisted",
            }

        result = (
            run_article_intelligence_shadow(
                **self.base_shadow_kwargs(),
                seed_persister=(
                    seed_persister
                ),
                semantic_assessor=(
                    semantic_assessor
                ),
                snapshot_builder=(
                    snapshot_builder
                ),
                baseline_runtime_runner=(
                    baseline_runtime_runner
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
            calls,
            [
                "seed",
                "semantic",
                "snapshot",
                "baseline",
                "pipeline",
                "adjudication",
            ],
        )

        self.assertEqual(
            captured[
                "additional"
            ],
            [
                baseline_run
            ],
        )

        self.assertEqual(
            result[
                "primary_baseline"
            ][
                "status"
            ],
            "persisted",
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )

    def test_primary_baseline_failure_is_best_effort(
        self,
    ):
        calls = []

        def seed_persister(
            **kwargs,
        ):
            return {
                "claim": {
                    "id": "claim-1",
                    "subject_key": "subject-1",
                    "canonical_text": (
                        "Player A joins Team B"
                    ),
                },
                "source": {
                    "id": "source-1",
                },
            }

        def semantic_assessor(
            **kwargs,
        ):
            raise RuntimeError(
                "semantic failure"
            )

        def pipeline_runner(
            **kwargs,
        ):
            calls.append(
                "pipeline"
            )

            return self.pipeline()

        def adjudication_runner(
            **kwargs,
        ):
            calls.append(
                "adjudication"
            )

            self.assertEqual(
                kwargs[
                    "additional_evaluator_runs"
                ],
                [],
            )

            return {
                "version": (
                    ARTICLE_ADJUDICATION_RUNTIME_VERSION
                ),
                "status": (
                    "no_evaluator_runs"
                ),
            }

        result = (
            run_article_intelligence_shadow(
                **self.base_shadow_kwargs(),
                seed_persister=(
                    seed_persister
                ),
                semantic_assessor=(
                    semantic_assessor
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
            calls,
            [
                "pipeline",
                "adjudication",
            ],
        )

        self.assertEqual(
            result[
                "primary_baseline"
            ][
                "status"
            ],
            "failed",
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )

    def test_article_adjudication_carries_baseline_and_graph_runs_together(
        self,
    ):
        captured = {}

        graph_run = {
            "run_id": "graph-run",
            "evaluator_id": "graph-v1",
            "evaluator_family": (
                "provenance_graph"
            ),
            "derivation_mode": "mixed",
            "judgments": [
                {
                    "id": "graph-judgment",
                    "field": "stance",
                    "value": "supports",
                    "confidence": 1.0,
                    "evaluator_id": "graph-v1",
                    "evaluator_family": (
                        "provenance_graph"
                    ),
                    "basis_class": (
                        "provenance_graph"
                    ),
                    "evidence_ids": [
                        "evidence-graph"
                    ],
                    "training_eligible": False,
                },
            ],
        }

        baseline_run = {
            "run_id": "baseline-run",
            "evaluator_id": "semantic-v1",
            "evaluator_family": (
                "observation_semantic_model"
            ),
            "derivation_mode": (
                "model_assisted"
            ),
            "judgments": [
                {
                    "id": "baseline-judgment",
                    "field": (
                        "authority_class"
                    ),
                    "value": "none",
                    "confidence": 0.91,
                    "evaluator_id": (
                        "semantic-v1"
                    ),
                    "evaluator_family": (
                        "observation_semantic_model"
                    ),
                    "basis_class": (
                        "model_inference"
                    ),
                    "evidence_ids": [
                        "evidence-baseline"
                    ],
                    "training_eligible": False,
                },
            ],
        }

        def history_runner(
            **kwargs,
        ):
            captured[
                "runs"
            ] = kwargs[
                "evaluator_runs"
            ]

            return {
                "status": "persisted",
                "revision": {
                    "revision_id": "revision-1",
                    "transitions": [],
                },
                "persistence": {
                    "transition_count": 0,
                },
            }

        pipeline = self.pipeline()

        result = (
            run_article_adjudication_runtime(
                claim={
                    "id": "claim-1",
                },
                pipeline=pipeline,
                as_of=(
                    "2026-08-15T08:00:00+00:00"
                ),
                connection_factory=(
                    lambda: None
                ),
                additional_evaluator_runs=[
                    baseline_run
                ],
                evaluator_run_builder=(
                    lambda **kwargs: [
                        graph_run
                    ]
                ),
                latest_loader=(
                    lambda **kwargs: None
                ),
                history_runner=(
                    history_runner
                ),
            )
        )

        self.assertEqual(
            {
                run[
                    "run_id"
                ]
                for run
                in captured[
                    "runs"
                ]
            },
            {
                "graph-run",
                "baseline-run",
            },
        )

        self.assertEqual(
            result[
                "evaluator_run_count"
            ],
            2,
        )

        self.assertEqual(
            result[
                "graph_evaluator_run_count"
            ],
            1,
        )

        self.assertEqual(
            result[
                "carried_evaluator_run_count"
            ],
            1,
        )

    def test_baseline_runtime_does_not_rewind_combined_history(
        self,
    ):
        raw = {
            "claim_relevance": "same_claim",
            "source_role": "publisher",
            "authority_class": "none",
            "reliability_class": "unknown",
            "provenance_class": (
                "firsthand_reporting"
            ),
            "stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_targets": [],
            "field_evidence": [],
            "source_role_confidence": 0.9,
            "authority_confidence": 0.9,
            "reliability_confidence": 0.5,
            "provenance_confidence": 0.9,
            "stance_confidence": 0.9,
            "dependency_confidence": 0.9,
        }

        assessment = (
            normalize_claim_observation_semantics(
                raw,
                claim_id="claim-1",
                source_url=(
                    "https://example.com/story"
                ),
                context={},
                evaluator_id=(
                    "semantic-v1"
                ),
            )
        )

        baseline = (
            build_model_assisted_baseline_evaluator_runs(
                semantic_assessment=(
                    assessment
                )
            )
        )

        latest_runs = copy.deepcopy(
            baseline[
                "evaluator_runs"
            ]
        )

        latest_runs.append(
            {
                "run_id": "graph-run",
                "evaluator_id": "graph-v1",
                "evaluator_family": (
                    "provenance_graph"
                ),
                "derivation_mode": "mixed",
                "judgments": [],
            }
        )

        history_calls = []

        result = (
            persist_model_assisted_baseline_revision(
                assembly={
                    "claim_id": "claim-1",
                    "source_url": (
                        "https://example.com/story"
                    ),
                    "snapshot": {
                        "as_of": (
                            "2026-08-15T08:00:00+00:00"
                        ),
                    },
                },
                semantic_assessment=(
                    assessment
                ),
                source_id="source-1",
                subject_key="subject-1",
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    lambda: None
                ),
                snapshot_persister=(
                    lambda **kwargs: {
                        "version": (
                            MODEL_ASSISTED_SNAPSHOT_PERSISTENCE_VERSION
                        ),
                        "claim_id": (
                            "claim-1"
                        ),
                        "snapshot_evidence": {
                            "id": (
                                "evidence-1"
                            ),
                            "verification_status": (
                                "unverified"
                            ),
                        },
                    }
                ),
                latest_loader=(
                    lambda **kwargs: {
                        "revision_id": (
                            "combined-revision"
                        ),
                        "as_of": (
                            "2026-08-15T09:00:00+00:00"
                        ),
                        "trigger": {
                            "type": (
                                "evaluator_refresh"
                            ),
                            "evidence_ids": [],
                        },
                        "adjudication": {
                            "evaluators": (
                                latest_runs
                            ),
                        },
                    }
                ),
                history_writer=(
                    lambda **kwargs: (
                        history_calls.append(
                            kwargs
                        )
                    )
                ),
            )
        )

        self.assertEqual(
            history_calls,
            [],
        )

        self.assertEqual(
            result[
                "status"
            ],
            "baseline_already_present",
        )

        self.assertEqual(
            result[
                "revision"
            ][
                "revision_id"
            ],
            "combined-revision",
        )


class ProviderFreeArticleBaselinePersistenceTests(
    unittest.TestCase
):
    URL = (
        "https://publisher.example/"
        "player-a-set-to-join-team-b"
    )
    OBSERVED_AT = (
        "2026-09-10T08:00:00+00:00"
    )

    def setUp(
        self,
    ):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = (
            Path(self.tmp.name)
            / "article-baseline.db"
        )

        def factory():
            conn = sqlite3.connect(
                self.path
            )
            conn.row_factory = sqlite3.Row
            conn.execute(
                "PRAGMA foreign_keys=ON"
            )
            return conn

        self.factory = factory
        bootstrap = self.factory()
        bootstrap.executescript(
            SCHEMA
        )
        bootstrap.close()

    def tearDown(
        self,
    ):
        self.tmp.cleanup()

    def persist_media(
        self,
        *,
        url=None,
        title=(
            "Player A set to join Team B"
        ),
    ):
        target_url = url or self.URL

        return upsert_media_item(
            url=target_url,
            mode="article",
            title=title,
            content_hash="content-hash",
            seen_at=self.OBSERVED_AT,
            normalize_url=(
                normalized_analysis_url
            ),
            id_resolver=(
                lambda value: (
                    media_item_id_for_url(
                        value,
                        normalize_url=(
                            normalized_analysis_url
                        ),
                    )
                )
            ),
            connection_factory=(
                self.factory
            ),
        )

    def baseline_counts(
        self,
    ):
        conn = self.factory()

        try:
            return {
                table: conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                for table in (
                    "intelligence_sources",
                    "intelligence_claims",
                    "source_observations",
                    "claim_links",
                    "intelligence_stories",
                    "story_media_links",
                    "story_claim_links",
                    "evidence_records",
                    "observation_dependencies",
                    (
                        "observation_"
                        "independence_assertions"
                    ),
                    (
                        "verified_claim_"
                        "entity_participants"
                    ),
                    (
                        "verified_source_"
                        "entity_bindings"
                    ),
                )
            }

        finally:
            conn.close()

    def test_repeated_baseline_is_idempotent_and_result_context_reads_it(
        self,
    ):
        media = self.persist_media()
        kwargs = {
            "media_item_id": media["id"],
            "observed_at": (
                media["first_seen_at"]
            ),
            "title": media["title"],
            "url": self.URL,
            "article_type": (
                "transfer_report"
            ),
            "type_confidence": 0.91,
            "normalize_url": (
                normalized_analysis_url
            ),
            "connection_factory": (
                self.factory
            ),
        }

        first = (
            persist_article_intelligence_baseline(
                **kwargs
            )
        )
        first_counts = (
            self.baseline_counts()
        )
        second = (
            persist_article_intelligence_baseline(
                **kwargs
            )
        )

        self.assertEqual(
            first["status"],
            "baseline_persisted",
        )
        self.assertEqual(
            first["claim"]["id"],
            second["claim"]["id"],
        )
        self.assertEqual(
            first["source"]["id"],
            second["source"]["id"],
        )
        self.assertEqual(
            first["observation"]["id"],
            second["observation"]["id"],
        )
        self.assertEqual(
            first["claim_link"]["id"],
            second["claim_link"]["id"],
        )
        self.assertEqual(
            first_counts,
            self.baseline_counts(),
        )

        self.assertEqual(
            first_counts[
                "intelligence_sources"
            ],
            1,
        )
        self.assertEqual(
            first_counts[
                "intelligence_claims"
            ],
            1,
        )
        self.assertEqual(
            first_counts[
                "source_observations"
            ],
            1,
        )
        self.assertEqual(
            first_counts[
                "claim_links"
            ],
            1,
        )

        conn = self.factory()

        try:
            persisted = conn.execute(
                """
                SELECT media.source_id,
                       source.canonical_domain,
                       observation.status,
                       link.relationship_type
                FROM media_items AS media
                JOIN intelligence_sources AS source
                  ON source.id = media.source_id
                JOIN source_observations AS observation
                  ON observation.media_item_id = media.id
                JOIN claim_links AS link
                  ON link.source_observation_id = observation.id
                WHERE media.id = ?
                """,
                (
                    media["id"],
                ),
            ).fetchone()

        finally:
            conn.close()

        self.assertEqual(
            persisted["source_id"],
            first["source"]["id"],
        )
        self.assertEqual(
            persisted["canonical_domain"],
            "publisher.example",
        )
        self.assertEqual(
            persisted["status"],
            "reported",
        )
        self.assertEqual(
            persisted["relationship_type"],
            "reports",
        )

        context = build_analysis_result_context(
            url=self.URL,
            connection_factory=(
                self.factory
            ),
        )

        self.assertEqual(
            context["status"],
            "ready",
        )
        self.assertEqual(
            context["media"]["id"],
            media["id"],
        )
        self.assertEqual(
            context["media"][
                "source_domain"
            ],
            "publisher.example",
        )
        self.assertEqual(
            context["primary_claim"]["id"],
            first["claim"]["id"],
        )
        self.assertEqual(
            context["primary_claim"][
                "canonical_text"
            ],
            media["title"],
        )
        self.assertIsNone(
            context["story"]
        )
        self.assertEqual(
            context["related_reports"],
            [],
        )
        self.assertEqual(
            context["stakeholders"],
            [],
        )
        self.assertFalse(
            context["policy"][
                "provider_call_performed"
            ]
        )

        for table in (
            "intelligence_stories",
            "story_media_links",
            "story_claim_links",
            "evidence_records",
            "observation_dependencies",
            (
                "observation_"
                "independence_assertions"
            ),
            (
                "verified_claim_"
                "entity_participants"
            ),
            (
                "verified_source_"
                "entity_bindings"
            ),
        ):
            self.assertEqual(
                first_counts[table],
                0,
                table,
            )

    def test_non_claim_article_persists_only_source_media_baseline(
        self,
    ):
        media = self.persist_media(
            url=(
                "https://publisher.example/"
                "tactical-analysis"
            ),
            title="How Team B built its press",
        )

        result = (
            persist_article_intelligence_baseline(
                media_item_id=media["id"],
                observed_at=(
                    media["first_seen_at"]
                ),
                title=media["title"],
                url=media["canonical_url"],
                article_type=(
                    "tactical_analysis"
                ),
                type_confidence=0.93,
                normalize_url=(
                    normalized_analysis_url
                ),
                connection_factory=(
                    self.factory
                ),
            )
        )

        repeated = (
            persist_article_intelligence_baseline(
                media_item_id=media["id"],
                observed_at=(
                    media["first_seen_at"]
                ),
                title=media["title"],
                url=media["canonical_url"],
                article_type=(
                    "tactical_analysis"
                ),
                type_confidence=0.93,
                normalize_url=(
                    normalized_analysis_url
                ),
                connection_factory=(
                    self.factory
                ),
            )
        )

        self.assertEqual(
            result["status"],
            "source_media_baseline_persisted",
        )
        self.assertEqual(
            result["claim_baseline"][
                "status"
            ],
            "skipped",
        )
        self.assertEqual(
            result["claim_baseline"][
                "reason"
            ],
            "article_type_not_claim_seeded",
        )
        self.assertEqual(
            result["source"]["id"],
            repeated["source"]["id"],
        )
        self.assertIsNone(
            result["claim"]
        )
        self.assertIsNone(
            result["observation"]
        )
        self.assertIsNone(
            result["claim_link"]
        )
        self.assertIsNone(
            result["story"]
        )
        self.assertFalse(
            result["policy"][
                "provider_call_performed"
            ]
        )
        self.assertFalse(
            result["policy"][
                "truth_established"
            ]
        )

        counts = self.baseline_counts()

        self.assertEqual(
            counts[
                "intelligence_sources"
            ],
            1,
        )

        for table in (
            "intelligence_claims",
            "source_observations",
            "claim_links",
            "intelligence_stories",
            "story_media_links",
            "story_claim_links",
            "evidence_records",
            "observation_dependencies",
            (
                "observation_"
                "independence_assertions"
            ),
            (
                "verified_claim_"
                "entity_participants"
            ),
            (
                "verified_source_"
                "entity_bindings"
            ),
        ):
            self.assertEqual(
                counts[table],
                0,
                table,
            )

        conn = self.factory()

        try:
            row = conn.execute(
                """
                SELECT media.source_id,
                       source.canonical_domain
                FROM media_items AS media
                JOIN intelligence_sources AS source
                  ON source.id = media.source_id
                WHERE media.id = ?
                """,
                (
                    media["id"],
                ),
            ).fetchone()

        finally:
            conn.close()

        self.assertEqual(
            row["source_id"],
            result["source"]["id"],
        )
        self.assertEqual(
            row["canonical_domain"],
            "publisher.example",
        )

        context = build_analysis_result_context(
            url=media["canonical_url"],
            connection_factory=(
                self.factory
            ),
        )

        self.assertEqual(
            context["status"],
            "ready",
        )
        self.assertEqual(
            context["media"][
                "source_domain"
            ],
            "publisher.example",
        )
        self.assertIsNone(
            context["primary_claim"]
        )
        self.assertIsNone(
            context["story"]
        )


if __name__ == "__main__":
    unittest.main()
