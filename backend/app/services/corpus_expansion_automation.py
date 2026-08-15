import hashlib
import json

from typing import Any, Dict, Iterable, Optional


from app.analysis.corpus_expansion import (
    DEFAULT_ALLOWED_PROVIDER_STATUSES,
    DEFAULT_TARGET_RECORDS_PER_SPORT,
    VALIDATION_CORPUS_EXPANSION_VERSION,
    build_validation_corpus_expansion,
)

from app.services.corpus_adapters import (
    build_cricsheet_request,
    build_openf1_request,
    build_statsbomb_open_request,
    fetch_remote_request,
    ingest_normalized_records,
    normalize_cricsheet_matches,
    normalize_openf1_rows,
    normalize_statsbomb_rows,
    read_cricsheet_json_archive,
)


CORPUS_EXPANSION_AUTOMATION_VERSION = (
    "corpus-expansion-automation-v1"
)

CORPUS_EXPANSION_TASK_PLAN_VERSION = (
    "corpus-expansion-task-plan-v1"
)

CORPUS_EXPANSION_TASK_VERSION = (
    "corpus-expansion-task-v1"
)


EXECUTABLE_PROVIDER_KEYS = {
    "openf1",
    "statsbomb_open",
    "cricsheet",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _copy(
    value: Any,
) -> Any:
    return json.loads(
        _canonical_json(
            value
        )
    )


def _stable_id(
    value: Any,
    *,
    prefix: str,
) -> str:
    return hashlib.sha256(
        (
            prefix
            + _canonical_json(
                value
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _positive_int(
    value: Any,
    *,
    label: str,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{label} must be an integer."
        )

    try:
        result = int(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{label} must be an integer."
        ) from exc

    if result < 1:
        raise ValueError(
            f"{label} must be at least 1."
        )

    return result


def load_persisted_structured_corpus_records(
    *,
    connection_factory,
):
    if connection_factory is None:
        raise ValueError(
            "Corpus automation connection "
            "factory is required."
        )

    conn = connection_factory()

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM corpus_records
            WHERE data_family = ?
              AND sport_key <> ''
            ORDER BY
              sport_key ASC,
              dataset_name ASC,
              external_record_id ASC,
              ingested_at ASC,
              id ASC
            """,
            (
                "structured_sports_data",
            ),
        ).fetchall()

    finally:
        conn.close()

    return [
        dict(
            row
        )
        for row in rows
    ]


def _provider_parameters(
    *,
    provider_parameters: Dict[
        str,
        Any,
    ],
    provider_key: str,
    sport_key: str,
) -> Optional[
    Dict[str, Any]
]:
    direct = provider_parameters.get(
        provider_key
    )

    if isinstance(
        direct,
        dict,
    ):
        return _copy(
            direct
        )

    sport_block = provider_parameters.get(
        sport_key
    )

    if isinstance(
        sport_block,
        dict,
    ):
        nested = sport_block.get(
            provider_key
        )

        if isinstance(
            nested,
            dict,
        ):
            return _copy(
                nested
            )

    return None


def _build_provider_request(
    *,
    provider_key: str,
    parameters: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    if provider_key == "openf1":
        endpoint = _key(
            parameters.get(
                "endpoint"
            )
        )

        if not endpoint:
            raise ValueError(
                "OpenF1 automation requires "
                "an endpoint."
            )

        filters = parameters.get(
            "filters",
            {},
        )

        if not isinstance(
            filters,
            dict,
        ):
            raise ValueError(
                "OpenF1 automation filters "
                "must be a dictionary."
            )

        return build_openf1_request(
            endpoint=endpoint,
            filters=filters,
        )

    if provider_key == "statsbomb_open":
        resource = _key(
            parameters.get(
                "resource"
            )
        )

        if not resource:
            raise ValueError(
                "StatsBomb automation requires "
                "a resource."
            )

        return build_statsbomb_open_request(
            resource=resource,
            competition_id=(
                parameters.get(
                    "competition_id"
                )
            ),
            season_id=(
                parameters.get(
                    "season_id"
                )
            ),
            match_id=(
                parameters.get(
                    "match_id"
                )
            ),
        )

    if provider_key == "cricsheet":
        archive_name = _clean(
            parameters.get(
                "archive_name"
            )
        )

        if not archive_name:
            raise ValueError(
                "Cricsheet automation requires "
                "an archive name."
            )

        return build_cricsheet_request(
            archive_name=(
                archive_name
            ),
        )

    raise ValueError(
        "Corpus automation provider "
        "is not executable."
    )


def build_corpus_expansion_tasks(
    *,
    expansion: Dict[
        str,
        Any,
    ],
    provider_parameters: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    if not isinstance(
        expansion,
        dict,
    ):
        raise ValueError(
            "Corpus expansion packet "
            "must be a dictionary."
        )

    if (
        _clean(
            expansion.get(
                "version"
            )
        )
        != (
            VALIDATION_CORPUS_EXPANSION_VERSION
        )
    ):
        raise ValueError(
            "Corpus automation requires "
            "the current expansion version."
        )

    provider_parameters = (
        provider_parameters
        or {}
    )

    if not isinstance(
        provider_parameters,
        dict,
    ):
        raise ValueError(
            "Corpus automation provider "
            "parameters must be a dictionary."
        )

    queue = expansion.get(
        "expansion_queue"
    )

    if not isinstance(
        queue,
        list,
    ):
        raise ValueError(
            "Corpus expansion queue "
            "must be a list."
        )

    tasks = []
    blocked = []

    for raw in queue:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "Corpus expansion queue rows "
                "must be dictionaries."
            )

        sport_key = _key(
            raw.get(
                "sport_key"
            )
        )

        needed = _positive_int(
            raw.get(
                "needed_unique_records"
            ),
            label=(
                "Corpus automation deficit"
            ),
        )

        execution_status = _key(
            raw.get(
                "execution_status"
            )
        )

        if not sport_key:
            raise ValueError(
                "Corpus automation sport "
                "key is required."
            )

        provider_candidates = raw.get(
            "provider_candidates",
            [],
        )

        if not isinstance(
            provider_candidates,
            list,
        ):
            raise ValueError(
                "Corpus automation provider "
                "candidates must be a list."
            )

        if execution_status != "ready":
            blocked.append(
                {
                    "sport_key": sport_key,
                    "needed_unique_records": (
                        needed
                    ),
                    "status": (
                        "blocked_provider_gate"
                    ),
                    "provider_candidates": [],
                }
            )

            continue

        implemented = sorted(
            {
                _key(
                    row.get(
                        "provider_key"
                    )
                )
                for row
                in provider_candidates
                if (
                    isinstance(
                        row,
                        dict,
                    )
                    and _key(
                        row.get(
                            "provider_key"
                        )
                    )
                    in (
                        EXECUTABLE_PROVIDER_KEYS
                    )
                )
            }
        )

        if not implemented:
            blocked.append(
                {
                    "sport_key": sport_key,
                    "needed_unique_records": (
                        needed
                    ),
                    "status": (
                        "blocked_adapter_not_implemented"
                    ),
                    "provider_candidates": sorted(
                        {
                            _key(
                                row.get(
                                    "provider_key"
                                )
                            )
                            for row
                            in provider_candidates
                            if (
                                isinstance(
                                    row,
                                    dict,
                                )
                                and _key(
                                    row.get(
                                        "provider_key"
                                    )
                                )
                            )
                        }
                    ),
                }
            )

            continue

        selected_provider = None
        selected_parameters = None

        for provider_key in implemented:
            parameters = (
                _provider_parameters(
                    provider_parameters=(
                        provider_parameters
                    ),
                    provider_key=(
                        provider_key
                    ),
                    sport_key=(
                        sport_key
                    ),
                )
            )

            if parameters is None:
                continue

            selected_provider = (
                provider_key
            )

            selected_parameters = (
                parameters
            )

            break

        if selected_provider is None:
            blocked.append(
                {
                    "sport_key": sport_key,
                    "needed_unique_records": (
                        needed
                    ),
                    "status": (
                        "blocked_missing_parameters"
                    ),
                    "provider_candidates": (
                        implemented
                    ),
                }
            )

            continue

        request = _build_provider_request(
            provider_key=(
                selected_provider
            ),
            parameters=(
                selected_parameters
            ),
        )

        identity = {
            "sport_key": sport_key,
            "provider_key": (
                selected_provider
            ),
            "needed_unique_records": (
                needed
            ),
            "request": request,
            "parameters": (
                selected_parameters
            ),
        }

        tasks.append(
            {
                "version": (
                    CORPUS_EXPANSION_TASK_VERSION
                ),
                "id": _stable_id(
                    identity,
                    prefix=(
                        "corpus-expansion-task|"
                    ),
                ),
                **identity,
            }
        )

    tasks = sorted(
        tasks,
        key=lambda row: (
            row[
                "sport_key"
            ],
            row[
                "provider_key"
            ],
            row[
                "id"
            ],
        ),
    )

    blocked = sorted(
        blocked,
        key=lambda row: (
            row[
                "sport_key"
            ],
            row[
                "status"
            ],
        ),
    )

    return {
        "version": (
            CORPUS_EXPANSION_TASK_PLAN_VERSION
        ),
        "tasks": tasks,
        "blocked": blocked,
        "summary": {
            "task_count": len(
                tasks
            ),
            "blocked_count": len(
                blocked
            ),
        },
        "policy": {
            "only_existing_adapter_paths_execute": True,
            "provider_review_gates_are_preserved": True,
            "missing_provider_parameters_block_execution": True,
            "one_provider_task_per_sport_per_plan": True,
            "task_identity_is_deterministic": True,
            "does_not_fetch_by_itself": True,
            "does_not_change_live_merit": True,
        },
    }


def _normalize_provider_payload(
    *,
    task: Dict[
        str,
        Any,
    ],
    payload: Any,
    cricsheet_reader,
):
    provider_key = task[
        "provider_key"
    ]

    parameters = task[
        "parameters"
    ]

    if provider_key == "openf1":
        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "OpenF1 automation payload "
                "must be a list."
            )

        return normalize_openf1_rows(
            endpoint=(
                parameters[
                    "endpoint"
                ]
            ),
            rows=payload,
            season_key=_clean(
                parameters.get(
                    "season_key"
                )
            ),
        )

    if provider_key == "statsbomb_open":
        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "StatsBomb automation payload "
                "must be a list."
            )

        return normalize_statsbomb_rows(
            resource=(
                parameters[
                    "resource"
                ]
            ),
            rows=payload,
            competition_key=_clean(
                parameters.get(
                    "competition_key"
                )
            ),
            season_key=_clean(
                parameters.get(
                    "season_key"
                )
            ),
            match_id=(
                parameters.get(
                    "match_id"
                )
            ),
        )

    if provider_key == "cricsheet":
        if not isinstance(
            payload,
            (
                bytes,
                bytearray,
            ),
        ):
            raise ValueError(
                "Cricsheet automation payload "
                "must be bytes."
            )

        matches = cricsheet_reader(
            bytes(
                payload
            )
        )

        return normalize_cricsheet_matches(
            matches=matches,
            competition_key=_clean(
                parameters.get(
                    "competition_key"
                )
            ),
            season_key=_clean(
                parameters.get(
                    "season_key"
                )
            ),
        )

    raise ValueError(
        "Corpus automation provider "
        "is not executable."
    )


def execute_corpus_expansion_tasks(
    *,
    task_plan: Dict[
        str,
        Any,
    ],
    connection_factory,
    dry_run: bool = False,
    fetcher=fetch_remote_request,
    ingestor=ingest_normalized_records,
    cricsheet_reader=(
        read_cricsheet_json_archive
    ),
) -> Dict[str, Any]:
    if not isinstance(
        task_plan,
        dict,
    ):
        raise ValueError(
            "Corpus automation task plan "
            "must be a dictionary."
        )

    if (
        _clean(
            task_plan.get(
                "version"
            )
        )
        != (
            CORPUS_EXPANSION_TASK_PLAN_VERSION
        )
    ):
        raise ValueError(
            "Unsupported corpus automation "
            "task plan version."
        )

    if not isinstance(
        dry_run,
        bool,
    ):
        raise ValueError(
            "Corpus automation dry_run "
            "must be boolean."
        )

    if connection_factory is None:
        raise ValueError(
            "Corpus automation connection "
            "factory is required."
        )

    tasks = task_plan.get(
        "tasks"
    )

    if not isinstance(
        tasks,
        list,
    ):
        raise ValueError(
            "Corpus automation tasks "
            "must be a list."
        )

    results = []

    for raw_task in tasks:
        if not isinstance(
            raw_task,
            dict,
        ):
            raise ValueError(
                "Corpus automation task "
                "must be a dictionary."
            )

        task = _copy(
            raw_task
        )

        if (
            _clean(
                task.get(
                    "version"
                )
            )
            != (
                CORPUS_EXPANSION_TASK_VERSION
            )
        ):
            raise ValueError(
                "Unsupported corpus automation "
                "task version."
            )

        task_id = _clean(
            task.get(
                "id"
            )
        )

        provider_key = _key(
            task.get(
                "provider_key"
            )
        )

        needed = _positive_int(
            task.get(
                "needed_unique_records"
            ),
            label=(
                "Corpus automation task deficit"
            ),
        )

        if not task_id:
            raise ValueError(
                "Corpus automation task ID "
                "is required."
            )

        if (
            provider_key
            not in (
                EXECUTABLE_PROVIDER_KEYS
            )
        ):
            raise ValueError(
                "Corpus automation task provider "
                "is not executable."
            )

        if dry_run:
            results.append(
                {
                    "task_id": task_id,
                    "sport_key": (
                        task[
                            "sport_key"
                        ]
                    ),
                    "provider_key": (
                        provider_key
                    ),
                    "status": "planned",
                    "fetched_record_count": 0,
                    "selected_record_count": 0,
                    "created_record_count": 0,
                    "existing_record_count": 0,
                }
            )

            continue

        try:
            payload = fetcher(
                task[
                    "request"
                ]
            )

            normalized = (
                _normalize_provider_payload(
                    task=task,
                    payload=payload,
                    cricsheet_reader=(
                        cricsheet_reader
                    ),
                )
            )

            fetched_count = len(
                normalized
            )

            selected = normalized[
                :needed
            ]

            if selected:
                ingestion = ingestor(
                    records=selected,
                    connection_factory=(
                        connection_factory
                    ),
                )

                counts = ingestion.get(
                    "counts",
                    {},
                )

                created = int(
                    counts.get(
                        "created",
                        0,
                    )
                )

                existing = int(
                    counts.get(
                        "existing",
                        0,
                    )
                )

            else:
                created = 0
                existing = 0

            results.append(
                {
                    "task_id": task_id,
                    "sport_key": (
                        task[
                            "sport_key"
                        ]
                    ),
                    "provider_key": (
                        provider_key
                    ),
                    "status": (
                        "completed"
                        if selected
                        else "completed_empty"
                    ),
                    "fetched_record_count": (
                        fetched_count
                    ),
                    "selected_record_count": (
                        len(
                            selected
                        )
                    ),
                    "created_record_count": (
                        created
                    ),
                    "existing_record_count": (
                        existing
                    ),
                }
            )

        except Exception as exc:
            results.append(
                {
                    "task_id": task_id,
                    "sport_key": (
                        task[
                            "sport_key"
                        ]
                    ),
                    "provider_key": (
                        provider_key
                    ),
                    "status": "failed",
                    "error_type": (
                        type(
                            exc
                        ).__name__
                    ),
                    "error": _clean(
                        str(
                            exc
                        )
                    ),
                    "fetched_record_count": 0,
                    "selected_record_count": 0,
                    "created_record_count": 0,
                    "existing_record_count": 0,
                }
            )

    results = sorted(
        results,
        key=lambda row: (
            row[
                "sport_key"
            ],
            row[
                "provider_key"
            ],
            row[
                "task_id"
            ],
        ),
    )

    return {
        "version": (
            CORPUS_EXPANSION_AUTOMATION_VERSION
        ),
        "dry_run": dry_run,
        "results": results,
        "blocked": _copy(
            task_plan.get(
                "blocked",
                [],
            )
        ),
        "summary": {
            "planned_task_count": len(
                tasks
            ),
            "completed_task_count": sum(
                1
                for row in results
                if row[
                    "status"
                ]
                in {
                    "completed",
                    "completed_empty",
                }
            ),
            "failed_task_count": sum(
                1
                for row in results
                if row[
                    "status"
                ]
                == "failed"
            ),
            "blocked_task_count": len(
                task_plan.get(
                    "blocked",
                    [],
                )
            ),
            "created_record_count": sum(
                row[
                    "created_record_count"
                ]
                for row
                in results
            ),
            "existing_record_count": sum(
                row[
                    "existing_record_count"
                ]
                for row
                in results
            ),
        },
        "policy": {
            "automation_is_explicitly_invoked": True,
            "provider_failures_are_isolated": True,
            "ingestion_is_capped_to_coverage_deficit": True,
            "existing_corpus_persistence_is_reused": True,
            "provider_review_gates_are_preserved": True,
            "unimplemented_adapters_do_not_execute": True,
            "does_not_establish_truth": True,
            "does_not_train_model": True,
            "does_not_change_adjudication": True,
            "does_not_change_live_merit": True,
            "not_wired_to_production_scheduler": True,
            "human_review_required": False,
        },
    }


def run_corpus_expansion_automation(
    *,
    connection_factory,
    provider_parameters: Optional[
        Dict[str, Any]
    ] = None,
    records: Optional[
        Iterable[
            Dict[str, Any]
        ]
    ] = None,
    target_records_per_sport: int = (
        DEFAULT_TARGET_RECORDS_PER_SPORT
    ),
    allowed_provider_statuses=(
        DEFAULT_ALLOWED_PROVIDER_STATUSES
    ),
    validation_sample_per_sport: int = 5,
    dry_run: bool = False,
    fetcher=fetch_remote_request,
    ingestor=ingest_normalized_records,
    cricsheet_reader=(
        read_cricsheet_json_archive
    ),
) -> Dict[str, Any]:
    if records is None:
        source_records = (
            load_persisted_structured_corpus_records(
                connection_factory=(
                    connection_factory
                ),
            )
        )
    else:
        source_records = list(
            records
        )

    expansion = (
        build_validation_corpus_expansion(
            records=source_records,
            target_records_per_sport=(
                target_records_per_sport
            ),
            allowed_provider_statuses=(
                allowed_provider_statuses
            ),
            validation_sample_per_sport=(
                validation_sample_per_sport
            ),
        )
    )

    task_plan = (
        build_corpus_expansion_tasks(
            expansion=expansion,
            provider_parameters=(
                provider_parameters
            ),
        )
    )

    execution = (
        execute_corpus_expansion_tasks(
            task_plan=task_plan,
            connection_factory=(
                connection_factory
            ),
            dry_run=dry_run,
            fetcher=fetcher,
            ingestor=ingestor,
            cricsheet_reader=(
                cricsheet_reader
            ),
        )
    )

    return {
        "version": (
            CORPUS_EXPANSION_AUTOMATION_VERSION
        ),
        "coverage": expansion,
        "task_plan": task_plan,
        "execution": execution,
        "policy": {
            "coverage_drives_automation": True,
            "only_deficits_generate_work": True,
            "remote_provider_parameters_are_explicit": True,
            "existing_adapter_and_corpus_layers_are_reused": True,
            "not_wired_to_main": True,
            "not_wired_to_scheduler": True,
            "does_not_change_live_merit": True,
        },
    }
