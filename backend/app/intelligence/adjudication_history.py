import json

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


from app.analysis.adjudication_state import (
    AUTOMATED_ADJUDICATION_STATE_VERSION,
    build_adjudication_state_revision,
)

from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)


AUTOMATED_ADJUDICATION_HISTORY_VERSION = (
    "automated-adjudication-history-v1"
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
                "Adjudication recorded_at"
            ),
        )

    return datetime.now(
        timezone.utc
    ).isoformat()


def _decode_revision(
    value: Any,
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
            "Stored adjudication revision "
            "contains invalid JSON."
        ) from exc

    if not isinstance(
        parsed,
        dict,
    ):
        raise RuntimeError(
            "Stored adjudication revision "
            "must be a JSON object."
        )

    return parsed


def _latest_row(
    conn,
    claim_id: str,
):
    rows = conn.execute(
        """
        SELECT revision.*
        FROM adjudication_state_revisions revision
        WHERE
          revision.claim_id = ?
          AND NOT EXISTS (
            SELECT 1
            FROM adjudication_state_revisions child
            WHERE
              child.previous_revision_id
              = revision.id
          )
        ORDER BY
          revision.recorded_at DESC,
          revision.id DESC
        LIMIT 2
        """,
        (
            claim_id,
        ),
    ).fetchall()

    if len(
        rows
    ) > 1:
        raise RuntimeError(
            "Adjudication history contains "
            "multiple active leaves."
        )

    return (
        rows[0]
        if rows
        else None
    )


def load_latest_adjudication_state_revision(
    *,
    claim_id: str,
    connection_factory,
) -> Optional[
    Dict[str, Any]
]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Adjudication history claim ID "
            "is required."
        )

    conn = connection_factory()

    try:
        row = _latest_row(
            conn,
            normalized_claim_id,
        )

    finally:
        conn.close()

    if row is None:
        return None

    return _decode_revision(
        row[
            "revision_json"
        ]
    )


def _validate_trigger_evidence(
    *,
    conn,
    claim_id: str,
    evidence_ids: List[str],
) -> None:
    for evidence_id in evidence_ids:
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
                "Adjudication trigger evidence "
                "does not exist."
            )

        link = conn.execute(
            """
            SELECT id
            FROM claim_links
            WHERE
              claim_id = ?
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
                "Adjudication trigger evidence "
                "is not linked to the claim."
            )


def persist_adjudication_state_revision(
    *,
    revision: Dict[str, Any],
    recorded_at: Optional[str] = None,
    connection_factory,
) -> Dict[str, Any]:
    if not isinstance(
        revision,
        dict,
    ):
        raise ValueError(
            "Adjudication revision must "
            "be a dictionary."
        )

    if (
        _clean(
            revision.get(
                "version"
            )
        )
        != (
            AUTOMATED_ADJUDICATION_STATE_VERSION
        )
    ):
        raise ValueError(
            "Unsupported adjudication "
            "state revision version."
        )

    revision_id = _clean(
        revision.get(
            "revision_id"
        )
    )

    claim_id = _clean(
        revision.get(
            "claim_id"
        )
    )

    previous_revision_id = _clean(
        revision.get(
            "previous_revision_id"
        )
    )

    if not revision_id:
        raise ValueError(
            "Adjudication revision ID "
            "is required."
        )

    if not claim_id:
        raise ValueError(
            "Adjudication revision claim ID "
            "is required."
        )

    trigger = revision.get(
        "trigger"
    )

    if not isinstance(
        trigger,
        dict,
    ):
        raise ValueError(
            "Adjudication revision trigger "
            "is required."
        )

    trigger_type = (
        _clean(
            trigger.get(
                "type"
            )
        ).lower()
    )

    evidence_ids = trigger.get(
        "evidence_ids",
        [],
    )

    if not isinstance(
        evidence_ids,
        list,
    ):
        raise ValueError(
            "Adjudication trigger evidence IDs "
            "must be a list."
        )

    evidence_ids = sorted(
        {
            _clean(
                value
            )
            for value
            in evidence_ids
            if _clean(
                value
            )
        }
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
                "Adjudication claim "
                "does not exist."
            )

        _validate_trigger_evidence(
            conn=conn,
            claim_id=claim_id,
            evidence_ids=(
                evidence_ids
            ),
        )

        existing = conn.execute(
            """
            SELECT *
            FROM adjudication_state_revisions
            WHERE id = ?
            """,
            (
                revision_id,
            ),
        ).fetchone()

        if existing is not None:
            stored = _decode_revision(
                existing[
                    "revision_json"
                ]
            )

            if (
                _canonical_json(
                    stored
                )
                != _canonical_json(
                    revision
                )
            ):
                raise ValueError(
                    "Adjudication revision ID "
                    "collision detected."
                )

            stored_transition_ids = sorted(
                row[
                    "id"
                ]
                for row
                in conn.execute(
                    """
                    SELECT id
                    FROM adjudication_state_transitions
                    WHERE revision_id = ?
                    """,
                    (
                        revision_id,
                    ),
                ).fetchall()
            )

            expected_transition_ids = sorted(
                _clean(
                    row.get(
                        "id"
                    )
                )
                for row
                in revision.get(
                    "transitions",
                    [],
                )
            )

            if (
                stored_transition_ids
                != expected_transition_ids
            ):
                raise RuntimeError(
                    "Stored adjudication transitions "
                    "do not match the revision."
                )

            conn.commit()

            return {
                "version": (
                    AUTOMATED_ADJUDICATION_HISTORY_VERSION
                ),
                "status": "replayed",
                "created": False,
                "revision": stored,
                "transition_count": len(
                    stored_transition_ids
                ),
            }

        previous_revision = None

        if previous_revision_id:
            previous = conn.execute(
                """
                SELECT *
                FROM adjudication_state_revisions
                WHERE id = ?
                """,
                (
                    previous_revision_id,
                ),
            ).fetchone()

            if previous is None:
                raise ValueError(
                    "Previous adjudication revision "
                    "does not exist."
                )

            if (
                _clean(
                    previous[
                        "claim_id"
                    ]
                )
                != claim_id
            ):
                raise ValueError(
                    "Previous adjudication revision "
                    "belongs to a different claim."
                )

            previous_revision = (
                _decode_revision(
                    previous[
                        "revision_json"
                    ]
                )
            )

        latest = _latest_row(
            conn,
            claim_id,
        )

        if latest is None:
            if previous_revision_id:
                raise ValueError(
                    "Initial adjudication revision "
                    "cannot specify a previous revision."
                )

        else:
            latest_id = _clean(
                latest[
                    "id"
                ]
            )

            if not previous_revision_id:
                raise ValueError(
                    "Existing adjudication history "
                    "requires a previous revision."
                )

            if (
                previous_revision_id
                != latest_id
            ):
                raise ValueError(
                    "Previous adjudication revision "
                    "is not the latest claim revision."
                )

        rebuilt = (
            build_adjudication_state_revision(
                adjudication=(
                    revision.get(
                        "adjudication"
                    )
                ),
                as_of=(
                    revision.get(
                        "as_of"
                    )
                ),
                trigger_type=(
                    trigger_type
                ),
                trigger_evidence_ids=(
                    evidence_ids
                ),
                previous_revision=(
                    previous_revision
                ),
            )
        )

        if (
            _canonical_json(
                rebuilt
            )
            != _canonical_json(
                revision
            )
        ):
            raise ValueError(
                "Adjudication revision failed "
                "deterministic reconstruction."
            )

        conn.execute(
            """
            INSERT INTO adjudication_state_revisions (
              id,
              claim_id,
              state_version,
              adjudication_version,
              adjudication_sha256,
              as_of,
              previous_revision_id,
              trigger_type,
              trigger_evidence_ids_json,
              revision_json,
              recorded_at
            )
            VALUES (
              ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?
            )
            """,
            (
                revision_id,
                claim_id,
                _clean(
                    revision[
                        "version"
                    ]
                ),
                _clean(
                    revision[
                        "adjudication_version"
                    ]
                ),
                _clean(
                    revision[
                        "adjudication_sha256"
                    ]
                ),
                _clean(
                    revision[
                        "as_of"
                    ]
                ),
                (
                    previous_revision_id
                    or None
                ),
                trigger_type,
                _canonical_json(
                    evidence_ids
                ),
                _canonical_json(
                    revision
                ),
                normalized_recorded_at,
            ),
        )

        transitions = revision.get(
            "transitions",
            [],
        )

        if not isinstance(
            transitions,
            list,
        ):
            raise ValueError(
                "Adjudication transitions "
                "must be a list."
            )

        for transition in transitions:
            if not isinstance(
                transition,
                dict,
            ):
                raise ValueError(
                    "Adjudication transition "
                    "must be a dictionary."
                )

            conn.execute(
                """
                INSERT INTO adjudication_state_transitions (
                  id,
                  revision_id,
                  claim_id,
                  field,
                  kind,
                  from_state_json,
                  to_state_json,
                  recorded_at
                )
                VALUES (
                  ?, ?, ?, ?, ?,
                  ?, ?, ?
                )
                """,
                (
                    _clean(
                        transition[
                            "id"
                        ]
                    ),
                    revision_id,
                    claim_id,
                    _clean(
                        transition[
                            "field"
                        ]
                    ),
                    _clean(
                        transition[
                            "kind"
                        ]
                    ),
                    (
                        None
                        if (
                            transition.get(
                                "from_state"
                            )
                            is None
                        )
                        else _canonical_json(
                            transition[
                                "from_state"
                            ]
                        )
                    ),
                    _canonical_json(
                        transition[
                            "to_state"
                        ]
                    ),
                    normalized_recorded_at,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return {
        "version": (
            AUTOMATED_ADJUDICATION_HISTORY_VERSION
        ),
        "status": "persisted",
        "created": True,
        "revision": revision,
        "transition_count": len(
            transitions
        ),
    }


def re_adjudicate_claim(
    *,
    claim_id: str,
    evaluator_runs: List[
        Dict[str, Any]
    ],
    as_of: str,
    trigger_type: str,
    trigger_evidence_ids: Any = None,
    recorded_at: Optional[str] = None,
    connection_factory,
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Re-adjudication claim ID "
            "is required."
        )

    normalized_as_of = _timestamp(
        as_of,
        label=(
            "Re-adjudication as_of"
        ),
    )

    normalized_trigger_type = (
        _clean(
            trigger_type
        ).lower()
    )

    if trigger_evidence_ids is None:
        trigger_evidence_ids = []

    if not isinstance(
        trigger_evidence_ids,
        list,
    ):
        raise ValueError(
            "Re-adjudication trigger evidence "
            "IDs must be a list."
        )

    normalized_evidence_ids = sorted(
        {
            _clean(
                value
            )
            for value
            in trigger_evidence_ids
            if _clean(
                value
            )
        }
    )

    adjudication = (
        build_multi_evaluator_adjudication(
            claim_id=(
                normalized_claim_id
            ),
            evaluator_runs=(
                evaluator_runs
            ),
        )
    )

    latest = (
        load_latest_adjudication_state_revision(
            claim_id=(
                normalized_claim_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    )

    trigger = {
        "type": (
            normalized_trigger_type
        ),
        "evidence_ids": (
            normalized_evidence_ids
        ),
    }

    if (
        latest is not None
        and latest.get(
            "as_of"
        )
        == normalized_as_of
        and latest.get(
            "trigger"
        )
        == trigger
        and _canonical_json(
            latest.get(
                "adjudication"
            )
        )
        == _canonical_json(
            adjudication
        )
    ):
        persistence = (
            persist_adjudication_state_revision(
                revision=latest,
                recorded_at=recorded_at,
                connection_factory=(
                    connection_factory
                ),
            )
        )

        return {
            "version": (
                AUTOMATED_ADJUDICATION_HISTORY_VERSION
            ),
            "status": "replayed",
            "adjudication": (
                adjudication
            ),
            "revision": latest,
            "persistence": (
                persistence
            ),
            "policy": {
                "fully_automatic": True,
                "human_review_required": False,
                "manual_corrections_used": False,
                "does_not_verify_evidence": True,
                "does_not_train_model": True,
                "does_not_change_live_merit": True,
            },
        }

    revision = (
        build_adjudication_state_revision(
            adjudication=(
                adjudication
            ),
            as_of=(
                normalized_as_of
            ),
            trigger_type=(
                normalized_trigger_type
            ),
            trigger_evidence_ids=(
                normalized_evidence_ids
            ),
            previous_revision=(
                latest
            ),
        )
    )

    persistence = (
        persist_adjudication_state_revision(
            revision=revision,
            recorded_at=recorded_at,
            connection_factory=(
                connection_factory
            ),
        )
    )

    return {
        "version": (
            AUTOMATED_ADJUDICATION_HISTORY_VERSION
        ),
        "status": (
            persistence[
                "status"
            ]
        ),
        "adjudication": (
            adjudication
        ),
        "revision": revision,
        "persistence": (
            persistence
        ),
        "policy": {
            "fully_automatic": True,
            "human_review_required": False,
            "manual_corrections_used": False,
            "append_only_history": True,
            "linear_revision_chain": True,
            "trigger_evidence_must_link_to_claim": True,
            "does_not_verify_evidence": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
        },
    }
