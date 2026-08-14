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
from app.analysis.independence_verification import (
    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION,
)
from app.services.corroboration_independence import (
    CORROBORATION_INDEPENDENCE_PLAN_VERSION,
)
from app.services.corroboration_independence_materialization import (
    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION,
)
from app.services.corroboration_independence_pipeline import (
    CORROBORATION_INDEPENDENCE_PIPELINE_VERSION,
    run_independence_verification_batch,
)
from app.services.corroboration_independence_semantics import (
    CORROBORATION_INDEPENDENCE_GEMINI_VERSION,
)


class CorroborationIndependencePipelineTests(
    unittest.TestCase
):
    def setUp(self):
        self.claim = {
            "id": "claim-1",
            "subject_key": (
                "transfer|alpha|beta"
            ),
            "canonical_text": (
                "Player Alpha has agreed "
                "to join Club Beta."
            ),
        }

        self.pair = {
            "pair_id": "pair-1",
            "claim_id": "claim-1",
            "status": (
                "verification_required"
            ),
            "observation_a_id": (
                "obs-a"
            ),
            "observation_b_id": (
                "obs-b"
            ),
            "source_a_id": (
                "source-a"
            ),
            "source_b_id": (
                "source-b"
            ),
            "provenance_url_a": (
                "https://a.example/story"
            ),
            "provenance_url_b": (
                "https://b.example/story"
            ),
        }

        self.plan = {
            "version": (
                CORROBORATION_INDEPENDENCE_PLAN_VERSION
            ),
            "claim_id": "claim-1",
            "status": (
                "verification_pairs_available"
            ),
            "pairs": [
                self.pair,
            ],
        }

        self.article_texts = {
            "https://a.example/story": (
                "A Sports sources say "
                "the agreement is done."
            ),
            "https://b.example/story": (
                "B Sports understands from "
                "club sources that terms "
                "are agreed."
            ),
        }

    def semantic(
        self,
        *,
        status="assessed",
        positive=True,
    ):
        assessment_status = (
            "positive_independence_evidence"
            if positive
            else "insufficient_evidence"
        )

        return {
            "version": (
                CORROBORATION_INDEPENDENCE_GEMINI_VERSION
            ),
            "claim_id": "claim-1",
            "pair_id": "pair-1",
            "status": status,
            "assessment": (
                {
                    "version": (
                        CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION
                    ),
                    "claim_id": (
                        "claim-1"
                    ),
                    "pair_id": (
                        "pair-1"
                    ),
                    "status": (
                        assessment_status
                    ),
                    (
                        "positive_independence_"
                        "evidence_present"
                    ): positive,
                }
                if status == "assessed"
                else None
            ),
        }

    def materialization(
        self,
        *,
        status=(
            "materialized_verified_independence"
        ),
    ):
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
            ),
            "claim_id": "claim-1",
            "pair_id": "pair-1",
            "status": status,
        }

    def run_batch(
        self,
        *,
        plan=None,
        article_texts=None,
        assessor=None,
        materializer=None,
        evidence_loader=None,
    ):
        if assessor is None:
            assessor = (
                lambda **kwargs: (
                    self.semantic()
                )
            )

        if materializer is None:
            materializer = (
                lambda **kwargs: (
                    self.materialization()
                )
            )

        if evidence_loader is None:
            evidence_loader = (
                lambda **kwargs: {
                    "version": (
                        EVIDENCE_ANALYSIS_BUNDLE_VERSION
                    ),
                    "marker": "final",
                }
            )

        return (
            run_independence_verification_batch(
                claim=self.claim,
                plan=(
                    self.plan
                    if plan is None
                    else plan
                ),
                media_item_id="media-1",
                article_texts_by_url=(
                    self.article_texts
                    if article_texts is None
                    else article_texts
                ),
                normalize_url=(
                    lambda value: (
                        str(value or "")
                        .strip()
                        .rstrip("/")
                    )
                ),
                client=object(),
                client_key="client-key",
                generator=object(),
                connection_factory=object(),
                assessor=assessor,
                materializer=materializer,
                evidence_loader=(
                    evidence_loader
                ),
            )
        )

    def test_positive_pair_runs_semantics_and_materialization(
        self,
    ):
        calls = []

        def assessor(
            **kwargs,
        ):
            calls.append(
                "semantic"
            )

            self.assertEqual(
                kwargs[
                    "article_a_text"
                ],
                (
                    "A Sports sources say "
                    "the agreement is done."
                ),
            )

            self.assertEqual(
                kwargs[
                    "article_b_text"
                ],
                (
                    "B Sports understands from "
                    "club sources that terms "
                    "are agreed."
                ),
            )

            return self.semantic()

        def materializer(
            **kwargs,
        ):
            calls.append(
                "materialize"
            )

            return (
                self.materialization()
            )

        result = self.run_batch(
            assessor=assessor,
            materializer=materializer,
        )

        self.assertEqual(
            calls,
            [
                "semantic",
                "materialize",
            ],
        )

        self.assertEqual(
            result["version"],
            CORROBORATION_INDEPENDENCE_PIPELINE_VERSION,
        )

        self.assertEqual(
            result["counts"][
                "verified_materialized"
            ],
            1,
        )

    def test_missing_article_text_skips_provider(
        self,
    ):
        calls = []

        def assessor(
            **kwargs,
        ):
            calls.append(
                kwargs
            )

            raise AssertionError(
                "assessor should not run"
            )

        result = self.run_batch(
            article_texts={
                "https://a.example/story": (
                    "Article A"
                ),
            },
            assessor=assessor,
        )

        self.assertEqual(
            calls,
            [],
        )

        self.assertEqual(
            result["results"][0][
                "status"
            ],
            "article_text_missing",
        )

        self.assertEqual(
            result["results"][0][
                "missing"
            ],
            [
                "article_b",
            ],
        )

    def test_unavailable_semantics_does_not_materialize(
        self,
    ):
        materialize_calls = []

        def materializer(
            **kwargs,
        ):
            materialize_calls.append(
                kwargs
            )

            raise AssertionError(
                "materializer should not run"
            )

        result = self.run_batch(
            assessor=(
                lambda **kwargs: (
                    self.semantic(
                        status=(
                            "unavailable"
                        ),
                    )
                )
            ),
            materializer=(
                materializer
            ),
        )

        self.assertEqual(
            materialize_calls,
            [],
        )

        self.assertEqual(
            result["counts"][
                "semantic_unavailable"
            ],
            1,
        )

    def test_failed_semantics_does_not_materialize(
        self,
    ):
        calls = []

        result = self.run_batch(
            assessor=(
                lambda **kwargs: (
                    self.semantic(
                        status=(
                            "assessment_failed"
                        ),
                    )
                )
            ),
            materializer=(
                lambda **kwargs: (
                    calls.append(
                        kwargs
                    )
                )
            ),
        )

        self.assertEqual(
            calls,
            [],
        )

        self.assertEqual(
            result["counts"][
                "semantic_failed"
            ],
            1,
        )

    def test_non_positive_assessment_does_not_materialize(
        self,
    ):
        calls = []

        result = self.run_batch(
            assessor=(
                lambda **kwargs: (
                    self.semantic(
                        positive=False
                    )
                )
            ),
            materializer=(
                lambda **kwargs: (
                    calls.append(
                        kwargs
                    )
                )
            ),
        )

        self.assertEqual(
            calls,
            [],
        )

        self.assertEqual(
            result["counts"][
                "non_positive_assessments"
            ],
            1,
        )

        self.assertEqual(
            result["counts"][
                "materialization_attempts"
            ],
            0,
        )

    def test_already_materialized_is_counted(
        self,
    ):
        result = self.run_batch(
            materializer=(
                lambda **kwargs: (
                    self.materialization(
                        status=(
                            "already_materialized"
                        )
                    )
                )
            ),
        )

        self.assertEqual(
            result["counts"][
                "already_materialized"
            ],
            1,
        )

        self.assertEqual(
            result["counts"][
                "verified_materialized"
            ],
            0,
        )

    def test_not_materialized_is_counted(
        self,
    ):
        result = self.run_batch(
            materializer=(
                lambda **kwargs: (
                    self.materialization(
                        status=(
                            "not_materialized"
                        )
                    )
                )
            ),
        )

        self.assertEqual(
            result["counts"][
                "not_materialized"
            ],
            1,
        )

    def test_final_evidence_is_reloaded_once(
        self,
    ):
        calls = []

        def loader(
            **kwargs,
        ):
            calls.append(
                kwargs
            )

            return {
                "version": (
                    EVIDENCE_ANALYSIS_BUNDLE_VERSION
                ),
                "marker": (
                    "reloaded-once"
                ),
            }

        result = self.run_batch(
            evidence_loader=loader,
        )

        self.assertEqual(
            len(calls),
            1,
        )

        self.assertEqual(
            calls[0][
                "media_item_id"
            ],
            "media-1",
        )

        self.assertEqual(
            result[
                "evidence_bundle"
            ][
                "marker"
            ],
            "reloaded-once",
        )

    def test_no_pairs_calls_no_provider_but_reloads_evidence(
        self,
    ):
        plan = {
            **self.plan,
            "pairs": [],
            "status": (
                "no_verification_pairs"
            ),
        }

        calls = []

        result = self.run_batch(
            plan=plan,
            assessor=(
                lambda **kwargs: (
                    calls.append(
                        kwargs
                    )
                )
            ),
        )

        self.assertEqual(
            calls,
            [],
        )

        self.assertEqual(
            result["status"],
            "no_verification_pairs",
        )

        self.assertEqual(
            result["counts"][
                "verification_pairs"
            ],
            0,
        )

    def test_pairs_are_processed_deterministically(
        self,
    ):
        pair_two = {
            **self.pair,
            "pair_id": "pair-2",
        }

        pair_one = {
            **self.pair,
            "pair_id": "pair-1",
        }

        plan = {
            **self.plan,
            "pairs": [
                pair_two,
                pair_one,
            ],
        }

        seen = []

        def assessor(
            **kwargs,
        ):
            pair_id = kwargs[
                "pair"
            ][
                "pair_id"
            ]

            seen.append(
                pair_id
            )

            semantic = (
                self.semantic()
            )

            semantic[
                "pair_id"
            ] = pair_id

            semantic[
                "assessment"
            ][
                "pair_id"
            ] = pair_id

            return semantic

        def materializer(
            **kwargs,
        ):
            pair_id = kwargs[
                "pair"
            ][
                "pair_id"
            ]

            return {
                "version": (
                    CORROBORATION_INDEPENDENCE_MATERIALIZATION_VERSION
                ),
                "claim_id": "claim-1",
                "pair_id": (
                    pair_id
                ),
                "status": (
                    "materialized_verified_"
                    "independence"
                ),
            }

        self.run_batch(
            plan=plan,
            assessor=assessor,
            materializer=materializer,
        )

        self.assertEqual(
            seen,
            [
                "pair-1",
                "pair-2",
            ],
        )

    def test_rejects_wrong_plan_version(
        self,
    ):
        plan = {
            **self.plan,
            "version": (
                "corroboration-independence-"
                "plan-v999"
            ),
        }

        with self.assertRaisesRegex(
            ValueError,
            "Unsupported independence",
        ):
            self.run_batch(
                plan=plan,
            )

    def test_rejects_plan_claim_mismatch(
        self,
    ):
        plan = {
            **self.plan,
            "claim_id": (
                "other-claim"
            ),
        }

        with self.assertRaisesRegex(
            ValueError,
            "claim ID does not match",
        ):
            self.run_batch(
                plan=plan,
            )


if __name__ == "__main__":
    unittest.main()
