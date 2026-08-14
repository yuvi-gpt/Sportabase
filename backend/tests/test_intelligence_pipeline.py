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


from app.analysis.corroboration import (
    CLAIM_CORROBORATION_POLICY_VERSION,
)
from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
)
from app.analysis.merit import (
    MERIT_CORROBORATION_OVERLAY_VERSION,
)
from app.services.corroboration_independence import (
    CORROBORATION_INDEPENDENCE_PLAN_VERSION,
)
from app.services.corroboration_independence_pipeline import (
    CORROBORATION_INDEPENDENCE_PIPELINE_VERSION,
)
from app.services.corroboration_pipeline import (
    CORROBORATION_PIPELINE_VERSION,
)
from app.services.corroboration_resolution import (
    CORROBORATION_RESOLUTION_VERSION,
)
from app.services.intelligence_pipeline import (
    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
    build_pipeline_article_text_map,
    run_sportabase_intelligence_pipeline,
)


class IntelligencePipelineTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.claim = {
            "id": "claim-1",
            "canonical_key": "claim-key",
            "subject_key": "subject",
            "canonical_text": (
                "Driver A will join Team B."
            ),
            "claim_type": "assertion",
        }

        self.media_id = "media-1"

        self.source_url = (
            "https://source.example/story"
        )

        self.source_text = (
            "Original source article text."
        )

        self.legacy_score = {
            "total": 72,
            "components": {
                "corroboration": 4,
            },
        }

        self.evidence_bundle = {
            "version": (
                EVIDENCE_ANALYSIS_BUNDLE_VERSION
            ),
            "scope": {
                "media_item_id": (
                    self.media_id
                ),
            },
            "claims": [
                {
                    "id": "claim-1",
                }
            ],
        }

        self.candidate_collection = {
            "resolved_candidates": [
                {
                    "final_url": (
                        "https://candidate.example/a"
                    ),
                    "text": (
                        "Candidate article A."
                    ),
                },
                {
                    "final_url": (
                        "https://candidate.example/b"
                    ),
                    "text": (
                        "Candidate article B."
                    ),
                },
            ]
        }

        self.corroboration_state = {
            "version": (
                CLAIM_CORROBORATION_POLICY_VERSION
            ),
            "claims": [
                {
                    "claim_id": "claim-1",
                    "status": (
                        "support_independence_unknown"
                    ),
                    "corroboration_established": (
                        False
                    ),
                    "contested": False,
                    "contradiction_present": False,
                    "independent_support_established": (
                        False
                    ),
                    "supporting_source_ids": [
                        "source-a",
                        "source-b",
                    ],
                }
            ],
        }

    def normalize_url(
        self,
        value,
    ):
        return (
            str(value)
            .strip()
            .lower()
            .split(
                "#",
                1,
            )[0]
        )

    def stage_stubs(
        self,
        *,
        batch_status="completed",
        overlay_live_enabled=False,
        overlay_live_total=72.0,
    ):
        calls = []
        captured = {}

        def corroboration_runner(
            **kwargs,
        ):
            calls.append(
                "corroboration"
            )

            return {
                "version": (
                    CORROBORATION_PIPELINE_VERSION
                ),
                "status": "completed",
                "claim_id": "claim-1",
                "media_item_id": (
                    self.media_id
                ),
                "stages": {
                    "candidate_collection": (
                        self.candidate_collection
                    ),
                    "evidence_bundle": (
                        self.evidence_bundle
                    ),
                },
            }

        def plan_builder(
            *,
            evidence_bundle,
            claim_id,
        ):
            calls.append(
                "plan"
            )

            self.assertIs(
                evidence_bundle,
                self.evidence_bundle,
            )

            return {
                "version": (
                    CORROBORATION_INDEPENDENCE_PLAN_VERSION
                ),
                "claim_id": claim_id,
                "status": (
                    "verification_pairs_available"
                ),
                "pairs": [],
            }

        def batch_runner(
            **kwargs,
        ):
            calls.append(
                "batch"
            )

            captured[
                "article_texts"
            ] = dict(
                kwargs[
                    "article_texts_by_url"
                ]
            )

            return {
                "version": (
                    CORROBORATION_INDEPENDENCE_PIPELINE_VERSION
                ),
                "status": batch_status,
                "claim_id": "claim-1",
                "media_item_id": (
                    self.media_id
                ),
                "evidence_bundle": (
                    self.evidence_bundle
                ),
            }

        def resolver(
            *,
            batch_result,
        ):
            calls.append(
                "resolution"
            )

            return {
                "version": (
                    CORROBORATION_RESOLUTION_VERSION
                ),
                "status": "assessed",
                "claim_id": "claim-1",
                "media_item_id": (
                    self.media_id
                ),
                "stages": {
                    "corroboration": (
                        self.corroboration_state
                    ),
                },
            }

        def overlay_builder(
            **kwargs,
        ):
            calls.append(
                "overlay"
            )

            self.assertIs(
                kwargs[
                    "corroboration_state"
                ],
                self.corroboration_state,
            )

            return {
                "version": (
                    MERIT_CORROBORATION_OVERLAY_VERSION
                ),
                "mode": "shadow",
                "claim_id": "claim-1",
                "live": {
                    "score_effect_enabled": (
                        overlay_live_enabled
                    ),
                    "total": (
                        overlay_live_total
                    ),
                },
                "proposed": {
                    "adjustment": 0.0,
                    "shadow_total": 72.0,
                },
            }

        return {
            "calls": calls,
            "captured": captured,
            "corroboration_runner": (
                corroboration_runner
            ),
            "independence_plan_builder": (
                plan_builder
            ),
            "independence_batch_runner": (
                batch_runner
            ),
            "corroboration_resolver": (
                resolver
            ),
            "merit_overlay_builder": (
                overlay_builder
            ),
        }

    def run_pipeline(
        self,
        stubs,
    ):
        return (
            run_sportabase_intelligence_pipeline(
                claim=self.claim,
                media_item_id=(
                    self.media_id
                ),
                source_url=(
                    self.source_url
                ),
                source_article_text=(
                    self.source_text
                ),
                legacy_score=(
                    self.legacy_score
                ),
                news_api_key="fake-key",
                normalize_url=(
                    self.normalize_url
                ),
                domain_resolver=(
                    lambda url: (
                        "example"
                    )
                ),
                fetch_article=(
                    lambda url: {}
                ),
                extract_article=(
                    lambda html: {}
                ),
                gemini_client=object(),
                gemini_client_key=(
                    "fake-client"
                ),
                gemini_generator=(
                    lambda **kwargs: None
                ),
                connection_factory=(
                    lambda: None
                ),
                corroboration_runner=(
                    stubs[
                        "corroboration_runner"
                    ]
                ),
                independence_plan_builder=(
                    stubs[
                        "independence_plan_builder"
                    ]
                ),
                independence_batch_runner=(
                    stubs[
                        "independence_batch_runner"
                    ]
                ),
                corroboration_resolver=(
                    stubs[
                        "corroboration_resolver"
                    ]
                ),
                merit_overlay_builder=(
                    stubs[
                        "merit_overlay_builder"
                    ]
                ),
            )
        )

    def test_full_pipeline_stage_order(
        self,
    ):
        stubs = self.stage_stubs()

        result = self.run_pipeline(
            stubs
        )

        self.assertEqual(
            stubs["calls"],
            [
                "corroboration",
                "plan",
                "batch",
                "resolution",
                "overlay",
            ],
        )

        self.assertEqual(
            result["version"],
            SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
        )

        self.assertEqual(
            result["mode"],
            "shadow",
        )

    def test_resolved_article_text_is_reused(
        self,
    ):
        stubs = self.stage_stubs()

        result = self.run_pipeline(
            stubs
        )

        texts = stubs[
            "captured"
        ][
            "article_texts"
        ]

        self.assertEqual(
            texts[
                self.normalize_url(
                    self.source_url
                )
            ],
            self.source_text,
        )

        self.assertEqual(
            texts[
                (
                    "https://candidate.example/a"
                )
            ],
            "Candidate article A.",
        )

        self.assertEqual(
            result[
                "article_text_count"
            ],
            3,
        )

    def test_article_map_deduplicates_same_text(
        self,
    ):
        collection = {
            "resolved_candidates": [
                {
                    "final_url": (
                        "HTTPS://A.EXAMPLE/X#one"
                    ),
                    "text": "Same text.",
                },
                {
                    "final_url": (
                        "https://a.example/x#two"
                    ),
                    "text": "Same text.",
                },
            ]
        }

        result = (
            build_pipeline_article_text_map(
                source_url=(
                    "https://source.example/x"
                ),
                source_article_text=(
                    "Source."
                ),
                candidate_collection=(
                    collection
                ),
                normalize_url=(
                    self.normalize_url
                ),
            )
        )

        self.assertEqual(
            len(result),
            2,
        )

    def test_article_map_rejects_conflicting_text(
        self,
    ):
        collection = {
            "resolved_candidates": [
                {
                    "final_url": (
                        "https://a.example/x#one"
                    ),
                    "text": "First.",
                },
                {
                    "final_url": (
                        "https://a.example/x#two"
                    ),
                    "text": "Second.",
                },
            ]
        }

        with self.assertRaisesRegex(
            ValueError,
            "Conflicting article text",
        ):
            build_pipeline_article_text_map(
                source_url=(
                    self.source_url
                ),
                source_article_text=(
                    self.source_text
                ),
                candidate_collection=(
                    collection
                ),
                normalize_url=(
                    self.normalize_url
                ),
            )

    def test_bad_corroboration_version_is_rejected(
        self,
    ):
        stubs = self.stage_stubs()

        original = stubs[
            "corroboration_runner"
        ]

        def bad_runner(
            **kwargs,
        ):
            result = original(
                **kwargs
            )

            result["version"] = "wrong"

            return result

        stubs[
            "corroboration_runner"
        ] = bad_runner

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            self.run_pipeline(
                stubs
            )

    def test_bad_evidence_bundle_version_is_rejected(
        self,
    ):
        stubs = self.stage_stubs()

        self.evidence_bundle = {
            **self.evidence_bundle,
            "version": "wrong",
        }

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            self.run_pipeline(
                stubs
            )

    def test_plan_claim_mismatch_is_rejected(
        self,
    ):
        stubs = self.stage_stubs()

        original = stubs[
            "independence_plan_builder"
        ]

        def bad_plan(
            **kwargs,
        ):
            result = original(
                **kwargs
            )

            result[
                "claim_id"
            ] = "different"

            return result

        stubs[
            "independence_plan_builder"
        ] = bad_plan

        with self.assertRaisesRegex(
            ValueError,
            "plan claim ID",
        ):
            self.run_pipeline(
                stubs
            )

    def test_bad_batch_version_is_rejected(
        self,
    ):
        stubs = self.stage_stubs()

        original = stubs[
            "independence_batch_runner"
        ]

        def bad_batch(
            **kwargs,
        ):
            result = original(
                **kwargs
            )

            result[
                "version"
            ] = "wrong"

            return result

        stubs[
            "independence_batch_runner"
        ] = bad_batch

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            self.run_pipeline(
                stubs
            )

    def test_bad_resolution_version_is_rejected(
        self,
    ):
        stubs = self.stage_stubs()

        original = stubs[
            "corroboration_resolver"
        ]

        def bad_resolution(
            **kwargs,
        ):
            result = original(
                **kwargs
            )

            result[
                "version"
            ] = "wrong"

            return result

        stubs[
            "corroboration_resolver"
        ] = bad_resolution

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            self.run_pipeline(
                stubs
            )

    def test_pipeline_rejects_live_merit_enablement(
        self,
    ):
        stubs = self.stage_stubs(
            overlay_live_enabled=True,
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot enable live Merit",
        ):
            self.run_pipeline(
                stubs
            )

    def test_pipeline_rejects_live_total_mutation(
        self,
    ):
        stubs = self.stage_stubs(
            overlay_live_total=78.0,
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot change",
        ):
            self.run_pipeline(
                stubs
            )

    def test_no_verification_pairs_still_resolves_safely(
        self,
    ):
        stubs = self.stage_stubs(
            batch_status=(
                "no_verification_pairs"
            ),
        )

        result = self.run_pipeline(
            stubs
        )

        self.assertEqual(
            result["status"],
            "completed",
        )

        self.assertFalse(
            result[
                "live"
            ][
                "merit_score_effect_enabled"
            ]
        )

        self.assertEqual(
            result[
                "live"
            ][
                "total"
            ],
            72.0,
        )


if __name__ == "__main__":
    unittest.main()
