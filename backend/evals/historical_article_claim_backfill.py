from __future__ import annotations

import hashlib
import json

from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
)


from app.content.resolution import (
    normalized_analysis_url,
)

from app.db.connection import (
    connect_database,
)

from app.intelligence.sources import (
    source_domain_for_url,
)

from app.services.analysis_history import (
    media_item_id_for_url,
    upsert_media_item,
)

from app.services.article_intelligence_shadow import (
    ARTICLE_PRIMARY_CLAIM_TYPES,
    build_article_primary_claim_seed,
    persist_article_primary_claim_seed,
)

from evals.historical_article_claim_backfill_plan import (
    HISTORICAL_ARTICLE_CLAIM_BACKFILL_PLAN_VERSION,
    HISTORICAL_ARTICLE_CLAIM_BACKFILL_REPORT_VERSION,
    build_historical_article_claim_backfill_plan,
)


HISTORICAL_ARTICLE_CLAIM_BACKFILL_ALLOWLIST_VERSION = (
    "historical-article-claim-backfill-allowlist-v1"
)

HISTORICAL_ARTICLE_CLAIM_BACKFILL_RUNTIME_VERSION = (
    "historical-article-claim-backfill-runtime-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


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


def _digest(
    value: Any,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _domain(
    value: str,
) -> str:
    return source_domain_for_url(
        value,
        normalize_url=(
            normalized_analysis_url
        ),
    )


def _media_id(
    value: str,
) -> str:
    return media_item_id_for_url(
        value,
        normalize_url=(
            normalized_analysis_url
        ),
    )


def _historical_capture_hash(
    story: Dict[str, Any],
) -> str:
    payload = {
        "scope": (
            "legacy_feed_title_summary"
        ),
        "story_id": _clean(
            story.get(
                "id"
            )
        ),
        "title": _clean(
            story.get(
                "title"
            )
        ),
        "summary": _clean(
            story.get(
                "summary"
            )
        ),
        "url": normalized_analysis_url(
            _clean(
                story.get(
                    "link"
                )
            )
        ),
        "published": _clean(
            story.get(
                "published"
            )
        ),
    }

    return _digest(
        payload
    )


def build_frozen_allowlist_from_plan(
    *,
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(
        plan,
        dict,
    ):
        raise ValueError(
            "Historical backfill plan must "
            "be a dictionary."
        )

    if (
        _clean(
            plan.get(
                "version"
            )
        )
        != (
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_REPORT_VERSION
        )
    ):
        raise ValueError(
            "Historical backfill plan report "
            "version is unsupported."
        )

    if (
        _clean(
            plan.get(
                "planner_version"
            )
        )
        != (
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_PLAN_VERSION
        )
    ):
        raise ValueError(
            "Historical backfill planner "
            "version is unsupported."
        )

    report_digest = _clean(
        plan.get(
            "report_digest"
        )
    )

    if len(
        report_digest
    ) != 64:
        raise ValueError(
            "Historical backfill plan digest "
            "is required."
        )

    admitted = plan.get(
        "admit"
    )

    if not isinstance(
        admitted,
        list,
    ):
        raise ValueError(
            "Historical backfill admitted "
            "population is missing."
        )

    entries = []

    for case in admitted:
        if not isinstance(
            case,
            dict,
        ):
            raise ValueError(
                "Historical backfill admitted "
                "case is invalid."
            )

        if (
            _clean(
                case.get(
                    "decision"
                )
            )
            != "admit"
        ):
            raise ValueError(
                "Historical allowlist can only "
                "freeze admitted cases."
            )

        story_id = _clean(
            case.get(
                "story_id"
            )
        )

        title = _clean(
            case.get(
                "title"
            )
        )

        url = normalized_analysis_url(
            _clean(
                case.get(
                    "url"
                )
            )
        )

        planned_article_type = _clean(
            case.get(
                "planned_article_type"
            )
        ).lower()

        if (
            not story_id
            or not title
            or not url
            or planned_article_type
            not in ARTICLE_PRIMARY_CLAIM_TYPES
        ):
            raise ValueError(
                "Historical admitted case "
                "is missing frozen identity."
            )

        entries.append(
            {
                "story_id": (
                    story_id
                ),
                "title": (
                    title
                ),
                "url": (
                    url
                ),
                "source": _clean(
                    case.get(
                        "source"
                    )
                ),
                "sport": _clean(
                    case.get(
                        "sport"
                    )
                ),
                "observed_at": _clean(
                    case.get(
                        "observed_at"
                    )
                ),
                "planned_article_type": (
                    planned_article_type
                ),
                "planned_article_type_source": (
                    _clean(
                        case.get(
                            "planned_article_type_source"
                        )
                    )
                ),
                "current_rule_type": (
                    _clean(
                        case.get(
                            "current_rule_type"
                        )
                    )
                ),
                "current_rule_confidence": (
                    case.get(
                        "current_rule_confidence"
                    )
                ),
                "admission_reason": (
                    _clean(
                        case.get(
                            "reason"
                        )
                    )
                ),
            }
        )

    entries.sort(
        key=lambda item: (
            item[
                "story_id"
            ]
        )
    )

    identity = {
        "version": (
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_ALLOWLIST_VERSION
        ),
        "planner_version": (
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_PLAN_VERSION
        ),
        "planner_report_digest": (
            report_digest
        ),
        "entries": entries,
    }

    return {
        **identity,
        "allowlist_digest": (
            _digest(
                identity
            )
        ),
        "policy": {
            "frozen_admit_population_only": True,
            "headline_is_reported_claim_only": True,
            "claim_truth_established": False,
            "provider_call_performed": False,
            "historical_merit_score_used_as_calibration_baseline": False,
            "full_article_capture_claimed": False,
            "live_merit_changed": False,
        },
    }


def write_allowlist(
    path: Path,
    allowlist: Dict[str, Any],
) -> None:
    destination = Path(
        path
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination.write_text(
        json.dumps(
            allowlist,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_allowlist(
    path: Path,
) -> Dict[str, Any]:
    try:
        value = json.loads(
            Path(
                path
            ).read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            "Historical backfill allowlist "
            "could not be read."
        ) from error

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Historical backfill allowlist "
            "must be a dictionary."
        )

    if (
        _clean(
            value.get(
                "version"
            )
        )
        != (
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_ALLOWLIST_VERSION
        )
    ):
        raise ValueError(
            "Historical backfill allowlist "
            "version is unsupported."
        )

    entries = value.get(
        "entries"
    )

    if (
        not isinstance(
            entries,
            list,
        )
        or not entries
    ):
        raise ValueError(
            "Historical backfill allowlist "
            "requires entries."
        )

    identity = {
        "version": (
            value.get(
                "version"
            )
        ),
        "planner_version": (
            value.get(
                "planner_version"
            )
        ),
        "planner_report_digest": (
            value.get(
                "planner_report_digest"
            )
        ),
        "entries": entries,
    }

    expected_digest = _digest(
        identity
    )

    if (
        _clean(
            value.get(
                "allowlist_digest"
            )
        )
        != expected_digest
    ):
        raise ValueError(
            "Historical backfill allowlist "
            "digest mismatch."
        )

    seen_ids = set()

    for entry in entries:
        if not isinstance(
            entry,
            dict,
        ):
            raise ValueError(
                "Historical backfill allowlist "
                "entry is invalid."
            )

        story_id = _clean(
            entry.get(
                "story_id"
            )
        )

        if not story_id:
            raise ValueError(
                "Historical allowlist story ID "
                "is required."
            )

        if story_id in seen_ids:
            raise ValueError(
                "Historical allowlist story IDs "
                "must be unique."
            )

        seen_ids.add(
            story_id
        )

        if (
            _clean(
                entry.get(
                    "planned_article_type"
                )
            ).lower()
            not in ARTICLE_PRIMARY_CLAIM_TYPES
        ):
            raise ValueError(
                "Historical allowlist contains "
                "unsupported planned article type."
            )

    return value


def _load_story(
    *,
    connection_factory,
    story_id: str,
):
    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM stories
            WHERE id = ?
            """,
            (
                story_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    return (
        dict(
            row
        )
        if row is not None
        else None
    )


def _validate_frozen_population(
    *,
    db_path: Path,
    allowlist: Dict[str, Any],
) -> Dict[str, Any]:
    current_plan = (
        build_historical_article_claim_backfill_plan(
            db_path=(
                db_path
            )
        )
    )

    expected_plan_digest = _clean(
        allowlist.get(
            "planner_report_digest"
        )
    )

    current_plan_digest = _clean(
        current_plan.get(
            "report_digest"
        )
    )

    if (
        current_plan_digest
        != expected_plan_digest
    ):
        raise ValueError(
            "Current historical planner report "
            "does not match frozen allowlist."
        )

    admitted = current_plan.get(
        "admit"
    )

    if not isinstance(
        admitted,
        list,
    ):
        raise ValueError(
            "Current historical admitted "
            "population is unavailable."
        )

    current_by_id = {
        _clean(
            case.get(
                "story_id"
            )
        ): case
        for case
        in admitted
        if isinstance(
            case,
            dict,
        )
    }

    frozen_entries = allowlist[
        "entries"
    ]

    frozen_ids = {
        _clean(
            entry.get(
                "story_id"
            )
        )
        for entry
        in frozen_entries
    }

    current_ids = set(
        current_by_id
    )

    if (
        frozen_ids
        != current_ids
    ):
        raise ValueError(
            "Frozen historical allowlist "
            "does not exactly match current "
            "admitted population."
        )

    for entry in frozen_entries:
        story_id = _clean(
            entry[
                "story_id"
            ]
        )

        case = current_by_id[
            story_id
        ]

        comparisons = {
            "title": _clean(
                case.get(
                    "title"
                )
            ),
            "url": normalized_analysis_url(
                _clean(
                    case.get(
                        "url"
                    )
                )
            ),
            "source": _clean(
                case.get(
                    "source"
                )
            ),
            "sport": _clean(
                case.get(
                    "sport"
                )
            ),
            "observed_at": _clean(
                case.get(
                    "observed_at"
                )
            ),
            "planned_article_type": _clean(
                case.get(
                    "planned_article_type"
                )
            ),
            "planned_article_type_source": _clean(
                case.get(
                    "planned_article_type_source"
                )
            ),
            "current_rule_type": _clean(
                case.get(
                    "current_rule_type"
                )
            ),
            "admission_reason": _clean(
                case.get(
                    "reason"
                )
            ),
        }

        for key, current_value in (
            comparisons.items()
        ):
            frozen_value = _clean(
                entry.get(
                    key
                )
            )

            if (
                frozen_value
                != current_value
            ):
                raise ValueError(
                    "Frozen historical allowlist "
                    "identity mismatch for "
                    + story_id
                    + ":"
                    + key
                )

    return current_plan


def execute_historical_article_claim_backfill(
    *,
    db_path: Path,
    allowlist: Dict[str, Any],
    apply: bool,
) -> Dict[str, Any]:
    path = Path(
        db_path
    ).resolve()

    if not path.is_file():
        raise FileNotFoundError(
            "Sportabase database does not exist: "
            + str(
                path
            )
        )

    _validate_frozen_population(
        db_path=path,
        allowlist=allowlist,
    )

    connection_factory = (
        lambda: connect_database(
            path
        )
    )

    if not apply:
        return {
            "version": (
                HISTORICAL_ARTICLE_CLAIM_BACKFILL_RUNTIME_VERSION
            ),
            "status": (
                "validated_no_write"
            ),
            "applied": False,
            "entry_count": len(
                allowlist[
                    "entries"
                ]
            ),
            "allowlist_digest": (
                allowlist[
                    "allowlist_digest"
                ]
            ),
            "provider_call_performed": False,
            "live_merit_changed": False,
        }

    persisted = []

    for entry in allowlist[
        "entries"
    ]:
        story_id = _clean(
            entry[
                "story_id"
            ]
        )

        story = _load_story(
            connection_factory=(
                connection_factory
            ),
            story_id=story_id,
        )

        if story is None:
            raise ValueError(
                "Frozen historical story "
                "does not exist: "
                + story_id
            )

        title = _clean(
            story.get(
                "title"
            )
        )

        url = normalized_analysis_url(
            _clean(
                story.get(
                    "link"
                )
            )
        )

        summary = _clean(
            story.get(
                "summary"
            )
        )

        observed_at = _clean(
            entry.get(
                "observed_at"
            )
        )

        planned_article_type = _clean(
            entry.get(
                "planned_article_type"
            )
        ).lower()

        capture_hash = (
            _historical_capture_hash(
                story
            )
        )

        media_metadata = {
            "historical_backfill": True,
            "historical_backfill_runtime_version": (
                HISTORICAL_ARTICLE_CLAIM_BACKFILL_RUNTIME_VERSION
            ),
            "historical_backfill_allowlist_version": (
                HISTORICAL_ARTICLE_CLAIM_BACKFILL_ALLOWLIST_VERSION
            ),
            "historical_backfill_allowlist_digest": (
                allowlist[
                    "allowlist_digest"
                ]
            ),
            "historical_backfill_planner_digest": (
                allowlist[
                    "planner_report_digest"
                ]
            ),
            "legacy_story_id": (
                story_id
            ),
            "capture_scope": (
                "legacy_feed_title_summary"
            ),
            "full_article_capture": False,
            "summary_character_count": len(
                summary
            ),
            "historical_merit_score_archival_only": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        }

        media_item = upsert_media_item(
            url=url,
            mode="article",
            title=title,
            content_hash=(
                capture_hash
            ),
            published_at=(
                _clean(
                    story.get(
                        "published"
                    )
                )
                or None
            ),
            source_id=None,
            reporter_id=None,
            metadata=(
                media_metadata
            ),
            seen_at=(
                observed_at
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            id_resolver=(
                _media_id
            ),
            connection_factory=(
                connection_factory
            ),
        )

        seed = (
            build_article_primary_claim_seed(
                media_item_id=(
                    media_item[
                        "id"
                    ]
                ),
                title=title,
                url=url,
                article_type=(
                    planned_article_type
                ),
                observed_at=(
                    observed_at
                ),
                normalize_url=(
                    normalized_analysis_url
                ),
            )
        )

        if (
            seed.get(
                "status"
            )
            != "claim_seed_ready"
        ):
            raise ValueError(
                "Frozen historical entry did "
                "not produce a claim seed."
            )

        planned_type_source = _clean(
            entry.get(
                "planned_article_type_source"
            )
        )

        if (
            planned_type_source
            == "current_rule_confirmed_by_headline"
        ):
            try:
                type_confidence = float(
                    entry.get(
                        "current_rule_confidence"
                    )
                    or 0.0
                )

            except (
                TypeError,
                ValueError,
            ):
                type_confidence = 0.0

        else:
            type_confidence = 0.0

        seed_result = (
            persist_article_primary_claim_seed(
                seed=seed,
                type_confidence=(
                    type_confidence
                ),
                normalize_url=(
                    normalized_analysis_url
                ),
                connection_factory=(
                    connection_factory
                ),
            )
        )

        source = seed_result.get(
            "source"
        )

        if not isinstance(
            source,
            dict,
        ):
            raise ValueError(
                "Historical claim seed did "
                "not produce a source."
            )

        media_item = upsert_media_item(
            url=url,
            mode="article",
            title=title,
            content_hash=(
                capture_hash
            ),
            published_at=(
                _clean(
                    story.get(
                        "published"
                    )
                )
                or None
            ),
            source_id=(
                source[
                    "id"
                ]
            ),
            reporter_id=None,
            metadata=(
                media_metadata
            ),
            seen_at=(
                observed_at
            ),
            normalize_url=(
                normalized_analysis_url
            ),
            id_resolver=(
                _media_id
            ),
            connection_factory=(
                connection_factory
            ),
        )

        claim = seed_result.get(
            "claim"
        )

        observation = seed_result.get(
            "observation"
        )

        claim_link = seed_result.get(
            "claim_link"
        )

        if not all(
            isinstance(
                value,
                dict,
            )
            for value
            in (
                claim,
                observation,
                claim_link,
            )
        ):
            raise ValueError(
                "Historical claim seed "
                "persistence is incomplete."
            )

        persisted.append(
            {
                "story_id": (
                    story_id
                ),
                "media_item_id": (
                    media_item[
                        "id"
                    ]
                ),
                "source_id": (
                    source[
                        "id"
                    ]
                ),
                "claim_id": (
                    claim[
                        "id"
                    ]
                ),
                "observation_id": (
                    observation[
                        "id"
                    ]
                ),
                "claim_link_id": (
                    claim_link[
                        "id"
                    ]
                ),
                "planned_article_type": (
                    planned_article_type
                ),
            }
        )

    return {
        "version": (
            HISTORICAL_ARTICLE_CLAIM_BACKFILL_RUNTIME_VERSION
        ),
        "status": (
            "persisted"
        ),
        "applied": True,
        "entry_count": len(
            persisted
        ),
        "allowlist_digest": (
            allowlist[
                "allowlist_digest"
            ]
        ),
        "persisted": (
            persisted
        ),
        "policy": {
            "provider_call_performed": False,
            "full_article_capture_persisted": False,
            "analysis_snapshot_created": False,
            "verification_evidence_created": False,
            "claim_truth_established": False,
            "historical_merit_score_used_as_calibration_baseline": False,
            "live_merit_changed": False,
        },
    }
