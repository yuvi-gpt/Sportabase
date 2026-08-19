from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark_campaign import (
    high_information_campaign_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the bounded Sportabase high-information Google generation "
            "campaign plan. This command is offline-only and never executes "
            "provider calls."
        )
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path.",
    )
    return parser


def _write_payload(
    payload: dict[str, object],
    output_path: str,
) -> None:
    rendered = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    if output_path:
        path = Path(output_path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)


def main() -> int:
    args = _parser().parse_args()
    payload = high_information_campaign_manifest()
    _write_payload(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
