from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from evals.negative_merit_resolved_corpus import (  # noqa: E402
    corpus_template,
    evaluate_negative_merit_resolved_corpus,
    write_json,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a frozen real-world "
            "negative-Merit resolved-case corpus "
            "without providers or live scoring."
        )
    )

    parser.add_argument(
        "--corpus",
        type=Path,
        help=(
            "Path to the frozen real-world "
            "resolved-case corpus JSON."
        ),
    )

    parser.add_argument(
        "--json-out",
        type=Path,
        help=(
            "Write the evaluation report to JSON."
        ),
    )

    parser.add_argument(
        "--write-template",
        type=Path,
        help=(
            "Write an empty corpus collection "
            "template. It is not calibration evidence."
        ),
    )

    return parser


def _print_summary(
    report,
):
    print(
        "Sportabase resolved negative Merit corpus"
    )

    print(
        "version:",
        report.get(
            "version"
        ),
    )

    print(
        "status:",
        report.get(
            "status"
        ),
    )

    corpus = report.get(
        "corpus"
    )

    if isinstance(
        corpus,
        dict,
    ):
        print(
            "corpus:",
            corpus.get(
                "corpus_id"
            ),
        )

        print(
            "cases:",
            corpus.get(
                "case_count"
            ),
        )

        print(
            "resolved cases:",
            corpus.get(
                "resolved_against_claim_case_count"
            ),
        )

        print(
            "corpus digest:",
            corpus.get(
                "corpus_digest"
            ),
        )

        missing = corpus.get(
            "missing_required_classes"
        )

        if isinstance(
            missing,
            list,
        ):
            print(
                "missing classes:",
                (
                    ", ".join(
                        missing
                    )
                    if missing
                    else "none"
                ),
            )

    calibration = report.get(
        "calibration"
    )

    if isinstance(
        calibration,
        dict,
    ):
        print(
            "corpus complete:",
            calibration.get(
                "corpus_complete_for_measurement"
            ),
        )

        print(
            "numeric penalty authorized:",
            calibration.get(
                "numeric_penalty_authorized"
            ),
        )

        print(
            "live negative Merit authorized:",
            calibration.get(
                "live_negative_merit_authorized"
            ),
        )

    digest = report.get(
        "report_digest"
    )

    if digest:
        print(
            "report digest:",
            digest,
        )


def main(
    argv=None,
) -> int:
    args = _parser().parse_args(
        argv
    )

    if args.write_template:
        write_json(
            args.write_template,
            corpus_template(),
        )

        print(
            "wrote corpus template:",
            args.write_template,
        )

        if not args.corpus:
            return 0

    if not args.corpus:
        print(
            "a corpus path is required unless "
            "--write-template is used",
            file=sys.stderr,
        )

        return 2

    try:
        corpus = json.loads(
            args.corpus.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(
            "failed to read corpus:",
            error,
            file=sys.stderr,
        )

        return 2

    try:
        report = (
            evaluate_negative_merit_resolved_corpus(
                corpus=corpus
            )
        )

    except ValueError as error:
        print(
            "invalid resolved corpus:",
            error,
            file=sys.stderr,
        )

        return 2

    if args.json_out:
        write_json(
            args.json_out,
            report,
        )

    _print_summary(
        report
    )

    return (
        0
        if report.get(
            "status"
        )
        == "pass"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
