from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.application.config import DB_PATH
from app.db.connection import connect_database
from app.intelligence.claim_evolution_backfill import run_claim_evolution_backfill


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or apply the bounded, idempotent Sportabase claim-evolution backfill."
        )
    )
    parser.add_argument(
        "--database",
        default=str(DB_PATH),
        help="SQLite application database path. Defaults to configured DB_PATH.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5000,
        help="Maximum structured claims to inspect in one pass.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist evolution reconciliation. Without this flag the command is dry-run only.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    database_path = Path(args.database).expanduser().resolve()

    def connection_factory():
        return connect_database(database_path)

    report = run_claim_evolution_backfill(
        connection_factory=connection_factory,
        limit=args.limit,
        apply=args.apply,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {"planned", "completed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
