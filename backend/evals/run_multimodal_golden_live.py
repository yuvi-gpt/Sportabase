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
from .golden_live_scoring import provider_call_plan


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
        help="Print the frozen live subset and zero-cost provider plan, then exit.",
    )
    return parser


def _write_json(path: str, payload) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _print_plan(plan, *, configured_cap: int) -> None:
    print("Gemini provider call plan")
    print("cases:", plan["case_count"])
    print("candidate pairs:", plan["candidate_pair_count"])
    print("guaranteed semantic calls:", plan["guaranteed_semantic_calls"])
    print("conditional observation calls:", plan["conditional_observation_calls"])
    print("minimum provider calls:", plan["minimum_calls"])
    print("maximum provider calls:", plan["maximum_calls"])
    print(
        "possible actual provider calls:",
        ", ".join(str(value) for value in plan["possible_actual_calls"]),
    )
    print("configured hard cap:", configured_cap)
    print("exact pre-run count available:", plan["exact_pre_run_count_available"])
    print("why:", plan["exact_pre_run_count_reason"])
    for row in plan["cases"]:
        print("case:", row["case_id"])
        print("  candidate pairs:", row["candidate_pair_count"])
        print("  candidate labels:", ", ".join(row["candidate_labels"]))
        print("  guaranteed calls:", row["minimum_calls"])
        print("  maximum calls:", row["maximum_calls"])


def _provider_event_logger(event) -> None:
    kind = event.get("event")
    index = event.get("call_index")
    cap = event.get("max_calls")
    mode = event.get("mode") or "unknown"
    model = event.get("model") or "unknown"
    if kind == "provider_call_started":
        print(
            f"[Gemini {index}/{cap} START] mode={mode} model={model}",
            flush=True,
        )
        return
    if kind == "provider_call_completed":
        print(
            f"[Gemini {index}/{cap} DONE] "
            f"prompt={event.get('prompt_tokens', 0)} "
            f"output={event.get('output_tokens', 0)} "
            f"thought={event.get('thought_tokens', 0)} "
            f"cached={event.get('cached_tokens', 0)} "
            f"total={event.get('total_tokens', 0)} | "
            f"cumulative_calls={event.get('cumulative_calls', 0)} "
            f"cumulative_tokens={event.get('cumulative_total_tokens', 0)}",
            flush=True,
        )
        return
    if kind == "provider_call_failed":
        print(
            f"[Gemini {index}/{cap} FAILED] mode={mode} model={model} | "
            f"cumulative_calls={event.get('cumulative_calls', 0)} "
            f"cumulative_tokens={event.get('cumulative_total_tokens', 0)}",
            flush=True,
        )


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    plan = provider_call_plan(DEFAULT_LIVE_CASE_IDS)

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
        print()
        _print_plan(plan, configured_cap=args.max_calls)
        print("provider calls made by --describe: 0")
        return 0

    if not args.live:
        print(
            "Refusing to make provider calls without explicit --live opt-in.",
            file=sys.stderr,
        )
        return 2

    print("Sportabase bounded live evaluation preflight")
    _print_plan(plan, configured_cap=args.max_calls)
    if args.max_calls < plan["maximum_calls"]:
        print(
            "Configured call budget cannot cover the frozen full-case maximum.",
            file=sys.stderr,
        )
        return 2

    backend_root = Path(__file__).resolve().parents[1]
    load_dotenv(backend_root / ".env")
    api_key = str(os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        print("GEMINI_API_KEY is not configured.", file=sys.stderr)
        return 2

    print()
    print("=== LIVE GEMINI CALL LOG ===")
    try:
        report = evaluate_live_golden_subset(
            api_key=api_key,
            max_calls=args.max_calls,
            event_sink=_provider_event_logger,
        )
    except MultimodalGoldenLiveError as error:
        print(type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 3

    _write_json(args.json_out, report)

    provider = report["provider"]
    print()
    print("=== EXACT PROVIDER USAGE ===")
    print("actual provider calls:", provider["call_count"])
    print("hard provider cap:", provider["max_calls"])
    print("remaining call headroom:", provider["remaining_calls"])
    print("prompt tokens:", provider["prompt_tokens"])
    print("output tokens:", provider["output_tokens"])
    print("thought tokens:", provider["thought_tokens"])
    print("cached tokens:", provider["cached_tokens"])
    print("total tokens:", provider["total_tokens"])
    print("calls by mode:", provider["calls_by_mode"])
    print("calls by model:", provider["calls_by_model"])

    print()
    print("=== PER-CALL TOKEN LOG ===")
    for row in provider["call_log"]:
        print(
            f"call {row['call_index']}: "
            f"mode={row['mode']} model={row['model']} status={row['status']} "
            f"prompt={row['prompt_tokens']} output={row['output_tokens']} "
            f"thought={row['thought_tokens']} cached={row['cached_tokens']} "
            f"total={row['total_tokens']}"
        )

    print()
    print("=== EVALUATION RESULT ===")
    print("version:", report["version"])
    print("mode:", report["mode"])
    print("cases:", ", ".join(report["subset_case_ids"]))
    print("provider_complete:", report["provider_complete"])
    print("hard_safety_status:", report["hard_safety_status"])
    print("quality_case_pass_rate:", report["quality_case_pass_rate"])
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
