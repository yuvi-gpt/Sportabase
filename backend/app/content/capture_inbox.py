from __future__ import annotations

import hashlib
import json
import os
import sqlite3

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from fastapi import HTTPException

from app.services import browser_ingestion
from app.services import content_normalization


BROWSER_CAPTURE_INBOX_VERSION = (
    "browser-capture-inbox-v1"
)

BROWSER_CAPTURE_INBOX_FLAG = (
    "SPORTABASE_BROWSER_CAPTURE_INBOX_ENABLED"
)

BROWSER_CAPTURE_INBOX_MAX_BYTES = (
    "SPORTABASE_BROWSER_CAPTURE_INBOX_MAX_BYTES"
)

DEFAULT_BROWSER_CAPTURE_INBOX_MAX_BYTES = 131072


class BrowserCaptureInboxError(RuntimeError):
    pass


class BrowserCaptureInboxInputError(
    BrowserCaptureInboxError
):
    pass


class BrowserCaptureInboxPersistenceError(
    BrowserCaptureInboxError
):
    pass


class BrowserCaptureInboxIntegrityError(
    BrowserCaptureInboxError
):
    pass


class BrowserCaptureInboxNotFoundError(
    BrowserCaptureInboxError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise BrowserCaptureInboxInputError(
            "Browser capture must be JSON serializable."
        ) from error


def _mapping(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BrowserCaptureInboxInputError(
            label + " must be an object."
        )

    return dict(value)


def inbox_enabled(
    *,
    env_getter=os.getenv,
) -> bool:
    raw = _clean(
        env_getter(
            BROWSER_CAPTURE_INBOX_FLAG,
            "0",
        )
    ).lower()

    return raw in {
        "1",
        "true",
        "yes",
        "on",
    }


def inbox_max_bytes(
    *,
    env_getter=os.getenv,
) -> int:
    raw = _clean(
        env_getter(
            BROWSER_CAPTURE_INBOX_MAX_BYTES,
            str(
                DEFAULT_BROWSER_CAPTURE_INBOX_MAX_BYTES
            ),
        )
    )

    try:
        value = int(raw)
    except (
        TypeError,
        ValueError,
    ):
        return DEFAULT_BROWSER_CAPTURE_INBOX_MAX_BYTES

    if value < 4096:
        return 4096

    if value > 1048576:
        return 1048576

    return value


def _capture_json(
    raw_capture: Mapping[str, Any],
) -> str:
    capture = _mapping(
        raw_capture,
        label="Browser capture",
    )

    return _json(capture)


def _capture_hash(
    capture_json: str,
) -> str:
    return hashlib.sha256(
        capture_json.encode("utf-8")
    ).hexdigest()


def capture_record_id_for_hash(
    capture_hash: str,
) -> str:
    clean_hash = _clean(
        capture_hash
    ).lower()

    if not clean_hash:
        raise BrowserCaptureInboxInputError(
            "Capture hash is required."
        )

    digest = hashlib.sha256(
        (
            BROWSER_CAPTURE_INBOX_VERSION
            + "|"
            + clean_hash
        ).encode("utf-8")
    ).hexdigest()

    return "bci_" + digest


def capture_record_identity(
    raw_capture: Mapping[str, Any],
) -> Dict[str, str]:
    capture_json = _capture_json(
        raw_capture
    )

    capture_hash = _capture_hash(
        capture_json
    )

    return {
        "capture_json": capture_json,
        "capture_hash": capture_hash,
        "capture_record_id": (
            capture_record_id_for_hash(
                capture_hash
            )
        ),
    }


def _normalized_descriptor(
    raw_capture: Mapping[str, Any],
) -> Dict[str, str]:
    try:
        item = (
            browser_ingestion
            .normalize_browser_capture(
                raw_capture
            )
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise BrowserCaptureInboxInputError(
            str(error)
        ) from error

    fingerprint = (
        content_normalization
        .normalized_item_fingerprint(
            item
        )
    )

    if not fingerprint:
        raise BrowserCaptureInboxIntegrityError(
            "Normalized browser capture fingerprint is empty."
        )

    return {
        "normalized_item_id": _clean(
            item.item_id
        ),
        "normalized_content_hash": fingerprint,
        "canonical_url": _clean(
            item.canonical_url
        ),
        "platform": _clean(
            item.platform
        ).lower(),
        "platform_surface": _clean(
            item.platform_surface
        ).lower(),
        "observed_at": _clean(
            item.observed_at
        ),
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



def _connect(connection_factory):
    try:
        conn = connection_factory()
    except Exception as error:
        raise BrowserCaptureInboxPersistenceError(
            "Browser capture inbox database is unavailable."
        ) from error

    if conn is None:
        raise BrowserCaptureInboxPersistenceError(
            "Browser capture inbox database is unavailable."
        )

    return conn


def store_browser_capture(
    *,
    raw_capture: Mapping[str, Any],
    connection_factory,
    now_provider=_utc_now,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise BrowserCaptureInboxPersistenceError(
            "Browser capture inbox requires database access."
        )

    identity = capture_record_identity(
        raw_capture
    )

    descriptor = _normalized_descriptor(
        raw_capture
    )

    received_at = _clean(
        now_provider()
    )

    if not received_at:
        raise BrowserCaptureInboxIntegrityError(
            "Browser capture inbox clock returned an empty timestamp."
        )

    conn = _connect(
        connection_factory
    )

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        existing = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_inbox
            WHERE id = ?
            """,
            (
                identity[
                    "capture_record_id"
                ],
            ),
        )

        status = "stored"

        if existing is None:
            collision = _one(
                conn,
                """
                SELECT id
                FROM browser_capture_inbox
                WHERE capture_hash = ?
                """,
                (
                    identity[
                        "capture_hash"
                    ],
                ),
            )

            if collision is not None:
                raise BrowserCaptureInboxIntegrityError(
                    "Capture hash resolved to an unexpected inbox ID."
                )

            conn.execute(
                """
                INSERT INTO browser_capture_inbox (
                  id,
                  capture_hash,
                  canonical_url,
                  platform,
                  platform_surface,
                  normalized_item_id,
                  normalized_content_hash,
                  observed_at,
                  first_received_at,
                  last_received_at,
                  receive_count,
                  capture_json,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    identity[
                        "capture_record_id"
                    ],
                    identity[
                        "capture_hash"
                    ],
                    descriptor[
                        "canonical_url"
                    ],
                    descriptor[
                        "platform"
                    ],
                    descriptor[
                        "platform_surface"
                    ],
                    descriptor[
                        "normalized_item_id"
                    ],
                    descriptor[
                        "normalized_content_hash"
                    ],
                    descriptor[
                        "observed_at"
                    ],
                    received_at,
                    received_at,
                    identity[
                        "capture_json"
                    ],
                    _json({
                        "inbox_version": (
                            BROWSER_CAPTURE_INBOX_VERSION
                        ),
                        "trust_class": (
                            "untrusted_browser_capture"
                        ),
                        "identity_only": False,
                        "subject_asserted": False,
                        "source_authority_asserted": False,
                        "evidence_verified": False,
                        "training_eligible": False,
                        "affects_live_merit": False,
                    }),
                ),
            )

        else:
            for field, expected in (
                (
                    "capture_hash",
                    identity[
                        "capture_hash"
                    ],
                ),
                (
                    "capture_json",
                    identity[
                        "capture_json"
                    ],
                ),
                (
                    "canonical_url",
                    descriptor[
                        "canonical_url"
                    ],
                ),
                (
                    "normalized_item_id",
                    descriptor[
                        "normalized_item_id"
                    ],
                ),
                (
                    "normalized_content_hash",
                    descriptor[
                        "normalized_content_hash"
                    ],
                ),
            ):
                if _clean(
                    existing.get(field)
                ) != _clean(expected):
                    raise BrowserCaptureInboxIntegrityError(
                        "Stored browser capture identity changed: "
                        + field
                    )

            conn.execute(
                """
                UPDATE browser_capture_inbox
                SET
                  last_received_at = ?,
                  receive_count = receive_count + 1
                WHERE id = ?
                """,
                (
                    received_at,
                    identity[
                        "capture_record_id"
                    ],
                ),
            )

            status = "replayed"

        row = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_inbox
            WHERE id = ?
            """,
            (
                identity[
                    "capture_record_id"
                ],
            ),
        )

        if row is None:
            raise BrowserCaptureInboxPersistenceError(
                "Browser capture inbox persistence failed."
            )

        conn.commit()

    except BrowserCaptureInboxError:
        conn.rollback()
        raise

    except sqlite3.Error as error:
        conn.rollback()
        raise BrowserCaptureInboxPersistenceError(
            "Browser capture inbox persistence failed."
        ) from error

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "version": BROWSER_CAPTURE_INBOX_VERSION,
        "status": status,
        "capture_record_id": row["id"],
        "capture_hash": row["capture_hash"],
        "canonical_url": row["canonical_url"],
        "platform": row["platform"],
        "platform_surface": row["platform_surface"],
        "observed_at": row["observed_at"],
        "receive_count": int(
            row["receive_count"]
        ),
        "policy": {
            "untrusted_acquisition_record": True,
            "subject_asserted": False,
            "source_identity_created": False,
            "media_item_created": False,
            "claim_created": False,
            "observation_created": False,
            "evidence_record_created": False,
            "authority_established": False,
            "independence_established": False,
            "training_eligible": False,
            "affects_live_merit": False,
        },
    }


def load_browser_capture_record(
    *,
    capture_record_id: str,
    connection_factory,
) -> Dict[str, Any]:
    record_id = _clean(
        capture_record_id
    )

    if not record_id:
        raise BrowserCaptureInboxInputError(
            "Capture record ID is required."
        )

    if connection_factory is None:
        raise BrowserCaptureInboxPersistenceError(
            "Browser capture inbox requires database access."
        )

    conn = _connect(
        connection_factory
    )

    try:
        row = _one(
            conn,
            """
            SELECT *
            FROM browser_capture_inbox
            WHERE id = ?
            """,
            (
                record_id,
            ),
        )
    except sqlite3.Error as error:
        raise BrowserCaptureInboxPersistenceError(
            "Browser capture inbox lookup failed."
        ) from error
    finally:
        conn.close()

    if row is None:
        raise BrowserCaptureInboxNotFoundError(
            "Browser capture inbox record does not exist."
        )

    capture_json = str(
        row.get("capture_json")
        or ""
    )

    if not capture_json:
        raise BrowserCaptureInboxIntegrityError(
            "Stored browser capture payload is empty."
        )

    try:
        capture = json.loads(
            capture_json
        )
    except json.JSONDecodeError as error:
        raise BrowserCaptureInboxIntegrityError(
            "Stored browser capture payload is invalid JSON."
        ) from error

    capture = _mapping(
        capture,
        label="Stored browser capture",
    )

    identity = capture_record_identity(
        capture
    )

    if (
        identity[
            "capture_record_id"
        ]
        != record_id
        or identity[
            "capture_hash"
        ]
        != _clean(
            row.get("capture_hash")
        ).lower()
        or identity[
            "capture_json"
        ]
        != capture_json
    ):
        raise BrowserCaptureInboxIntegrityError(
            "Stored browser capture identity validation failed."
        )

    descriptor = _normalized_descriptor(
        capture
    )

    for field in (
        "canonical_url",
        "platform",
        "platform_surface",
        "normalized_item_id",
        "normalized_content_hash",
        "observed_at",
    ):
        if _clean(
            row.get(field)
        ) != _clean(
            descriptor.get(field)
        ):
            raise BrowserCaptureInboxIntegrityError(
                "Stored browser capture normalization changed: "
                + field
            )

    return {
        "version": BROWSER_CAPTURE_INBOX_VERSION,
        "capture_record_id": record_id,
        "capture": capture,
        "canonical_url": descriptor[
            "canonical_url"
        ],
        "platform": descriptor[
            "platform"
        ],
        "platform_surface": descriptor[
            "platform_surface"
        ],
        "observed_at": descriptor[
            "observed_at"
        ],
        "receive_count": int(
            row["receive_count"]
        ),
        "policy": {
            "record_is_untrusted": True,
            "integrity_rechecked_on_load": True,
            "load_is_read_only": True,
            "affects_live_merit": False,
        },
    }


def preview_and_maybe_store_browser_capture(
    *,
    raw_capture: Mapping[str, Any],
    short_video_threshold_seconds: float,
    connection_factory,
    env_getter=os.getenv,
    automation_enqueue=None,
    analysis_version: str = "",
    scoring_version: str = "",
) -> Dict[str, Any]:
    try:
        preview = (
            browser_ingestion
            .preview_browser_capture(
                raw_capture,
                short_video_threshold_seconds=(
                    short_video_threshold_seconds
                ),
            )
        )
    except (
        TypeError,
        ValueError,
    ) as error:
        raise BrowserCaptureInboxInputError(
            str(error)
        ) from error

    payload = dict(preview)
    payload.update({
        "capture_record_id": "",
        "capture_persisted": False,
        "capture_inbox_status": "disabled",
        "capture_inbox_version": (
            BROWSER_CAPTURE_INBOX_VERSION
        ),
    })

    if not inbox_enabled(
        env_getter=env_getter
    ):
        return payload

    capture_json = _capture_json(
        raw_capture
    )

    size_bytes = len(
        capture_json.encode("utf-8")
    )

    if size_bytes > inbox_max_bytes(
        env_getter=env_getter
    ):
        payload[
            "capture_inbox_status"
        ] = "oversize"
        return payload

    try:
        stored = store_browser_capture(
            raw_capture=raw_capture,
            connection_factory=(
                connection_factory
            ),
        )
    except (
        BrowserCaptureInboxPersistenceError,
        BrowserCaptureInboxIntegrityError,
    ):
        payload[
            "capture_inbox_status"
        ] = "unavailable"
        return payload

    payload[
        "capture_record_id"
    ] = stored[
        "capture_record_id"
    ]
    payload[
        "capture_persisted"
    ] = True
    payload[
        "capture_inbox_status"
    ] = stored[
        "status"
    ]

    if callable(automation_enqueue):
        try:
            automation_enqueue(
                capture_record_id=stored[
                    "capture_record_id"
                ],
                analysis_version=analysis_version,
                scoring_version=scoring_version,
                connection_factory=connection_factory,
                env_getter=env_getter,
            )
        except Exception:
            # Public acquisition stays fail-open. The persistent
            # worker reconciles any missed article inbox records.
            pass

    return payload


def execute_browser_capture_http(
    *,
    req,
    connection_factory,
    response_model,
    automation_enqueue=None,
    analysis_version: str = "",
    scoring_version: str = "",
    env_getter=os.getenv,
):
    try:
        payload = (
            preview_and_maybe_store_browser_capture(
                raw_capture=req.capture,
                short_video_threshold_seconds=(
                    req.short_video_threshold_seconds
                ),
                connection_factory=(
                    connection_factory
                ),
                env_getter=env_getter,
                automation_enqueue=(
                    automation_enqueue
                ),
                analysis_version=analysis_version,
                scoring_version=scoring_version,
            )
        )
    except BrowserCaptureInboxInputError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return response_model(
        **payload
    )
