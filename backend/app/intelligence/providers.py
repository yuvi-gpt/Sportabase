from typing import Any, Dict, List


PROVIDER_REGISTRY_VERSION = (
    "corpus-provider-registry-v1"
)


_PROVIDER_ROWS = {
    "openf1": {
        "display_name": "OpenF1",
        "sports": [
            "motorsport",
        ],
        "competitions": [
            "formula-1",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": "remote_api",
        "adapter_status": "active",
        "capabilities": [
            "meeting",
            "session",
            "driver",
            "lap",
            "telemetry_sample",
            "pit_stop",
            "position_sample",
            "race_control",
            "stint",
            "weather_sample",
            "interval_sample",
            "location_sample",
            "team_radio",
        ],
        "base_url": (
            "https://api.openf1.org/v1"
        ),
        "usage_note": (
            "Historical OpenF1 access. "
            "Live access may have separate "
            "subscription requirements."
        ),
    },

    "statsbomb_open": {
        "display_name": (
            "StatsBomb Open Data"
        ),
        "sports": [
            "football",
        ],
        "competitions": [
            "*",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": (
            "remote_http_json"
        ),
        "adapter_status": "active",
        "capabilities": [
            "competition",
            "match",
            "lineup",
            "atomic_event",
            "tracking_snapshot",
        ],
        "base_url": (
            "https://raw.githubusercontent.com/"
            "statsbomb/open-data/master/data"
        ),
        "usage_note": (
            "Open-data subset. Preserve "
            "StatsBomb attribution."
        ),
    },

    "cricsheet": {
        "display_name": "Cricsheet",
        "sports": [
            "cricket",
        ],
        "competitions": [
            "*",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": (
            "remote_bulk_zip"
        ),
        "adapter_status": "active",
        "capabilities": [
            "match",
            "innings",
            "over",
            "delivery",
        ],
        "base_url": (
            "https://cricsheet.org/downloads"
        ),
        "usage_note": (
            "JSON is treated as the "
            "canonical Cricsheet format."
        ),
    },

    "nflverse": {
        "display_name": "nflverse",
        "sports": [
            "american_football",
        ],
        "competitions": [
            "nfl",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": (
            "remote_bulk_release"
        ),
        "adapter_status": "registered",
        "capabilities": [
            "schedule",
            "play_by_play",
            "player_stats",
            "roster",
            "injury",
            "participation",
            "trade",
        ],
        "base_url": (
            "https://github.com/"
            "nflverse/nflverse-data/releases"
        ),
        "usage_note": (
            "Prefer release URLs rather "
            "than repository cloning."
        ),
    },

    "nba_api": {
        "display_name": "NBA.com via nba_api",
        "sports": [
            "basketball",
        ],
        "competitions": [
            "nba",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": "remote_api",
        "adapter_status": (
            "registered_terms_review"
        ),
        "capabilities": [
            "scoreboard",
            "box_score",
            "play_by_play",
            "shot_chart",
            "player_stats",
            "team_stats",
            "lineup",
        ],
        "base_url": (
            "https://stats.nba.com/stats"
        ),
        "usage_note": (
            "NBA.com usage remains subject "
            "to NBA digital-platform terms."
        ),
    },

    "retrosheet": {
        "display_name": "Retrosheet",
        "sports": [
            "baseball",
        ],
        "competitions": [
            "mlb",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": (
            "remote_bulk_csv"
        ),
        "adapter_status": "registered",
        "capabilities": [
            "game",
            "play_by_play",
            "roster",
            "team_stats",
            "game_log",
        ],
        "base_url": (
            "https://www.retrosheet.org/"
            "downloads"
        ),
        "usage_note": (
            "Prefer season-scoped parsed "
            "play-by-play where practical."
        ),
    },

    "moneypuck": {
        "display_name": "MoneyPuck",
        "sports": [
            "ice_hockey",
        ],
        "competitions": [
            "nhl",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": (
            "remote_bulk_csv_zip"
        ),
        "adapter_status": (
            "registered_usage_review"
        ),
        "capabilities": [
            "shot",
            "expected_goal",
            "player_game",
            "team_summary",
            "goalie_summary",
        ],
        "base_url": (
            "https://moneypuck.com/data.htm"
        ),
        "usage_note": (
            "Respect MoneyPuck usage and "
            "attribution requirements."
        ),
    },

    "tennis_atp": {
        "display_name": (
            "Jeff Sackmann ATP Data"
        ),
        "sports": [
            "tennis",
        ],
        "competitions": [
            "atp",
        ],
        "data_family": (
            "structured_sports_data"
        ),
        "access_mode": (
            "remote_bulk_csv"
        ),
        "adapter_status": "registered",
        "capabilities": [
            "match",
            "ranking",
            "player",
        ],
        "base_url": (
            "https://raw.githubusercontent.com/"
            "JeffSackmann/tennis_atp/"
            "master"
        ),
        "usage_note": (
            "Season files can be fetched "
            "incrementally."
        ),
    },

    "gdelt": {
        "display_name": "GDELT",
        "sports": [
            "*",
        ],
        "competitions": [
            "*",
        ],
        "data_family": (
            "reporting_evidence"
        ),
        "access_mode": "remote_api",
        "adapter_status": "registered",
        "capabilities": [
            "article_discovery",
            "publication_timeline",
            "source_discovery",
        ],
        "base_url": (
            "https://api.gdeltproject.org"
        ),
        "usage_note": (
            "Cross-sport reporting source; "
            "not sports ground truth."
        ),
    },
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _normalized_provider(
    provider_key: str,
    row: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "version": (
            PROVIDER_REGISTRY_VERSION
        ),
        "provider_key": (
            provider_key
        ),
        "display_name": (
            _clean(
                row.get(
                    "display_name"
                )
            )
        ),
        "sports": tuple(
            _key(
                value
            )
            for value in row.get(
                "sports",
                [],
            )
        ),
        "competitions": tuple(
            _key(
                value
            )
            for value in row.get(
                "competitions",
                [],
            )
        ),
        "data_family": (
            _key(
                row.get(
                    "data_family"
                )
            )
        ),
        "access_mode": (
            _key(
                row.get(
                    "access_mode"
                )
            )
        ),
        "adapter_status": (
            _key(
                row.get(
                    "adapter_status"
                )
            )
        ),
        "capabilities": tuple(
            _key(
                value
            )
            for value in row.get(
                "capabilities",
                [],
            )
        ),
        "base_url": (
            _clean(
                row.get(
                    "base_url"
                )
            )
        ),
        "usage_note": (
            _clean(
                row.get(
                    "usage_note"
                )
            )
        ),
        "live_merit_enabled": False,
    }


PROVIDER_REGISTRY = {
    key: _normalized_provider(
        key,
        row,
    )
    for key, row in _PROVIDER_ROWS.items()
}


def get_provider(
    provider_key: str,
) -> Dict[str, Any]:
    normalized_key = _key(
        provider_key
    )

    if normalized_key not in PROVIDER_REGISTRY:
        raise ValueError(
            "Unknown corpus provider."
        )

    return dict(
        PROVIDER_REGISTRY[
            normalized_key
        ]
    )


def list_providers(
) -> List[Dict[str, Any]]:
    return [
        dict(
            PROVIDER_REGISTRY[
                key
            ]
        )
        for key in sorted(
            PROVIDER_REGISTRY
        )
    ]


def select_providers(
    *,
    sport_key: str = "",
    data_family: str = "",
    capability: str = "",
    active_only: bool = False,
) -> List[Dict[str, Any]]:
    sport = _key(
        sport_key
    )

    family = _key(
        data_family
    )

    requested_capability = _key(
        capability
    )

    selected = []

    for provider in list_providers():
        if (
            sport
            and sport
            not in provider[
                "sports"
            ]
            and "*"
            not in provider[
                "sports"
            ]
        ):
            continue

        if (
            family
            and provider[
                "data_family"
            ]
            != family
        ):
            continue

        if (
            requested_capability
            and requested_capability
            not in provider[
                "capabilities"
            ]
        ):
            continue

        if (
            active_only
            and provider[
                "adapter_status"
            ]
            != "active"
        ):
            continue

        selected.append(
            provider
        )

    return selected
