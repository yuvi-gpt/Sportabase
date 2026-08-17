from __future__ import annotations

import json
import math
import sqlite3

from typing import Any, Dict, Mapping

from app.services import analysis_cache
from app.services import article_rules
from app.services import browser_capture_inbox
from app.services import content_resolution
from app.services import inbox_auto_shadow_orchestration
from app.services import live_merit_release


MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION = (
    "multimodal-inbox-history-auto-shadow-v1"
)


class MultimodalInboxHistoryAutoShadowError(RuntimeError):
    pass


class MultimodalInboxHistoryAutoShadowInputError(
    MultimodalInboxHistoryAutoShadowError
):
    pass


class MultimodalInboxHistoryAutoShadowBaselineUnavailable(
    MultimodalInboxHistoryAutoShadowError
):
    pass


class MultimodalInboxHistoryAutoShadowLookupError(
    MultimodalInboxHistoryAutoShadowError
):
    pass


class MultimodalInboxHistoryAutoShadowProviderUnavailable(
    MultimodalInboxHistoryAutoShadowError
):
    pass


class MultimodalInboxHistoryAutoShadowExecutionError(
    MultimodalInboxHistoryAutoShadowError
):
    pass


class MultimodalInboxHistoryAutoShadowIntegrityError(
    MultimodalInboxHistoryAutoShadowError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _bounded_int(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise MultimodalInboxHistoryAutoShadowInputError(
            label + " must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxHistoryAutoShadowInputError(
            label + " must be an integer."
        ) from error

    if result < minimum or result > maximum:
        raise MultimodalInboxHistoryAutoShadowInputError(
            label
            + " must be between "
            + str(minimum)
            + " and "
            + str(maximum)
            + "."
        )

    return result


def _finite_total(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(value, bool):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            label + " must be numeric."
        )

    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            label + " must be numeric."
        ) from error

    if (
        not math.isfinite(number)
        or number < 0.0
        or number > 100.0
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            label + " must be between 0 and 100."
        )

    return number


def _json_object(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    try:
        parsed = json.loads(
            str(value or "")
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            label + " contains invalid JSON."
        ) from error

    if not isinstance(parsed, dict):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            label + " must contain a JSON object."
        )

    return parsed


def _connect(connection_factory):
    if connection_factory is None:
        raise MultimodalInboxHistoryAutoShadowInputError(
            "Connection factory is required."
        )

    try:
        conn = connection_factory()
    except Exception as error:
        raise MultimodalInboxHistoryAutoShadowLookupError(
            "Persisted analysis history is unavailable."
        ) from error

    if conn is None:
        raise MultimodalInboxHistoryAutoShadowLookupError(
            "Persisted analysis history is unavailable."
        )

    return conn


def _load_anchor(
    *,
    anchor_capture_record_id: str,
    connection_factory,
    capture_loader,
) -> Dict[str, Any]:
    try:
        loaded = capture_loader(
            capture_record_id=anchor_capture_record_id,
            connection_factory=connection_factory,
        )
    except browser_capture_inbox.BrowserCaptureInboxInputError as error:
        raise MultimodalInboxHistoryAutoShadowInputError(
            str(error)
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxNotFoundError as error:
        raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
            "Anchor browser capture record does not exist."
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxPersistenceError as error:
        raise MultimodalInboxHistoryAutoShadowLookupError(
            "Anchor browser capture lookup failed."
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxIntegrityError as error:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture failed integrity validation."
        ) from error

    if not isinstance(loaded, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture loader returned an invalid result."
        )

    result = dict(loaded)

    if (
        _clean(result.get("version"))
        != browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture inbox version mismatch."
        )

    if (
        _clean(result.get("capture_record_id"))
        != anchor_capture_record_id
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture scope changed."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture policy is missing."
        )

    if policy.get("record_is_untrusted") is not True:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture trust boundary is missing."
        )

    if policy.get("integrity_rechecked_on_load") is not True:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture integrity boundary is missing."
        )

    if bool(policy.get("affects_live_merit")):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture unexpectedly affects Live Merit."
        )

    capture = result.get("capture")

    if not isinstance(capture, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor browser capture payload is missing."
        )

    return result


def _article_descriptor(
    loaded: Mapping[str, Any],
    *,
    content_hash_resolver,
    clean_html,
    url_normalizer,
) -> Dict[str, str]:
    platform = _clean(
        loaded.get("platform")
    ).lower()
    surface = _clean(
        loaded.get("platform_surface")
    ).lower()

    if platform != "web" or surface != "article":
        raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
            "Automatic persisted baseline resolution currently supports web article anchors only."
        )

    capture = loaded.get("capture")

    if not isinstance(capture, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor capture payload is missing."
        )

    payload = capture.get("payload")

    if not isinstance(payload, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor capture content payload is missing."
        )

    payload_platform = _clean(
        payload.get("platform")
    ).lower()
    payload_surface = _clean(
        payload.get("surface")
    ).lower()

    if payload_platform != "web" or payload_surface != "article":
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor capture article scope changed."
        )

    title = _clean(
        payload.get("title")
    )
    body = str(
        payload.get("body")
        or ""
    ).strip()

    if not title or not body:
        raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
            "Anchor article capture does not contain the title and body needed for exact baseline lookup."
        )

    canonical_url = _clean(
        url_normalizer(
            loaded.get("canonical_url")
        )
    )

    if not canonical_url:
        raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
            "Anchor article canonical URL is unavailable."
        )

    try:
        content_hash = _clean(
            content_hash_resolver(
                title + "\n" + body,
                clean_html=clean_html,
            )
        )
    except Exception as error:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor article content hash could not be reproduced."
        ) from error

    if not content_hash:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Anchor article content hash is empty."
        )

    return {
        "canonical_url": canonical_url,
        "title": title,
        "body": body,
        "content_hash": content_hash,
    }


def _snapshot_rows(
    *,
    descriptor: Mapping[str, Any],
    analysis_version: str,
    scoring_version: str,
    connection_factory,
) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    conn = _connect(
        connection_factory
    )

    try:
        media_rows = conn.execute(
            """
            SELECT
              id,
              canonical_url,
              mode
            FROM media_items
            WHERE canonical_url = ?
            """,
            (
                descriptor["canonical_url"],
            ),
        ).fetchall()

        if len(media_rows) != 1:
            if not media_rows:
                raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
                    "No persisted article media item matches the anchor canonical URL."
                )

            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted article media identity is ambiguous."
            )

        media = dict(media_rows[0])

        if _clean(media.get("canonical_url")) != descriptor["canonical_url"]:
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted article canonical URL changed."
            )

        if _clean(media.get("mode")).lower() != "article":
            raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
                "Persisted media item is not an article analysis target."
            )

        rows = conn.execute(
            """
            SELECT
              id,
              media_item_id,
              analyzed_at,
              mode,
              analysis_version,
              scoring_version,
              content_hash,
              context_hash,
              merit_score,
              score_calculation_json,
              response_json
            FROM analysis_snapshots
            WHERE media_item_id = ?
              AND mode = 'article'
              AND content_hash = ?
              AND analysis_version = ?
              AND scoring_version = ?
            ORDER BY
              analyzed_at DESC,
              id DESC
            """,
            (
                _clean(media.get("id")),
                descriptor["content_hash"],
                analysis_version,
                scoring_version,
            ),
        ).fetchall()

    except MultimodalInboxHistoryAutoShadowError:
        raise
    except sqlite3.Error as error:
        raise MultimodalInboxHistoryAutoShadowLookupError(
            "Persisted article baseline lookup failed."
        ) from error
    finally:
        conn.close()

    if not rows:
        raise MultimodalInboxHistoryAutoShadowBaselineUnavailable(
            "No current persisted article analysis snapshot exactly matches the anchor content."
        )

    return media, [
        dict(row)
        for row in rows
    ]


def _snapshot_legacy_total(
    snapshot: Mapping[str, Any],
) -> Dict[str, Any]:
    response = _json_object(
        snapshot.get("response_json"),
        label="Persisted analysis response",
    )

    debug = response.get("debug")

    if not isinstance(debug, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Persisted analysis response is missing release metadata."
        )

    release = debug.get("live_merit_release")

    if not isinstance(release, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Persisted analysis response is missing Live Merit lineage metadata."
        )

    if (
        _clean(release.get("version"))
        != live_merit_release.LIVE_MERIT_RELEASE_RUNTIME_VERSION
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Persisted Live Merit lineage version mismatch."
        )

    legacy_total = _finite_total(
        release.get("legacy_total"),
        label="Persisted legacy Merit total",
    )
    live_total = _finite_total(
        release.get("live_total"),
        label="Persisted live Merit total",
    )
    snapshot_total = _finite_total(
        snapshot.get("merit_score"),
        label="Persisted snapshot Merit total",
    )
    response_total = _finite_total(
        response.get("merit_score"),
        label="Persisted response Merit total",
    )

    score_effect_applied = release.get(
        "score_effect_applied"
    )

    if not isinstance(score_effect_applied, bool):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Persisted Live Merit lineage effect flag is invalid."
        )

    status = _clean(
        release.get("status")
    ).lower()

    if score_effect_applied:
        if status != "applied":
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted Live Merit lineage reports an inconsistent applied state."
            )
    else:
        if status != "legacy_fallback":
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted Live Merit lineage reports an inconsistent fallback state."
            )

        if abs(live_total - legacy_total) > 1e-9:
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted fallback changed the legacy Merit total."
            )

    if (
        abs(snapshot_total - live_total) > 1e-9
        or abs(response_total - live_total) > 1e-9
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Persisted analysis snapshot and Live Merit lineage totals disagree."
        )

    calculation = _json_object(
        snapshot.get("score_calculation_json"),
        label="Persisted score calculation",
    )

    if score_effect_applied:
        calculation_legacy = _finite_total(
            calculation.get(
                "legacy_total_before_certified_corroboration"
            ),
            label="Persisted score calculation legacy total",
        )
        calculation_final = _finite_total(
            calculation.get("final_total"),
            label="Persisted score calculation final total",
        )

        if (
            abs(calculation_legacy - legacy_total) > 1e-9
            or abs(calculation_final - live_total) > 1e-9
        ):
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted score calculation disagrees with Live Merit lineage."
            )

    return {
        "legacy_total": legacy_total,
        "live_total": live_total,
        "score_effect_applied": score_effect_applied,
        "release_status": status,
    }


def _resolve_baseline(
    *,
    descriptor: Mapping[str, Any],
    analysis_version: str,
    scoring_version: str,
    connection_factory,
) -> Dict[str, Any]:
    media, rows = _snapshot_rows(
        descriptor=descriptor,
        analysis_version=analysis_version,
        scoring_version=scoring_version,
        connection_factory=connection_factory,
    )

    resolved = []

    for row in rows:
        if _clean(row.get("media_item_id")) != _clean(media.get("id")):
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted analysis snapshot media scope changed."
            )

        if _clean(row.get("mode")).lower() != "article":
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted analysis snapshot mode changed."
            )

        if _clean(row.get("content_hash")) != descriptor["content_hash"]:
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted analysis snapshot content scope changed."
            )

        if _clean(row.get("analysis_version")) != analysis_version:
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted analysis version scope changed."
            )

        if _clean(row.get("scoring_version")) != scoring_version:
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Persisted scoring version scope changed."
            )

        lineage = _snapshot_legacy_total(
            row
        )

        resolved.append({
            "row": row,
            "lineage": lineage,
        })

    legacy_totals = {
        round(
            float(item["lineage"]["legacy_total"]),
            9,
        )
        for item in resolved
    }

    if len(legacy_totals) != 1:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Matching persisted snapshots disagree on the legacy Merit baseline."
        )

    selected = resolved[0]
    legacy_total = selected[
        "lineage"
    ]["legacy_total"]

    if abs(legacy_total - round(legacy_total)) <= 1e-9:
        public_total: int | float = int(
            round(legacy_total)
        )
    else:
        public_total = round(
            legacy_total,
            6,
        )

    return {
        "legacy_score": {
            "total": public_total,
        },
        "baseline": {
            "media_item_id": _clean(
                media.get("id")
            ),
            "canonical_url": descriptor[
                "canonical_url"
            ],
            "content_hash": descriptor[
                "content_hash"
            ],
            "analysis_version": analysis_version,
            "scoring_version": scoring_version,
            "snapshot_id": selected["row"]["id"],
            "snapshot_analyzed_at": _clean(
                selected["row"].get("analyzed_at")
            ),
            "matching_snapshot_count": len(
                resolved
            ),
            "legacy_total": public_total,
            "selected_snapshot_live_total": (
                selected["lineage"]["live_total"]
            ),
            "selected_snapshot_score_effect_applied": (
                selected["lineage"][
                    "score_effect_applied"
                ]
            ),
        },
    }


def _validate_auto_shadow(
    value: Any,
    *,
    anchor_capture_record_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Automatic inbox shadow orchestration returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != inbox_auto_shadow_orchestration.MULTIMODAL_INBOX_AUTO_SHADOW_VERSION
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Automatic inbox shadow orchestration version mismatch."
        )

    if _clean(result.get("status")).lower() != "completed_shadow":
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Automatic inbox shadow orchestration did not complete."
        )

    if (
        _clean(result.get("anchor_capture_record_id"))
        != anchor_capture_record_id
    ):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Automatic inbox shadow anchor scope changed."
        )

    if not _clean(result.get("claim_id")):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Automatic inbox shadow orchestration did not expose a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            "Automatic inbox shadow policy is missing."
        )

    required_true = (
        "automatic_selection_is_candidate_routing_only",
        "automatic_selection_requires_exactly_one_eligible_candidate",
        "eligible_candidate_requires_exactly_one_shared_entity",
        "candidate_score_is_not_a_truth_confidence",
        "selected_subject_is_not_verified_by_auto_selection",
        "downstream_candidate_gate_revalidates_selection",
        "downstream_exact_common_claim_required",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Automatic inbox shadow safety boundary missing: "
                + field
            )

    required_false = (
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    )

    for field in required_false:
        if bool(policy.get(field)):
            raise MultimodalInboxHistoryAutoShadowIntegrityError(
                "Automatic inbox shadow enabled forbidden field: "
                + field
            )

    return result


def execute_multimodal_inbox_history_auto_shadow(
    *,
    anchor_capture_record_id: str,
    analysis_version: str,
    scoring_version: str,
    target_claim_id: str = "",
    scan_limit: int = 100,
    max_candidates: int = 12,
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    capture_loader=(
        browser_capture_inbox
        .load_browser_capture_record
    ),
    content_hash_resolver=(
        analysis_cache
        .analysis_content_hash
    ),
    clean_html=(
        article_rules
        .clean_html
    ),
    url_normalizer=(
        content_resolution
        .normalized_analysis_url
    ),
    auto_shadow_runner=(
        inbox_auto_shadow_orchestration
        .execute_multimodal_inbox_auto_shadow
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(
        anchor_capture_record_id
    )
    current_analysis_version = _clean(
        analysis_version
    )
    current_scoring_version = _clean(
        scoring_version
    )

    if not anchor_id:
        raise MultimodalInboxHistoryAutoShadowInputError(
            "Anchor capture record ID is required."
        )

    if len(anchor_id) > 256:
        raise MultimodalInboxHistoryAutoShadowInputError(
            "Anchor capture record ID is too long."
        )

    if not current_analysis_version:
        raise MultimodalInboxHistoryAutoShadowInputError(
            "Current analysis version is required."
        )

    if not current_scoring_version:
        raise MultimodalInboxHistoryAutoShadowInputError(
            "Current scoring version is required."
        )

    scan_limit = _bounded_int(
        scan_limit,
        label="Inbox scan limit",
        minimum=1,
        maximum=500,
    )

    max_candidates = _bounded_int(
        max_candidates,
        label="Candidate limit",
        minimum=1,
        maximum=50,
    )

    if gemini_client is None:
        raise MultimodalInboxHistoryAutoShadowProviderUnavailable(
            "Gemini multimodal client is not configured."
        )

    if not callable(gemini_generator):
        raise MultimodalInboxHistoryAutoShadowProviderUnavailable(
            "Gemini generator is unavailable."
        )

    loaded = _load_anchor(
        anchor_capture_record_id=anchor_id,
        connection_factory=connection_factory,
        capture_loader=capture_loader,
    )

    descriptor = _article_descriptor(
        loaded,
        content_hash_resolver=content_hash_resolver,
        clean_html=clean_html,
        url_normalizer=url_normalizer,
    )

    baseline_resolution = _resolve_baseline(
        descriptor=descriptor,
        analysis_version=current_analysis_version,
        scoring_version=current_scoring_version,
        connection_factory=connection_factory,
    )

    try:
        auto_raw = auto_shadow_runner(
            anchor_capture_record_id=anchor_id,
            legacy_score=baseline_resolution[
                "legacy_score"
            ],
            target_claim_id=_clean(
                target_claim_id
            ),
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            connection_factory=connection_factory,
            gemini_client=gemini_client,
            gemini_client_key=(
                _clean(gemini_client_key)
                or "anonymous"
            ),
            gemini_generator=gemini_generator,
        )
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowInputError as error:
        raise MultimodalInboxHistoryAutoShadowInputError(
            str(error)
        ) from error
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowDiscoveryError as error:
        raise MultimodalInboxHistoryAutoShadowExecutionError(
            str(error)
        ) from error
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowSelectionError as error:
        raise MultimodalInboxHistoryAutoShadowExecutionError(
            str(error)
        ) from error
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowProviderUnavailable as error:
        raise MultimodalInboxHistoryAutoShadowProviderUnavailable(
            str(error)
        ) from error
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowExecutionError as error:
        raise MultimodalInboxHistoryAutoShadowExecutionError(
            str(error)
        ) from error
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowIntegrityError as error:
        raise MultimodalInboxHistoryAutoShadowIntegrityError(
            str(error)
        ) from error

    auto_shadow = _validate_auto_shadow(
        auto_raw,
        anchor_capture_record_id=anchor_id,
    )

    return {
        "version": (
            MULTIMODAL_INBOX_HISTORY_AUTO_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": auto_shadow["claim_id"],
        "anchor_capture_record_id": anchor_id,
        "selected_candidate_capture_record_id": (
            auto_shadow[
                "selected_candidate_capture_record_id"
            ]
        ),
        "selected_subject_entity_id": (
            auto_shadow[
                "selected_subject_entity_id"
            ]
        ),
        "baseline_resolution": baseline_resolution[
            "baseline"
        ],
        "automatic_selection": auto_shadow.get(
            "automatic_selection",
            {},
        ),
        "orchestration": auto_shadow,
        "policy": {
            "caller_cannot_supply_legacy_score": True,
            "baseline_from_persisted_analysis_snapshot": True,
            "baseline_resolution_is_read_only": True,
            "baseline_url_exact_match_required": True,
            "baseline_content_hash_exact_match_required": True,
            "baseline_current_analysis_version_required": True,
            "baseline_current_scoring_version_required": True,
            "matching_snapshot_legacy_totals_must_agree": True,
            "legacy_total_recovered_from_live_merit_lineage": True,
            "snapshot_displayed_score_not_used_as_legacy_baseline_when_live_effect_applied": True,
            "non_article_anchor_auto_baseline_unsupported": True,
            "baseline_score_does_not_establish_truth": True,
            "baseline_score_does_not_establish_authority": True,
            "automatic_selection_is_candidate_routing_only": True,
            "downstream_auto_selection_revalidated": True,
            "downstream_exact_common_claim_required": True,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
