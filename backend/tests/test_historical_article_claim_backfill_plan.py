import hashlib
import sys
import tempfile
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


from app.db.connection import (
    connect_database,
)

from app.db.schema import (
    SCHEMA,
)

from evals.historical_article_claim_backfill_plan import (
    HISTORICAL_ARTICLE_CLAIM_BACKFILL_REPORT_VERSION,
    build_historical_article_claim_backfill_plan,
    evaluate_historical_story_for_backfill,
)


def story(
    *,
    title,
    summary="Sports article summary.",
    url="https://example.com/story",
    merit_score=20,
):
    return {
        "id": (
            hashlib.sha1(
                title.encode(
                    "utf-8"
                )
            ).hexdigest()
        ),
        "source": (
            "Example Sports"
        ),
        "sport": (
            "football"
        ),
        "title": title,
        "link": url,
        "published": (
            "2026-05-05T12:00:00+00:00"
        ),
        "summary": summary,
        "tldr_json": "[]",
        "merit_score": merit_score,
        "badge": "",
        "created_at": (
            "2026-05-05T13:00:00+00:00"
        ),
    }


class HistoricalArticleClaimBackfillPlanTests(
    unittest.TestCase
):
    def test_newsletter_false_positive_is_rejected(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Signup for the Moving the "
                        "Goalposts newsletter: our "
                        "free women's football email"
                    )
                )
            )
        )

        self.assertEqual(
            result[
                "decision"
            ],
            "reject",
        )

        self.assertEqual(
            result[
                "reason"
            ],
            (
                "subscription_or_service_content"
            ),
        )

    def test_signs_off_is_not_completed_transfer_signal(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Millie Bright, serial "
                        "silverware winner, signs "
                        "off with a legacy few "
                        "will match"
                    )
                )
            )
        )

        self.assertNotEqual(
            result[
                "decision"
            ],
            "admit",
        )

    def test_fine_margins_is_not_legal_signal(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Arsenal ponder fine margins "
                        "after defeat but Gunners "
                        "are not in decline"
                    )
                )
            )
        )

        self.assertNotEqual(
            result[
                "decision"
            ],
            "admit",
        )

    def test_match_draw_is_not_fixture_schedule_signal(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "The night Man City lost "
                        "the title? Chaotic draw "
                        "with Everton"
                    )
                )
            )
        )

        self.assertNotEqual(
            result[
                "decision"
            ],
            "admit",
        )

    def test_match_report_is_not_injury_signal(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Bukayo Saka edges Arsenal "
                        "past Atletico Madrid to "
                        "reach Champions League final"
                    )
                )
            )
        )

        self.assertNotEqual(
            result[
                "decision"
            ],
            "admit",
        )

    def test_contract_headline_can_be_admitted(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Sources: Foden agrees new "
                        "deal with Man City"
                    ),
                    summary=(
                        "Phil Foden has reached "
                        "agreement on a new contract "
                        "with Manchester City."
                    ),
                )
            )
        )

        self.assertEqual(
            result[
                "decision"
            ],
            "admit",
        )

        self.assertEqual(
            result[
                "current_rule_type"
            ],
            "contract_news",
        )

    def test_explicit_injury_headline_can_be_admitted(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Forest hopeful of "
                        "Gibbs-White fitness "
                        "for Europa tie"
                    ),
                    summary=(
                        "Forest are hopeful over "
                        "the player's fitness."
                    ),
                )
            )
        )

        self.assertEqual(
            result[
                "decision"
            ],
            "admit",
        )

        self.assertIn(
            "injury",
            result[
                "explicit_signal_families"
            ],
        )

        self.assertEqual(
            result[
                "planned_article_type"
            ],
            "injury_rumor",
        )

        self.assertEqual(
            result[
                "planned_article_type_source"
            ],
            "explicit_headline_signal",
        )

    def test_explicit_legal_headline_can_be_admitted(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Rangers' Sterling banned "
                        "from road after drink "
                        "driving crash"
                    ),
                    summary=(
                        "The Rangers player was "
                        "banned from driving."
                    ),
                )
            )
        )

        self.assertEqual(
            result[
                "decision"
            ],
            "admit",
        )

    def test_transfer_rumor_headline_can_be_admitted(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Transfer rumors, news: "
                        "Barcelona keen on "
                        "Newcastle winger"
                    ),
                    summary=(
                        "Barcelona are keen on "
                        "a move for the player."
                    ),
                )
            )
        )

        self.assertEqual(
            result[
                "decision"
            ],
            "admit",
        )

    def test_clear_type_mismatch_requires_review(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Michael Carrick expected "
                        "to be offered head coach "
                        "deal by Manchester United"
                    ),
                    summary=(
                        "Manchester United are "
                        "expected to offer Carrick "
                        "a head coach deal."
                    ),
                )
            )
        )

        self.assertEqual(
            result[
                "decision"
            ],
            "review",
        )

        self.assertIn(
            "managerial",
            result[
                "explicit_signal_families"
            ],
        )

    def test_historical_score_is_never_calibration_baseline(
        self,
    ):
        result = (
            evaluate_historical_story_for_backfill(
                story=story(
                    title=(
                        "Sources: Foden agrees "
                        "new deal with Man City"
                    ),
                    summary=(
                        "Foden has agreed a new "
                        "contract."
                    ),
                    merit_score=99,
                )
            )
        )

        self.assertFalse(
            result[
                "calibration_baseline_eligible"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "historical_score_is_archival_only"
            ]
        )

    def test_planner_reads_database_without_modifying_it(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp:
            db_path = (
                Path(
                    temp
                )
                / "planner.db"
            )

            conn = connect_database(
                db_path
            )

            try:
                conn.executescript(
                    SCHEMA
                )

                row = story(
                    title=(
                        "Sources: Foden agrees "
                        "new deal with Man City"
                    ),
                    summary=(
                        "Foden agreed a new "
                        "contract."
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO stories (
                      id,
                      source,
                      sport,
                      title,
                      link,
                      published,
                      summary,
                      tldr_json,
                      merit_score,
                      badge,
                      created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row[
                            "id"
                        ],
                        row[
                            "source"
                        ],
                        row[
                            "sport"
                        ],
                        row[
                            "title"
                        ],
                        row[
                            "link"
                        ],
                        row[
                            "published"
                        ],
                        row[
                            "summary"
                        ],
                        row[
                            "tldr_json"
                        ],
                        row[
                            "merit_score"
                        ],
                        row[
                            "badge"
                        ],
                        row[
                            "created_at"
                        ],
                    ),
                )

                conn.commit()

            finally:
                conn.close()

            before = hashlib.sha256(
                db_path.read_bytes()
            ).hexdigest()

            report = (
                build_historical_article_claim_backfill_plan(
                    db_path=db_path
                )
            )

            after = hashlib.sha256(
                db_path.read_bytes()
            ).hexdigest()

            self.assertEqual(
                before,
                after,
            )

            self.assertEqual(
                report[
                    "version"
                ],
                HISTORICAL_ARTICLE_CLAIM_BACKFILL_REPORT_VERSION,
            )

            self.assertEqual(
                report[
                    "metrics"
                ][
                    "historical_story_count"
                ],
                1,
            )

            self.assertEqual(
                report[
                    "metrics"
                ][
                    "calibration_baseline_eligible_count"
                ],
                0,
            )


if __name__ == "__main__":
    unittest.main()
