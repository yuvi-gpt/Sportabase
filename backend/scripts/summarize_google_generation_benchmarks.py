from __future__ import annotations

import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark import article_benchmark_case
from app.ai.benchmark_reporting import (
    evaluation_observation_from_payload,
    score_article_observations_with_reliability,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Combine one or more saved Sportabase Google generation "
            "benchmark JSON files without making provider calls."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Saved benchmark JSON result files.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional combined JSON output path.",
    )
    return parser


def _load_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise SystemExit(
            "Unable to read benchmark result: " + str(path)
        ) from error

    if not isinstance(payload, dict):
        raise SystemExit(
            "Benchmark result must contain a JSON object: " + str(path)
        )

    return payload


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

    source_files: list[str] = []
    observations = []
    case_ids: list[str] = []

    for raw_path in args.inputs:
        path = Path(raw_path).expanduser().resolve()
        payload = _load_payload(path)
        source_files.append(str(path))

        run = payload.get("run")
        if not isinstance(run, dict):
            raise SystemExit(
                "Benchmark result is missing a run object: " + str(path)
            )

        raw_observations = run.get("observations")
        if not isinstance(raw_observations, list):
            raise SystemExit(
                "Benchmark result is missing run observations: " + str(path)
            )

        for raw_observation in raw_observations:
            if not isinstance(raw_observation, dict):
                raise SystemExit(
                    "Benchmark observation must be a JSON object: " + str(path)
                )

            observation = evaluation_observation_from_payload(
                raw_observation
            )
            observations.append(observation)

            if observation.case_id not in case_ids:
                case_ids.append(observation.case_id)

    if not observations:
        raise SystemExit("No benchmark observations were found.")

    cases = tuple(
        article_benchmark_case(case_id)
        for case_id in case_ids
    )

    report = score_article_observations_with_reliability(
        observations,
        cases=cases,
    )

    payload = {
        "mode": "offline_combined_summary",
        "source_files": source_files,
        "observation_count": len(observations),
        "case_ids": case_ids,
        "report": report.as_dict(),
    }

    _write_payload(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
