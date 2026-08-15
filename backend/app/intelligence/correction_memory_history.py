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


from app.analysis.correction_memory import (
    AUTOMATIC_CORRECTION_EVENT_VERSION,
    AUTOMATIC_MEMORY_CANDIDATE_VERSION,
    PATTERN_MINIMUM_DISTINCT_CLAIMS,
    build_automatic_correction_memory,
)


AUTOMATIC_CORRECTION_MEMORY_HISTORY_VERSION = (
    "automatic-correction-memory-history-v1"
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
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )


def _decode_object(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    try:
        parsed = json.loads(
            str(
                value or ""
            )
        )

    except Exception as exc:
        raise RuntimeError(
            f"{label} contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise RuntimeError(
            f"{label} must be a JSON object."
        )

    return parsed


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
        parsed = datetime.fromisoformat(
            candidate
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


def _recorded_at(
    value: Any,
) -> str:
    text = _clean(
        value
    )

    if text:
        return _timestamp(
            text,
            label=(
                "Correction memory recorded_at"
            ),
        )

    return datetime.now(
        timezone.utc
    ).isoformat()


def _revision_row(
    conn,
    revision_id: str,
    *,
    label: str,
):
    row = conn.execute(
        """
        SELECT *
        FROM adjudication_state_revisions
        WHERE id = ?
        """,
        (
            revision_id,
        ),
    ).fetchone()

    if row is None:
        raise ValueError(
            f"{label} must be persisted before "
            "correction memory is extracted."
        )

    return row


def _validate_persisted_pair(
    *,
    conn,
    previous_revision: Dict[
        str,
        Any,
    ],
    current_revision: Dict[
        str,
        Any,
    ],
) -> None:
    previous_id = _clean(
        previous_revision.get(
            "revision_id"
        )
    )

    current_id = _clean(
        current_revision.get(
            "revision_id"
        )
    )

    if not previous_id or not current_id:
        raise ValueError(
            "Correction memory revision IDs "
            "are required."
        )

    previous_row = _revision_row(
        conn,
        previous_id,
        label=(
            "Previous adjudication revision"
        ),
    )

    current_row = _revision_row(
        conn,
        current_id,
        label=(
            "Current adjudication revision"
        ),
    )

    stored_previous = _decode_object(
        previous_row[
            "revision_json"
        ],
        label=(
            "Stored previous adjudication revision"
        ),
    )

    stored_current = _decode_object(
        current_row[
            "revision_json"
        ],
        label=(
            "Stored current adjudication revision"
        ),
    )

    if (
        _canonical_json(
            stored_previous
        )
        != _canonical_json(
            previous_revision
        )
    ):
        raise ValueError(
            "Previous adjudication revision "
            "does not match persisted history."
        )

    if (
        _canonical_json(
            stored_current
        )
        != _canonical_json(
            current_revision
        )
    ):
        raise ValueError(
            "Current adjudication revision "
            "does not match persisted history."
        )

    previous_claim = _clean(
        previous_row[
            "claim_id"
        ]
    )

    current_claim = _clean(
        current_row[
            "claim_id"
        ]
    )

    if previous_claim != current_claim:
        raise ValueError(
            "Correction memory revisions "
            "belong to different claims."
        )

    if (
        _clean(
            current_row[
                "previous_revision_id"
            ]
        )
        != previous_id
    ):
        raise ValueError(
            "Correction memory revisions "
            "are not directly consecutive."
        )


def _load_prior_events(
    conn,
):
    rows = conn.execute(
        """
        SELECT event_json
        FROM automatic_correction_events
        ORDER BY id
        """
    ).fetchall()

    return [
        _decode_object(
            row[
                "event_json"
            ],
            label=(
                "Stored automatic correction event"
            ),
        )
        for row in rows
    ]


def _validate_event(
    event: Dict[
        str,
        Any,
    ],
) -> None:
    if not isinstance(
        event,
        dict,
    ):
        raise ValueError(
            "Automatic correction event "
            "must be a dictionary."
        )

    if (
        _clean(
            event.get(
                "version"
            )
        )
        != (
            AUTOMATIC_CORRECTION_EVENT_VERSION
        )
    ):
        raise ValueError(
            "Automatic correction event "
            "version is unsupported."
        )

    required = (
        "id",
        "claim_id",
        "field",
        "signature",
        "previous_revision_id",
        "current_revision_id",
    )

    if not all(
        _clean(
            event.get(
                key
            )
        )
        for key
        in required
    ):
        raise ValueError(
            "Automatic correction event "
            "identity is incomplete."
        )

    if not bool(
        event.get(
            "learning_signal_candidate",
            False,
        )
    ):
        raise ValueError(
            "Automatic correction event "
            "is not a learning-signal candidate."
        )


def _persist_event(
    *,
    conn,
    event: Dict[
        str,
        Any,
    ],
    recorded_at: str,
) -> bool:
    _validate_event(
        event
    )

    event_id = _clean(
        event[
            "id"
        ]
    )

    current_revision_id = _clean(
        event[
            "current_revision_id"
        ]
    )

    field = _clean(
        event[
            "field"
        ]
    )

    existing = conn.execute(
        """
        SELECT *
        FROM automatic_correction_events
        WHERE id = ?
        """,
        (
            event_id,
        ),
    ).fetchone()

    if existing is not None:
        stored = _decode_object(
            existing[
                "event_json"
            ],
            label=(
                "Stored automatic correction event"
            ),
        )

        if (
            _canonical_json(
                stored
            )
            != _canonical_json(
                event
            )
        ):
            raise ValueError(
                "Automatic correction event "
                "ID collision detected."
            )

        return False

    conflicting = conn.execute(
        """
        SELECT id
        FROM automatic_correction_events
        WHERE
          current_revision_id = ?
          AND field = ?
        LIMIT 1
        """,
        (
            current_revision_id,
            field,
        ),
    ).fetchone()

    if conflicting is not None:
        raise ValueError(
            "Automatic correction event "
            "conflicts with an existing "
            "revision-field event."
        )

    conn.execute(
        """
        INSERT INTO automatic_correction_events (
          id,
          claim_id,
          field,
          signature,
          previous_revision_id,
          current_revision_id,
          event_version,
          event_json,
          recorded_at
        )
        VALUES (
          ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            event_id,
            _clean(
                event[
                    "claim_id"
                ]
            ),
            field,
            _clean(
                event[
                    "signature"
                ]
            ),
            _clean(
                event[
                    "previous_revision_id"
                ]
            ),
            current_revision_id,
            _clean(
                event[
                    "version"
                ]
            ),
            _canonical_json(
                event
            ),
            recorded_at,
        ),
    )

    return True


def _validate_candidate(
    candidate: Dict[
        str,
        Any,
    ],
) -> None:
    if not isinstance(
        candidate,
        dict,
    ):
        raise ValueError(
            "Automatic memory candidate "
            "must be a dictionary."
        )

    if (
        _clean(
            candidate.get(
                "version"
            )
        )
        != (
            AUTOMATIC_MEMORY_CANDIDATE_VERSION
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "version is unsupported."
        )

    candidate_id = _clean(
        candidate.get(
            "id"
        )
    )

    signature = _clean(
        candidate.get(
            "signature"
        )
    )

    field = _clean(
        candidate.get(
            "field"
        )
    )

    if not all(
        (
            candidate_id,
            signature,
            field,
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "identity is incomplete."
        )

    claims = candidate.get(
        "supporting_claim_ids"
    )

    corrections = candidate.get(
        "supporting_correction_ids"
    )

    if (
        not isinstance(
            claims,
            list,
        )
        or not isinstance(
            corrections,
            list,
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "support must be lists."
        )

    normalized_claims = sorted(
        {
            _clean(
                value
            )
            for value
            in claims
            if _clean(
                value
            )
        }
    )

    if (
        int(
            candidate.get(
                "support_count",
                0,
            )
        )
        != len(
            normalized_claims
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "support count is inconsistent."
        )

    expected_status = (
        "pattern_candidate"
        if (
            len(
                normalized_claims
            )
            >= (
                PATTERN_MINIMUM_DISTINCT_CLAIMS
            )
        )
        else "case_memory"
    )

    if (
        _clean(
            candidate.get(
                "status"
            )
        )
        != expected_status
    ):
        raise ValueError(
            "Automatic memory candidate "
            "status is inconsistent."
        )

    if bool(
        candidate.get(
            "eligible_for_automatic_global_rule",
            False,
        )
    ):
        raise ValueError(
            "Automatic global rule promotion "
            "is forbidden."
        )


def _json_list(
    text: Any,
    *,
    label: str,
):
    try:
        value = json.loads(
            str(
                text or "[]"
            )
        )

    except Exception as exc:
        raise RuntimeError(
            f"{label} contains invalid JSON."
        ) from exc

    if not isinstance(
        value,
        list,
    ):
        raise RuntimeError(
            f"{label} must be a JSON list."
        )

    return value


def _persist_candidate(
    *,
    conn,
    candidate: Dict[
        str,
        Any,
    ],
    recorded_at: str,
) -> str:
    _validate_candidate(
        candidate
    )

    candidate_id = _clean(
        candidate[
            "id"
        ]
    )

    signature = _clean(
        candidate[
            "signature"
        ]
    )

    field = _clean(
        candidate[
            "field"
        ]
    )

    new_claims = sorted(
        {
            _clean(
                value
            )
            for value
            in candidate[
                "supporting_claim_ids"
            ]
            if _clean(
                value
            )
        }
    )

    new_corrections = sorted(
        {
            _clean(
                value
            )
            for value
            in candidate[
                "supporting_correction_ids"
            ]
            if _clean(
                value
            )
        }
    )

    existing = conn.execute(
        """
        SELECT *
        FROM automatic_memory_candidates
        WHERE id = ?
        """,
        (
            candidate_id,
        ),
    ).fetchone()

    if existing is None:
        signature_collision = conn.execute(
            """
            SELECT id
            FROM automatic_memory_candidates
            WHERE signature = ?
            """,
            (
                signature,
            ),
        ).fetchone()

        if signature_collision is not None:
            raise ValueError(
                "Automatic memory candidate "
                "signature collision detected."
            )

        conn.execute(
            """
            INSERT INTO automatic_memory_candidates (
              id,
              signature,
              field,
              candidate_version,
              status,
              support_count,
              supporting_claim_ids_json,
              supporting_correction_ids_json,
              candidate_json,
              first_seen_at,
              last_seen_at
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                candidate_id,
                signature,
                field,
                _clean(
                    candidate[
                        "version"
                    ]
                ),
                _clean(
                    candidate[
                        "status"
                    ]
                ),
                int(
                    candidate[
                        "support_count"
                    ]
                ),
                _canonical_json(
                    new_claims
                ),
                _canonical_json(
                    new_corrections
                ),
                _canonical_json(
                    candidate
                ),
                recorded_at,
                recorded_at,
            ),
        )

        return "created"

    if (
        _clean(
            existing[
                "signature"
            ]
        )
        != signature
        or (
            _clean(
                existing[
                    "field"
                ]
            )
            != field
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "identity collision detected."
        )

    old_claims = set(
        _json_list(
            existing[
                "supporting_claim_ids_json"
            ],
            label=(
                "Stored memory candidate claims"
            ),
        )
    )

    old_corrections = set(
        _json_list(
            existing[
                "supporting_correction_ids_json"
            ],
            label=(
                "Stored memory candidate corrections"
            ),
        )
    )

    if not old_claims.issubset(
        set(
            new_claims
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "claim support cannot shrink."
        )

    if not old_corrections.issubset(
        set(
            new_corrections
        )
    ):
        raise ValueError(
            "Automatic memory candidate "
            "correction support cannot shrink."
        )

    stored_candidate = _decode_object(
        existing[
            "candidate_json"
        ],
        label=(
            "Stored automatic memory candidate"
        ),
    )

    if (
        _canonical_json(
            stored_candidate
        )
        == _canonical_json(
            candidate
        )
    ):
        return "unchanged"

    conn.execute(
        """
        UPDATE automatic_memory_candidates
        SET
          status = ?,
          support_count = ?,
          supporting_claim_ids_json = ?,
          supporting_correction_ids_json = ?,
          candidate_json = ?,
          last_seen_at = ?
        WHERE id = ?
        """,
        (
            _clean(
                candidate[
                    "status"
                ]
            ),
            int(
                candidate[
                    "support_count"
                ]
            ),
            _canonical_json(
                new_claims
            ),
            _canonical_json(
                new_corrections
            ),
            _canonical_json(
                candidate
            ),
            recorded_at,
            candidate_id,
        ),
    )

    return "updated"


def process_automatic_correction_memory(
    *,
    previous_revision: Dict[
        str,
        Any,
    ],
    current_revision: Dict[
        str,
        Any,
    ],
    recorded_at: Optional[str] = None,
    connection_factory,
) -> Dict[str, Any]:
    if not isinstance(
        previous_revision,
        dict,
    ) or not isinstance(
        current_revision,
        dict,
    ):
        raise ValueError(
            "Correction memory requires "
            "revision dictionaries."
        )

    normalized_recorded_at = (
        _recorded_at(
            recorded_at
        )
    )

    conn = connection_factory()

    try:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        _validate_persisted_pair(
            conn=conn,
            previous_revision=(
                previous_revision
            ),
            current_revision=(
                current_revision
            ),
        )

        prior_events = (
            _load_prior_events(
                conn
            )
        )

        memory = (
            build_automatic_correction_memory(
                previous_revision=(
                    previous_revision
                ),
                current_revision=(
                    current_revision
                ),
                prior_correction_events=(
                    prior_events
                ),
            )
        )

        created_events = 0

        for event in memory[
            "corrections"
        ]:
            if _persist_event(
                conn=conn,
                event=event,
                recorded_at=(
                    normalized_recorded_at
                ),
            ):
                created_events += 1

        candidate_changes = {
            "created": 0,
            "updated": 0,
            "unchanged": 0,
        }

        for candidate in memory[
            "memory_candidates"
        ]:
            status = (
                _persist_candidate(
                    conn=conn,
                    candidate=candidate,
                    recorded_at=(
                        normalized_recorded_at
                    ),
                )
            )

            candidate_changes[
                status
            ] += 1

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    if not memory[
        "corrections"
    ]:
        status = "no_correction"

    elif (
        created_events == 0
        and candidate_changes[
            "created"
        ] == 0
        and candidate_changes[
            "updated"
        ] == 0
    ):
        status = "replayed"

    else:
        status = "persisted"

    return {
        "version": (
            AUTOMATIC_CORRECTION_MEMORY_HISTORY_VERSION
        ),
        "status": status,
        "claim_id": (
            memory[
                "claim_id"
            ]
        ),
        "created_event_count": (
            created_events
        ),
        "candidate_changes": (
            candidate_changes
        ),
        "memory": memory,
        "policy": {
            "correction_events_are_append_only": True,
            "candidate_support_is_monotonic": True,
            "candidate_aggregation_is_automatic": True,
            "distinct_claim_support_required_for_pattern": True,
            "pattern_candidate_is_not_active_rule": True,
            "automatic_global_rule_promotion_forbidden": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
            "human_review_required": False,
        },
    }


def load_automatic_memory_candidate(
    *,
    candidate_id: str,
    connection_factory,
) -> Optional[
    Dict[str, Any]
]:
    normalized_id = _clean(
        candidate_id
    )

    if not normalized_id:
        raise ValueError(
            "Automatic memory candidate ID "
            "is required."
        )

    conn = connection_factory()

    try:
        row = conn.execute(
            """
            SELECT candidate_json
            FROM automatic_memory_candidates
            WHERE id = ?
            """,
            (
                normalized_id,
            ),
        ).fetchone()

    finally:
        conn.close()

    if row is None:
        return None

    return _decode_object(
        row[
            "candidate_json"
        ],
        label=(
            "Stored automatic memory candidate"
        ),
    )
