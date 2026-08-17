from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evals.multimodal_golden import (  # noqa: E402
    evaluate_deterministic_golden_set,
    evaluate_observed_artifact,
    golden_dataset_descriptor,
    observed_template,
    write_json,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Sportabase multimodal golden evaluation without "
            "touching the production database or calling Gemini by default."
        )
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Write the evaluation report to this JSON file.",
    )
    parser.add_argument(
        "--observed",
        type=Path,
        help=(
            "Score a previously captured full-pipeline observed artifact "
            "instead of running deterministic discovery/selection."
        ),
    )
    parser.add_argument(
        "--write-observed-template",
        type=Path,
        help=(
            "Write the expected observed-artifact shape for later model/full-pipeline runs."
        ),
    )
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Print only the frozen dataset descriptor.",
    )
    return parser


def _print_summary(report):
    print("Sportabase multimodal golden evaluation")
    print("version:", report.get("version"))
    print("mode:", report.get("mode", "descriptor"))
    print("status:", report.get("status", "n/a"))

    dataset = report.get("dataset")
    if isinstance(dataset, dict):
        print("dataset:", dataset.get("dataset_id"))
        print("cases:", dataset.get("case_count"))
        print("captures:", dataset.get("capture_count"))
        print("dataset digest:", dataset.get("dataset_digest"))

    metrics = report.get("metrics")
    if isinstance(metrics, dict):
        for key in sorted(metrics):
            print(f"{key}: {metrics[key]}")

    failures = report.get("case_failures")
    if isinstance(failures, list) and failures:
        print("case failures:", ", ".join(failures))

    digest = report.get("report_digest")
    if digest:
        print("report digest:", digest)


def main(argv=None) -> int:
    args = _parser().parse_args(argv)

    if args.write_observed_template:
        write_json(args.write_observed_template, observed_template())
        print("wrote observed template:", args.write_observed_template)

    if args.describe:
        descriptor = golden_dataset_descriptor()
        print(json.dumps(descriptor, indent=2, sort_keys=True))
        return 0

    if args.observed:
        try:
            artifact = json.loads(args.observed.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print("failed to read observed artifact:", error, file=sys.stderr)
            return 2
        report = evaluate_observed_artifact(artifact)
    else:
        report = evaluate_deterministic_golden_set()

    if args.json_out:
        write_json(args.json_out, report)

    _print_summary(report)
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
