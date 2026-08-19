import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _observation_dependency_identity(
    *,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    downstream_source_observation_id:
        Optional[str] = None,
    downstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_observation_id:
        Optional[str] = None,
    upstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_id: Optional[str] = None,
    upstream_reporter_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_relationship_type = str(
        relationship_type or ""
    ).strip().lower()

    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    if not normalized_relationship_type:
        raise ValueError(
            "Observation dependency relationship "
            "type is required."
        )

    if not normalized_observed_at:
        raise ValueError(
            "Observation dependency observed "
            "time is required."
        )

    downstream_targets = {
        "source_observation": (
            str(
                downstream_source_observation_id
                or ""
            ).strip()
            or None
        ),
        "reporter_observation": (
            str(
                downstream_reporter_observation_id
                or ""
            ).strip()
            or None
        ),
    }

    active_downstream = [
        (
            target_type,
            target_id,
        )
        for (
            target_type,
            target_id,
        ) in downstream_targets.items()
        if target_id is not None
    ]

    if len(active_downstream) != 1:
        raise ValueError(
            "Observation dependency requires "
            "exactly one downstream observation."
        )

    upstream_targets = {
        "source_observation": (
            str(
                upstream_source_observation_id
                or ""
            ).strip()
            or None
        ),
        "reporter_observation": (
            str(
                upstream_reporter_observation_id
                or ""
            ).strip()
            or None
        ),
        "source": (
            str(
                upstream_source_id or ""
            ).strip()
            or None
        ),
        "reporter": (
            str(
                upstream_reporter_id or ""
            ).strip()
            or None
        ),
    }

    active_upstream = [
        (
            target_type,
            target_id,
        )
        for (
            target_type,
            target_id,
        ) in upstream_targets.items()
        if target_id is not None
    ]

    if len(active_upstream) != 1:
        raise ValueError(
            "Observation dependency requires "
            "exactly one upstream target."
        )

    normalized_confidence = None

    if confidence is not None:
        try:
            normalized_confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Observation dependency confidence "
                "must be numeric."
            ) from exc

        if not (
            0.0
            <= normalized_confidence
            <= 1.0
        ):
            raise ValueError(
                "Observation dependency confidence "
                "must be between 0 and 1."
            )

    (
        downstream_type,
        downstream_id,
    ) = active_downstream[0]

    (
        upstream_type,
        upstream_id,
    ) = active_upstream[0]

    return {
        "downstream_type": downstream_type,
        "downstream_id": downstream_id,
        "upstream_type": upstream_type,
        "upstream_id": upstream_id,
        "relationship_type": (
            normalized_relationship_type
        ),
        "confidence": normalized_confidence,
        "observed_at": normalized_observed_at,
    }


def observation_dependency_id_for_record(
    *,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    downstream_source_observation_id:
        Optional[str] = None,
    downstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_observation_id:
        Optional[str] = None,
    upstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_id: Optional[str] = None,
    upstream_reporter_id: Optional[str] = None,
) -> str:
    identity = (
        _observation_dependency_identity(
            relationship_type=relationship_type,
            observed_at=observed_at,
            confidence=confidence,
            downstream_source_observation_id=(
                downstream_source_observation_id
            ),
            downstream_reporter_observation_id=(
                downstream_reporter_observation_id
            ),
            upstream_source_observation_id=(
                upstream_source_observation_id
            ),
            upstream_reporter_observation_id=(
                upstream_reporter_observation_id
            ),
            upstream_source_id=upstream_source_id,
            upstream_reporter_id=(
                upstream_reporter_id
            ),
        )
    )

    identity_payload = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            "observation-dependency|"
            + identity_payload
        ).encode("utf-8")
    ).hexdigest()


def record_observation_dependency(
    *,
    relationship_type: str,
    observed_at: str,
    confidence: Optional[float] = None,
    downstream_source_observation_id:
        Optional[str] = None,
    downstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_observation_id:
        Optional[str] = None,
    upstream_reporter_observation_id:
        Optional[str] = None,
    upstream_source_id: Optional[str] = None,
    upstream_reporter_id: Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    identity = (
        _observation_dependency_identity(
            relationship_type=relationship_type,
            observed_at=observed_at,
            confidence=confidence,
            downstream_source_observation_id=(
                downstream_source_observation_id
            ),
            downstream_reporter_observation_id=(
                downstream_reporter_observation_id
            ),
            upstream_source_observation_id=(
                upstream_source_observation_id
            ),
            upstream_reporter_observation_id=(
                upstream_reporter_observation_id
            ),
            upstream_source_id=upstream_source_id,
            upstream_reporter_id=(
                upstream_reporter_id
            ),
        )
    )

    dependency_id = (
        observation_dependency_id_for_record(
            relationship_type=(
                identity["relationship_type"]
            ),
            observed_at=identity["observed_at"],
            confidence=identity["confidence"],
            downstream_source_observation_id=(
                identity["downstream_id"]
                if identity["downstream_type"]
                == "source_observation"
                else None
            ),
            downstream_reporter_observation_id=(
                identity["downstream_id"]
                if identity["downstream_type"]
                == "reporter_observation"
                else None
            ),
            upstream_source_observation_id=(
                identity["upstream_id"]
                if identity["upstream_type"]
                == "source_observation"
                else None
            ),
            upstream_reporter_observation_id=(
                identity["upstream_id"]
                if identity["upstream_type"]
                == "reporter_observation"
                else None
            ),
            upstream_source_id=(
                identity["upstream_id"]
                if identity["upstream_type"]
                == "source"
                else None
            ),
            upstream_reporter_id=(
                identity["upstream_id"]
                if identity["upstream_type"]
                == "reporter"
                else None
            ),
        )
    )

    downstream_source_id = (
        identity["downstream_id"]
        if identity["downstream_type"]
        == "source_observation"
        else None
    )

    downstream_reporter_id = (
        identity["downstream_id"]
        if identity["downstream_type"]
        == "reporter_observation"
        else None
    )

    upstream_source_observation = (
        identity["upstream_id"]
        if identity["upstream_type"]
        == "source_observation"
        else None
    )

    upstream_reporter_observation = (
        identity["upstream_id"]
        if identity["upstream_type"]
        == "reporter_observation"
        else None
    )

    upstream_source = (
        identity["upstream_id"]
        if identity["upstream_type"]
        == "source"
        else None
    )

    upstream_reporter = (
        identity["upstream_id"]
        if identity["upstream_type"]
        == "reporter"
        else None
    )

    normalized_recorded_at = (
        str(
            recorded_at or ""
        ).strip()
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    metadata_json = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    conn = connection_factory()

    try:
        cursor = conn.execute(
            """
            INSERT INTO observation_dependencies (
              id,
              downstream_source_observation_id,
              downstream_reporter_observation_id,
              upstream_source_observation_id,
              upstream_reporter_observation_id,
              upstream_source_id,
              upstream_reporter_id,
              relationship_type,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                dependency_id,
                downstream_source_id,
                downstream_reporter_id,
                upstream_source_observation,
                upstream_reporter_observation,
                upstream_source,
                upstream_reporter,
                identity["relationship_type"],
                identity["confidence"],
                identity["observed_at"],
                normalized_recorded_at,
                metadata_json,
            ),
        )

        created = (
            cursor.rowcount == 1
        )

        row = conn.execute(
            """
            SELECT *
            FROM observation_dependencies
            WHERE id = ?
            """,
            (
                dependency_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Observation dependency "
            "persistence failed."
        )

    return {
        "dependency": dict(row),
        "created": created,
    }
