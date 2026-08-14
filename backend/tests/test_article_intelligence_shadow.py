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


from app.services.article_intelligence_shadow import (
    ARTICLE_INTELLIGENCE_SHADOW_VERSION,
    build_article_primary_claim_seed,
    persist_article_primary_claim_seed,
    run_article_intelligence_shadow,
)
from app.services.intelligence_pipeline import (
    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION,
)


class ArticleIntelligenceShadowTests(
    unittest.TestCase
):
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

    def base_kwargs(
        self,
    ):
        return {
            "enabled": True,
            "media_item_id": "media-1",
            "observed_at": (
                "2026-08-14T06:00:00+00:00"
            ),
            "title": (
                "Driver A set to join Team B"
            ),
            "article_text": (
                "Article body reporting "
                "the proposed move."
            ),
            "url": (
                "https://example.com/story"
            ),
            "article_type": (
                "transfer_report"
            ),
            "type_confidence": 0.82,
            "legacy_score": {
                "total": 72,
                "components": {
                    "corroboration": 4,
                },
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

    def test_shadow_disabled_has_no_work(
        self,
    ):
        kwargs = self.base_kwargs()
        kwargs["enabled"] = False

        result = (
            run_article_intelligence_shadow(
                **kwargs
            )
        )

        self.assertEqual(
            result["reason"],
            "shadow_disabled",
        )

    def test_missing_news_key_skips(
        self,
    ):
        kwargs = self.base_kwargs()
        kwargs["news_api_key"] = ""

        result = (
            run_article_intelligence_shadow(
                **kwargs
            )
        )

        self.assertEqual(
            result["reason"],
            "news_api_key_missing",
        )

    def test_missing_gemini_skips(
        self,
    ):
        kwargs = self.base_kwargs()
        kwargs["gemini_client"] = None

        result = (
            run_article_intelligence_shadow(
                **kwargs
            )
        )

        self.assertEqual(
            result["reason"],
            "gemini_unavailable",
        )

    def test_non_claim_article_type_skips(
        self,
    ):
        kwargs = self.base_kwargs()

        kwargs[
            "article_type"
        ] = "opinion_analysis"

        result = (
            run_article_intelligence_shadow(
                **kwargs
            )
        )

        self.assertEqual(
            result["reason"],
            "article_type_not_claim_seeded",
        )

    def test_claim_seed_is_deterministic(
        self,
    ):
        kwargs = {
            "media_item_id": "media-1",
            "title": (
                "Driver A set to join Team B"
            ),
            "url": (
                "HTTPS://EXAMPLE.COM/story#x"
            ),
            "article_type": (
                "transfer_report"
            ),
            "observed_at": (
                "2026-08-14T06:00:00+00:00"
            ),
            "normalize_url": (
                self.normalize_url
            ),
        }

        first = (
            build_article_primary_claim_seed(
                **kwargs
            )
        )

        second = (
            build_article_primary_claim_seed(
                **kwargs
            )
        )

        self.assertEqual(
            first[
                "canonical_key"
            ],
            second[
                "canonical_key"
            ],
        )

        self.assertEqual(
            first[
                "canonical_url"
            ],
            "https://example.com/story",
        )

    def test_claim_seed_does_not_claim_truth(
        self,
    ):
        seed = (
            build_article_primary_claim_seed(
                media_item_id="media-1",
                title="Player joins Club",
                url="https://example.com/a",
                article_type=(
                    "transfer_official"
                ),
                observed_at=(
                    "2026-08-14T06:00:00+00:00"
                ),
                normalize_url=(
                    self.normalize_url
                ),
            )
        )

        self.assertTrue(
            seed[
                "policy"
            ][
                "headline_does_not_establish_truth"
            ]
        )

    def test_seed_persistence_records_reported_support(
        self,
    ):
        seed = (
            build_article_primary_claim_seed(
                media_item_id="media-1",
                title="Player joins Club",
                url="https://example.com/a",
                article_type=(
                    "transfer_official"
                ),
                observed_at=(
                    "2026-08-14T06:00:00+00:00"
                ),
                normalize_url=(
                    self.normalize_url
                ),
            )
        )

        captured = {}

        def source_upserter(
            **kwargs,
        ):
            captured[
                "source"
            ] = kwargs

            return {
                "id": "source-1",
            }

        def claim_upserter(
            **kwargs,
        ):
            captured[
                "claim"
            ] = kwargs

            return {
                "id": "claim-1",
            }

        def observation_recorder(
            **kwargs,
        ):
            captured[
                "observation"
            ] = kwargs

            return {
                "observation": {
                    "id": "obs-1",
                },
                "created": True,
            }

        def claim_link_recorder(
            **kwargs,
        ):
            captured[
                "link"
            ] = kwargs

            return {
                "link": {
                    "id": "link-1",
                },
                "created": True,
            }

        result = (
            persist_article_primary_claim_seed(
                seed=seed,
                type_confidence=0.9,
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    lambda: None
                ),
                source_upserter=(
                    source_upserter
                ),
                claim_upserter=(
                    claim_upserter
                ),
                observation_recorder=(
                    observation_recorder
                ),
                claim_link_recorder=(
                    claim_link_recorder
                ),
            )
        )

        self.assertEqual(
            captured[
                "observation"
            ][
                "status"
            ],
            "reported",
        )

        self.assertEqual(
            captured[
                "link"
            ][
                "relationship_type"
            ],
            "supports",
        )

        self.assertFalse(
            captured[
                "link"
            ][
                "metadata"
            ][
                "truth_established"
            ]
        )

        self.assertEqual(
            result["status"],
            "seed_persisted",
        )

    def test_full_shadow_runs_pipeline_once(
        self,
    ):
        kwargs = self.base_kwargs()

        calls = []

        def seed_persister(
            **kwargs,
        ):
            calls.append(
                "seed"
            )

            return {
                "claim": {
                    "id": "claim-1",
                    "canonical_key": (
                        "claim-key"
                    ),
                    "subject_key": (
                        "subject"
                    ),
                    "canonical_text": (
                        "Driver A joins Team B"
                    ),
                    "claim_type": (
                        "headline_assertion"
                    ),
                }
            }

        def pipeline_runner(
            **kwargs,
        ):
            calls.append(
                "pipeline"
            )

            return {
                "version": (
                    SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
                ),
                "status": "completed",
                "mode": "shadow",
                "live": {
                    "merit_score_effect_enabled": (
                        False
                    ),
                    "legacy_total": 72.0,
                    "total": 72.0,
                },
                "stages": {
                    "merit_overlay": {
                        "signal": (
                            "support_independence_unknown"
                        ),
                        "proposed": {
                            "adjustment": 0.0,
                            "shadow_total": 72.0,
                        },
                    },
                    "independence_plan": {
                        "counts": {
                            "verification_pairs": 2,
                        }
                    },
                    "corroboration_pipeline": {
                        "stages": {
                            "candidate_collection": {
                                "counts": {
                                    "resolved": 3,
                                }
                            }
                        }
                    },
                },
            }

        result = (
            run_article_intelligence_shadow(
                **kwargs,
                seed_persister=(
                    seed_persister
                ),
                pipeline_runner=(
                    pipeline_runner
                ),
            )
        )

        self.assertEqual(
            calls,
            [
                "seed",
                "pipeline",
            ],
        )

        self.assertEqual(
            result["status"],
            "completed",
        )

        self.assertEqual(
            result[
                "candidate_count"
            ],
            3,
        )

        self.assertEqual(
            result[
                "verification_pairs"
            ],
            2,
        )

    def test_shadow_summary_has_no_live_effect(
        self,
    ):
        kwargs = self.base_kwargs()

        result = (
            run_article_intelligence_shadow(
                **kwargs,
                seed_persister=(
                    lambda **kwargs: {
                        "claim": {
                            "id": "claim-1",
                        }
                    }
                ),
                pipeline_runner=(
                    lambda **kwargs: {
                        "version": (
                            SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
                        ),
                        "status": "completed",
                        "mode": "shadow",
                        "live": {
                            "merit_score_effect_enabled": (
                                False
                            ),
                            "total": 72.0,
                        },
                        "stages": {
                            "merit_overlay": {
                                "signal": (
                                    "verified_corroboration"
                                ),
                                "proposed": {
                                    "adjustment": 6.0,
                                    "shadow_total": 78.0,
                                },
                            }
                        },
                    }
                ),
            )
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )

        self.assertEqual(
            result[
                "live_total"
            ],
            72.0,
        )

        self.assertEqual(
            result[
                "shadow_total"
            ],
            78.0,
        )

    def test_shadow_rejects_live_merit_enablement(
        self,
    ):
        kwargs = self.base_kwargs()

        with self.assertRaisesRegex(
            ValueError,
            "shadow",
        ):
            run_article_intelligence_shadow(
                **kwargs,
                seed_persister=(
                    lambda **kwargs: {
                        "claim": {
                            "id": "claim-1",
                        }
                    }
                ),
                pipeline_runner=(
                    lambda **kwargs: {
                        "version": (
                            SPORTABASE_INTELLIGENCE_PIPELINE_VERSION
                        ),
                        "status": "completed",
                        "mode": "live",
                        "live": {
                            "merit_score_effect_enabled": (
                                True
                            ),
                            "total": 78.0,
                        },
                        "stages": {},
                    }
                ),
            )

    def test_wrong_pipeline_version_is_rejected(
        self,
    ):
        kwargs = self.base_kwargs()

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            run_article_intelligence_shadow(
                **kwargs,
                seed_persister=(
                    lambda **kwargs: {
                        "claim": {
                            "id": "claim-1",
                        }
                    }
                ),
                pipeline_runner=(
                    lambda **kwargs: {
                        "version": "wrong",
                    }
                ),
            )

    def test_version_constant_is_exposed(
        self,
    ):
        self.assertEqual(
            ARTICLE_INTELLIGENCE_SHADOW_VERSION,
            "article-intelligence-shadow-v1",
        )


if __name__ == "__main__":
    unittest.main()
