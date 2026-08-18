from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .claim_semantic_extraction_router_live import (
    CLAIM_SEMANTIC_EXTRACTION_ROUTER_LIVE_VERSION,
    CLIENT_KEY,
    EXACT_PROVIDER_CALLS,
    LIVE_CASE_ID,
    LIVE_MODEL,
    ClaimSemanticExtractionRouterLiveError,
    evaluate_live_router_hard_negative,
    live_capacity_preflight,
    live_input,
)
from .golden_live_budget import sqlite_connection_factory


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the bounded #35F one-call live validation of the #35E three-way router."
        )
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Required explicit opt-in for the one real Gemini call.",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=EXACT_PROVIDER_CALLS,
        help="Must be exactly 1 for #35F.",
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print the exact one-call plan and capacity with zero provider calls.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional path for the sanitized live report.",
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


def _print_capacity(snapshot) -> None:
    print("#34A capacity preflight")
    print("policy:", snapshot.get("policy_version", ""))
    print("model:", snapshot.get("model", ""))
    print("provider day:", snapshot.get("provider_day", ""))
    print("provider timezone:", snapshot.get("provider_timezone", ""))
    print("dispatch RPM:", snapshot.get("dispatch_rpm", ""))
    print(
        "minimum spacing seconds:",
        snapshot.get("minimum_dispatch_interval_seconds", ""),
    )
    print("usable input TPM:", snapshot.get("usable_tpm", ""))
    print("model usable RPD:", snapshot.get("usable_rpd", ""))
    print("global daily cap:", snapshot.get("global_daily_call_cap", ""))
    print("per-client cap:", snapshot.get("client_daily_call_cap", ""))
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
    print(
        "eval client remaining:",
        sorted(dict(snapshot.get("client_remaining") or {}).values()),
    )
    print("required calls:", snapshot.get("required_calls", ""))
    print("capacity ready:", snapshot.get("ready") is True)
    if snapshot.get("failures"):
        print("capacity failures:", ", ".join(snapshot["failures"]))


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
            f"[Gemini {index}/{cap} FAILED] mode={mode} model={model}",
            flush=True,
        )


def _print_plan() -> None:
    print("Sportabase #35F one-call three-way router validation")
    print("case:", LIVE_CASE_ID)
    print("model:", LIVE_MODEL)
    print("source: hard_negative ONLY")
    print("provider calls: EXACTLY 1")
    print("positive source calls: 0")
    print("anchor provider calls: 0")
    print("deterministic anchor: TRUE")
    print("call 2: IMPOSSIBLE")
    print("client bucket:", CLIENT_KEY)
    print("frozen text:", live_input())
    print("Live Merit release: never called")


def main(argv=None) -> int:
    args = _parser().parse_args(argv)

    if int(args.max_calls) != EXACT_PROVIDER_CALLS:
        print("#35F requires --max-calls 1 exactly.", file=sys.stderr)
        return 2

    backend_root = Path(__file__).resolve().parents[1]
    usage_db_path = backend_root / "data" / "sportabase.db"
    usage_factory = sqlite_connection_factory(usage_db_path)

    _print_plan()
    snapshot = live_capacity_preflight(
        usage_connection_factory=usage_factory
    )
    print()
    _print_capacity(snapshot)

    if args.describe:
        print()
        print("provider calls made by --describe: 0")
        print("API key read by --describe: FALSE")
        return 0 if snapshot.get("ready") is True else 2

    if not args.live:
        print()
        print(
            "Refusing provider call without explicit --live opt-in.",
            file=sys.stderr,
        )
        print("Provider calls made: 0", file=sys.stderr)
        print("API key read: FALSE", file=sys.stderr)
        return 2

    if snapshot.get("ready") is not True:
        print(
            "Provider-day capacity is insufficient. No API key was read and no provider calls were made.",
            file=sys.stderr,
        )
        return 2

    print()
    print("ZERO-COST PREFLIGHT: PASS")
    print("Provider calls spent so far: 0")
    print("API key read so far: FALSE")

    load_dotenv(backend_root / ".env")
    api_key = str(os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        print("GEMINI_API_KEY is not configured.", file=sys.stderr)
        return 2

    print()
    print("=== LIVE GEMINI ROUTER CALL LOG ===")
    try:
        report = evaluate_live_router_hard_negative(
            api_key=api_key,
            usage_db_path=usage_db_path,
            max_calls=EXACT_PROVIDER_CALLS,
            event_sink=_provider_event_logger,
        )
    except ClaimSemanticExtractionRouterLiveError as error:
        print(type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 3

    _write_json(args.json_out, report)
    provider = report["provider"]
    row = report["extraction"]
    comparison = report["comparison"]

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
    print("calls by eval client:", provider["calls_by_eval_client"])

    print()
    print("=== PER-CALL TOKEN + LEDGER LOG ===")
    for call in provider["call_log"]:
        print(
            f"call {call['call_index']}: usage_id={call['usage_id']} "
            f"mode={call['mode']} model={call['model']} status={call['status']} "
            f"prompt={call['prompt_tokens']} output={call['output_tokens']} "
            f"thought={call['thought_tokens']} cached={call['cached_tokens']} "
            f"total={call['total_tokens']}"
        )

    print()
    print("=== THREE-WAY ROUTER OUTPUT ===")
    print("status:", row["status"])
    print("route:", row["route"])
    if row.get("candidate") is not None:
        candidate = row["candidate"]
        print("event_type:", candidate.get("event_type"))
        print("state:", candidate.get("state"))
        print("negated:", candidate.get("negated"))
        print("roles:", candidate.get("roles"))
        print("facets:", candidate.get("facets"))
    print("identity_complete:", row["identity_complete"])
    print("missing_identity_fields:", row["missing_identity_fields"])
    print("core_fingerprint:", row["core_fingerprint"] or "NONE")
    print("specific_fingerprint:", row["specific_fingerprint"] or "NONE")
    if row.get("reason"):
        print("reason:", row["reason"])
    if row.get("error_type"):
        print("error_type:", row["error_type"])

    print()
    print("=== DETERMINISTIC #35D COMPARISON ===")
    print("kind:", comparison["kind"])
    print("status:", comparison["status"])
    print("structural_conflicts:", comparison["structural_conflicts"])
    print("safe_exclusion:", comparison["safe_exclusion"])
    print("safe_acceptance:", comparison["safe_acceptance"])

    print()
    print("=== #35F RESULT ===")
    print("version:", report["version"])
    print("provider_complete:", report["provider_complete"])
    print("quality:", report["quality"]["status"])
    print(
        "quality_failures:",
        ", ".join(report["quality"]["failures"]) or "NONE",
    )
    print("hard_safety:", report["hard_safety"]["status"])
    print(
        "hard_safety_failures:",
        ", ".join(report["hard_safety"]["failures"]) or "NONE",
    )
    print("Live Merit effect: FALSE")
    print("raw provider responses stored: FALSE")
    print("report_digest:", report["report_digest"])

    if report["hard_safety"]["status"] != "pass":
        return 4
    if report["provider_complete"] is not True:
        return 5

    # A quality failure is a measured result, not an execution failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
