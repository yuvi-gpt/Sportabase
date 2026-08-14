import hashlib
import json

from datetime import datetime, timezone
from typing import Any, Dict, Optional


OBSERVATION_INDEPENDENCE_ASSERTION_VERSION = (
    "observation-independence-v1"
)

OBSERVATION_INDEPENDENCE_VERIFICATION_VOCABULARY = (
    "unverified",
    "verified",
)


def _observation_independence_assertion_identity(
    *,
    observed_at: str,
    provenance_evidence_id: str,
    verification_status: str = "unverified",
    confidence: Optional[float] = None,
    left_source_observation_id:
        Optional[str] = None,
    left_reporter_observation_id:
        Optional[str] = None,
    right_source_observation_id:
        Optional[str] = None,
    right_reporter_observation_id:
        Optional[str] = None,
) -> Dict[str, Any]:
    normalized_observed_at = str(
        observed_at or ""
    ).strip()

    if not normalized_observed_at:
        raise ValueError(
            "Observation independence observed "
            "time is required."
        )

    normalized_evidence_id = str(
        provenance_evidence_id or ""
    ).strip()

    if not normalized_evidence_id:
        raise ValueError(
            "Observation independence provenance "
            "evidence ID is required."
        )

    normalized_verification_status = str(
        verification_status or ""
    ).strip().lower()

    if (
        normalized_verification_status
        not in
        OBSERVATION_INDEPENDENCE_VERIFICATION_VOCABULARY
    ):
        raise ValueError(
            "Observation independence verification "
            "status must be unverified or verified."
        )

    left_targets = {
        "source_observation": (
            str(
                left_source_observation_id
                or ""
            ).strip()
            or None
        ),
        "reporter_observation": (
            str(
                left_reporter_observation_id
                or ""
            ).strip()
            or None
        ),
    }

    right_targets = {
        "source_observation": (
            str(
                right_source_observation_id
                or ""
            ).strip()
            or None
        ),
        "reporter_observation": (
            str(
                right_reporter_observation_id
                or ""
            ).strip()
            or None
        ),
    }

    active_left = [
        (
            target_type,
            target_id,
        )
        for (
            target_type,
            target_id,
        ) in left_targets.items()
        if target_id is not None
    ]

    active_right = [
        (
            target_type,
            target_id,
        )
        for (
            target_type,
            target_id,
        ) in right_targets.items()
        if target_id is not None
    ]

    if len(active_left) != 1:
        raise ValueError(
            "Observation independence requires "
            "exactly one left observation."
        )

    if len(active_right) != 1:
        raise ValueError(
            "Observation independence requires "
            "exactly one right observation."
        )

    left = active_left[0]
    right = active_right[0]

    if left == right:
        raise ValueError(
            "An observation cannot be independent "
            "of itself."
        )

    observation_a, observation_b = sorted(
        (
            left,
            right,
        )
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
                "Observation independence confidence "
                "must be numeric."
            ) from exc

        if not (
            0.0
            <= normalized_confidence
            <= 1.0
        ):
            raise ValueError(
                "Observation independence confidence "
                "must be between 0 and 1."
            )

    return {
        "observation_a_type": (
            observation_a[0]
        ),
        "observation_a_id": (
            observation_a[1]
        ),
        "observation_b_type": (
            observation_b[0]
        ),
        "observation_b_id": (
            observation_b[1]
        ),
        "provenance_evidence_id": (
            normalized_evidence_id
        ),
        "verification_status": (
            normalized_verification_status
        ),
        "confidence": normalized_confidence,
        "observed_at": (
            normalized_observed_at
        ),
    }


def observation_independence_assertion_id_for_record(
    *,
    observed_at: str,
    provenance_evidence_id: str,
    verification_status: str = "unverified",
    confidence: Optional[float] = None,
    left_source_observation_id:
        Optional[str] = None,
    left_reporter_observation_id:
        Optional[str] = None,
    right_source_observation_id:
        Optional[str] = None,
    right_reporter_observation_id:
        Optional[str] = None,
) -> str:
    identity = (
        _observation_independence_assertion_identity(
            observed_at=observed_at,
            provenance_evidence_id=(
                provenance_evidence_id
            ),
            verification_status=(
                verification_status
            ),
            confidence=confidence,
            left_source_observation_id=(
                left_source_observation_id
            ),
            left_reporter_observation_id=(
                left_reporter_observation_id
            ),
            right_source_observation_id=(
                right_source_observation_id
            ),
            right_reporter_observation_id=(
                right_reporter_observation_id
            ),
        )
    )

    payload = json.dumps(
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
            "observation-independence|"
            + payload
        ).encode("utf-8")
    ).hexdigest()


def record_observation_independence_assertion(
    *,
    observed_at: str,
    provenance_evidence_id: str,
    verification_status: str = "unverified",
    confidence: Optional[float] = None,
    left_source_observation_id:
        Optional[str] = None,
    left_reporter_observation_id:
        Optional[str] = None,
    right_source_observation_id:
        Optional[str] = None,
    right_reporter_observation_id:
        Optional[str] = None,
    recorded_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    connection_factory=None,
) -> Dict[str, Any]:
    identity = (
        _observation_independence_assertion_identity(
            observed_at=observed_at,
            provenance_evidence_id=(
                provenance_evidence_id
            ),
            verification_status=(
                verification_status
            ),
            confidence=confidence,
            left_source_observation_id=(
                left_source_observation_id
            ),
            left_reporter_observation_id=(
                left_reporter_observation_id
            ),
            right_source_observation_id=(
                right_source_observation_id
            ),
            right_reporter_observation_id=(
                right_reporter_observation_id
            ),
        )
    )

    assertion_id = (
        observation_independence_assertion_id_for_record(
            observed_at=identity["observed_at"],
            provenance_evidence_id=(
                identity[
                    "provenance_evidence_id"
                ]
            ),
            verification_status=(
                identity[
                    "verification_status"
                ]
            ),
            confidence=identity["confidence"],
            left_source_observation_id=(
                identity["observation_a_id"]
                if (
                    identity[
                        "observation_a_type"
                    ]
                    == "source_observation"
                )
                else None
            ),
            left_reporter_observation_id=(
                identity["observation_a_id"]
                if (
                    identity[
                        "observation_a_type"
                    ]
                    == "reporter_observation"
                )
                else None
            ),
            right_source_observation_id=(
                identity["observation_b_id"]
                if (
                    identity[
                        "observation_b_type"
                    ]
                    == "source_observation"
                )
                else None
            ),
            right_reporter_observation_id=(
                identity["observation_b_id"]
                if (
                    identity[
                        "observation_b_type"
                    ]
                    == "reporter_observation"
                )
                else None
            ),
        )
    )

    a_source = (
        identity["observation_a_id"]
        if (
            identity[
                "observation_a_type"
            ]
            == "source_observation"
        )
        else None
    )

    a_reporter = (
        identity["observation_a_id"]
        if (
            identity[
                "observation_a_type"
            ]
            == "reporter_observation"
        )
        else None
    )

    b_source = (
        identity["observation_b_id"]
        if (
            identity[
                "observation_b_type"
            ]
            == "source_observation"
        )
        else None
    )

    b_reporter = (
        identity["observation_b_id"]
        if (
            identity[
                "observation_b_type"
            ]
            == "reporter_observation"
        )
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
            INSERT INTO
            observation_independence_assertions (
              id,
              observation_a_source_observation_id,
              observation_a_reporter_observation_id,
              observation_b_source_observation_id,
              observation_b_reporter_observation_id,
              provenance_evidence_id,
              verification_status,
              confidence,
              observed_at,
              recorded_at,
              metadata_json
            )
            VALUES (
              ?, ?, ?, ?, ?, ?,
              ?, ?, ?, ?, ?
            )
            ON CONFLICT(id)
            DO NOTHING
            """,
            (
                assertion_id,
                a_source,
                a_reporter,
                b_source,
                b_reporter,
                identity[
                    "provenance_evidence_id"
                ],
                identity[
                    "verification_status"
                ],
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
            FROM observation_independence_assertions
            WHERE id = ?
            """,
            (
                assertion_id,
            ),
        ).fetchone()

        conn.commit()

    finally:
        conn.close()

    if row is None:
        raise RuntimeError(
            "Observation independence assertion "
            "persistence failed."
        )

    return {
        "assertion": dict(row),
        "created": created,
    }
