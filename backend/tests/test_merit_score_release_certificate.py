import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.merit_score_release import (
    MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
    MERIT_SCORE_RELEASE_REQUIRED_SCENARIOS,
    validate_merit_score_release_certificate,
)

CERTIFICATE_PATH = BACKEND_DIR / "data" / "merit_score_release_certificate.json"


class MeritScoreReleaseCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(CERTIFICATE_PATH.read_text(encoding="utf-8"))
        cls.certificate = validate_merit_score_release_certificate(cls.raw)

    def test_checked_in_certificate_is_authorized_and_valid(self):
        self.assertEqual(
            self.certificate["version"],
            MERIT_SCORE_RELEASE_CERTIFICATE_VERSION,
        )
        self.assertEqual(self.certificate["status"], "authorized")
        self.assertTrue(self.certificate["live_enablement_authorized"])
        self.assertEqual(self.certificate["blockers"], [])
        self.assertEqual(self.certificate["case_count"], 3)
        self.assertEqual(self.certificate["evaluation"]["status"], "passed")
        self.assertEqual(
            self.certificate["evaluation"]["metrics"]["safety_violations"],
            0,
        )

    def test_checked_in_certificate_covers_each_required_real_world_scenario_once(self):
        self.assertEqual(
            set(self.certificate["scenario_counts"]),
            set(MERIT_SCORE_RELEASE_REQUIRED_SCENARIOS),
        )
        self.assertEqual(
            self.certificate["scenario_counts"],
            {scenario: 1 for scenario in MERIT_SCORE_RELEASE_REQUIRED_SCENARIOS},
        )
        for case in self.certificate["cases"]:
            self.assertEqual(case["origin"], "real_world")
            self.assertTrue(case["machine_verified"])

    def test_certificate_authorizes_release_but_does_not_activate_live_merit(self):
        self.assertTrue(
            self.certificate["policy"][
                "certificate_does_not_itself_activate_live_merit"
            ]
        )
        for case in self.certificate["cases"]:
            self.assertEqual(
                float(case["expectations"]["live_total"]),
                float(case["legacy_score"]["total"]),
            )


if __name__ == "__main__":
    unittest.main()
