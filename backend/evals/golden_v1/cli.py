from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .errors import GoldenV1Error
from .loader import load_corpus
from .reporting import evaluate_corpus, select_cases, text_report
from .serialization import deterministic_json

DEFAULT_CORPUS = Path(__file__).with_name("corpus")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Offline, provider-free Sportabase Golden-Set V1 evaluator.")
    value.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    value.add_argument("--candidate-root", type=Path, help="External <case-id>/candidate.json tree for final-output cases.")
    value.add_argument("--case", action="append", default=[])
    value.add_argument("--tag", action="append", default=[])
    value.add_argument("--mode", choices=("article", "video", "intelligence"))
    value.add_argument("--json-out", type=Path)
    value.add_argument("--format", choices=("text", "json"), default="text")
    value.add_argument("--list-cases", action="store_true")
    value.add_argument("--validate-only", action="store_true")
    value.add_argument("--warnings-as-errors", action="store_true")
    value.add_argument("--candidate-label", default="fixture")
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.candidate_root is not None and (not args.candidate_root.is_dir() or args.candidate_root.is_symlink()):
            raise GoldenV1Error("--candidate-root must be a regular directory.")
        corpus = load_corpus(args.corpus)
        selected = select_cases(corpus, case_ids=args.case, tags=args.tag, mode=args.mode)
        if args.list_cases:
            print("\n".join(case.data["case_id"] for case in selected))
            return 0
        if args.validate_only:
            invalid = sorted(
                (
                    case.data["case_id"],
                    case.validation_error,
                )
                for case in selected
                if case.validation_error is not None
            )
            if not selected:
                print("0 cases selected")
                return 0
            print(f"selected cases: {len(selected)}")
            print(f"invalid cases: {len(invalid)}")
            for case_id, diagnostic in invalid:
                print(f"INVALID_CASE {case_id}: {diagnostic}")
            return 2 if invalid else 0
        report = evaluate_corpus(corpus, candidate_label=args.candidate_label, candidate_root=args.candidate_root, case_ids=args.case, tags=args.tag, mode=args.mode)
        rendered = deterministic_json(report, pretty=True)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(rendered, encoding="utf-8")
        sys.stdout.write(rendered if args.format == "json" else text_report(report))
        totals = report["totals"]
        if totals["invalid"]: return 2
        if totals["failed"] or (args.warnings_as_errors and totals["warned"]): return 1
        return 0
    except GoldenV1Error as error:
        print("golden-v1 error: " + str(error), file=sys.stderr)
        return 2
