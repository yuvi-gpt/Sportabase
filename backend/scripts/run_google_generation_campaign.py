from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark_campaign import (
    build_high_information_generation_campaign,
)
from app.ai.benchmark_campaign_runtime import (
    GENERATION_CAMPAIGN_CLIENT_KEY,
    evaluate_campaign_execution_preflight,
    load_campaign_daily_usage_snapshot,
)
from app.ai.benchmark_reporting import (
    score_article_observations_with_reliability,
)
from app.ai.evaluation import (
    EvaluationCapacityBlocked,
    run_generation_evaluation,
)
from app.ai.quota import provider_usage_day


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight or explicitly execute the bounded 15-call Sportabase "
            "high-information Google generation campaign. Dry-run is default."
        )
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "Read the local usage ledger and report whether all 15 calls fit. "
            "Makes no provider calls."
        ),
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Explicitly allow live provider execution after every preflight "
            "gate passes."
        ),
    )

    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path.",
    )

    return parser


def _write_payload(payload: dict[str, object], output_path: str) -> None:
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


def _resource_ids(plan) -> tuple[str, ...]:
    seen: list[str] = []

    for item in plan.items:
        if item.resource_id not in seen:
            seen.append(item.resource_id)

    return tuple(seen)


def main() -> int:
    args = _parser().parse_args()

    cases, plan = build_high_information_generation_campaign()

    payload: dict[str, object] = {
        "mode": (
            "live"
            if args.execute
            else "preflight"
            if args.preflight
            else "dry_run"
        ),
        "provider_calls_made": 0,
        "case_ids": [case.case_id for case in cases],
        "article_types": [case.expected_article_type for case in cases],
        "resource_ids": list(_resource_ids(plan)),
        "plan": plan.as_dict(),
    }

    if not args.preflight and not args.execute:
        _write_payload(payload, args.output)
        return 0

    from app import main as app_main
    from app.application.config import (
        CLIENT_DAILY_GEMINI_CALL_CAP,
        DB_PATH,
        GLOBAL_DAILY_GEMINI_CALL_CAP,
    )

    app_main.init_db()

    snapshot = load_campaign_daily_usage_snapshot(
        db_path=DB_PATH,
        provider_day=provider_usage_day(),
        client_key=GENERATION_CAMPAIGN_CLIENT_KEY,
        resource_ids=_resource_ids(plan),
        global_daily_call_cap=GLOBAL_DAILY_GEMINI_CALL_CAP,
        client_daily_call_cap=CLIENT_DAILY_GEMINI_CALL_CAP,
    )

    preflight = evaluate_campaign_execution_preflight(
        plan,
        snapshot=snapshot,
    )

    payload["usage_snapshot"] = snapshot.as_dict()
    payload["preflight"] = preflight.as_dict()

    if args.preflight:
        _write_payload(payload, args.output)
        return 0

    if not preflight.allowed:
        _write_payload(payload, args.output)
        return 2

    client = app_main.gemini_client()

    if client is None:
        raise SystemExit("GEMINI_API_KEY is required for --execute.")

    def executor(item):
        response = app_main.generate_gemini_content(
            client=client,
            client_key=GENERATION_CAMPAIGN_CLIENT_KEY,
            mode=item.task_id,
            model=item.resource_id,
            contents=item.contents,
        )

        return {
            "text": str(getattr(response, "text", "") or ""),
            "usage": app_main.usage_metadata_counts(response),
        }

    try:
        run = run_generation_evaluation(
            plan,
            executor=executor,
            allow_provider_execution=True,
            usage_counter=lambda output: output.get("usage", {}),
        )
    except EvaluationCapacityBlocked as error:
        raise SystemExit(str(error)) from error

    report = score_article_observations_with_reliability(
        run.observations,
        cases=cases,
    )

    payload["provider_calls_made"] = len(run.observations)
    payload["run"] = run.as_dict()
    payload["benchmark_quality_reliability"] = report.as_dict()

    _write_payload(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
