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

from evals.negative_merit_real_case_inventory import (  # noqa: E402
    build_negative_merit_real_case_inventory,
    write_inventory_json,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect persisted Sportabase article "
            "claims for real negative-Merit corpus "
            "candidates using read-only SQLite access."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=(
            "SQLite database to inspect. Defaults "
            "to Sportabase's configured DB path."
        ),
    )

    parser.add_argument(
        "--json-out",
        type=Path,
        help=(
            "Optional JSON path for the complete "
            "inventory report."
        ),
    )

    return parser


def _print_summary(
    report,
):
    print(
        "Sportabase Negative Merit real-case inventory"
    )

    print(
        "status:",
        report.get(
            "status"
        ),
    )

    print(
        "database:",
        (
            report.get(
                "database",
                {},
            ).get(
                "path"
            )
        ),
    )

    print(
        "read only:",
        (
            report.get(
                "database",
                {},
            ).get(
                "read_only"
            )
        ),
    )

    metrics = report.get(
        "metrics",
        {},
    )

    for key in (
        "primary_claims",
        "analysis_snapshots_found",
        "legacy_scores_ready",
        "article_captures_ready",
        "authority_gate_ready",
        "semantic_gate_ready",
        "two_gate_ready",
        "resolved_verifications_ready",
        "corpus_export_ready",
        "exclusive_controls_requiring_curation",
    ):
        print(
            key + ":",
            metrics.get(
                key
            ),
        )

    counts = report.get(
        "suggested_class_counts",
        {},
    )

    print(
        "suggested classes:"
    )

    for key in sorted(
        counts
    ):
        print(
            "  "
            + key
            + ":",
            counts[
                key
            ],
        )

    print(
        "report digest:",
        report.get(
            "report_digest"
        ),
    )


def main(
    argv=None,
) -> int:
    args = _parser().parse_args(
        argv
    )

    try:
        report = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    args.db
                )
            )
        )

    except Exception as error:
        print(
            "real-case inventory failed:",
            (
                type(
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
        write_inventory_json(
            args.json_out,
            report,
        )

    _print_summary(
        report
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
