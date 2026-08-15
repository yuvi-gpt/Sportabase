import copy
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.corroboration import CLAIM_CORROBORATION_POLICY_VERSION
from app.analysis.merit_score_release import (
    MERIT_SCORE_RELEASE_CASE_VERSION,
    MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
    build_merit_score_release_certificate,
    validate_merit_score_release_certificate,
)
from app.services.direct_stakeholder_independence_verifier import (
    DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
)


class MeritScoreReleaseTests(unittest.TestCase):
    def state(self, *, claim_id, status, established=False, independent=False, sources=None):
        return {
            "version": CLAIM_CORROBORATION_POLICY_VERSION,
            "claims": [
                {
                    "claim_id": claim_id,
                    "status": status,
                    "corroboration_established": established,
                    "contested": False,
                    "contradiction_present": False,
                    "independent_support_established": independent,
                    "supporting_source_ids": sources or [],
                }
            ],
        }

    def capture(self, source_id, suffix):
        return {
            "url": f"https://{suffix}.example/story",
            "source_id": source_id,
            "content_sha256": (suffix[0] * 64),
        }

    def positive(self):
        claim_id = "positive-claim"
        return {
            "version": MERIT_SCORE_RELEASE_CASE_VERSION,
            "id": "positive",
            "scenario": "verified_independent_corroboration",
            "origin": "real_world",
            "machine_verified": True,
            "claim_id": claim_id,
            "source_captures": [
                self.capture("source-a", "a"),
                self.capture("source-b", "b"),
            ],
            "legacy_score": {"total": 60, "components": {"corroboration": 4}},
            "corroboration_state": self.state(
                claim_id=claim_id,
                status="corroboration_established",
                established=True,
                independent=True,
                sources=["source-a", "source-b"],
            ),
            "expectations": {
                "signal": "verified_corroboration",
                "adjustment": 6,
                "live_total": 60,
                "shadow_total": 66,
            },
            "lineage": {
                "independence_verifier_version": DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
                "independence_assertion_id": "assertion-1",
                "independence_evidence_id": "evidence-1",
            },
        }

    def dependency(self):
        claim_id = "dependency-claim"
        return {
            "version": MERIT_SCORE_RELEASE_CASE_VERSION,
            "id": "dependency",
            "scenario": "recorded_dependency_no_boost",
            "origin": "real_world",
            "machine_verified": True,
            "claim_id": claim_id,
            "source_captures": [
                self.capture("source-c", "c"),
                self.capture("source-d", "d"),
            ],
            "legacy_score": {"total": 70, "components": {"corroboration": 5}},
            "corroboration_state": self.state(
                claim_id=claim_id,
                status="recorded_support_dependency_present",
                sources=["source-c", "source-d"],
            ),
            "expectations": {
                "signal": "support_dependency_present",
                "adjustment": 0,
                "live_total": 70,
                "shadow_total": 70,
            },
            "lineage": {
                "dependency_id": "dependency-1",
                "dependency_evidence_id": "evidence-2",
            },
        }

    def same_publisher(self):
        claim_id = "same-publisher-claim"
        return {
            "version": MERIT_SCORE_RELEASE_CASE_VERSION,
            "id": "same-publisher",
            "scenario": "same_publisher_no_diversity",
            "origin": "real_world",
            "machine_verified": True,
            "claim_id": claim_id,
            "source_captures": [
                self.capture("source-nba", "e"),
                self.capture("source-nba", "f"),
            ],
            "legacy_score": {"total": 80, "components": {"corroboration": 6}},
            "corroboration_state": self.state(
                claim_id=claim_id,
                status="support_source_diversity_not_established",
                sources=["source-nba"],
            ),
            "expectations": {
                "signal": "no_verified_corroboration_boost",
                "adjustment": 0,
                "live_total": 80,
                "shadow_total": 80,
            },
            "lineage": {
                "source_identity_basis": "publisher|canonical_domain",
            },
        }

    def complete_cases(self):
        return [self.positive(), self.dependency(), self.same_publisher()]

    def test_complete_machine_verified_real_world_cases_authorize_certificate(self):
        result = build_merit_score_release_certificate(cases=self.complete_cases())
        self.assertEqual(result["version"], MERIT_SCORE_RELEASE_CERTIFICATE_VERSION)
        self.assertEqual(result["status"], "authorized")
        self.assertTrue(result["live_enablement_authorized"])
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["case_count"], 3)
        self.assertEqual(result["evaluation"]["status"], "passed")
        self.assertEqual(result["evaluation"]["metrics"]["safety_violations"], 0)
        self.assertTrue(result["policy"]["human_review_not_part_of_release_path"])
        self.assertTrue(result["policy"]["certificate_does_not_itself_activate_live_merit"])
        self.assertEqual(validate_merit_score_release_certificate(result), result)

    def test_missing_required_scenario_blocks_certificate(self):
        result = build_merit_score_release_certificate(cases=self.complete_cases()[:2])
        self.assertFalse(result["live_enablement_authorized"])
        self.assertIn("required_real_world_score_scenarios_missing", result["blockers"])

    def test_human_review_metadata_is_rejected(self):
        cases = self.complete_cases()
        cases[0]["reviewer"] = "someone"
        with self.assertRaisesRegex(ValueError, "human-review key"):
            build_merit_score_release_certificate(cases=cases)

    def test_tampered_certificate_is_rejected(self):
        certificate = build_merit_score_release_certificate(cases=self.complete_cases())
        tampered = copy.deepcopy(certificate)
        tampered["cases"][0]["expectations"]["adjustment"] = 5
        with self.assertRaises(ValueError):
            validate_merit_score_release_certificate(tampered)


if __name__ == "__main__":
    unittest.main()
