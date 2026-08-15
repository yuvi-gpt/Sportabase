import hashlib
import json

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    Optional,
)


from app.analysis.adjudication import (
    CORRECTION_SCOPES,
)

from app.analysis.review_queue import (
    REVIEW_QUEUE_ITEM_VERSION,
    REVIEW_QUEUE_PACKET_VERSION,
    review_key_for_item,
)


REVIEW_QUEUE_PERSISTENCE_VERSION = (
    "review-queue-persistence-v1"
)

REVIEW_QUEUE_STATUSES = {
    "pending",
    "resolved",
    "dismissed",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _timestamp(
    value: Any,
    *,
    label: str,
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    candidate = text

    if candidate.endswith(
        "Z"
    ):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = (
            datetime.fromisoformat(
                candidate
            )
        )

    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed.isoformat()


def _review_row(
    row,
) -> Dict[str, Any]:
    result = dict(
        row
    )

    try:
        payload = json.loads(
            result.pop(
                "payload_json",
                "{}",
            )
            or "{}"
        )

    except Exception as exc:
        raise RuntimeError(
            "Persisted review payload "
            "is invalid JSON."
        ) from exc

    result[
        "payload"
    ] = payload

    return result


def _preflight(
    *,
    claim_id: str,
    evidence_id: str,
    connection_factory,
) -> None:
    conn = connection_factory()

    try:
        claim = conn.execute(
            """
            SELECT id
            FROM intelligence_claims
            WHERE id = ?
            """,
            (
                claim_id,
            ),
        ).fetchone()

        if claim is None:
            raise ValueError(
                "Review queue claim "
                "does not exist."
            )

        evidence = conn.execute(
            """
            SELECT id
            FROM evidence_records
            WHERE id = ?
            """,
            (
                evidence_id,
            ),
        ).fetchone()

        if evidence is None:
            raise ValueError(
                "Review queue evidence "
                "does not exist."
            )

        link = conn.execute(
            """
            SELECT id
            FROM claim_links
            WHERE claim_id = ?
              AND evidence_id = ?
            LIMIT 1
            """,
            (
                claim_id,
                evidence_id,
            ),
        ).fetchone()

        if link is None:
            raise ValueError(
                "Review queue evidence "
                "is not linked to the claim."
            )

    finally:
        conn.close()


def record_review_queue_item(
    *,
    item: Dict[
        str,
        Any,
    ],
    recorded_at: Optional[
        str
    ] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Review queue persistence "
            "requires database access."
        )

    if not isinstance(
        item,
        dict,
    ):
        raise ValueError(
            "Review queue item "
            "must be a dictionary."
        )

    if (
        _clean(
            item.get(
                "version"
            )
        )
        != REVIEW_QUEUE_ITEM_VERSION
    ):
        raise ValueError(
            "Unsupported review queue "
            "item version."
        )

    review_key = _clean(
        item.get(
            "review_key"
        )
    )

    claim_id = _clean(
        item.get(
            "claim_id"
        )
    )

    evidence_id = _clean(
        item.get(
            "evidence_id"
        )
    )

    field = _clean(
        item.get(
            "field"
        )
    ).lower()

    queue_reason = _clean(
        item.get(
            "queue_reason"
        )
    ).lower()

    automatic_tier = _clean(
        item.get(
            "automatic_tier"
        )
    ).lower()

    automatic_value = _clean(
        item.get(
            "automatic_value"
        )
    )

    adjudication_version = (
        _clean(
            item.get(
                "adjudication_version"
            )
        )
    )

    content_sha256 = (
        _clean(
            item.get(
                "content_sha256"
            )
        ).lower()
    )

    if not all(
        (
            review_key,
            claim_id,
            evidence_id,
            field,
            queue_reason,
            automatic_tier,
            adjudication_version,
            content_sha256,
        )
    ):
        raise ValueError(
            "Review queue item "
            "identity is incomplete."
        )

    expected_key = (
        review_key_for_item(
            claim_id=claim_id,
            evidence_id=evidence_id,
            field=field,
            adjudication_version=(
                adjudication_version
            ),
            content_sha256=(
                content_sha256
            ),
        )
    )

    if review_key != expected_key:
        raise ValueError(
            "Review queue item key "
            "does not match its content identity."
        )

    priority = item.get(
        "priority"
    )

    if isinstance(
        priority,
        bool,
    ):
        raise ValueError(
            "Review queue priority "
            "must be an integer."
        )

    try:
        priority = int(
            priority
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Review queue priority "
            "must be an integer."
        ) from exc

    if (
        priority < 0
        or priority > 1000
    ):
        raise ValueError(
            "Review queue priority "
            "must be between 0 and 1000."
        )

    _preflight(
        claim_id=claim_id,
        evidence_id=evidence_id,
        connection_factory=(
            connection_factory
        ),
    )

    created_at = _timestamp(
        (
            _clean(
                recorded_at
            )
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        label=(
            "Review queue recorded_at"
        ),
    )

    payload_json = json.dumps(
        item,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    review_id = hashlib.sha256(
        (
            "review-queue-item|"
            + review_key
        ).encode(
            "utf-8"
        )
    ).hexdigest()

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO review_queue_items (
              id,
              review_key,
              claim_id,
              evidence_id,
              field,
              queue_reason,
              priority,
              automatic_tier,
              automatic_value,
              adjudication_version,
              content_hash,
              status,
              payload_json,
              created_at,
              updated_at,
              reviewed_by,
              reviewed_at,
              resolution_value,
              resolution_reason,
              resolution_scope
            )
            VALUES (
              ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?,
              'pending',
              ?, ?, ?,
              '', NULL, '', '', ''
            )
            ON CONFLICT(review_key)
            DO NOTHING
            """,
            (
                review_id,
                review_key,
                claim_id,
                evidence_id,
                field,
                queue_reason,
                priority,
                automatic_tier,
                automatic_value,
                adjudication_version,
                content_sha256,
                payload_json,
                created_at,
                created_at,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM review_queue_items
            WHERE review_key = ?
            """,
            (
                review_key,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Review queue persistence failed."
        )

    if (
        str(
            row[
                "content_hash"
            ]
            or ""
        ).strip().lower()
        != content_sha256
        or str(
            row[
                "payload_json"
            ]
            or ""
        )
        != payload_json
    ):
        raise RuntimeError(
            "Review queue identity collision "
            "detected."
        )

    return {
        "review": (
            _review_row(
                row
            )
        ),
        "created": created,
        "policy": {
            "review_item_is_not_truth": True,
            "review_item_does_not_change_live_merit": True,
        },
    }


def persist_review_queue_packet(
    *,
    packet: Dict[
        str,
        Any,
    ],
    recorded_at: Optional[
        str
    ] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    if not isinstance(
        packet,
        dict,
    ):
        raise ValueError(
            "Review queue packet "
            "must be a dictionary."
        )

    if (
        _clean(
            packet.get(
                "version"
            )
        )
        != REVIEW_QUEUE_PACKET_VERSION
    ):
        raise ValueError(
            "Unsupported review queue "
            "packet version."
        )

    claim_id = _clean(
        packet.get(
            "claim_id"
        )
    )

    evidence_id = _clean(
        packet.get(
            "evidence_id"
        )
    )

    items = packet.get(
        "items",
        [],
    )

    if not isinstance(
        items,
        list,
    ):
        raise ValueError(
            "Review queue packet "
            "items must be a list."
        )

    results = []

    for item in items:
        if (
            not isinstance(
                item,
                dict,
            )
            or _clean(
                item.get(
                    "claim_id"
                )
            )
            != claim_id
            or _clean(
                item.get(
                    "evidence_id"
                )
            )
            != evidence_id
        ):
            raise ValueError(
                "Review queue packet/item "
                "lineage mismatch."
            )

        results.append(
            record_review_queue_item(
                item=item,
                recorded_at=(
                    recorded_at
                ),
                connection_factory=(
                    connection_factory
                ),
            )
        )

    return {
        "version": (
            REVIEW_QUEUE_PERSISTENCE_VERSION
        ),
        "claim_id": (
            claim_id
        ),
        "evidence_id": (
            evidence_id
        ),
        "results": results,
        "created_count": sum(
            1
            for result
            in results
            if result[
                "created"
            ]
        ),
        "policy": {
            "packet_persistence_is_replay_safe": True,
            "packet_persistence_is_multi_write_not_single_transaction": True,
            "review_persistence_does_not_apply_corrections": True,
            "review_persistence_does_not_change_live_merit": True,
        },
    }


def list_review_queue_items(
    *,
    status: str = "pending",
    claim_id: str = "",
    limit: int = 100,
    connection_factory=None,
):
    if connection_factory is None:
        raise ValueError(
            "Review queue listing "
            "requires database access."
        )

    normalized_status = (
        _clean(
            status
        ).lower()
    )

    if (
        normalized_status
        not in REVIEW_QUEUE_STATUSES
        and normalized_status
        != "all"
    ):
        raise ValueError(
            "Review queue status "
            "is unsupported."
        )

    if (
        isinstance(
            limit,
            bool,
        )
        or not isinstance(
            limit,
            int,
        )
        or limit < 1
        or limit > 500
    ):
        raise ValueError(
            "Review queue limit "
            "must be between 1 and 500."
        )

    normalized_claim_id = (
        _clean(
            claim_id
        )
    )

    clauses = []
    params = []

    if normalized_status != "all":
        clauses.append(
            "status = ?"
        )

        params.append(
            normalized_status
        )

    if normalized_claim_id:
        clauses.append(
            "claim_id = ?"
        )

        params.append(
            normalized_claim_id
        )

    where_sql = ""

    if clauses:
        where_sql = (
            "WHERE "
            + " AND ".join(
                clauses
            )
        )

    params.append(
        limit
    )

    conn = connection_factory()

    try:
        rows = conn.execute(
            f"""
            SELECT *
            FROM review_queue_items
            {where_sql}
            ORDER BY
              priority DESC,
              created_at ASC,
              id ASC
            LIMIT ?
            """,
            tuple(
                params
            ),
        ).fetchall()

    finally:
        conn.close()

    return [
        _review_row(
            row
        )
        for row
        in rows
    ]


def resolve_review_queue_item(
    *,
    review_id: str,
    value: str,
    reason: str,
    corrected_by: str,
    corrected_at: str,
    scope: str = "case_only",
    connection_factory=None,
) -> Dict[str, Any]:
    if connection_factory is None:
        raise ValueError(
            "Review resolution "
            "requires database access."
        )

    normalized_review_id = (
        _clean(
            review_id
        )
    )

    normalized_value = _clean(
        value
    )

    normalized_reason = _clean(
        reason
    )

    normalized_corrected_by = (
        _clean(
            corrected_by
        )
    )

    normalized_scope = (
        _clean(
            scope
        ).lower()
    )

    normalized_corrected_at = (
        _timestamp(
            corrected_at,
            label=(
                "Review correction "
                "corrected_at"
            ),
        )
    )

    if not normalized_review_id:
        raise ValueError(
            "Review item ID is required."
        )

    if not normalized_value:
        raise ValueError(
            "Review correction value "
            "is required."
        )

    if not normalized_reason:
        raise ValueError(
            "Review correction reason "
            "is required."
        )

    if not normalized_corrected_by:
        raise ValueError(
            "Review correction actor "
            "is required."
        )

    if (
        normalized_scope
        not in CORRECTION_SCOPES
    ):
        raise ValueError(
            "Review correction scope "
            "is unsupported."
        )

    correction = {
        "value": (
            normalized_value
        ),
        "reason": (
            normalized_reason
        ),
        "corrected_by": (
            normalized_corrected_by
        ),
        "corrected_at": (
            normalized_corrected_at
        ),
        "scope": (
            normalized_scope
        ),
    }

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM review_queue_items
            WHERE id = ?
            """,
            (
                normalized_review_id,
            ),
        ).fetchone()

        if row is None:
            raise ValueError(
                "Review queue item "
                "does not exist."
            )

        status = _clean(
            row[
                "status"
            ]
        ).lower()

        changed = False

        if status == "pending":
            conn.execute(
                """
                UPDATE review_queue_items
                SET
                  status = 'resolved',
                  updated_at = ?,
                  reviewed_by = ?,
                  reviewed_at = ?,
                  resolution_value = ?,
                  resolution_reason = ?,
                  resolution_scope = ?
                WHERE id = ?
                  AND status = 'pending'
                """,
                (
                    normalized_corrected_at,
                    normalized_corrected_by,
                    normalized_corrected_at,
                    normalized_value,
                    normalized_reason,
                    normalized_scope,
                    normalized_review_id,
                ),
            )

            changed = True

        elif status == "resolved":
            existing = {
                "value": _clean(
                    row[
                        "resolution_value"
                    ]
                ),
                "reason": _clean(
                    row[
                        "resolution_reason"
                    ]
                ),
                "corrected_by": _clean(
                    row[
                        "reviewed_by"
                    ]
                ),
                "corrected_at": _clean(
                    row[
                        "reviewed_at"
                    ]
                ),
                "scope": _clean(
                    row[
                        "resolution_scope"
                    ]
                ).lower(),
            }

            if existing != correction:
                raise ValueError(
                    "Review queue item is "
                    "already resolved with "
                    "a different correction."
                )

        else:
            raise ValueError(
                "Dismissed review queue item "
                "cannot be resolved."
            )

        row = conn.execute(
            """
            SELECT *
            FROM review_queue_items
            WHERE id = ?
            """,
            (
                normalized_review_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Review queue resolution failed."
        )

    return {
        "review": (
            _review_row(
                row
            )
        ),
        "correction": (
            correction
        ),
        "changed": (
            changed
        ),
        "policy": {
            "automatic_history_is_preserved": True,
            "human_resolution_outputs_adjudication_correction": True,
            "resolution_does_not_verify_evidence_by_itself": True,
            "resolution_does_not_change_claim_links_by_itself": True,
            "resolution_does_not_retrain_by_itself": True,
            "resolution_does_not_change_live_merit": True,
        },
    }
