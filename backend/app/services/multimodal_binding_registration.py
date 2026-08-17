from __future__ import annotations

import hashlib
import json
import sqlite3

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from app.intelligence import entities
from app.intelligence import sources
from app.services import analysis_history
from app.services import browser_ingestion
from app.services import content_normalization
from app.services.content_resolution import normalized_analysis_url


MULTIMODAL_BINDING_REGISTRATION_VERSION = (
    "multimodal-binding-registration-v1"
)

SUPPORTED_BROWSER_PLATFORMS = {
    "web",
    "x",
    "instagram",
    "tiktok",
    "reddit",
    "facebook",
    "youtube",
}


class MultimodalBindingRegistrationError(RuntimeError):
    pass


class MultimodalBindingInputError(
    MultimodalBindingRegistrationError
):
    pass


class MultimodalBindingIdentityError(
    MultimodalBindingRegistrationError
):
    pass


class MultimodalBindingPersistenceError(
    MultimodalBindingRegistrationError
):
    pass


class MultimodalBindingIntegrityError(
    MultimodalBindingRegistrationError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _key(value: Any) -> str:
    return _clean(value).casefold()


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _mapping(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalBindingInputError(
            label + " must be an object."
        )

    return dict(value)


def _subject_descriptor(
    value: Any,
) -> Dict[str, str]:
    subject = _mapping(
        value,
        label="Subject",
    )

    entity_key = _key(
        subject.get("entity_key")
    )
    entity_type = _key(
        subject.get("entity_type")
    )
    canonical_name = _clean(
        subject.get("canonical_name")
    )
    sport_key = _key(
        subject.get("sport_key")
    )

    if not entity_key:
        raise MultimodalBindingInputError(
            "Subject entity_key is required."
        )

    if entity_type not in entities.ENTITY_TYPES:
        raise MultimodalBindingInputError(
            "Subject entity_type is unsupported."
        )

    if not canonical_name:
        raise MultimodalBindingInputError(
            "Subject canonical_name is required."
        )

    return {
        "entity_key": entity_key,
        "entity_type": entity_type,
        "canonical_name": canonical_name,
        "sport_key": sport_key,
        "entity_id": (
            entities.canonical_entity_id_for_key(
                entity_key
            )
        ),
    }


def _normalize_capture(
    value: Any,
    *,
    label: str,
):
    capture = _mapping(
        value,
        label=label + " capture",
    )

    try:
        item = (
            browser_ingestion
            .normalize_browser_capture(
                capture
            )
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise MultimodalBindingInputError(
            label
            + " capture is invalid: "
            + str(error)
        ) from error

    platform = _key(
        item.platform
    )

    if platform not in SUPPORTED_BROWSER_PLATFORMS:
        raise MultimodalBindingInputError(
            label
            + " capture platform is unsupported."
        )

    canonical_url = normalized_analysis_url(
        item.canonical_url
    )

    if not canonical_url:
        raise MultimodalBindingInputError(
            label
            + " capture requires a canonical URL."
        )

    return item


def _domain_for_url(url: str) -> str:
    return sources.source_domain_for_url(
        url,
        normalize_url=normalized_analysis_url,
    )


def _source_id_for_key(source_key: str) -> str:
    return hashlib.sha256(
        (
            "source|"
            + source_key
        ).encode("utf-8")
    ).hexdigest()


def _actor_identity(
    actor: Mapping[str, Any],
) -> Dict[str, str]:
    platform_actor_id = _key(
        actor.get(
            "platform_actor_id",
            actor.get("id"),
        )
    )

    handle = _key(
        actor.get(
            "handle",
            actor.get("username"),
        )
    ).lstrip("@")

    profile_url = normalized_analysis_url(
        actor.get(
            "profile_url",
            actor.get("url"),
        )
    )

    if platform_actor_id:
        return {
            "basis": "platform_actor_id",
            "value": platform_actor_id,
        }

    if handle:
        return {
            "basis": "handle",
            "value": handle,
        }

    if profile_url:
        return {
            "basis": "profile_url",
            "value": profile_url.casefold(),
        }

    raise MultimodalBindingIdentityError(
        "Social browser captures require a stable "
        "captured actor identity (platform_actor_id, "
        "handle, or profile_url)."
    )


def _source_descriptor(
    item,
    captured_actor: Mapping[str, Any],
) -> Dict[str, Any]:
    canonical_url = normalized_analysis_url(
        item.canonical_url
    )

    canonical_domain = _domain_for_url(
        canonical_url
    )

    if not canonical_domain:
        raise MultimodalBindingIdentityError(
            "Capture source domain could not be resolved."
        )

    platform = _key(
        item.platform
    )

    if platform == "web":
        source_key = (
            sources.source_key_for_url(
                canonical_url,
                "publisher",
                domain_resolver=_domain_for_url,
            )
        )

        return {
            "source_id": (
                _source_id_for_key(
                    source_key
                )
            ),
            "source_key": source_key,
            "source_type": "publisher",
            "canonical_domain": canonical_domain,
            "display_name": canonical_domain,
            "identity_basis": "domain",
            "identity_value": canonical_domain,
            "metadata": {
                "platform": platform,
                "identity_basis": "domain",
                "identity_value": canonical_domain,
                "registration_version": (
                    MULTIMODAL_BINDING_REGISTRATION_VERSION
                ),
            },
        }

    identity = _actor_identity(
        captured_actor
    )

    source_type = (
        "channel"
        if platform == "youtube"
        else "social_account"
    )

    source_key = "|".join(
        (
            source_type,
            platform,
            identity["basis"],
            identity["value"],
        )
    )

    captured_handle = _clean(
        captured_actor.get(
            "handle",
            captured_actor.get("username"),
        )
    )

    captured_profile_url = _clean(
        captured_actor.get(
            "profile_url",
            captured_actor.get("url"),
        )
    )

    captured_platform_actor_id = _clean(
        captured_actor.get(
            "platform_actor_id",
            captured_actor.get("id"),
        )
    )

    display_name = (
        _clean(
            captured_actor.get(
                "display_name",
                captured_actor.get("name"),
            )
        )
        or captured_handle
        or identity["value"]
    )

    return {
        "source_id": (
            _source_id_for_key(
                source_key
            )
        ),
        "source_key": source_key,
        "source_type": source_type,
        "canonical_domain": canonical_domain,
        "display_name": display_name,
        "identity_basis": identity["basis"],
        "identity_value": identity["value"],
        "metadata": {
            "platform": platform,
            "identity_basis": identity["basis"],
            "identity_value": identity["value"],
            "identity_from_capture_actor": True,
            "structural_actor_hint_not_promoted": True,
            "handle": captured_handle,
            "profile_url": captured_profile_url,
            "platform_actor_id": captured_platform_actor_id,
            "actor_canonical_entity_id_ignored": bool(
                _clean(
                    captured_actor.get(
                        "canonical_entity_id"
                    )
                )
            ),
            "registration_version": (
                MULTIMODAL_BINDING_REGISTRATION_VERSION
            ),
        },
    }


def _item_title(item) -> str:
    for component in item.text_components:
        if component.role == "title":
            return _clean(
                component.text
            )

    return ""


def _media_descriptor(
    item,
    source: Mapping[str, Any],
) -> Dict[str, Any]:
    canonical_url = normalized_analysis_url(
        item.canonical_url
    )

    try:
        media_item_id = (
            analysis_history
            .media_item_id_for_url(
                canonical_url,
                normalize_url=(
                    normalized_analysis_url
                ),
            )
        )
    except ValueError as error:
        raise MultimodalBindingInputError(
            "Capture media identity is invalid."
        ) from error

    content_hash = (
        content_normalization
        .normalized_item_fingerprint(
            item
        )
    )

    if not content_hash:
        raise MultimodalBindingIntegrityError(
            "Normalized capture fingerprint is empty."
        )

    seen_at = (
        _clean(item.observed_at)
        or _now()
    )

    return {
        "media_item_id": media_item_id,
        "canonical_url": canonical_url,
        "mode": "multimodal_capture",
        "source_id": source["source_id"],
        "title": _item_title(item),
        "published_at": (
            _clean(item.published_at)
            or None
        ),
        "content_hash": content_hash,
        "seen_at": seen_at,
        "metadata": {
            "unified_item_id": item.item_id,
            "platform": _key(item.platform),
            "platform_surface": _clean(
                item.platform_surface
            ),
            "container_kind": _clean(
                item.container_kind
            ),
            "registration_version": (
                MULTIMODAL_BINDING_REGISTRATION_VERSION
            ),
        },
    }


def _prepare_side(
    capture: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    raw_capture = _mapping(
        capture,
        label=label + " capture",
    )

    item = _normalize_capture(
        raw_capture,
        label=label,
    )

    actor_value = raw_capture.get(
        "actor",
        {},
    )

    if actor_value is None:
        actor_value = {}

    if not isinstance(
        actor_value,
        Mapping,
    ):
        raise MultimodalBindingInputError(
            label
            + " capture actor must be an object."
        )

    source = _source_descriptor(
        item,
        dict(actor_value),
    )

    media = _media_descriptor(
        item,
        source,
    )

    return {
        "item": item,
        "source": source,
        "media": media,
    }


def _one(
    conn,
    sql: str,
    parameters=(),
):
    row = conn.execute(
        sql,
        parameters,
    ).fetchone()

    if row is None:
        return None

    return dict(row)


def _persist_subject(
    conn,
    subject: Mapping[str, str],
    *,
    recorded_at: str,
) -> Dict[str, Any]:
    existing = _one(
        conn,
        """
        SELECT *
        FROM canonical_entities
        WHERE entity_key = ?
        """,
        (
            subject["entity_key"],
        ),
    )

    if existing is None:
        id_collision = _one(
            conn,
            """
            SELECT entity_key
            FROM canonical_entities
            WHERE id = ?
            """,
            (
                subject["entity_id"],
            ),
        )

        if id_collision is not None:
            raise MultimodalBindingIntegrityError(
                "Canonical entity ID collision detected."
            )

        conn.execute(
            """
            INSERT INTO canonical_entities (
              id,
              entity_key,
              entity_type,
              sport_key,
              canonical_name,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subject["entity_id"],
                subject["entity_key"],
                subject["entity_type"],
                subject["sport_key"],
                subject["canonical_name"],
                recorded_at,
                recorded_at,
                _json({
                    "registration_version": (
                        MULTIMODAL_BINDING_REGISTRATION_VERSION
                    ),
                    "identity_admin_supplied": True,
                }),
            ),
        )

    else:
        if (
            _clean(existing.get("id"))
            != subject["entity_id"]
        ):
            raise MultimodalBindingIntegrityError(
                "Canonical entity key resolved to "
                "an unexpected deterministic ID."
            )

        if (
            _key(existing.get("entity_type"))
            != subject["entity_type"]
        ):
            raise MultimodalBindingIdentityError(
                "Subject entity_type conflicts with "
                "the persisted canonical entity."
            )

        if (
            _key(existing.get("sport_key"))
            != subject["sport_key"]
        ):
            raise MultimodalBindingIdentityError(
                "Subject sport_key conflicts with "
                "the persisted canonical entity."
            )

        conn.execute(
            """
            UPDATE canonical_entities
            SET
              canonical_name = ?,
              last_seen_at = ?
            WHERE entity_key = ?
            """,
            (
                subject["canonical_name"],
                recorded_at,
                subject["entity_key"],
            ),
        )

    row = _one(
        conn,
        """
        SELECT *
        FROM canonical_entities
        WHERE entity_key = ?
        """,
        (
            subject["entity_key"],
        ),
    )

    if row is None:
        raise MultimodalBindingPersistenceError(
            "Canonical subject persistence failed."
        )

    return row


def _persist_source(
    conn,
    source: Mapping[str, Any],
    *,
    seen_at: str,
) -> Dict[str, Any]:
    existing = _one(
        conn,
        """
        SELECT *
        FROM intelligence_sources
        WHERE source_key = ?
        """,
        (
            source["source_key"],
        ),
    )

    if existing is None:
        id_collision = _one(
            conn,
            """
            SELECT source_key
            FROM intelligence_sources
            WHERE id = ?
            """,
            (
                source["source_id"],
            ),
        )

        if id_collision is not None:
            raise MultimodalBindingIntegrityError(
                "Source ID collision detected."
            )

        conn.execute(
            """
            INSERT INTO intelligence_sources (
              id,
              source_key,
              display_name,
              source_type,
              canonical_domain,
              publication_founded_at,
              domain_registered_at,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
            """,
            (
                source["source_id"],
                source["source_key"],
                source["display_name"],
                source["source_type"],
                source["canonical_domain"],
                seen_at,
                seen_at,
                _json(source["metadata"]),
            ),
        )

    else:
        if (
            _clean(existing.get("id"))
            != source["source_id"]
        ):
            raise MultimodalBindingIntegrityError(
                "Source key resolved to an unexpected ID."
            )

        if (
            _key(existing.get("source_type"))
            != source["source_type"]
        ):
            raise MultimodalBindingIntegrityError(
                "Source type changed for a stable source key."
            )

        conn.execute(
            """
            UPDATE intelligence_sources
            SET
              display_name = CASE
                WHEN ? != '' THEN ?
                ELSE display_name
              END,
              canonical_domain = COALESCE(
                canonical_domain,
                ?
              ),
              last_seen_at = ?,
              metadata_json = ?
            WHERE source_key = ?
            """,
            (
                source["display_name"],
                source["display_name"],
                source["canonical_domain"],
                seen_at,
                _json(source["metadata"]),
                source["source_key"],
            ),
        )

    row = _one(
        conn,
        """
        SELECT *
        FROM intelligence_sources
        WHERE source_key = ?
        """,
        (
            source["source_key"],
        ),
    )

    if row is None:
        raise MultimodalBindingPersistenceError(
            "Source persistence failed."
        )

    return row


def _persist_media(
    conn,
    media: Mapping[str, Any],
) -> Dict[str, Any]:
    existing = _one(
        conn,
        """
        SELECT *
        FROM media_items
        WHERE canonical_url = ?
        """,
        (
            media["canonical_url"],
        ),
    )

    if existing is None:
        id_collision = _one(
            conn,
            """
            SELECT canonical_url
            FROM media_items
            WHERE id = ?
            """,
            (
                media["media_item_id"],
            ),
        )

        if id_collision is not None:
            raise MultimodalBindingIntegrityError(
                "Media item ID collision detected."
            )

        conn.execute(
            """
            INSERT INTO media_items (
              id,
              canonical_url,
              mode,
              source_id,
              reporter_id,
              title,
              published_at,
              latest_content_hash,
              first_seen_at,
              last_seen_at,
              metadata_json
            )
            VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                media["media_item_id"],
                media["canonical_url"],
                media["mode"],
                media["source_id"],
                media["title"],
                media["published_at"],
                media["content_hash"],
                media["seen_at"],
                media["seen_at"],
                _json(media["metadata"]),
            ),
        )

    else:
        if (
            _clean(existing.get("id"))
            != media["media_item_id"]
        ):
            raise MultimodalBindingIntegrityError(
                "Media canonical URL resolved to "
                "an unexpected deterministic ID."
            )

        existing_source = _clean(
            existing.get("source_id")
        )

        if (
            existing_source
            and existing_source
            != media["source_id"]
        ):
            raise MultimodalBindingIdentityError(
                "Persisted media item is already bound "
                "to a different source identity."
            )

        conn.execute(
            """
            UPDATE media_items
            SET
              source_id = COALESCE(
                source_id,
                ?
              ),
              title = CASE
                WHEN ? != '' THEN ?
                ELSE title
              END,
              published_at = COALESCE(
                ?,
                published_at
              ),
              latest_content_hash = ?,
              last_seen_at = ?,
              metadata_json = ?
            WHERE canonical_url = ?
            """,
            (
                media["source_id"],
                media["title"],
                media["title"],
                media["published_at"],
                media["content_hash"],
                media["seen_at"],
                _json(media["metadata"]),
                media["canonical_url"],
            ),
        )

    row = _one(
        conn,
        """
        SELECT *
        FROM media_items
        WHERE canonical_url = ?
        """,
        (
            media["canonical_url"],
        ),
    )

    if row is None:
        raise MultimodalBindingPersistenceError(
            "Media item persistence failed."
        )

    return row


def _side_result(
    prepared: Mapping[str, Any],
) -> Dict[str, Any]:
    item = prepared["item"]
    source = prepared["source"]
    media = prepared["media"]

    return {
        "source_id": source["source_id"],
        "source_key": source["source_key"],
        "source_type": source["source_type"],
        "source_identity_basis": (
            source["identity_basis"]
        ),
        "source_identity_value": (
            source["identity_value"]
        ),
        "media_item_id": media["media_item_id"],
        "canonical_url": media["canonical_url"],
        "unified_item_id": item.item_id,
        "story_id": "",
    }


def register_multimodal_bindings(
    *,
    subject: Mapping[str, Any],
    left_capture: Mapping[str, Any],
    right_capture: Mapping[str, Any],
    connection_factory,
    now_provider=_now,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise MultimodalBindingPersistenceError(
            "Binding registration requires database access."
        )

    normalized_subject = _subject_descriptor(
        subject
    )

    left = _prepare_side(
        left_capture,
        label="Left",
    )

    right = _prepare_side(
        right_capture,
        label="Right",
    )

    if (
        left["media"]["media_item_id"]
        == right["media"]["media_item_id"]
    ):
        raise MultimodalBindingInputError(
            "Binding registration requires two "
            "distinct media items."
        )

    recorded_at = _clean(
        now_provider()
    )

    if not recorded_at:
        raise MultimodalBindingIntegrityError(
            "Binding registration clock returned an empty timestamp."
        )

    conn = connection_factory()

    if conn is None:
        raise MultimodalBindingPersistenceError(
            "Database connection is unavailable."
        )

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        subject_row = _persist_subject(
            conn,
            normalized_subject,
            recorded_at=recorded_at,
        )

        for prepared in (left, right):
            source = prepared["source"]
            media = prepared["media"]

            _persist_source(
                conn,
                source,
                seen_at=media["seen_at"],
            )

            _persist_media(
                conn,
                media,
            )

        conn.commit()

    except MultimodalBindingRegistrationError:
        conn.rollback()
        raise

    except sqlite3.Error as error:
        conn.rollback()
        raise MultimodalBindingPersistenceError(
            "Multimodal binding persistence failed."
        ) from error

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "version": (
            MULTIMODAL_BINDING_REGISTRATION_VERSION
        ),
        "status": "registered",
        "subject": {
            "entity_id": subject_row["id"],
            "entity_key": subject_row["entity_key"],
            "entity_type": subject_row["entity_type"],
            "canonical_name": subject_row["canonical_name"],
            "sport_key": subject_row["sport_key"],
        },
        "subject_key": subject_row["entity_key"],
        "left": _side_result(left),
        "right": _side_result(right),
        "policy": {
            "admin_supplied_subject_identity": True,
            "subject_record_is_identity_only": True,
            "source_identity_is_deterministic": True,
            "social_source_identity_is_account_scoped": True,
            "stable_actor_identity_required_for_social": True,
            "social_identity_uses_capture_actor_only": True,
            "structural_actor_hint_not_promoted": True,
            "source_and_media_persisted_atomically": True,
            "story_record_created": False,
            "verified_source_entity_binding_created": False,
            "verified_claim_entity_participant_created": False,
            "claim_created": False,
            "observation_created": False,
            "evidence_record_created": False,
            "model_output_used": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "training_eligible": False,
            "affects_live_merit": False,
            "live_release_not_called": True,
        },
    }
