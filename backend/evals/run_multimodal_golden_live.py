from __future__ import annotations

import argparse
import json
import os
import sys

from pathlib import Path

from dotenv import load_dotenv

from .golden_live import (
    DEFAULT_LIVE_CASE_IDS,
    DEFAULT_MAX_PROVIDER_CALLS,
    MultimodalGoldenLiveError,
    evaluate_live_golden_subset,
)
from .golden_live_budget import HARD_MAX_PROVIDER_CALLS


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded, model-dependent Sportabase "
            "multimodal golden evaluation subset."
        )
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Required explicit opt-in. This command makes "
            "real Gemini API calls."
        ),
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=DEFAULT_MAX_PROVIDER_CALLS,
        help=(
            "Hard provider call budget; maximum "
            + str(HARD_MAX_PROVIDER_CALLS)
            + "."
        ),
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path for the live evaluation report.",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the frozen live subset and exit without provider calls.",
    )
    return parser


def _write_json(path: str, payload) -> None:
    if not path:
        return

    target = Path(path)
    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    target.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    args = _parser().parse_args(argv)

    if args.describe:
        print("Sportabase live golden subset")
        print("cases:")
        for case_id in DEFAULT_LIVE_CASE_IDS:
            print("  -", case_id)
        print("default max provider calls:", DEFAULT_MAX_PROVIDER_CALLS)
        print("hard max provider calls:", HARD_MAX_PROVIDER_CALLS)
        print("provider: Gemini only")
        print("real DB: never used")
        print("Live Merit release: never called")
        return 0

    if not args.live:
        print(
            "Refusing to make provider calls without explicit --live opt-in.",
            file=sys.stderr,
        )
        return 2

    backend_root = Path(__file__).resolve().parents[1]
    load_dotenv(
        backend_root / ".env"
    )
    api_key = str(
        os.getenv("GEMINI_API_KEY")
        or ""
    ).strip()

    if not api_key:
        print(
            "GEMINI_API_KEY is not configured.",
            file=sys.stderr,
        )
        return 2

    try:
        report = evaluate_live_golden_subset(
            api_key=api_key,
            max_calls=args.max_calls,
        )
    except MultimodalGoldenLiveError as error:
        print(
            type(error).__name__ + ": " + str(error),
            file=sys.stderr,
        )
        return 3

    _write_json(
        args.json_out,
        report,
    )

    provider = report["provider"]
    print("Sportabase multimodal live golden evaluation")
    print("version:", report["version"])
    print("mode:", report["mode"])
    print("cases:", ", ".join(report["subset_case_ids"]))
    print("provider_complete:", report["provider_complete"])
    print("hard_safety_status:", report["hard_safety_status"])
    print("quality_case_pass_rate:", report["quality_case_pass_rate"])
    print("provider_calls:", provider["call_count"])
    print("provider_call_budget:", provider["max_calls"])
    print("total_tokens:", provider["total_tokens"])
    print(
        "quality_case_failures:",
        ", ".join(report["quality_case_failures"]) or "NONE",
    )
    print(
        "hard_safety_case_failures:",
        ", ".join(report["hard_safety_case_failures"]) or "NONE",
    )
    print("report_digest:", report["report_digest"])

    for case in report["cases"]:
        score = case["score"]
        print()
        print("case:", case["case_id"])
        print("  status:", case["status"])
        print("  provider_calls:", case["provider_calls"])
        print("  quality:", score["quality_status"])
        print(
            "  quality_failures:",
            ", ".join(score["quality_failures"]) or "NONE",
        )
        print("  hard_safety:", score["hard_safety_status"])

    if report["hard_safety_status"] != "pass":
        return 4

    if not report["provider_complete"]:
        return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
