from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark import (
    DEFAULT_CHALLENGER_RESOURCE_IDS,
    DEFAULT_LIVE_BENCHMARK_CASE_IDS,
    build_article_single_pass_benchmark_plan,
    score_article_single_pass_run,
)
from app.ai.evaluation import (
    EvaluationBudget,
    EvaluationCapacityBlocked,
    run_generation_evaluation,
)


def _csv_values(raw: str) -> tuple[str, ...]:
    return tuple(
        value.strip()
        for value in str(raw or "").split(",")
        if value.strip()
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute the bounded Sportabase Google generation "
            "benchmark. Dry-run is the default."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly allow live provider calls.",
    )
    parser.add_argument(
        "--cases",
        default=",".join(DEFAULT_LIVE_BENCHMARK_CASE_IDS),
        help="Comma-separated benchmark case IDs.",
    )
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_CHALLENGER_RESOURCE_IDS),
        help=(
            "Comma-separated challenger resource IDs. The current production "
            "primary is always included automatically."
        ),
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=8,
        help="Maximum planned provider calls.",
    )
    parser.add_argument(
        "--max-input-tokens",
        type=int,
        default=100_000,
        help="Maximum total estimated input tokens across the plan.",
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


def main() -> int:
    args = _parser().parse_args()

    case_ids = _csv_values(args.cases)
    challenger_ids = _csv_values(args.models)

    cases, plan = build_article_single_pass_benchmark_plan(
        case_ids=case_ids,
        candidate_resource_ids=challenger_ids,
        budget=EvaluationBudget(
            max_provider_calls=args.max_calls,
            max_estimated_input_tokens=args.max_input_tokens,
        ),
    )

    plan_payload = {
        "mode": "live" if args.execute else "dry_run",
        "case_ids": [case.case_id for case in cases],
        "candidate_resource_ids": list(challenger_ids),
        "plan": plan.as_dict(),
    }

    if not args.execute:
        _write_payload(plan_payload, args.output)
        return 0

    if plan.blocked_provider_calls:
        blocked_resources = sorted(
            {
                item.resource_id
                for item in plan.items
                if item.capacity_blocked
            }
        )
        raise SystemExit(
            "Live benchmark blocked before provider execution. Configure "
            "project capacity for: "
            + ", ".join(blocked_resources)
        )

    from app import main as app_main

    app_main.init_db()
    client = app_main.gemini_client()

    if client is None:
        raise SystemExit(
            "GEMINI_API_KEY is required for --execute."
        )

    def executor(item):
        response = app_main.generate_gemini_content(
            client=client,
            client_key="sportabase-model-benchmark",
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

    report = score_article_single_pass_run(
        run,
        cases=cases,
    )

    payload = {
        **plan_payload,
        "run": run.as_dict(),
        "benchmark": report.as_dict(),
    }

    _write_payload(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
