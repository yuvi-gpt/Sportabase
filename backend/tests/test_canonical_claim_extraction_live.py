from __future__ import annotations

import unittest
from unittest.mock import patch

from app.intelligence import canonical_claims
from evals import canonical_claim_extraction_live as live


class TestCanonicalClaimExtractionLiveFixture(unittest.TestCase):
    def test_version_is_v1(self):
        self.assertEqual(
            live.CANONICAL_CLAIM_EXTRACTION_LIVE_VERSION,
            "canonical-claim-extraction-live-v1",
        )

    def test_exact_provider_calls_is_four(self):
        self.assertEqual(live.EXACT_PROVIDER_CALLS, 4)

    def test_client_keys_are_four_unique_buckets(self):
        self.assertEqual(len(live.CLIENT_KEYS), 4)
        self.assertEqual(len(set(live.CLIENT_KEYS.values())), 4)

    def test_live_inputs_have_exact_four_labels(self):
        self.assertEqual(
            set(live.live_inputs()),
            {"anchor", "web_positive", "youtube_positive", "hard_negative"},
        )

    def test_anchor_comes_from_frozen_bellingham_case(self):
        self.assertEqual(
            live.live_inputs()["anchor"],
            "Jude Bellingham completed his move to Real Madrid in 2023.",
        )

    def test_web_positive_comes_from_frozen_bellingham_case(self):
        self.assertEqual(
            live.live_inputs()["web_positive"],
            "Jude Bellingham signed for Real Madrid after his transfer from Borussia Dortmund.",
        )

    def test_youtube_positive_comes_from_frozen_bellingham_case(self):
        self.assertEqual(
            live.live_inputs()["youtube_positive"],
            "Real Madrid presented Jude Bellingham as a new midfielder.",
        )

    def test_allowed_entities_include_subject_and_two_clubs(self):
        self.assertEqual(
            set(live.ALLOWED_ENTITIES),
            {live.SUBJECT_KEY, live.REAL_MADRID_KEY, live.DORTMUND_KEY},
        )


class TestCanonicalClaimExtractionLiveScoring(unittest.TestCase):
    def setUp(self):
        self.anchor_candidate = canonical_claims.normalize_canonical_claim(
            {
                "subject_key": live.SUBJECT_KEY,
                "event_type": "transfer",
                "state": "completed",
                "roles": {"destination": live.REAL_MADRID_KEY},
                "facets": {"effective_period": "2023"},
            }
        )
        self.web_candidate = canonical_claims.normalize_canonical_claim(
            {
                "subject_key": live.SUBJECT_KEY,
                "event_type": "transfer",
                "state": "completed",
                "roles": {
                    "destination": live.REAL_MADRID_KEY,
                    "origin": live.DORTMUND_KEY,
                },
                "facets": {},
            }
        )
        self.youtube_candidate = canonical_claims.normalize_canonical_claim(
            {
                "subject_key": live.SUBJECT_KEY,
                "event_type": "transfer",
                "state": "completed",
                "roles": {"destination": live.REAL_MADRID_KEY},
                "facets": {},
            }
        )
        self.negative_candidate = canonical_claims.normalize_canonical_claim(
            {
                "subject_key": live.SUBJECT_KEY,
                "event_type": "match_event",
                "state": "scored",
                "roles": {},
                "facets": {"event_key": "football|match|later-league-match"},
            }
        )

    def _row(self, label, candidate):
        return {
            "label": label,
            "status": "extracted",
            "reason": "",
            "candidate": candidate,
        }

    def _passing_rows(self):
        return {
            "anchor": self._row("anchor", self.anchor_candidate),
            "web_positive": self._row("web_positive", self.web_candidate),
            "youtube_positive": self._row("youtube_positive", self.youtube_candidate),
            "hard_negative": self._row("hard_negative", self.negative_candidate),
        }

    def _passing_comparisons(self, rows):
        return {
            label: live._comparison(rows["anchor"], rows[label])
            for label in ("web_positive", "youtube_positive", "hard_negative")
        }

    def test_invalid_output_safe_row_does_not_store_raw_response(self):
        row = live._safe_extraction_row(
            label="anchor",
            parsed=None,
            error=ValueError("bad"),
        )
        self.assertEqual(row["status"], "invalid_output")
        self.assertIsNone(row["candidate"])
        self.assertFalse(row["raw_provider_response_stored"])

    def test_positive_comparison_converges(self):
        rows = self._passing_rows()
        result = live._comparison(rows["anchor"], rows["web_positive"])
        self.assertTrue(result["same_core"])
        self.assertEqual(result["status"], "same_core_no_material_conflict")

    def test_hard_negative_comparison_splits(self):
        rows = self._passing_rows()
        result = live._comparison(rows["anchor"], rows["hard_negative"])
        self.assertFalse(result["same_core"])
        self.assertEqual(result["status"], "different_core")

    def test_quality_passes_for_expected_structures(self):
        rows = self._passing_rows()
        quality = live._quality(rows, self._passing_comparisons(rows))
        self.assertEqual(quality, {"status": "pass", "failures": []})

    def test_quality_fails_when_anchor_is_not_extracted(self):
        rows = self._passing_rows()
        rows["anchor"] = {"status": "insufficient", "candidate": None}
        quality = live._quality(rows, self._passing_comparisons(rows))
        self.assertIn("anchor_not_extracted", quality["failures"])

    def test_quality_fails_when_web_positive_is_not_extracted(self):
        rows = self._passing_rows()
        rows["web_positive"] = {"status": "insufficient", "candidate": None}
        quality = live._quality(rows, self._passing_comparisons(rows))
        self.assertIn("web_positive_not_extracted", quality["failures"])

    def test_quality_fails_when_hard_negative_is_not_extracted(self):
        rows = self._passing_rows()
        rows["hard_negative"] = {"status": "insufficient", "candidate": None}
        quality = live._quality(rows, self._passing_comparisons(rows))
        self.assertIn("hard_negative_not_extracted", quality["failures"])

    def test_hard_safety_passes_for_expected_negative_split(self):
        rows = self._passing_rows()
        safety = live._hard_safety(rows, self._passing_comparisons(rows))
        self.assertEqual(safety["status"], "pass")
        self.assertFalse(safety["affects_live_merit"])

    def test_hard_safety_fails_if_hard_negative_shares_core(self):
        rows = self._passing_rows()
        comparisons = self._passing_comparisons(rows)
        comparisons["hard_negative"] = {
            "status": "same_core_no_material_conflict",
            "same_core": True,
            "same_specific": False,
            "material_conflicts": [],
        }
        safety = live._hard_safety(rows, comparisons)
        self.assertEqual(safety["status"], "fail")
        self.assertIn("hard_negative_merged_with_anchor", safety["failures"])

    def test_hard_safety_never_establishes_truth_or_authority(self):
        rows = self._passing_rows()
        safety = live._hard_safety(rows, self._passing_comparisons(rows))
        self.assertFalse(safety["establishes_truth"])
        self.assertFalse(safety["establishes_authority"])
        self.assertFalse(safety["establishes_independence"])
        self.assertFalse(safety["establishes_corroboration"])


class TestCanonicalClaimExtractionLiveCapacity(unittest.TestCase):
    @patch("evals.canonical_claim_extraction_live.capacity_snapshot")
    def test_preflight_requires_exactly_four_calls(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(usage_connection_factory=object())
        self.assertEqual(result["exact_provider_calls"], 4)
        self.assertEqual(mocked.call_args.kwargs["required_calls"], 4)

    @patch("evals.canonical_claim_extraction_live.capacity_snapshot")
    def test_preflight_uses_one_call_per_client(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(usage_connection_factory=object())
        self.assertEqual(mocked.call_args.kwargs["max_calls_per_client"], 1)

    @patch("evals.canonical_claim_extraction_live.capacity_snapshot")
    def test_preflight_uses_all_four_client_keys(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(usage_connection_factory=object())
        self.assertEqual(
            set(mocked.call_args.kwargs["client_keys"]),
            set(live.CLIENT_KEYS.values()),
        )

    @patch("evals.canonical_claim_extraction_live.capacity_snapshot")
    def test_preflight_declares_no_repeated_anchor_calls(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(usage_connection_factory=object())
        self.assertTrue(result["one_call_per_unique_source"])
        self.assertFalse(result["pairwise_repeated_anchor_calls"])
        self.assertTrue(result["call_five_forbidden"])


class TestCanonicalClaimExtractionLiveValidation(unittest.TestCase):
    def test_evaluator_rejects_nonfour_budget(self):
        with self.assertRaises(live.CanonicalClaimExtractionLiveInputError):
            live.evaluate_live_extraction(
                api_key="x",
                usage_connection_factory=object(),
                max_calls=3,
                client=object(),
            )

    def test_evaluator_requires_key_or_client(self):
        with self.assertRaises(live.CanonicalClaimExtractionLiveInputError):
            live.evaluate_live_extraction(
                api_key="",
                usage_connection_factory=object(),
                max_calls=4,
                client=None,
            )

    def test_evaluator_requires_usage_database_when_factory_absent(self):
        with self.assertRaises(live.CanonicalClaimExtractionLiveInputError):
            live.evaluate_live_extraction(
                api_key="x",
                usage_db_path=None,
                usage_connection_factory=None,
                max_calls=4,
                client=object(),
            )


if __name__ == "__main__":
    unittest.main()
