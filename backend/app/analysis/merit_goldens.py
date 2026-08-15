import json

from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit

from app.analysis.merit_evaluation import (
    MERIT_CORROBORATION_GOLDEN_CASE_VERSION,
)
from app.analysis.validation_snapshot import (
    build_claim_evidence_snapshot,
)


MERIT_CORROBORATION_GOLDEN_DATASET_VERSION = (
    "merit-corroboration-golden-dataset-v1"
)

MERIT_CORROBORATION_CURATION_VERSION = (
    "merit-corroboration-curation-v1"
)

REAL_WORLD_ORIGIN = "real_world"
SYNTHETIC_POLICY_ORIGIN = "synthetic_policy"

CURATION_ORIGINS = (
    REAL_WORLD_ORIGIN,
    SYNTHETIC_POLICY_ORIGIN,
)

CURATION_REVIEW_STATUSES = (
    "draft",
    "approved",
    "rejected",
)

VERIFIED_CORROBORATION_SIGNALS = (
    "verified_corroboration",
    "verified_corroboration_contested",
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _reviewed_at(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            "Approved real-world golden case "
            "reviewed_at is required."
        )

    candidate = text

    if candidate.endswith("Z"):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            candidate
        )
    except ValueError as exc:
        raise ValueError(
            "Approved real-world golden case "
            "reviewed_at must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
    ):
        raise ValueError(
            "Approved real-world golden case "
            "reviewed_at must include a timezone."
        )

    return parsed.isoformat()


def _source_url(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            "Golden case source URL "
            "cannot be empty."
        )

    parsed = urlsplit(
        text
    )

    scheme = parsed.scheme.lower()
    hostname = (
        parsed.hostname or ""
    ).lower()

    if (
        scheme not in {
            "http",
            "https",
        }
        or not hostname
    ):
        raise ValueError(
            "Golden case source URL "
            "must be an absolute HTTP(S) URL."
        )

    netloc = hostname

    if parsed.port is not None:
        netloc += (
            ":"
            + str(parsed.port)
        )

    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            parsed.query,
            "",
        )
    )


def validate_merit_corroboration_golden_dataset(
    dataset: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        dataset,
        dict,
    ):
        raise ValueError(
            "Merit corroboration golden "
            "dataset must be a dictionary."
        )

    if (
        _clean(
            dataset.get(
                "version"
            )
        )
        != MERIT_CORROBORATION_GOLDEN_DATASET_VERSION
    ):
        raise ValueError(
            "Unsupported Merit corroboration "
            "golden dataset version."
        )

    raw_cases = dataset.get(
        "cases",
        [],
    )

    if not isinstance(
        raw_cases,
        list,
    ):
        raise ValueError(
            "Merit corroboration golden "
            "dataset cases must be a list."
        )

    seen_ids = set()
    normalized_cases = []

    counts = {
        "cases": 0,
        "real_world": 0,
        "synthetic_policy": 0,
        "draft": 0,
        "approved": 0,
        "rejected": 0,
        "approved_real_world": 0,
        "evaluation_eligible": 0,
    }

    for raw_case in raw_cases:
        if not isinstance(
            raw_case,
            dict,
        ):
            raise ValueError(
                "Each golden dataset case "
                "must be a dictionary."
            )

        if (
            _clean(
                raw_case.get(
                    "version"
                )
            )
            != MERIT_CORROBORATION_GOLDEN_CASE_VERSION
        ):
            raise ValueError(
                "Unsupported Merit "
                "corroboration golden "
                "case version."
            )

        case_id = _clean(
            raw_case.get(
                "id"
            )
        )

        claim_id = _clean(
            raw_case.get(
                "claim_id"
            )
        )

        if not case_id:
            raise ValueError(
                "Golden case ID is required."
            )

        if case_id in seen_ids:
            raise ValueError(
                "Golden dataset case IDs "
                "must be unique."
            )

        seen_ids.add(
            case_id
        )

        if not claim_id:
            raise ValueError(
                "Golden case claim ID "
                "is required."
            )

        for field in (
            "legacy_score",
            "corroboration_state",
            "expectations",
        ):
            if not isinstance(
                raw_case.get(field),
                dict,
            ):
                raise ValueError(
                    f"Golden case {field} "
                    "must be a dictionary."
                )

        expectations = raw_case[
            "expectations"
        ]

        expected_signal = _clean(
            expectations.get(
                "signal"
            )
        )

        if not expected_signal:
            raise ValueError(
                "Golden case expected "
                "signal is required."
            )

        curation = raw_case.get(
            "curation"
        )

        if not isinstance(
            curation,
            dict,
        ):
            raise ValueError(
                "Golden case curation "
                "metadata is required."
            )

        if (
            _clean(
                curation.get(
                    "version"
                )
            )
            != MERIT_CORROBORATION_CURATION_VERSION
        ):
            raise ValueError(
                "Unsupported golden case "
                "curation version."
            )

        origin = _clean(
            curation.get(
                "origin"
            )
        ).lower()

        review_status = _clean(
            curation.get(
                "review_status"
            )
        ).lower()

        if origin not in CURATION_ORIGINS:
            raise ValueError(
                "Golden case curation origin "
                "is unsupported."
            )

        if (
            review_status
            not in CURATION_REVIEW_STATUSES
        ):
            raise ValueError(
                "Golden case review status "
                "is unsupported."
            )

        source_urls = curation.get(
            "source_urls",
            [],
        )

        if not isinstance(
            source_urls,
            list,
        ):
            raise ValueError(
                "Golden case source_urls "
                "must be a list."
            )

        normalized_urls = [
            _source_url(
                value
            )
            for value in source_urls
        ]

        if (
            len(
                set(
                    normalized_urls
                )
            )
            != len(
                normalized_urls
            )
        ):
            raise ValueError(
                "Golden case source URLs "
                "must be unique."
            )

        label_basis = _clean(
            curation.get(
                "label_basis"
            )
        )

        reviewer = _clean(
            curation.get(
                "reviewer"
            )
        )

        reviewed_at = _clean(
            curation.get(
                "reviewed_at"
            )
        )

        raw_evidence_snapshot = (
            raw_case.get(
                "evidence_snapshot"
            )
        )

        normalized_evidence_snapshot = None

        if raw_evidence_snapshot is not None:
            if not isinstance(
                raw_evidence_snapshot,
                dict,
            ):
                raise ValueError(
                    "Golden case evidence_snapshot "
                    "must be a dictionary."
                )

            normalized_evidence_snapshot = (
                build_claim_evidence_snapshot(
                    raw_evidence_snapshot
                )
            )

            if (
                normalized_evidence_snapshot[
                    "claim_id"
                ]
                != claim_id
            ):
                raise ValueError(
                    "Golden case evidence snapshot "
                    "claim ID must match the "
                    "golden claim ID."
                )

        approved_real_world = bool(
            origin
            == REAL_WORLD_ORIGIN
            and review_status
            == "approved"
        )

        if origin == REAL_WORLD_ORIGIN:
            if not normalized_urls:
                raise ValueError(
                    "Real-world golden case "
                    "requires at least one "
                    "source URL."
                )

            if not label_basis:
                raise ValueError(
                    "Real-world golden case "
                    "label_basis is required."
                )

        if approved_real_world:
            if not reviewer:
                raise ValueError(
                    "Approved real-world "
                    "golden case reviewer "
                    "is required."
                )

            reviewed_at = (
                _reviewed_at(
                    reviewed_at
                )
            )

            if (
                normalized_evidence_snapshot
                is None
            ):
                raise ValueError(
                    "Approved real-world golden "
                    "case requires a time-bounded "
                    "evidence snapshot."
                )

            snapshot_review = (
                normalized_evidence_snapshot[
                    "review"
                ]
            )

            if (
                snapshot_review[
                    "status"
                ]
                != "approved"
            ):
                raise ValueError(
                    "Approved real-world golden "
                    "case requires an approved "
                    "evidence snapshot."
                )

            if (
                snapshot_review[
                    "reviewer"
                ]
                != reviewer
            ):
                raise ValueError(
                    "Golden curation reviewer "
                    "must match evidence snapshot "
                    "reviewer."
                )

            golden_review_instant = (
                datetime.fromisoformat(
                    reviewed_at.replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

            snapshot_review_instant = (
                datetime.fromisoformat(
                    snapshot_review[
                        "reviewed_at"
                    ].replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

            if (
                golden_review_instant
                != snapshot_review_instant
            ):
                raise ValueError(
                    "Golden curation reviewed_at "
                    "must match evidence snapshot "
                    "reviewed_at."
                )

            snapshot_source_urls = [
                _source_url(
                    observation[
                        "source_url"
                    ]
                )
                for observation
                in normalized_evidence_snapshot[
                    "observations"
                ]
            ]

            if (
                sorted(
                    set(
                        snapshot_source_urls
                    )
                )
                != sorted(
                    normalized_urls
                )
            ):
                raise ValueError(
                    "Golden case source URLs "
                    "must match evidence snapshot "
                    "source URLs."
                )

            if (
                expected_signal
                in VERIFIED_CORROBORATION_SIGNALS
                and len(
                    normalized_urls
                )
                < 2
            ):
                raise ValueError(
                    "Approved verified "
                    "corroboration case "
                    "requires at least two "
                    "unique source URLs."
                )

        normalized_curation = {
            **curation,
            "version": (
                MERIT_CORROBORATION_CURATION_VERSION
            ),
            "origin": origin,
            "review_status": (
                review_status
            ),
            "source_urls": (
                normalized_urls
            ),
            "label_basis": (
                label_basis
            ),
            "reviewer": (
                reviewer
            ),
            "reviewed_at": (
                reviewed_at
            ),
        }

        normalized_case = {
            **raw_case,
            "id": case_id,
            "claim_id": claim_id,
            "curation": (
                normalized_curation
            ),
        }

        if (
            normalized_evidence_snapshot
            is not None
        ):
            normalized_case[
                "evidence_snapshot"
            ] = (
                normalized_evidence_snapshot
            )

        normalized_cases.append(
            normalized_case
        )

        counts["cases"] += 1
        counts[origin] += 1
        counts[review_status] += 1

        if approved_real_world:
            counts[
                "approved_real_world"
            ] += 1

            counts[
                "evaluation_eligible"
            ] += 1

    eligible_cases = [
        case
        for case in normalized_cases
        if (
            case[
                "curation"
            ][
                "origin"
            ]
            == REAL_WORLD_ORIGIN
            and case[
                "curation"
            ][
                "review_status"
            ]
            == "approved"
        )
    ]

    evaluation_ready = bool(
        eligible_cases
    )

    return {
        "version": (
            MERIT_CORROBORATION_GOLDEN_DATASET_VERSION
        ),
        "status": (
            "ready_for_evaluation"
            if evaluation_ready
            else "awaiting_curated_cases"
        ),
        "counts": (
            counts
        ),
        "cases": (
            normalized_cases
        ),
        "approved_real_world_cases": (
            eligible_cases
        ),
        "evaluation_ready": (
            evaluation_ready
        ),
        "live_enablement_authorized": (
            False
        ),
        "policy": {
            (
                "synthetic_cases_are_not_"
                "real_world_validation"
            ): True,
            (
                "only_approved_real_world_"
                "cases_are_evaluation_eligible"
            ): True,
            (
                "approved_real_world_cases_"
                "require_human_review_metadata"
            ): True,
            (
                "approved_real_world_cases_"
                "require_time_bounded_"
                "evidence_snapshot"
            ): True,
            (
                "real_world_cases_require_"
                "source_provenance"
            ): True,
            (
                "verified_corroboration_cases_"
                "require_multiple_sources"
            ): True,
            (
                "dataset_validation_never_"
                "authorizes_live_merit"
            ): True,
        },
    }


def load_merit_corroboration_golden_dataset(
    path,
) -> Dict[str, Any]:
    dataset_path = Path(
        path
    )

    try:
        raw_text = dataset_path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise ValueError(
            "Unable to read Merit "
            "corroboration golden dataset."
        ) from exc

    try:
        dataset = json.loads(
            raw_text
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Merit corroboration golden "
            "dataset is not valid JSON."
        ) from exc

    return (
        validate_merit_corroboration_golden_dataset(
            dataset
        )
    )


def select_approved_real_world_golden_cases(
    dataset: Dict[str, Any],
):
    validated = (
        validate_merit_corroboration_golden_dataset(
            dataset
        )
    )

    return list(
        validated[
            "approved_real_world_cases"
        ]
    )
