from __future__ import annotations

import argparse
import sys

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


from app.application.config import (  # noqa: E402
    DB_PATH,
)

from evals.historical_article_claim_backfill_plan import (  # noqa: E402
    build_historical_article_claim_backfill_plan,
    write_backfill_plan,
)


def _parser():
    parser = argparse.ArgumentParser(
        description=(
            "Build a read-only high-precision "
            "historical article claim backfill plan."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
    )

    parser.add_argument(
        "--json-out",
        type=Path,
    )

    return parser


def _print_case(
    prefix,
    case,
):
    print(
        prefix
        + "|"
        + str(
            case.get(
                "current_rule_type"
            )
            or ""
        )
        + "|"
        + str(
            case.get(
                "reason"
            )
            or ""
        )
        + "|"
        + str(
            case.get(
                "title"
            )
            or ""
        )
    )


def main(
    argv=None,
):
    args = _parser().parse_args(
        argv
    )

    try:
        report = (
            build_historical_article_claim_backfill_plan(
                db_path=args.db
            )
        )

    except Exception as error:
        print(
            (
                "historical backfill planner failed: "
                + type(
                    error
                ).__name__
                + ": "
                + str(
                    error
                )
            ),
            file=sys.stderr,
        )

        return 2

    if args.json_out:
        write_backfill_plan(
            args.json_out,
            report,
        )

    metrics = report[
        "metrics"
    ]

    print(
        "Sportabase historical claim backfill plan"
    )

    print(
        "stories:",
        metrics[
            "historical_story_count"
        ],
    )

    print(
        "admit:",
        metrics[
            "admit_count"
        ],
    )

    print(
        "review:",
        metrics[
            "review_count"
        ],
    )

    print(
        "reject:",
        metrics[
            "reject_count"
        ],
    )

    print(
        "calibration baseline eligible:",
        metrics[
            "calibration_baseline_eligible_count"
        ],
    )

    print(
        "\nADMIT"
    )

    for case in report[
        "admit"
    ]:
        _print_case(
            "ADMIT",
            case,
        )

    print(
        "\nREVIEW"
    )

    for case in report[
        "review"
    ]:
        _print_case(
            "REVIEW",
            case,
        )

    print(
        "\nREPORT_DIGEST="
        + report[
            "report_digest"
        ]
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
