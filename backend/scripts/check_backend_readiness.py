from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.application.config import DB_PATH
from app.db.connection import connect_database
from app.intelligence.readiness import build_backend_intelligence_readiness


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the read-only Sportabase intelligence backend readiness audit."
        )
    )
    parser.add_argument(
        "--database",
        default=str(DB_PATH),
        help="SQLite application database path. Defaults to configured DB_PATH.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    database_path = Path(args.database).expanduser().resolve()

    def connection_factory():
        return connect_database(database_path)

    report = build_backend_intelligence_readiness(
        connection_factory=connection_factory,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
