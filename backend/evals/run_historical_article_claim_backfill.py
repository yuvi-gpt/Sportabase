from __future__ import annotations

import argparse
import json
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

from evals.historical_article_claim_backfill import (  # noqa: E402
    execute_historical_article_claim_backfill,
    load_allowlist,
)


def _parser():
    parser = argparse.ArgumentParser(
        description=(
            "Validate or apply the frozen "
            "zero-provider historical article "
            "claim-seed backfill."
        )
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
    )

    parser.add_argument(
        "--allowlist",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist the frozen reported-claim "
            "seed layer. Without this flag the "
            "runner performs validation only."
        ),
    )

    parser.add_argument(
        "--json-out",
        type=Path,
    )

    return parser


def main(
    argv=None,
):
    args = _parser().parse_args(
        argv
    )

    try:
        allowlist = load_allowlist(
            args.allowlist
        )

        report = (
            execute_historical_article_claim_backfill(
                db_path=(
                    args.db
                ),
                allowlist=(
                    allowlist
                ),
                apply=bool(
                    args.apply
                ),
            )
        )

    except Exception as error:
        print(
            (
                "historical claim backfill failed: "
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
        args.json_out.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.json_out.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        "Sportabase historical claim backfill"
    )

    print(
        "status:",
        report.get(
            "status"
        ),
    )

    print(
        "applied:",
        report.get(
            "applied"
        ),
    )

    print(
        "entry_count:",
        report.get(
            "entry_count"
        ),
    )

    print(
        "allowlist_digest:",
        report.get(
            "allowlist_digest"
        ),
    )

    persisted = report.get(
        "persisted"
    )

    if isinstance(
        persisted,
        list,
    ):
        for row in persisted:
            print(
                "PERSISTED|"
                + str(
                    row.get(
                        "story_id"
                    )
                    or ""
                )
                + "|"
                + str(
                    row.get(
                        "planned_article_type"
                    )
                    or ""
                )
                + "|"
                + str(
                    row.get(
                        "claim_id"
                    )
                    or ""
                )
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
