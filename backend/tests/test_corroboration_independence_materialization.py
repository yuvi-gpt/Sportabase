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
from app.analysis.evidence import (
    load_evidence_analysis_bundle_for_media_item,
)
from app.analysis.independence_verification import (
    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION,
)
from app.analysis.support import (
    build_claim_support_provenance,
)
from app.services.corroboration_independence_materialization import (
    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION,
    materialize_verified_independence_evidence,
)
from app.services.corroboration_independence_semantics import (
    CORROBORATION_INDEPENDENCE_GEMINI_MODE,
    CORROBORATION_INDEPENDENCE_GEMINI_MODEL,
    CORROBORATION_INDEPENDENCE_GEMINI_VERSION,
)


class CorroborationIndependenceMaterializationTests(
    unittest.TestCase
):
    def setUp(self):
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
            / "independence-materialization.db"
        )

        main.init_db()

        self.article_a = (
            "Sources close to Player Alpha "
            "have told A Sports that an "
            "agreement with Club Beta is done."
        )

        self.article_b = (
            "B Sports understands from club "
            "sources that Player Alpha has "
            "agreed terms with Club Beta."
        )

        self.source_a = (
            main.upsert_intelligence_source(
                url=(
                    "https://a.example/"
                ),
                display_name=(
                    "A Sports"
                ),
                seen_at=(
                    "2026-08-14T08:00:00+00:00"
                ),
            )
        )

        self.source_b = (
            main.upsert_intelligence_source(
                url=(
                    "https://b.example/"
                ),
                display_name=(
                    "B Sports"
                ),
                seen_at=(
                    "2026-08-14T08:05:00+00:00"
                ),
            )
        )

        self.media = (
            main.upsert_media_item(
                url=(
                    "https://a.example/story"
                ),
                mode="article",
                title=(
                    "Alpha agrees Beta move"
                ),
                content_hash=(
                    "materialization-origin"
                ),
                source_id=(
                    self.source_a["id"]
                ),
                seen_at=(
                    "2026-08-14T08:00:00+00:00"
                ),
            )
        )

        self.claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|alpha|beta|agreement"
                ),
                subject_key=(
                    "transfer|alpha|beta"
                ),
                canonical_text=(
                    "Player Alpha has agreed "
                    "to join Club Beta."
                ),
                claim_type=(
                    "assertion"
                ),
                seen_at=(
                    "2026-08-14T08:00:00+00:00"
                ),
            )
        )

        self.observation_a = (
            main.record_source_observation(
                source_id=(
                    self.source_a["id"]
                ),
                media_item_id=(
                    self.media["id"]
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observation_type=(
                    "report"
                ),
                status=(
                    "unresolved"
                ),
                claim_summary=(
                    self.claim[
                        "canonical_text"
                    ]
                ),
                provenance_url=(
                    "https://a.example/story"
                ),
                confidence=0.90,
                observed_at=(
                    "2026-08-14T08:00:00+00:00"
                ),
            )[
                "observation"
            ]
        )

        self.observation_b = (
            main.record_source_observation(
                source_id=(
                    self.source_b["id"]
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observation_type=(
                    "report"
                ),
                status=(
                    "unresolved"
                ),
                claim_summary=(
                    self.claim[
                        "canonical_text"
                    ]
                ),
                provenance_url=(
                    "https://b.example/story"
                ),
                confidence=0.91,
                observed_at=(
                    "2026-08-14T08:05:00+00:00"
                ),
            )[
                "observation"
            ]
        )

        for observation in (
            self.observation_a,
            self.observation_b,
        ):
            main.record_claim_link(
                claim_id=(
                    self.claim["id"]
                ),
                relationship_type=(
                    "supports"
                ),
                observed_at=(
                    observation[
                        "observed_at"
                    ]
                ),
                confidence=0.90,
                source_observation_id=(
                    observation["id"]
                ),
            )

        self.pair = {
            "pair_id": "pair-verified-1",
            "claim_id": (
                self.claim["id"]
            ),
            "status": (
                "verification_required"
            ),
            "observation_a_id": (
                self.observation_a["id"]
            ),
            "observation_b_id": (
                self.observation_b["id"]
            ),
            "source_a_id": (
                self.source_a["id"]
            ),
            "source_b_id": (
                self.source_b["id"]
            ),
            "provenance_url_a": (
                "https://a.example/story"
            ),
            "provenance_url_b": (
                "https://b.example/story"
            ),
        }

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def semantic_result(
        self,
        *,
        assessment_status=(
            "positive_independence_evidence"
        ),
    ):
        positive = (
            assessment_status
            == "positive_independence_evidence"
        )

        return {
            "version": (
                CORROBORATION_INDEPENDENCE_GEMINI_VERSION
            ),
            "mode": (
                CORROBORATION_INDEPENDENCE_GEMINI_MODE
            ),
            "model": (
                CORROBORATION_INDEPENDENCE_GEMINI_MODEL
            ),
            "claim_id": (
                self.claim["id"]
            ),
            "pair_id": (
                self.pair["pair_id"]
            ),
            "status": "assessed",
            "assessment": {
                "version": (
                    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION
                ),
                "claim_id": (
                    self.claim["id"]
                ),
                "pair_id": (
                    self.pair["pair_id"]
                ),
                "status": (
                    assessment_status
                ),
                "source_a_reporting_basis": (
                    "original_reporting"
                    if positive
                    else "unclear"
                ),
                "source_b_reporting_basis": (
                    "original_reporting"
                    if positive
                    else "unclear"
                ),
                "cross_source_dependency": (
                    "not_detected"
                    if positive
                    else "uncertain"
                ),
                "source_a_evidence": (
                    [
                        (
                            "Sources close to Player "
                            "Alpha have told A Sports"
                        ),
                    ]
                    if positive
                    else []
                ),
                "source_b_evidence": (
                    [
                        (
                            "B Sports understands from "
                            "club sources"
                        ),
                    ]
                    if positive
                    else []
                ),
                "dependency_evidence": [],
                "confidence": 0.93,
                (
                    "positive_independence_"
                    "evidence_present"
                ): positive,
                (
                    "explicit_dependency_present"
                ): False,
                (
                    "independence_established"
                ): False,
                (
                    "independence_assertion_created"
                ): False,
            },
        }

    def materialize(
        self,
        *,
        semantic_result=None,
        pair=None,
        article_a=None,
        article_b=None,
    ):
        return (
            materialize_verified_independence_evidence(
                claim=self.claim,
                pair=(
                    self.pair
                    if pair is None
                    else pair
                ),
                semantic_result=(
                    self.semantic_result()
                    if semantic_result is None
                    else semantic_result
                ),
                media_item_id=(
                    self.media["id"]
                ),
                article_a_text=(
                    self.article_a
                    if article_a is None
                    else article_a
                ),
                article_b_text=(
                    self.article_b
                    if article_b is None
                    else article_b
                ),
                normalize_url=(
                    lambda value: (
                        str(value or "")
                        .strip()
                        .rstrip("/")
                    )
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

    def table_count(
        self,
        table_name,
    ):
        conn = main.db_conn()

        try:
            row = conn.execute(
                (
                    "SELECT COUNT(*) "
                    f"FROM {table_name}"
                )
            ).fetchone()

            return int(
                row[0]
            )

        finally:
            conn.close()

    def test_positive_grounded_evidence_materializes_verified_assertion(
        self,
    ):
        result = self.materialize()

        self.assertEqual(
            result["version"],
            CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION,
        )

        self.assertEqual(
            result["status"],
            (
                "materialized_verified_"
                "independence"
            ),
        )

        self.assertEqual(
            result["counts"],
            {
                "evidence_records_created": 1,
                "evidence_links_created": 1,
                "assertions_created": 1,
            },
        )

        self.assertEqual(
            result[
                "evidence"
            ][
                "evidence_type"
            ],
            "independence_verification",
        )

        self.assertEqual(
            result[
                "evidence"
            ][
                "verification_status"
            ],
            "verified",
        )

        self.assertEqual(
            result[
                "assertion"
            ][
                "verification_status"
            ],
            "verified",
        )

        self.assertEqual(
            result[
                "assertion"
            ][
                "provenance_evidence_id"
            ],
            result[
                "evidence"
            ][
                "id"
            ],
        )

    def test_persisted_provenance_reloads_with_assertion(
        self,
    ):
        result = self.materialize()

        bundle = (
            load_evidence_analysis_bundle_for_media_item(
                media_item_id=(
                    self.media["id"]
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

        evidence_ids = {
            row["id"]
            for row in bundle[
                "evidence_records"
            ]
        }

        self.assertIn(
            result[
                "evidence"
            ][
                "id"
            ],
            evidence_ids,
        )

        self.assertEqual(
            len(
                bundle[
                    "observation_independence_assertions"
                ]
            ),
            1,
        )

        self.assertEqual(
            bundle[
                "observation_independence_assertions"
            ][0][
                "verification_status"
            ],
            "verified",
        )

    def test_verified_assertion_changes_support_provenance_state(
        self,
    ):
        self.materialize()

        bundle = (
            load_evidence_analysis_bundle_for_media_item(
                media_item_id=(
                    self.media["id"]
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

        support = (
            build_claim_support_provenance(
                bundle
            )
        )

        claim_state = (
            support["claims"][0]
        )

        self.assertEqual(
            claim_state["status"],
            (
                "verified_independent_"
                "support"
            ),
        )

        self.assertTrue(
            claim_state[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim_state[
                "corroboration_status"
            ],
            "not_assessed",
        )

    def test_exact_retry_is_idempotent(
        self,
    ):
        first = self.materialize()
        second = self.materialize()

        self.assertEqual(
            first["status"],
            (
                "materialized_verified_"
                "independence"
            ),
        )

        self.assertEqual(
            second["status"],
            "already_materialized",
        )

        self.assertEqual(
            second["counts"],
            {
                "evidence_records_created": 0,
                "evidence_links_created": 0,
                "assertions_created": 0,
            },
        )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.table_count(
                "evidence_links"
            ),
            1,
        )

        self.assertEqual(
            self.table_count(
                (
                    "observation_"
                    "independence_assertions"
                )
            ),
            1,
        )

    def test_insufficient_assessment_writes_nothing(
        self,
    ):
        result = self.materialize(
            semantic_result=(
                self.semantic_result(
                    assessment_status=(
                        "insufficient_evidence"
                    )
                )
            )
        )

        self.assertEqual(
            result["status"],
            "not_materialized",
        )

        self.assertEqual(
            result["reason"],
            "insufficient_evidence",
        )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            0,
        )

        self.assertEqual(
            self.table_count(
                (
                    "observation_"
                    "independence_assertions"
                )
            ),
            0,
        )

    def test_unavailable_semantics_writes_nothing(
        self,
    ):
        semantic = (
            self.semantic_result()
        )

        semantic[
            "status"
        ] = "unavailable"

        semantic[
            "assessment"
        ] = None

        result = self.materialize(
            semantic_result=(
                semantic
            )
        )

        self.assertEqual(
            result["reason"],
            (
                "semantic_result_not_"
                "assessed"
            ),
        )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            0,
        )

    def test_ungrounded_excerpt_is_rejected_before_write(
        self,
    ):
        semantic = (
            self.semantic_result()
        )

        semantic[
            "assessment"
        ][
            "source_b_evidence"
        ] = [
            (
                "B Sports interviewed "
                "Player Alpha exclusively"
            ),
        ]

        with self.assertRaisesRegex(
            ValueError,
            (
                "Source B independence "
                "evidence is not grounded"
            ),
        ):
            self.materialize(
                semantic_result=(
                    semantic
                )
            )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            0,
        )

        self.assertEqual(
            self.table_count(
                (
                    "observation_"
                    "independence_assertions"
                )
            ),
            0,
        )

    def test_new_pair_dependency_blocks_stale_positive_assessment(
        self,
    ):
        main.record_observation_dependency(
            relationship_type=(
                "attributed_to"
            ),
            observed_at=(
                "2026-08-14T08:05:00+00:00"
            ),
            confidence=0.95,
            downstream_source_observation_id=(
                self.observation_b["id"]
            ),
            upstream_source_observation_id=(
                self.observation_a["id"]
            ),
        )

        result = self.materialize()

        self.assertEqual(
            result["status"],
            "not_materialized",
        )

        self.assertEqual(
            result["reason"],
            "recorded_pair_dependency",
        )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            0,
        )

        self.assertEqual(
            self.table_count(
                (
                    "observation_"
                    "independence_assertions"
                )
            ),
            0,
        )

    def test_removed_support_blocks_stale_positive_assessment(
        self,
    ):
        conn = main.db_conn()

        try:
            conn.execute(
                """
                DELETE FROM claim_links
                WHERE claim_id = ?
                  AND source_observation_id = ?
                """,
                (
                    self.claim["id"],
                    self.observation_b["id"],
                ),
            )

            conn.commit()

        finally:
            conn.close()

        result = self.materialize()

        self.assertEqual(
            result["status"],
            "not_materialized",
        )

        self.assertEqual(
            result["reason"],
            (
                "pair_not_in_current_"
                "evidence_scope"
            ),
        )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            0,
        )

    def test_pair_source_identity_mismatch_is_rejected(
        self,
    ):
        pair = {
            **self.pair,
            "source_b_id": (
                self.source_a["id"]
            ),
        }

        result = self.materialize(
            pair=pair,
        )

        self.assertEqual(
            result["status"],
            "not_materialized",
        )

        self.assertEqual(
            result["reason"],
            "same_source",
        )

        self.assertEqual(
            self.table_count(
                "evidence_records"
            ),
            0,
        )

    def test_verification_time_is_latest_observation_time(
        self,
    ):
        result = self.materialize()

        self.assertEqual(
            result[
                "verification_observed_at"
            ],
            (
                "2026-08-14"
                "T08:05:00+00:00"
            ),
        )

        self.assertEqual(
            result[
                "evidence"
            ][
                "observed_at"
            ],
            (
                "2026-08-14"
                "T08:05:00+00:00"
            ),
        )

        self.assertEqual(
            result[
                "assertion"
            ][
                "observed_at"
            ],
            (
                "2026-08-14"
                "T08:05:00+00:00"
            ),
        )


if __name__ == "__main__":
    unittest.main()
