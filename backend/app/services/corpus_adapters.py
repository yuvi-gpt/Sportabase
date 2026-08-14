import hashlib
import io
import json
import re
import zipfile

from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode

import requests

from app.intelligence.corpus import (
    record_corpus_record,
)
from app.intelligence.providers import (
    get_provider,
)


REMOTE_CORPUS_ADAPTER_VERSION = (
    "remote-corpus-adapter-v1"
)


OPENF1_ENDPOINTS = {
    "meetings": (
        "meeting",
        "record",
    ),
    "sessions": (
        "session",
        "record",
    ),
    "drivers": (
        "driver",
        "record",
    ),
    "laps": (
        "lap",
        "atomic_event",
    ),
    "car_data": (
        "telemetry_sample",
        "atomic_event",
    ),
    "pit": (
        "pit_stop",
        "atomic_event",
    ),
    "position": (
        "position_sample",
        "atomic_event",
    ),
    "race_control": (
        "race_control",
        "atomic_event",
    ),
    "stints": (
        "stint",
        "sequence",
    ),
    "weather": (
        "weather_sample",
        "atomic_event",
    ),
    "intervals": (
        "interval_sample",
        "atomic_event",
    ),
    "location": (
        "location_sample",
        "atomic_event",
    ),
    "team_radio": (
        "team_radio",
        "atomic_event",
    ),
}


STATSBOMB_RESOURCES = {
    "competitions",
    "matches",
    "events",
    "lineups",
    "three-sixty",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _slug(
    value: Any,
) -> str:
    text = _clean(
        value
    ).lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        text,
    )

    return text.strip(
        "-"
    )


def _stable_hash(
    value: Any,
) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return hashlib.sha256(
        serialized.encode(
            "utf-8"
        )
    ).hexdigest()


def _request(
    *,
    provider_key: str,
    url: str,
    expected_format: str,
) -> Dict[str, Any]:
    return {
        "version": (
            REMOTE_CORPUS_ADAPTER_VERSION
        ),
        "provider_key": (
            provider_key
        ),
        "url": url,
        "expected_format": (
            expected_format
        ),
    }


def build_openf1_request(
    *,
    endpoint: str,
    filters: Dict[str, Any] = None,
) -> Dict[str, Any]:
    normalized_endpoint = _clean(
        endpoint
    ).lower()

    if (
        normalized_endpoint
        not in OPENF1_ENDPOINTS
    ):
        raise ValueError(
            "Unsupported OpenF1 endpoint."
        )

    provider = get_provider(
        "openf1"
    )

    cleaned_filters = {}

    for key, value in sorted(
        (
            filters
            or {}
        ).items()
    ):
        normalized_key = _clean(
            key
        )

        if not normalized_key:
            raise ValueError(
                "OpenF1 filter key "
                "cannot be empty."
            )

        if value is None:
            continue

        cleaned_filters[
            normalized_key
        ] = value

    url = (
        provider[
            "base_url"
        ]
        + "/"
        + normalized_endpoint
    )

    if cleaned_filters:
        url += (
            "?"
            + urlencode(
                cleaned_filters,
                doseq=True,
            )
        )

    return _request(
        provider_key="openf1",
        url=url,
        expected_format="json",
    )


def build_statsbomb_open_request(
    *,
    resource: str,
    competition_id: Any = None,
    season_id: Any = None,
    match_id: Any = None,
) -> Dict[str, Any]:
    normalized_resource = _clean(
        resource
    ).lower()

    if (
        normalized_resource
        not in STATSBOMB_RESOURCES
    ):
        raise ValueError(
            "Unsupported StatsBomb "
            "Open Data resource."
        )

    provider = get_provider(
        "statsbomb_open"
    )

    base = provider[
        "base_url"
    ]

    if normalized_resource == "competitions":
        path = "competitions.json"

    elif normalized_resource == "matches":
        competition = _clean(
            competition_id
        )
        season = _clean(
            season_id
        )

        if (
            not competition
            or not season
        ):
            raise ValueError(
                "StatsBomb matches require "
                "competition and season IDs."
            )

        path = (
            "matches/"
            + competition
            + "/"
            + season
            + ".json"
        )

    else:
        match = _clean(
            match_id
        )

        if not match:
            raise ValueError(
                "StatsBomb resource requires "
                "a match ID."
            )

        path = (
            normalized_resource
            + "/"
            + match
            + ".json"
        )

    return _request(
        provider_key=(
            "statsbomb_open"
        ),
        url=(
            base
            + "/"
            + path
        ),
        expected_format="json",
    )


def build_cricsheet_request(
    *,
    archive_name: str,
) -> Dict[str, Any]:
    archive = _clean(
        archive_name
    ).lower()

    if not re.fullmatch(
        r"[a-z0-9_-]+_json\.zip",
        archive,
    ):
        raise ValueError(
            "Cricsheet archive must be "
            "a safe *_json.zip filename."
        )

    provider = get_provider(
        "cricsheet"
    )

    return _request(
        provider_key="cricsheet",
        url=(
            provider[
                "base_url"
            ]
            + "/"
            + archive
        ),
        expected_format="zip",
    )


def fetch_remote_request(
    request: Dict[str, Any],
    *,
    http_get=requests.get,
    timeout_seconds: float = 12.0,
):
    if not isinstance(
        request,
        dict,
    ):
        raise ValueError(
            "Remote corpus request "
            "must be a dictionary."
        )

    if (
        request.get(
            "version"
        )
        != REMOTE_CORPUS_ADAPTER_VERSION
    ):
        raise ValueError(
            "Unsupported remote corpus "
            "adapter request version."
        )

    url = _clean(
        request.get(
            "url"
        )
    )

    expected_format = _clean(
        request.get(
            "expected_format"
        )
    ).lower()

    if not url:
        raise ValueError(
            "Remote corpus request URL "
            "is required."
        )

    response = http_get(
        url,
        timeout=timeout_seconds,
    )

    status_code = int(
        getattr(
            response,
            "status_code",
            200,
        )
    )

    if not (
        200
        <= status_code
        < 300
    ):
        raise RuntimeError(
            "Remote corpus provider "
            f"returned HTTP {status_code}."
        )

    if expected_format == "json":
        try:
            if hasattr(
                response,
                "json",
            ):
                payload = response.json()
            else:
                payload = json.loads(
                    response.text
                )
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Remote provider returned "
                "invalid JSON."
            ) from exc

        if not isinstance(
            payload,
            (
                list,
                dict,
            ),
        ):
            raise ValueError(
                "Remote JSON payload must "
                "be a list or dictionary."
            )

        return payload

    if expected_format == "zip":
        content = bytes(
            getattr(
                response,
                "content",
                b"",
            )
        )

        if not content:
            raise ValueError(
                "Remote ZIP payload is empty."
            )

        return content

    raise ValueError(
        "Unsupported remote response format."
    )


def _openf1_external_id(
    *,
    endpoint: str,
    row: Dict[str, Any],
) -> str:
    key_sets = {
        "meetings": (
            "meeting_key",
        ),
        "sessions": (
            "session_key",
        ),
        "drivers": (
            "session_key",
            "driver_number",
        ),
        "laps": (
            "session_key",
            "driver_number",
            "lap_number",
        ),
        "car_data": (
            "session_key",
            "driver_number",
            "date",
        ),
        "pit": (
            "session_key",
            "driver_number",
            "lap_number",
        ),
        "position": (
            "session_key",
            "driver_number",
            "date",
        ),
        "race_control": (
            "session_key",
            "date",
            "category",
            "message",
        ),
        "stints": (
            "session_key",
            "driver_number",
            "stint_number",
        ),
        "weather": (
            "session_key",
            "date",
        ),
        "intervals": (
            "session_key",
            "driver_number",
            "date",
        ),
        "location": (
            "session_key",
            "driver_number",
            "date",
        ),
        "team_radio": (
            "session_key",
            "driver_number",
            "date",
        ),
    }

    values = [
        _clean(
            row.get(
                key
            )
        )
        for key in key_sets[
            endpoint
        ]
    ]

    if all(
        values
    ):
        return (
            endpoint
            + "|"
            + "|".join(
                values
            )
        )

    return (
        endpoint
        + "|hash|"
        + _stable_hash(
            row
        )
    )


def normalize_openf1_rows(
    *,
    endpoint: str,
    rows: Iterable[
        Dict[str, Any]
    ],
    season_key: str = "",
) -> List[Dict[str, Any]]:
    normalized_endpoint = _clean(
        endpoint
    ).lower()

    if (
        normalized_endpoint
        not in OPENF1_ENDPOINTS
    ):
        raise ValueError(
            "Unsupported OpenF1 endpoint."
        )

    event_type, granularity = (
        OPENF1_ENDPOINTS[
            normalized_endpoint
        ]
    )

    normalized = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "OpenF1 rows must be "
                "dictionaries."
            )

        resolved_season = (
            _clean(
                season_key
            )
            or _clean(
                row.get(
                    "year"
                )
            )
        )

        occurred_at = (
            _clean(
                row.get(
                    "date"
                )
            )
            or _clean(
                row.get(
                    "date_start"
                )
            )
            or None
        )

        normalized.append(
            {
                "origin_type": (
                    "remote_api"
                ),
                "data_family": (
                    "structured_sports_data"
                ),
                "dataset_name": (
                    "openf1"
                ),
                "external_record_id": (
                    _openf1_external_id(
                        endpoint=(
                            normalized_endpoint
                        ),
                        row=row,
                    )
                ),
                "adapter_version": (
                    REMOTE_CORPUS_ADAPTER_VERSION
                ),
                "sport_key": (
                    "motorsport"
                ),
                "competition_key": (
                    "formula-1"
                ),
                "season_key": (
                    resolved_season
                ),
                "event_type": (
                    event_type
                ),
                "granularity": (
                    granularity
                ),
                "measurement_kind": (
                    "direct"
                ),
                "occurred_at": (
                    occurred_at
                ),
                "payload": dict(
                    row
                ),
                "metadata": {
                    "provider_key": (
                        "openf1"
                    ),
                    "upstream_endpoint": (
                        normalized_endpoint
                    ),
                },
            }
        )

    return normalized


def normalize_statsbomb_rows(
    *,
    resource: str,
    rows: Iterable[
        Dict[str, Any]
    ],
    competition_key: str = "",
    season_key: str = "",
    match_id: Any = None,
) -> List[Dict[str, Any]]:
    normalized_resource = _clean(
        resource
    ).lower()

    if (
        normalized_resource
        not in STATSBOMB_RESOURCES
    ):
        raise ValueError(
            "Unsupported StatsBomb "
            "Open Data resource."
        )

    normalized = []

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "StatsBomb rows must be "
                "dictionaries."
            )

        if normalized_resource == "competitions":
            external_id = (
                "competition|"
                + _clean(
                    row.get(
                        "competition_id"
                    )
                )
                + "|season|"
                + _clean(
                    row.get(
                        "season_id"
                    )
                )
            )

            event_type = "competition"
            granularity = "record"

            resolved_competition = (
                _slug(
                    row.get(
                        "competition_name"
                    )
                )
            )

            resolved_season = (
                _clean(
                    row.get(
                        "season_name"
                    )
                )
            )

        elif normalized_resource == "matches":
            external_id = (
                "match|"
                + _clean(
                    row.get(
                        "match_id"
                    )
                )
            )

            event_type = "match"
            granularity = "match"

            resolved_competition = (
                _clean(
                    competition_key
                )
            )

            resolved_season = (
                _clean(
                    season_key
                )
            )

        elif normalized_resource == "events":
            event_uuid = _clean(
                row.get(
                    "id"
                )
            )

            external_id = (
                "event|"
                + (
                    event_uuid
                    or _stable_hash(
                        row
                    )
                )
            )

            event_name = ""

            event_block = row.get(
                "type"
            )

            if isinstance(
                event_block,
                dict,
            ):
                event_name = _slug(
                    event_block.get(
                        "name"
                    )
                )

            event_type = (
                event_name
                or "event"
            )

            granularity = (
                "atomic_event"
            )

            resolved_competition = (
                _clean(
                    competition_key
                )
            )

            resolved_season = (
                _clean(
                    season_key
                )
            )

        elif normalized_resource == "lineups":
            team_id = _clean(
                row.get(
                    "team_id"
                )
            )

            external_id = (
                "lineup|"
                + _clean(
                    match_id
                )
                + "|team|"
                + (
                    team_id
                    or _stable_hash(
                        row
                    )
                )
            )

            event_type = "lineup"
            granularity = "lineup"

            resolved_competition = (
                _clean(
                    competition_key
                )
            )

            resolved_season = (
                _clean(
                    season_key
                )
            )

        else:
            event_uuid = _clean(
                row.get(
                    "event_uuid"
                )
            )

            external_id = (
                "three-sixty|"
                + (
                    event_uuid
                    or _stable_hash(
                        row
                    )
                )
            )

            event_type = (
                "tracking_snapshot"
            )

            granularity = (
                "tracking_snapshot"
            )

            resolved_competition = (
                _clean(
                    competition_key
                )
            )

            resolved_season = (
                _clean(
                    season_key
                )
            )

        normalized.append(
            {
                "origin_type": (
                    "remote_bulk"
                ),
                "data_family": (
                    "structured_sports_data"
                ),
                "dataset_name": (
                    "statsbomb_open"
                ),
                "external_record_id": (
                    external_id
                ),
                "adapter_version": (
                    REMOTE_CORPUS_ADAPTER_VERSION
                ),
                "sport_key": (
                    "football"
                ),
                "competition_key": (
                    resolved_competition
                ),
                "season_key": (
                    resolved_season
                ),
                "event_type": (
                    event_type
                ),
                "granularity": (
                    granularity
                ),
                "measurement_kind": (
                    "direct"
                ),
                "payload": dict(
                    row
                ),
                "metadata": {
                    "provider_key": (
                        "statsbomb_open"
                    ),
                    "upstream_resource": (
                        normalized_resource
                    ),
                    "match_id": (
                        _clean(
                            match_id
                        )
                    ),
                },
            }
        )

    return normalized


def read_cricsheet_json_archive(
    content: bytes,
) -> List[Dict[str, Any]]:
    try:
        archive = zipfile.ZipFile(
            io.BytesIO(
                content
            )
        )
    except (
        zipfile.BadZipFile,
        TypeError,
    ) as exc:
        raise ValueError(
            "Cricsheet payload is not "
            "a valid ZIP archive."
        ) from exc

    records = []

    try:
        names = sorted(
            name
            for name in archive.namelist()
            if (
                name.lower().endswith(
                    ".json"
                )
                and not name.endswith(
                    "/"
                )
            )
        )

        for name in names:
            try:
                payload = json.loads(
                    archive.read(
                        name
                    ).decode(
                        "utf-8"
                    )
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as exc:
                raise ValueError(
                    "Cricsheet archive contains "
                    "invalid JSON."
                ) from exc

            if not isinstance(
                payload,
                dict,
            ):
                raise ValueError(
                    "Cricsheet match JSON must "
                    "be a dictionary."
                )

            external_id = (
                name.rsplit(
                    "/",
                    1,
                )[-1]
                .rsplit(
                    ".",
                    1,
                )[0]
            )

            records.append(
                {
                    "external_record_id": (
                        external_id
                    ),
                    "payload": (
                        payload
                    ),
                }
            )

    finally:
        archive.close()

    return records


def normalize_cricsheet_matches(
    *,
    matches: Iterable[
        Dict[str, Any]
    ],
    competition_key: str = "",
    season_key: str = "",
) -> List[Dict[str, Any]]:
    normalized = []

    for match in matches:
        if not isinstance(
            match,
            dict,
        ):
            raise ValueError(
                "Cricsheet archive rows "
                "must be dictionaries."
            )

        external_id = _clean(
            match.get(
                "external_record_id"
            )
        )

        payload = match.get(
            "payload"
        )

        if not external_id:
            raise ValueError(
                "Cricsheet match ID "
                "is required."
            )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Cricsheet match payload "
                "must be a dictionary."
            )

        info = payload.get(
            "info",
            {},
        )

        if not isinstance(
            info,
            dict,
        ):
            info = {}

        dates = info.get(
            "dates",
            [],
        )

        occurred_at = None

        if (
            isinstance(
                dates,
                list,
            )
            and dates
        ):
            occurred_at = _clean(
                dates[0]
            ) or None

        resolved_season = (
            _clean(
                season_key
            )
        )

        if not resolved_season:
            season = info.get(
                "season"
            )

            if (
                isinstance(
                    season,
                    (
                        str,
                        int,
                    ),
                )
            ):
                resolved_season = (
                    _clean(
                        season
                    )
                )

        normalized.append(
            {
                "origin_type": (
                    "remote_bulk"
                ),
                "data_family": (
                    "structured_sports_data"
                ),
                "dataset_name": (
                    "cricsheet"
                ),
                "external_record_id": (
                    external_id
                ),
                "adapter_version": (
                    REMOTE_CORPUS_ADAPTER_VERSION
                ),
                "sport_key": (
                    "cricket"
                ),
                "competition_key": (
                    _clean(
                        competition_key
                    )
                ),
                "season_key": (
                    resolved_season
                ),
                "event_type": (
                    "match"
                ),
                "granularity": (
                    "match"
                ),
                "measurement_kind": (
                    "direct"
                ),
                "occurred_at": (
                    occurred_at
                ),
                "payload": dict(
                    payload
                ),
                "metadata": {
                    "provider_key": (
                        "cricsheet"
                    ),
                    "contains_delivery_data": (
                        bool(
                            payload.get(
                                "innings"
                            )
                        )
                    ),
                },
            }
        )

    return normalized


def ingest_normalized_records(
    *,
    records: Iterable[
        Dict[str, Any]
    ],
    connection_factory,
    recorder=record_corpus_record,
) -> Dict[str, Any]:
    results = []

    created = 0
    existing = 0

    for record in records:
        if not isinstance(
            record,
            dict,
        ):
            raise ValueError(
                "Normalized corpus record "
                "must be a dictionary."
            )

        result = recorder(
            **record,
            connection_factory=(
                connection_factory
            ),
        )

        results.append(
            result
        )

        if result.get(
            "created"
        ):
            created += 1
        else:
            existing += 1

    return {
        "version": (
            REMOTE_CORPUS_ADAPTER_VERSION
        ),
        "records": (
            results
        ),
        "counts": {
            "processed": (
                len(
                    results
                )
            ),
            "created": created,
            "existing": existing,
        },
        "live_merit_effect_enabled": (
            False
        ),
    }
