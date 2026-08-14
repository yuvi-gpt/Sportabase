import sqlite3
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

from app import main
from app.db.schema import SCHEMA
from app.intelligence.claims import (
    upsert_intelligence_claim,
)
from app.services.corroboration_graph import (
    build_corroboration_graph_plan,
)
from app.services.corroboration_materialization import (
    CORROBORATION_GRAPH_MATERIALIZATION_VERSION,
    materialize_corroboration_graph_plan,
)


class CorroborationGraphMaterializationTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(self.temp.name)
            / "graph.sqlite3"
        )

        conn = self.connection()

        try:
            conn.executescript(
                SCHEMA
            )
            conn.commit()
        finally:
            conn.close()

        self.claim = (
            upsert_intelligence_claim(
                canonical_key=(
                    "transfer|alpha|beta|agreement"
                ),
                subject_key=(
                    "transfer|alpha|beta"
                ),
                canonical_text=(
                    "Player Alpha has agreed to "
                    "join Club Beta."
                ),
                claim_type="assertion",
                seen_at=(
                    "2026-08-13T12:00:00+00:00"
                ),
                id_resolver=(
                    main.claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection
                ),
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def connection(self):
        conn = sqlite3.connect(
            self.db_path
        )
        conn.row_factory = sqlite3.Row
        conn.execute(
            "PRAGMA foreign_keys = ON"
        )
        return conn

    def count(self, table):
        conn = self.connection()

        try:
            row = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table}"
            ).fetchone()

            return int(row["n"])
        finally:
            conn.close()

    def candidates(
        self,
        *,
        second=False,
    ):
        rows = [
            {
                "resolution_status": "resolved",
                "final_url": (
                    "https://news.example/story"
                ),
                "final_source_domain": (
                    "news.example"
                ),
                "final_same_source_domain": False,
                "published_at": (
                    "2026-08-13T12:00:00+00:00"
                ),
                "publication_time_status": "found",
                "publication_time_version": (
                    "publication-time-v1"
                ),
                "publication_time_source_type": (
                    "meta"
                ),
                "publication_time_source_key": (
                    "article:published_time"
                ),
                "provider": "brave_news",
                "provider_rank": 1,
            }
        ]

        if second:
            rows.append(
                {
                    **rows[0],
                    "final_url": (
                        "https://other.example/story"
                    ),
                    "final_source_domain": (
                        "other.example"
                    ),
                    "provider_rank": 2,
                }
            )

        return rows

    def semantic_rows(
        self,
        *,
        stance="supports",
        dependency=False,
        second=False,
    ):
        def row(
            url,
            rank,
        ):
            assessment = {
                "claim_relationship_type": (
                    stance
                ),
                "stance_confidence": 0.91,
                "explicit_dependency_present": (
                    dependency
                ),
                "dependency_relationship": (
                    "attributed_to"
                    if dependency
                    else ""
                ),
                "dependency_targets": (
                    [
                        "https://espn.com/"
                        "source-story"
                    ]
                    if dependency
                    else []
                ),
                "dependency_evidence": (
                    [
                        "According to ESPN."
                    ]
                    if dependency
                    else []
                ),
                "dependency_confidence": 0.80,
            }

            return {
                "candidate_url": url,
                "provider": "brave_news",
                "provider_rank": rank,
                "status": "assessed",
                "semantic_result": {
                    "status": "assessed",
                    "assessment": assessment,
                },
            }

        rows = [
            row(
                "https://news.example/story",
                1,
            )
        ]

        if second:
            rows.append(
                row(
                    "https://other.example/story",
                    2,
                )
            )

        return rows

    def plan(
        self,
        *,
        stance="supports",
        dependency=False,
        second=False,
    ):
        return (
            build_corroboration_graph_plan(
                claim={
                    "id": self.claim["id"],
                    "subject_key": (
                        self.claim[
                            "subject_key"
                        ]
                    ),
                    "canonical_text": (
                        self.claim[
                            "canonical_text"
                        ]
                    ),
                },
                collection={
                    "resolved_candidates": (
                        self.candidates(
                            second=second
                        )
                    ),
                },
                semantic_batch={
                    "candidate_assessments": (
                        self.semantic_rows(
                            stance=stance,
                            dependency=dependency,
                            second=second,
                        )
                    ),
                },
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

    def materialize(self, plan):
        return (
            materialize_corroboration_graph_plan(
                plan=plan,
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
                connection_factory=(
                    self.connection
                ),
            )
        )

    def test_support_persists_source_observation_and_claim_link(
        self,
    ):
        result = self.materialize(
            self.plan()
        )

        self.assertEqual(
            result["version"],
            CORROBORATION_GRAPH_MATERIALIZATION_VERSION,
        )

        self.assertEqual(
            result["status"],
            "materialized",
        )

        self.assertEqual(
            self.count(
                "intelligence_sources"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            1,
        )

        conn = self.connection()

        try:
            link = conn.execute(
                "SELECT relationship_type "
                "FROM claim_links"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            link["relationship_type"],
            "supports",
        )

    def test_contradiction_persists_as_contradiction(
        self,
    ):
        self.materialize(
            self.plan(
                stance="contradicts"
            )
        )

        conn = self.connection()

        try:
            row = conn.execute(
                "SELECT relationship_type "
                "FROM claim_links"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            row["relationship_type"],
            "contradicts",
        )

    def test_alignment_persists_as_aligned_to(
        self,
    ):
        self.materialize(
            self.plan(
                stance="aligned_to"
            )
        )

        conn = self.connection()

        try:
            row = conn.execute(
                "SELECT relationship_type "
                "FROM claim_links"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(
            row["relationship_type"],
            "aligned_to",
        )

    def test_explicit_dependency_persists_to_upstream_source(
        self,
    ):
        result = self.materialize(
            self.plan(
                dependency=True
            )
        )

        self.assertEqual(
            result["counts"][
                "dependencies_created"
            ],
            1,
        )

        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            1,
        )

        # Candidate source + explicit upstream source.
        self.assertEqual(
            self.count(
                "intelligence_sources"
            ),
            2,
        )

        conn = self.connection()

        try:
            dependency = conn.execute(
                "SELECT "
                "upstream_source_id, "
                "upstream_source_observation_id "
                "FROM observation_dependencies"
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(
            dependency[
                "upstream_source_id"
            ]
        )

        self.assertIsNone(
            dependency[
                "upstream_source_observation_id"
            ]
        )

    def test_no_dependency_creates_no_dependency_or_independence(
        self,
    ):
        result = self.materialize(
            self.plan()
        )

        self.assertEqual(
            result["counts"][
                "dependencies_created"
            ],
            0,
        )

        self.assertEqual(
            result["counts"][
                "independence_assertions_created"
            ],
            0,
        )

        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "observation_independence_assertions"
            ),
            0,
        )

    def test_exact_retry_is_idempotent(
        self,
    ):
        plan = self.plan(
            dependency=True
        )

        first = self.materialize(
            plan
        )

        second = self.materialize(
            plan
        )

        self.assertEqual(
            first["counts"][
                "source_observations_created"
            ],
            1,
        )

        self.assertEqual(
            second["counts"][
                "source_observations_created"
            ],
            0,
        )

        self.assertEqual(
            second["counts"][
                "claim_links_created"
            ],
            0,
        )

        self.assertEqual(
            second["counts"][
                "dependencies_created"
            ],
            0,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "observation_dependencies"
            ),
            1,
        )

    def test_plan_is_fully_validated_before_writes(
        self,
    ):
        plan = self.plan()

        plan["actions"][0][
            "claim_link"
        ]["claim_id"] = "wrong-claim"

        with self.assertRaises(
            ValueError
        ):
            self.materialize(
                plan
            )

        self.assertEqual(
            self.count(
                "intelligence_sources"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            0,
        )

    def test_empty_plan_makes_no_writes(
        self,
    ):
        plan = {
            "version": (
                "corroboration-graph-plan-v1"
            ),
            "claim_id": self.claim["id"],
            "actions": [],
        }

        result = self.materialize(
            plan
        )

        self.assertEqual(
            result["status"],
            "no_materializable_actions",
        )

        self.assertEqual(
            self.count(
                "intelligence_sources"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "source_observations"
            ),
            0,
        )

    def test_two_sources_do_not_create_independence(
        self,
    ):
        result = self.materialize(
            self.plan(
                second=True
            )
        )

        self.assertEqual(
            result["counts"]["actions"],
            2,
        )

        self.assertEqual(
            self.count(
                "source_observations"
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
                "observation_independence_assertions"
            ),
            0,
        )

    def test_dependency_does_not_invent_upstream_observation(
        self,
    ):
        result = self.materialize(
            self.plan(
                dependency=True
            )
        )

        dependency = (
            result["results"][0][
                "dependencies"
            ][0]
        )

        self.assertEqual(
            dependency[
                "upstream_observation_id"
            ],
            "",
        )

        # Only the actual candidate report becomes
        # an observation. The attributed source does
        # not gain a fabricated report observation.
        self.assertEqual(
            self.count(
                "source_observations"
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
