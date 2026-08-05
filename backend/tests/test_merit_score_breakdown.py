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


from app.main import (
    AnalyzeResponse,
    merit_score,
)


class MeritScoreBreakdownTests(
    unittest.TestCase
):
    def test_breakdown_preserves_public_fields(
        self,
    ):
        result = merit_score(
            title=(
                "Club officially announces "
                "new player signing"
            ),
            text=(
                "The club officially announced "
                "the signing in a statement. "
                "The player signed a four-year "
                "contract after completing a "
                "medical examination."
            ),
            url=(
                "https://example.com/"
                "official-signing"
            ),
        )

        self.assertIn(
            "total",
            result,
        )

        self.assertIn(
            "badge",
            result,
        )

        self.assertIn(
            "reasons",
            result,
        )

        self.assertIn(
            "components",
            result,
        )

        self.assertIn(
            "calculation",
            result,
        )


    def test_component_sum_matches_raw_total(
        self,
    ):
        result = merit_score(
            title=(
                "Sources link player "
                "with summer transfer"
            ),
            text=(
                "Reports suggest the player "
                "could leave this summer. "
                "Sources say talks may begin, "
                "but nothing has been confirmed."
            ),
            url=(
                "https://example.com/"
                "transfer-rumor"
            ),
        )

        component_total = sum(
            result[
                "components"
            ].values()
        )

        self.assertAlmostEqual(
            component_total,
            result[
                "calculation"
            ][
                "raw_total"
            ],
            places=2,
        )


    def test_api_model_exposes_breakdown(
        self,
    ):
        score = merit_score(
            title=(
                "Club confirms new signing"
            ),
            text=(
                "The club confirmed the signing "
                "in an official statement after "
                "the player completed a medical."
            ),
            url=(
                "https://example.com/"
                "confirmed-signing"
            ),
        )

        response = AnalyzeResponse(
            url=(
                "https://example.com/"
                "confirmed-signing"
            ),
            title=(
                "Club confirms new signing"
            ),
            tldr=[
                "The club officially confirmed "
                "the new signing."
            ],
            merit_score=score["total"],
            badge=score["badge"],
            reasons=score["reasons"],
            score_components=score[
                "components"
            ],
            score_calculation=score[
                "calculation"
            ],
        )

        payload = response.model_dump()

        self.assertEqual(
            payload[
                "score_components"
            ],
            score["components"],
        )

        self.assertEqual(
            payload[
                "score_calculation"
            ],
            score["calculation"],
        )


    def test_final_total_matches_existing_total(
        self,
    ):
        result = merit_score(
            title=(
                "Team wins league match 3-1"
            ),
            text=(
                "The team won the match 3-1 "
                "after scoring twice in the "
                "second half. The final result "
                "was confirmed by the league."
            ),
            url=(
                "https://example.com/"
                "match-report"
            ),
        )

        self.assertEqual(
            result["total"],
            result[
                "calculation"
            ][
                "final_total"
            ],
        )

        self.assertLessEqual(
            result[
                "calculation"
            ][
                "final_total"
            ],
            result[
                "calculation"
            ][
                "before_soft_ceilings"
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
