import sys
import unittest

from pathlib import Path
from unittest.mock import Mock


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.services.negative_merit_runtime import (
    NEGATIVE_MERIT_RUNTIME_VERSION,
    refresh_negative_merit_after_intelligence,
)


class NegativeMeritRefreshTests(
    unittest.TestCase
):
    @staticmethod
    def legacy():
        return {
            "total": 71,
            "badge": "Good",
            "components": {},
            "calculation": {},
            "reasons": [],
        }

    @staticmethod
    def prior():
        return {
            "version": (
                NEGATIVE_MERIT_RUNTIME_VERSION
            ),
            "status": (
                "no_certified_negative_evidence"
            ),
            "mode": "shadow",
            "live_merit_effect_enabled": False,
            "claim_truth_established": False,
            "provider_call_performed": False,
        }

    @staticmethod
    def completed_shadow():
        return {
            "status": "completed",
            "mode": "shadow",
            "live_merit_effect_enabled": False,
            "truth_established": False,
        }

    def test_completed_intelligence_reloads_fresh_evidence(
        self,
    ):
        prior = self.prior()

        bundle = {
            "claims": [
                {
                    "id": "claim-fresh-1",
                    "canonical_key": (
                        "article-primary|"
                        "media-fresh-1|"
                        "claim"
                    ),
                }
            ],
            "claim_links": [
                {
                    "id": "link-fresh-1",
                    "claim_id": (
                        "claim-fresh-1"
                    ),
                    "source_observation_id": (
                        "observation-fresh-1"
                    ),
                    "relationship_type": (
                        "contradicts"
                    ),
                }
            ],
        }

        loader = Mock(
            return_value={
                "bundle": bundle,
                "context_hash": (
                    "fresh-context-hash"
                ),
            }
        )

        refreshed_runtime = {
            "version": (
                NEGATIVE_MERIT_RUNTIME_VERSION
            ),
            "status": (
                "negative_evidence_"
                "calibration_eligible"
            ),
            "mode": "shadow",
            "live_merit_effect_enabled": False,
            "claim_truth_established": False,
            "provider_call_performed": False,
            "shadow": {
                "proposed": {
                    (
                        "eligible_for_"
                        "penalty_calibration"
                    ): True,
                    "adjustment": 0.0,
                },
                "live": {
                    "total": 71.0,
                },
            },
        }

        runtime_runner = Mock(
            return_value=(
                refreshed_runtime
            )
        )

        connection_factory = object()

        result = (
            refresh_negative_merit_after_intelligence(
                prior_result=prior,
                intelligence_shadow=(
                    self.completed_shadow()
                ),
                legacy_score=(
                    self.legacy()
                ),
                media_item_id=(
                    "media-fresh-1"
                ),
                evidence_state_loader=(
                    loader
                ),
                connection_factory=(
                    connection_factory
                ),
                runtime_runner=(
                    runtime_runner
                ),
            )
        )

        loader.assert_called_once_with(
            media_item_id=(
                "media-fresh-1"
            )
        )

        runtime_runner.assert_called_once_with(
            legacy_score=(
                self.legacy()
            ),
            evidence_bundle=bundle,
            media_item_id=(
                "media-fresh-1"
            ),
            connection_factory=(
                connection_factory
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "negative_evidence_"
                "calibration_eligible"
            ),
        )

        self.assertTrue(
            result[
                "refresh"
            ][
                "performed"
            ]
        )

        self.assertEqual(
            result[
                "refresh"
            ][
                "source"
            ],
            (
                "post_article_"
                "intelligence_shadow"
            ),
        )

        self.assertEqual(
            result[
                "refresh"
            ][
                "prior_status"
            ],
            (
                "no_certified_"
                "negative_evidence"
            ),
        )

        self.assertFalse(
            result[
                "live_merit_effect_enabled"
            ]
        )

        self.assertFalse(
            result[
                "provider_call_performed"
            ]
        )

    def test_skipped_intelligence_does_not_reload(
        self,
    ):
        prior = self.prior()

        loader = Mock()
        runtime_runner = Mock()

        result = (
            refresh_negative_merit_after_intelligence(
                prior_result=prior,
                intelligence_shadow={
                    "status": "skipped",
                    "mode": "shadow",
                },
                legacy_score=(
                    self.legacy()
                ),
                media_item_id=(
                    "media-fresh-1"
                ),
                evidence_state_loader=(
                    loader
                ),
                connection_factory=(
                    object()
                ),
                runtime_runner=(
                    runtime_runner
                ),
            )
        )

        self.assertIs(
            result,
            prior,
        )

        loader.assert_not_called()
        runtime_runner.assert_not_called()

    def test_evidence_reload_failure_preserves_prior(
        self,
    ):
        prior = self.prior()

        loader = Mock(
            side_effect=RuntimeError(
                "database unavailable"
            )
        )

        runtime_runner = Mock()

        result = (
            refresh_negative_merit_after_intelligence(
                prior_result=prior,
                intelligence_shadow=(
                    self.completed_shadow()
                ),
                legacy_score=(
                    self.legacy()
                ),
                media_item_id=(
                    "media-fresh-1"
                ),
                evidence_state_loader=(
                    loader
                ),
                connection_factory=(
                    object()
                ),
                runtime_runner=(
                    runtime_runner
                ),
            )
        )

        self.assertIs(
            result,
            prior,
        )

        runtime_runner.assert_not_called()

    def test_invalid_reloaded_bundle_preserves_prior(
        self,
    ):
        prior = self.prior()

        loader = Mock(
            return_value={
                "bundle": None,
            }
        )

        runtime_runner = Mock()

        result = (
            refresh_negative_merit_after_intelligence(
                prior_result=prior,
                intelligence_shadow=(
                    self.completed_shadow()
                ),
                legacy_score=(
                    self.legacy()
                ),
                media_item_id=(
                    "media-fresh-1"
                ),
                evidence_state_loader=(
                    loader
                ),
                connection_factory=(
                    object()
                ),
                runtime_runner=(
                    runtime_runner
                ),
            )
        )

        self.assertIs(
            result,
            prior,
        )

        runtime_runner.assert_not_called()

    def test_handler_refresh_occurs_after_intelligence_shadow(
        self,
    ):
        handler_path = (
            BACKEND_DIR
            / "app"
            / "services"
            / "analysis_handlers.py"
        )

        source = handler_path.read_text(
            encoding="utf-8"
        )

        article_start = source.index(
            "def analyze_article_impl("
        )

        intelligence_call = source.index(
            "run_article_intelligence_shadow(",
            article_start,
        )

        refresh_call = source.index(
            (
                "refresh_negative_merit_"
                "after_intelligence("
            ),
            intelligence_call,
        )

        snapshot_call = source.index(
            "persist_analysis_snapshot(",
            refresh_call,
        )

        self.assertLess(
            intelligence_call,
            refresh_call,
        )

        self.assertLess(
            refresh_call,
            snapshot_call,
        )

        refresh_region = source[
            refresh_call:
            snapshot_call
        ]

        self.assertIn(
            (
                "load_evidence_analysis_"
                "state_for_media_item"
            ),
            refresh_region,
        )

        self.assertIn(
            (
                'response.debug[\n'
                '            '
                '"negative_merit_shadow"'
            ),
            refresh_region,
        )


if __name__ == "__main__":
    unittest.main()
