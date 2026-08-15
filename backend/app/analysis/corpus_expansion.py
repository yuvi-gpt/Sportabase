import hashlib
import json

from typing import Any, Dict, Iterable, List, Tuple


from app.intelligence.providers import (
    list_providers,
)


VALIDATION_CORPUS_EXPANSION_VERSION = (
    "validation-corpus-expansion-v1"
)

DEFAULT_TARGET_RECORDS_PER_SPORT = 25

DEFAULT_ALLOWED_PROVIDER_STATUSES = (
    "active",
    "registered",
)


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).lower()


def _stable_id(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def _positive_int(
    value: Any,
    *,
    label: str,
) -> int:
    if isinstance(value, bool):
        raise ValueError(
            f"{label} must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{label} must be an integer."
        ) from exc

    if result < 1:
        raise ValueError(
            f"{label} must be at least 1."
        )

    return result


def _allowed_statuses(
    values: Iterable[str],
) -> Tuple[str, ...]:
    if isinstance(values, str):
        values = [values]

    try:
        normalized = sorted(
            {
                _key(value)
                for value in values
                if _key(value)
            }
        )
    except TypeError as exc:
        raise ValueError(
            "Allowed provider statuses "
            "must be iterable."
        ) from exc

    if not normalized:
        raise ValueError(
            "At least one allowed provider "
            "status is required."
        )

    return tuple(normalized)


def _provider_matrix():
    matrix = {}

    for provider in list_providers():
        if (
            _key(
                provider.get(
                    "data_family"
                )
            )
            != "structured_sports_data"
        ):
            continue

        provider_key = _key(
            provider.get(
                "provider_key"
            )
        )

        status = _key(
            provider.get(
                "adapter_status"
            )
        )

        sports = provider.get(
            "sports",
            (),
        )

        for sport in sports:
            sport_key = _key(sport)

            if not sport_key or sport_key == "*":
                continue

            matrix.setdefault(
                sport_key,
                [],
            ).append(
                {
                    "provider_key": (
                        provider_key
                    ),
                    "adapter_status": (
                        status
                    ),
                    "access_mode": _key(
                        provider.get(
                            "access_mode"
                        )
                    ),
                }
            )

    for sport_key in matrix:
        matrix[sport_key] = sorted(
            matrix[sport_key],
            key=lambda row: (
                row["provider_key"],
                row["adapter_status"],
            ),
        )

    return dict(
        sorted(
            matrix.items()
        )
    )


def _normalize_record(
    raw: Any,
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(
            "Corpus expansion records "
            "must be dictionaries."
        )

    sport_key = _key(
        raw.get(
            "sport_key"
        )
    )

    data_family = _key(
        raw.get(
            "data_family"
        )
    )

    origin_type = _key(
        raw.get(
            "origin_type"
        )
    )

    dataset_name = _key(
        raw.get(
            "dataset_name"
        )
    )

    external_record_id = _clean(
        raw.get(
            "external_record_id"
        )
    )

    payload_hash = _clean(
        raw.get(
            "payload_hash"
        )
    )

    if not origin_type:
        raise ValueError(
            "Corpus expansion origin type "
            "is required."
        )

    if not data_family:
        raise ValueError(
            "Corpus expansion data family "
            "is required."
        )

    if not dataset_name:
        raise ValueError(
            "Corpus expansion dataset name "
            "is required."
        )

    if not external_record_id:
        raise ValueError(
            "Corpus expansion external record "
            "ID is required."
        )

    logical_identity = {
        "origin_type": origin_type,
        "dataset_name": dataset_name,
        "external_record_id": (
            external_record_id
        ),
    }

    record_id = (
        _clean(
            raw.get(
                "id"
            )
        )
        or _stable_id(
            {
                **logical_identity,
                "payload_hash": (
                    payload_hash
                ),
            }
        )
    )

    return {
        "record_id": record_id,
        "sport_key": sport_key,
        "data_family": data_family,
        "origin_type": origin_type,
        "dataset_name": dataset_name,
        "external_record_id": (
            external_record_id
        ),
        "payload_hash": payload_hash,
        "occurred_at": _clean(
            raw.get(
                "occurred_at"
            )
        ),
        "ingested_at": _clean(
            raw.get(
                "ingested_at"
            )
        ),
        "logical_identity": (
            logical_identity
        ),
    }


def _representative_records(
    records: Iterable[
        Dict[str, Any]
    ],
) -> List[Dict[str, Any]]:
    if isinstance(records, dict):
        raise ValueError(
            "Corpus expansion records "
            "must be an iterable of rows."
        )

    try:
        normalized = [
            _normalize_record(row)
            for row in records
        ]
    except TypeError as exc:
        raise ValueError(
            "Corpus expansion records "
            "must be iterable."
        ) from exc

    normalized = [
        row
        for row in normalized
        if (
            row["data_family"]
            == "structured_sports_data"
            and row["sport_key"]
        )
    ]

    normalized.sort(
        key=lambda row: (
            row["sport_key"],
            row["origin_type"],
            row["dataset_name"],
            row["external_record_id"],
            row["ingested_at"],
            row["record_id"],
        )
    )

    representatives = {}

    for row in normalized:
        identity = (
            row["sport_key"],
            row["origin_type"],
            row["dataset_name"],
            row["external_record_id"],
        )

        # Multiple payload revisions of the same
        # external record count once for coverage.
        if identity not in representatives:
            representatives[
                identity
            ] = row

    return sorted(
        representatives.values(),
        key=lambda row: (
            row["sport_key"],
            row["dataset_name"],
            row["external_record_id"],
            row["record_id"],
        ),
    )


def build_balanced_validation_sample(
    *,
    records: Iterable[
        Dict[str, Any]
    ],
    per_sport_limit: int = 5,
) -> List[Dict[str, Any]]:
    limit = _positive_int(
        per_sport_limit,
        label=(
            "Validation sample per-sport limit"
        ),
    )

    target_sports = set(
        _provider_matrix()
    )

    representatives = [
        row
        for row
        in _representative_records(
            records
        )
        if row["sport_key"]
        in target_sports
    ]

    by_sport = {}

    for row in representatives:
        by_sport.setdefault(
            row["sport_key"],
            {},
        ).setdefault(
            row["dataset_name"],
            [],
        ).append(row)

    selected = []

    for sport_key in sorted(
        by_sport
    ):
        datasets = by_sport[
            sport_key
        ]

        dataset_keys = sorted(
            datasets
        )

        sport_rows = []

        index = 0

        while (
            len(sport_rows) < limit
        ):
            added = False

            for dataset_key in dataset_keys:
                rows = datasets[
                    dataset_key
                ]

                if index < len(rows):
                    sport_rows.append(
                        rows[index]
                    )

                    added = True

                    if (
                        len(sport_rows)
                        >= limit
                    ):
                        break

            if not added:
                break

            index += 1

        selected.extend(
            sport_rows
        )

    return selected


def build_validation_corpus_expansion(
    *,
    records: Iterable[
        Dict[str, Any]
    ],
    target_records_per_sport: int = (
        DEFAULT_TARGET_RECORDS_PER_SPORT
    ),
    allowed_provider_statuses: Iterable[
        str
    ] = DEFAULT_ALLOWED_PROVIDER_STATUSES,
    validation_sample_per_sport: int = 5,
) -> Dict[str, Any]:
    target = _positive_int(
        target_records_per_sport,
        label=(
            "Corpus expansion target "
            "records per sport"
        ),
    )

    sample_limit = _positive_int(
        validation_sample_per_sport,
        label=(
            "Validation sample per-sport limit"
        ),
    )

    allowed_statuses = (
        _allowed_statuses(
            allowed_provider_statuses
        )
    )

    provider_matrix = (
        _provider_matrix()
    )

    target_sports = sorted(
        provider_matrix
    )

    representatives = (
        _representative_records(
            records
        )
    )

    coverage_counts = {
        sport_key: 0
        for sport_key in target_sports
    }

    unregistered_sports = set()

    for row in representatives:
        sport_key = row[
            "sport_key"
        ]

        if sport_key in coverage_counts:
            coverage_counts[
                sport_key
            ] += 1
        else:
            unregistered_sports.add(
                sport_key
            )

    coverage = []
    expansion_queue = []

    for sport_key in target_sports:
        providers = (
            provider_matrix[
                sport_key
            ]
        )

        ready_providers = [
            row
            for row in providers
            if (
                row[
                    "adapter_status"
                ]
                in allowed_statuses
            )
        ]

        blocked_providers = [
            row
            for row in providers
            if (
                row[
                    "adapter_status"
                ]
                not in allowed_statuses
            )
        ]

        current_count = (
            coverage_counts[
                sport_key
            ]
        )

        deficit = max(
            0,
            target - current_count,
        )

        if deficit == 0:
            coverage_status = "covered"
            execution_status = (
                "not_needed"
            )

        elif current_count == 0:
            coverage_status = "empty"
            execution_status = (
                "ready"
                if ready_providers
                else "blocked"
            )

        else:
            coverage_status = (
                "under_covered"
            )
            execution_status = (
                "ready"
                if ready_providers
                else "blocked"
            )

        row = {
            "sport_key": sport_key,
            "unique_record_count": (
                current_count
            ),
            "target_record_count": (
                target
            ),
            "deficit": deficit,
            "coverage_status": (
                coverage_status
            ),
            "execution_status": (
                execution_status
            ),
            "provider_candidates": (
                ready_providers
            ),
            "blocked_provider_candidates": (
                blocked_providers
            ),
        }

        coverage.append(row)

        if deficit > 0:
            expansion_queue.append(
                {
                    "sport_key": (
                        sport_key
                    ),
                    "needed_unique_records": (
                        deficit
                    ),
                    "execution_status": (
                        execution_status
                    ),
                    "provider_candidates": (
                        ready_providers
                    ),
                    "blocked_provider_candidates": (
                        blocked_providers
                    ),
                }
            )

    sample = (
        build_balanced_validation_sample(
            records=representatives,
            per_sport_limit=(
                sample_limit
            ),
        )
    )

    return {
        "version": (
            VALIDATION_CORPUS_EXPANSION_VERSION
        ),
        "target_records_per_sport": (
            target
        ),
        "allowed_provider_statuses": list(
            allowed_statuses
        ),
        "target_sports": target_sports,
        "coverage": coverage,
        "expansion_queue": (
            expansion_queue
        ),
        "validation_sample": (
            sample
        ),
        "unregistered_record_sports": (
            sorted(
                unregistered_sports
            )
        ),
        "summary": {
            "target_sport_count": len(
                target_sports
            ),
            "covered_sport_count": sum(
                1
                for row in coverage
                if (
                    row[
                        "coverage_status"
                    ]
                    == "covered"
                )
            ),
            "under_covered_sport_count": sum(
                1
                for row in coverage
                if (
                    row[
                        "coverage_status"
                    ]
                    != "covered"
                )
            ),
            "blocked_expansion_sport_count": sum(
                1
                for row
                in expansion_queue
                if (
                    row[
                        "execution_status"
                    ]
                    == "blocked"
                )
            ),
            "unique_structured_record_count": (
                len(
                    representatives
                )
            ),
            "validation_sample_count": (
                len(
                    sample
                )
            ),
        },
        "policy": {
            "coverage_counts_unique_external_records": True,
            "payload_revisions_do_not_inflate_coverage": True,
            "provider_review_gates_are_respected": True,
            "benchmark_wildcards_are_not_sport_ground_truth": True,
            "balanced_sample_prefers_dataset_diversity": True,
            "record_volume_does_not_establish_truth": True,
            "does_not_fetch_remote_data": True,
            "does_not_establish_training_truth": True,
            "does_not_change_adjudication": True,
            "does_not_change_live_merit": True,
            "human_review_required": False,
        },
    }
