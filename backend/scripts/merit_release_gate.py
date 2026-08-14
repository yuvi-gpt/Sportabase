import argparse
import json
import sys

from pathlib import Path


BACKEND_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.analysis.merit_goldens import (
    load_merit_corroboration_golden_dataset,
)
from app.analysis.merit_release import (
    build_merit_live_release_gate,
)


DEFAULT_DATASET_PATH = (
    BACKEND_DIR
    / "data"
    / "merit_corroboration_goldens.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the Sportabase "
            "evidence-Merit release gate."
        )
    )

    parser.add_argument(
        "--dataset",
        default=str(
            DEFAULT_DATASET_PATH
        ),
    )

    parser.add_argument(
        "--request-live",
        action="store_true",
    )

    args = parser.parse_args()

    dataset = (
        load_merit_corroboration_golden_dataset(
            args.dataset
        )
    )

    # load_* returns a validated normalized
    # representation. Reconstruct the dataset
    # contract expected by the gate.
    gate_dataset = {
        "version": (
            dataset[
                "version"
            ]
        ),
        "cases": list(
            dataset[
                "cases"
            ]
        ),
    }

    gate = build_merit_live_release_gate(
        dataset=gate_dataset,
        request_live=(
            args.request_live
        ),
    )

    summary = {
        "version": gate[
            "version"
        ],
        "status": gate[
            "status"
        ],
        "request_live": gate[
            "request_live"
        ],
        "release_authorized": gate[
            "release_authorized"
        ],
        "live_merit_authorized": gate[
            "live_merit_authorized"
        ],
        "approved_real_world_cases": (
            gate[
                "approved_real_world_cases"
            ]
        ),
        "minimum_approved_real_world_cases": (
            gate[
                "minimum_approved_real_world_cases"
            ]
        ),
        "approved_signal_coverage": (
            gate[
                "approved_signal_coverage"
            ]
        ),
        "missing_signal_coverage": (
            gate[
                "missing_signal_coverage"
            ]
        ),
        "blockers": gate[
            "blockers"
        ],
    }

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    return (
        0
        if gate[
            "release_authorized"
        ]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
