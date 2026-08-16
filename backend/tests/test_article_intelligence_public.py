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


from app.services.article_intelligence_public import (
    ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
    build_article_intelligence_public_summary,
)


class ArticleIntelligencePublicTests(
    unittest.TestCase
):
    def test_version(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {}
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                ARTICLE_INTELLIGENCE_PUBLIC_VERSION
            ),
        )

        self.assertEqual(
            ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
            "article-intelligence-public-v2",
        )

    def test_verified_corroboration(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "completed",
                    "signal": (
                        "verified_corroboration"
                    ),
                    "candidate_count": 5,
                    "verification_pairs": 3,
                }
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "available",
        )

        self.assertEqual(
            result[
                "corroboration_status"
            ],
            "established",
        )

        self.assertEqual(
            result[
                "independence_status"
            ],
            "established",
        )

        self.assertFalse(
            result[
                "affects_merit_score"
            ]
        )

        self.assertTrue(
            result[
                "provisional"
            ]
        )

    def test_live_certified_effect_is_publicly_explicit(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "skipped",
                    "reason": (
                        "shadow_disabled"
                    ),
                },
                live_merit_release={
                    "status": "applied",
                    "score_effect_applied": True,
                    "signal": (
                        "verified_corroboration"
                    ),
                    "adjustment": 6.0,
                },
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "available",
        )
        self.assertTrue(
            result[
                "affects_merit_score"
            ]
        )
        self.assertFalse(
            result[
                "provisional"
            ]
        )
        self.assertEqual(
            result[
                "signal"
            ],
            "verified_corroboration",
        )
        self.assertIn(
            "+6",
            result[
                "detail"
            ],
        )

    def test_non_applied_live_runtime_never_claims_score_effect(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "completed",
                    "signal": (
                        "verified_corroboration"
                    ),
                },
                live_merit_release={
                    "status": (
                        "legacy_fallback"
                    ),
                    "score_effect_applied": False,
                    "signal": (
                        "verified_corroboration"
                    ),
                },
            )
        )

        self.assertFalse(
            result[
                "affects_merit_score"
            ]
        )
        self.assertTrue(
            result[
                "provisional"
            ]
        )

    def test_contested_corroboration(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "completed",
                    "signal": (
                        "verified_corroboration_contested"
                    ),
                }
            )
        )

        self.assertTrue(
            result[
                "contested"
            ]
        )

        self.assertEqual(
            result[
                "corroboration_status"
            ],
            "contested",
        )

    def test_dependency_does_not_claim_independence(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "completed",
                    "signal": (
                        "support_dependency_present"
                    ),
                }
            )
        )

        self.assertEqual(
            result[
                "independence_status"
            ],
            "not_established",
        )

    def test_unknown_independence_stays_unknown(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "completed",
                    "signal": (
                        "support_independence_unknown"
                    ),
                }
            )
        )

        self.assertEqual(
            result[
                "independence_status"
            ],
            "unknown",
        )

    def test_skip_is_safe_public_copy(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "skipped",
                    "reason": (
                        "gemini_unavailable"
                    ),
                    "error": "secret internal error",
                }
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "unavailable",
        )

        self.assertNotIn(
            "error",
            result,
        )

    def test_internal_lineage_is_not_exposed(
        self,
    ):
        result = (
            build_article_intelligence_public_summary(
                {
                    "status": "completed",
                    "signal": (
                        "verified_corroboration"
                    ),
                    "adjudication": {
                        "revision_id": "private",
                        "fields_evaluated": [
                            "stance"
                        ],
                    },
                    "error": "private",
                    "policy": {
                        "internal": True
                    },
                },
                live_merit_release={
                    "status": (
                        "legacy_fallback"
                    ),
                    "score_effect_applied": False,
                    "strict_independence": {
                        "evidence_id": "private",
                    },
                },
            )
        )

        self.assertNotIn(
            "adjudication",
            result,
        )

        self.assertNotIn(
            "revision_id",
            result,
        )

        self.assertNotIn(
            "error",
            result,
        )

        self.assertNotIn(
            "policy",
            result,
        )

        self.assertNotIn(
            "strict_independence",
            result,
        )


if __name__ == "__main__":
    unittest.main()
