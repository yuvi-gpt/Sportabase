from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.application.config import DB_PATH
from app.operations.ai_usage_audit import build_provider_day_ai_usage_audit
from app.services.gemini_capacity import provider_usage_day


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read the local Sportabase Gemini usage ledger for one provider "
            "day. This command never calls Google."
        )
    )
    parser.add_argument(
        "--provider-day",
        default="",
        help=(
            "Provider day to inspect (YYYY-MM-DD). Defaults to the current "
            "Google provider day."
        ),
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the JSON payload.",
    )
    return parser


def _write_json(payload: dict[str, object], output_path: str) -> str:
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

    return rendered


def _print_human_summary(payload: dict[str, object]) -> None:
    summary = dict(payload["summary"])

    print("SPORTABASE GOOGLE AI USAGE AUDIT")
    print("provider_day=" + str(payload["provider_day"]))
    print("provider_attempts=" + str(summary["provider_attempts"]))
    print("successful_calls=" + str(summary["successful_calls"]))
    print("failed_calls=" + str(summary["failed_calls"]))
    print("cache_hits=" + str(summary["cache_hits"]))
    print("inflight_joins=" + str(summary["inflight_joins"]))
    print("estimated_prompt_tokens=" + str(summary["estimated_prompt_tokens"]))
    print("prompt_tokens=" + str(summary["prompt_tokens"]))
    print("output_tokens=" + str(summary["output_tokens"]))
    print("thought_tokens=" + str(summary["thought_tokens"]))
    print("billable_output_tokens=" + str(summary["billable_output_tokens"]))
    print("total_tokens=" + str(summary["total_tokens"]))
    print("success_rate_percent=" + str(summary["success_rate_percent"]))
    print(
        "token_accounting_coverage_percent="
        + str(summary["token_accounting_coverage_percent"])
    )

    latency = dict(summary["latency"])
    print("average_latency_ms=" + str(latency["average_ms"]))
    print("median_latency_ms=" + str(latency["median_ms"]))
    print("p95_latency_ms=" + str(latency["p95_ms"]))
    print("slowest_latency_ms=" + str(latency["slowest_ms"]))

    print("\nBY MODEL")
    for row in payload["by_model"]:
        print(
            str(row["model"])
            + ": calls=" + str(row["provider_attempts"])
            + " success=" + str(row["successful_calls"])
            + " failed=" + str(row["failed_calls"])
            + " total_tokens=" + str(row["total_tokens"])
            + " avg_latency_ms=" + str(row["latency"]["average_ms"])
        )

    print("\nBY MODE")
    for row in payload["by_mode"]:
        print(
            str(row["mode"])
            + ": calls=" + str(row["provider_attempts"])
            + " success=" + str(row["successful_calls"])
            + " failed=" + str(row["failed_calls"])
            + " total_tokens=" + str(row["total_tokens"])
        )

    failures = payload["failures"]
    print("\nFAILURES=" + str(len(failures)))
    for row in failures:
        print(
            "#" + str(row["id"])
            + " " + str(row["model"])
            + " " + str(row["status_code"])
            + " " + str(row["failure_type"])
            + " latency_ms=" + str(row["latency_ms"])
        )
        print("  " + str(row["failure_detail"]))


def main() -> int:
    args = _parser().parse_args()

    day = str(args.provider_day or "").strip() or provider_usage_day()

    payload = build_provider_day_ai_usage_audit(
        db_path=DB_PATH,
        provider_day=day,
    )

    rendered = _write_json(payload, args.output)

    if args.json_only:
        print(rendered)
    else:
        _print_human_summary(payload)
        if args.output:
            print("\nJSON_OUTPUT=" + str(Path(args.output).expanduser().resolve()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
