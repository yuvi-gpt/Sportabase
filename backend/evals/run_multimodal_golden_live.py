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
    live_capacity_preflight,
)
from .golden_live_budget import (
    HARD_MAX_PROVIDER_CALLS,
    MultimodalGoldenLiveInputError,
    bounded_calls,
    sqlite_connection_factory,
)
from .golden_live_scoring import (
    provider_call_plan,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded #34B Sportabase "
            "multimodal golden evaluation subset."
        )
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Required explicit opt-in for a nonzero run. "
            "This command makes real Gemini API calls."
        ),
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=DEFAULT_MAX_PROVIDER_CALLS,
        help=(
            "Provider call budget from 0 to "
            + str(HARD_MAX_PROVIDER_CALLS)
            + ". 0 is a true zero-call dry run."
        ),
    )
    parser.add_argument(
        "--json-out",
        default="",
        help=(
            "Optional path for the sanitized "
            "live evaluation report."
        ),
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help=(
            "Print the frozen live subset, call plan, "
            "and current #34A capacity with zero provider calls."
        ),
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
        )
        + "\n",
        encoding="utf-8",
    )


def _print_plan(
    plan,
    *,
    configured_cap: int,
) -> None:
    print("Gemini provider call plan")
    print("cases:", plan["case_count"])
    print(
        "candidate pairs:",
        plan["candidate_pair_count"],
    )
    print(
        "guaranteed semantic calls:",
        plan["guaranteed_semantic_calls"],
    )
    print(
        "conditional observation calls:",
        plan["conditional_observation_calls"],
    )
    print(
        "minimum provider calls:",
        plan["minimum_calls"],
    )
    print(
        "maximum provider calls:",
        plan["maximum_calls"],
    )
    print(
        "possible actual provider calls:",
        ", ".join(
            str(value)
            for value in plan[
                "possible_actual_calls"
            ]
        ),
    )
    print("configured hard cap:", configured_cap)
    print(
        "exact pre-run count available:",
        plan["exact_pre_run_count_available"],
    )
    print(
        "why:",
        plan["exact_pre_run_count_reason"],
    )
    for row in plan["cases"]:
        print("case:", row["case_id"])
        print(
            "  candidate pairs:",
            row["candidate_pair_count"],
        )
        print(
            "  candidate labels:",
            ", ".join(
                row["candidate_labels"]
            ),
        )
        print(
            "  guaranteed calls:",
            row["minimum_calls"],
        )
        print(
            "  maximum calls:",
            row["maximum_calls"],
        )


def _print_capacity(snapshot) -> None:
    print("#34A capacity preflight")
    print(
        "policy:",
        snapshot.get("policy_version", ""),
    )
    print("model:", snapshot.get("model", ""))
    print(
        "provider day:",
        snapshot.get("provider_day", ""),
    )
    print(
        "provider timezone:",
        snapshot.get("provider_timezone", ""),
    )
    print(
        "dispatch RPM:",
        snapshot.get("dispatch_rpm", ""),
    )
    print(
        "minimum spacing seconds:",
        snapshot.get(
            "minimum_dispatch_interval_seconds",
            "",
        ),
    )
    print(
        "usable input TPM:",
        snapshot.get("usable_tpm", ""),
    )
    print(
        "model usable RPD:",
        snapshot.get("usable_rpd", ""),
    )
    print(
        "global daily cap:",
        snapshot.get("global_daily_call_cap", ""),
    )
    print(
        "per-client cap:",
        snapshot.get("client_daily_call_cap", ""),
    )
    print(
        "global used / remaining:",
        str(snapshot.get("global_used", ""))
        + " / "
        + str(snapshot.get("global_remaining", "")),
    )
    print(
        "model used / remaining:",
        str(snapshot.get("model_used", ""))
        + " / "
        + str(snapshot.get("model_remaining", "")),
    )
    client_remaining = snapshot.get(
        "client_remaining",
        {},
    )
    if isinstance(client_remaining, dict):
        print(
            "eval pair client remaining:",
            sorted(client_remaining.values()),
        )
    print(
        "capacity ready:",
        snapshot.get("ready") is True,
    )
    if snapshot.get("failures"):
        print(
            "capacity failures:",
            ", ".join(
                str(value)
                for value in snapshot["failures"]
            ),
        )


def _provider_event_logger(event) -> None:
    kind = event.get("event")
    index = event.get("call_index")
    cap = event.get("max_calls")
    mode = event.get("mode") or "unknown"
    model = event.get("model") or "unknown"

    if kind == "provider_call_started":
        print(
            f"[Gemini {index}/{cap} START] "
            f"mode={mode} model={model}",
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
            f"[Gemini {index}/{cap} FAILED] "
            f"mode={mode} model={model} | "
            f"cumulative_calls={event.get('cumulative_calls', 0)} "
            f"cumulative_tokens={event.get('cumulative_total_tokens', 0)}",
            flush=True,
        )


def _validated_budget(value):
    try:
        return bounded_calls(value)
    except MultimodalGoldenLiveInputError as error:
        print(
            type(error).__name__
            + ": "
            + str(error),
            file=sys.stderr,
        )
        return None


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    configured_cap = _validated_budget(
        args.max_calls
    )
    if configured_cap is None:
        return 2

    plan = provider_call_plan(
        DEFAULT_LIVE_CASE_IDS
    )
    backend_root = Path(__file__).resolve().parents[1]
    usage_db_path = (
        backend_root
        / "data"
        / "sportabase.db"
    )
    usage_factory = sqlite_connection_factory(
        usage_db_path
    )

    if args.describe:
        print("Sportabase #34B live golden subset")
        print("cases:")
        for case_id in DEFAULT_LIVE_CASE_IDS:
            print("  -", case_id)
        print(
            "default max provider calls:",
            DEFAULT_MAX_PROVIDER_CALLS,
        )
        print(
            "hard max provider calls:",
            HARD_MAX_PROVIDER_CALLS,
        )
        print("provider: Gemini only")
        print(
            "production DB use: Gemini usage ledger read-only"
        )
        print("Live Merit release: never called")
        print()
        _print_plan(
            plan,
            configured_cap=configured_cap,
        )
        if configured_cap >= plan["maximum_calls"]:
            snapshot = live_capacity_preflight(
                usage_connection_factory=usage_factory,
                max_calls=configured_cap,
            )
            print()
            _print_capacity(snapshot)
        print("provider calls made by --describe: 0")
        print("API key read by --describe: FALSE")
        return 0

    if configured_cap == 0:
        print("Sportabase zero-call live-eval dry run")
        _print_plan(
            plan,
            configured_cap=0,
        )
        print()
        print(
            "DRY RUN COMPLETE: exactly 0 Gemini calls made."
        )
        print("API key read: FALSE")
        print("token usage: 0")
        return 0

    if not args.live:
        print(
            "Refusing to make provider calls without "
            "explicit --live opt-in.",
            file=sys.stderr,
        )
        return 2

    print("Sportabase #34B bounded live evaluation preflight")
    _print_plan(
        plan,
        configured_cap=configured_cap,
    )

    if configured_cap < plan["maximum_calls"]:
        print(
            "Configured call budget cannot cover the frozen "
            "full-case maximum. No provider calls were made. "
            "Use --max-calls 12 to preserve the full "
            "two-positive-plus-hard-negative scope.",
            file=sys.stderr,
        )
        return 2

    snapshot = live_capacity_preflight(
        usage_connection_factory=usage_factory,
        max_calls=configured_cap,
    )
    print()
    _print_capacity(snapshot)
    if snapshot.get("ready") is not True:
        print(
            "Provider-day capacity is insufficient. "
            "No API key was read and no provider calls were made.",
            file=sys.stderr,
        )
        return 2

    print()
    print("ZERO-COST PREFLIGHT: PASS")
    print("Provider calls spent so far: 0")
    print("API key read so far: FALSE")

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

    print()
    print("=== LIVE GEMINI CALL LOG ===")
    try:
        report = evaluate_live_golden_subset(
            api_key=api_key,
            usage_db_path=usage_db_path,
            max_calls=configured_cap,
            event_sink=_provider_event_logger,
        )
    except MultimodalGoldenLiveError as error:
        print(
            type(error).__name__
            + ": "
            + str(error),
            file=sys.stderr,
        )
        return 3

    _write_json(
        args.json_out,
        report,
    )
    provider = report["provider"]

    print()
    print("=== EXACT PROVIDER USAGE ===")
    print(
        "actual provider calls:",
        provider["call_count"],
    )
    print(
        "hard provider cap:",
        provider["max_calls"],
    )
    print(
        "remaining call headroom:",
        provider["remaining_calls"],
    )
    print(
        "prompt tokens:",
        provider["prompt_tokens"],
    )
    print(
        "output tokens:",
        provider["output_tokens"],
    )
    print(
        "thought tokens:",
        provider["thought_tokens"],
    )
    print(
        "cached tokens:",
        provider["cached_tokens"],
    )
    print(
        "total tokens:",
        provider["total_tokens"],
    )
    print(
        "calls by mode:",
        provider["calls_by_mode"],
    )
    print(
        "calls by model:",
        provider["calls_by_model"],
    )
    print(
        "calls by eval client:",
        provider["calls_by_eval_client"],
    )

    print()
    print("=== PER-CALL TOKEN + LEDGER LOG ===")
    for row in provider["call_log"]:
        print(
            f"call {row['call_index']}: "
            f"usage_id={row['usage_id']} "
            f"mode={row['mode']} "
            f"model={row['model']} "
            f"status={row['status']} "
            f"prompt={row['prompt_tokens']} "
            f"output={row['output_tokens']} "
            f"thought={row['thought_tokens']} "
            f"cached={row['cached_tokens']} "
            f"total={row['total_tokens']}"
        )

    print()
    print("=== EVALUATION RESULT ===")
    print("version:", report["version"])
    print("mode:", report["mode"])
    print(
        "cases:",
        ", ".join(report["subset_case_ids"]),
    )
    print(
        "provider_complete:",
        report["provider_complete"],
    )
    print(
        "hard_safety_status:",
        report["hard_safety_status"],
    )
    print(
        "quality_case_pass_rate:",
        report["quality_case_pass_rate"],
    )
    print(
        "quality_case_failures:",
        ", ".join(
            report["quality_case_failures"]
        )
        or "NONE",
    )
    print(
        "hard_safety_case_failures:",
        ", ".join(
            report["hard_safety_case_failures"]
        )
        or "NONE",
    )
    print(
        "report_digest:",
        report["report_digest"],
    )

    for case in report["cases"]:
        score = case["score"]
        print()
        print("case:", case["case_id"])
        print("  status:", case["status"])
        print(
            "  provider_calls:",
            case["provider_calls"],
        )
        print(
            "  quality:",
            score["quality_status"],
        )
        print(
            "  quality_failures:",
            ", ".join(
                score["quality_failures"]
            )
            or "NONE",
        )
        print(
            "  hard_safety:",
            score["hard_safety_status"],
        )

    if report["hard_safety_status"] != "pass":
        return 4
    if not report["provider_complete"]:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
