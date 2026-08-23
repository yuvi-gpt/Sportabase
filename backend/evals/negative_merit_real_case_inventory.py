from __future__ import annotations

import hashlib
import json
import re
import sqlite3

from pathlib import Path
from typing import (
    Any,
    Dict,
    Optional,
)
from urllib.parse import urlparse


from app.analysis.negative_merit import (
    build_negative_merit_shadow,
)

from app.services.canonical_outcome_resolution_verifier import (
    CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE,
    CANONICAL_OUTCOME_PROOF_KIND,
    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION,
)

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE,
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
)


NEGATIVE_MERIT_REAL_CASE_INVENTORY_VERSION = (
    "negative-merit-real-case-inventory-v1"
)

NEGATIVE_MERIT_REAL_CASE_INVENTORY_REPORT_VERSION = (
    "negative-merit-real-case-inventory-report-v1"
)

_MACHINE_REFERENCE_EVIDENCE_TYPE = (
    "machine_verified_semantic_reference"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _json_object(
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
                value or "{}"
            )
        )

    except Exception:
        return {}

    return (
        parsed
        if isinstance(
            parsed,
            dict,
        )
        else {}
    )


def _json_list(
    value: Any,
):
    if isinstance(
        value,
        list,
    ):
        return value

    try:
        parsed = json.loads(
            str(
                value or "[]"
            )
        )

    except Exception:
        return []

    return (
        parsed
        if isinstance(
            parsed,
            list,
        )
        else []
    )


def _number(
    value: Any,
) -> Optional[float]:
    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    if not (
        0.0
        <= result
        <= 100.0
    ):
        return None

    return result


def _is_sha256(
    value: Any,
) -> bool:
    return bool(
        _SHA256_RE.fullmatch(
            _key(
                value
            )
        )
    )


def _is_https(
    value: Any,
) -> bool:
    text = _clean(
        value
    )

    try:
        parsed = urlparse(
            text
        )

    except Exception:
        return False

    return bool(
        parsed.scheme.lower()
        == "https"
        and parsed.netloc
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


def _connect_read_only(
    db_path: Path,
) -> sqlite3.Connection:
    resolved = Path(
        db_path
    ).resolve()

    if not resolved.is_file():
        raise FileNotFoundError(
            "Sportabase database does not exist: "
            + str(
                resolved
            )
        )

    uri = (
        resolved.as_uri()
        + "?mode=ro"
    )

    conn = sqlite3.connect(
        uri,
        uri=True,
        timeout=30,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA query_only=ON;"
    )

    conn.execute(
        "PRAGMA foreign_keys=ON;"
    )

    return conn


def _table_exists(
    conn,
    table_name: str,
) -> bool:
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


def _required_schema_available(
    conn,
):
    required = {
        "intelligence_claims",
        "media_items",
        "analysis_snapshots",
        "evidence_records",
        "adjudication_state_revisions",
    }

    missing = sorted(
        table_name
        for table_name
        in required
        if not _table_exists(
            conn,
            table_name,
        )
    )

    return missing


def _media_item_id_from_primary_claim(
    canonical_key: Any,
) -> str:
    text = _clean(
        canonical_key
    )

    prefix = (
        "article-primary|"
    )

    if not text.startswith(
        prefix
    ):
        return ""

    remainder = text[
        len(
            prefix
        ):
    ]

    if "|" not in remainder:
        return ""

    media_item_id, _ = (
        remainder.split(
            "|",
            1,
        )
    )

    return _clean(
        media_item_id
    )


def _latest_snapshot(
    conn,
    *,
    media_item_id: str,
):
    row = conn.execute(
        """
        SELECT *
        FROM analysis_snapshots
        WHERE media_item_id = ?
          AND mode = 'article'
          AND merit_score IS NOT NULL
        ORDER BY
          analyzed_at DESC,
          id DESC
        LIMIT 1
        """,
        (
            media_item_id,
        ),
    ).fetchone()

    return (
        dict(
            row
        )
        if row is not None
        else None
    )


def _legacy_total_from_snapshot(
    snapshot: Optional[
        Dict[str, Any]
    ],
):
    if not isinstance(
        snapshot,
        dict,
    ):
        return {
            "available": False,
            "total": None,
            "source": "",
        }

    response = _json_object(
        snapshot.get(
            "response_json"
        )
    )

    debug = response.get(
        "debug"
    )

    debug = (
        debug
        if isinstance(
            debug,
            dict,
        )
        else {}
    )

    negative_runtime = debug.get(
        "negative_merit_shadow"
    )

    if isinstance(
        negative_runtime,
        dict,
    ):
        shadow = negative_runtime.get(
            "shadow"
        )

        if isinstance(
            shadow,
            dict,
        ):
            legacy = shadow.get(
                "legacy"
            )

            if isinstance(
                legacy,
                dict,
            ):
                value = _number(
                    legacy.get(
                        "total"
                    )
                )

                if value is not None:
                    return {
                        "available": True,
                        "total": value,
                        "source": (
                            "snapshot.debug."
                            "negative_merit_shadow."
                            "shadow.legacy.total"
                        ),
                    }

    live_release = debug.get(
        "live_merit_release"
    )

    if isinstance(
        live_release,
        dict,
    ):
        value = _number(
            live_release.get(
                "legacy_total"
            )
        )

        if value is not None:
            return {
                "available": True,
                "total": value,
                "source": (
                    "snapshot.debug."
                    "live_merit_release."
                    "legacy_total"
                ),
            }

    return {
        "available": False,
        "total": None,
        "source": "",
    }


def _latest_verified_evidence(
    conn,
    *,
    evidence_type: str,
    subject_key: str,
):
    rows = conn.execute(
        """
        SELECT *
        FROM evidence_records
        WHERE evidence_type = ?
          AND subject_key = ?
          AND verification_status = 'verified'
        ORDER BY
          recorded_at DESC,
          id DESC
        """,
        (
            evidence_type,
            subject_key,
        ),
    ).fetchall()

    return [
        dict(
            row
        )
        for row
        in rows
    ]


def _authority_verification(
    conn,
    *,
    claim_id: str,
):
    rows = _latest_verified_evidence(
        conn,
        evidence_type=(
            DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE
        ),
        subject_key=(
            "merit-negative-evidence|"
            + claim_id
        ),
    )

    for evidence in rows:
        metadata = _json_object(
            evidence.get(
                "metadata_json"
            )
        )

        if (
            metadata.get(
                "verifier_version"
            )
            == (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            )
            and _clean(
                metadata.get(
                    "claim_id"
                )
            )
            == claim_id
        ):
            return {
                "version": (
                    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
                ),
                "status": (
                    "persisted_verified_"
                    "direct_stakeholder_"
                    "contradiction_lineage"
                ),
                "persisted": True,
                "evidence": evidence,
            }

    return None


def _semantic_verification(
    conn,
    *,
    claim_id: str,
):
    rows = _latest_verified_evidence(
        conn,
        evidence_type=(
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE
        ),
        subject_key=(
            "merit-negative-semantic-evidence|"
            + claim_id
        ),
    )

    for evidence in rows:
        metadata = _json_object(
            evidence.get(
                "metadata_json"
            )
        )

        if (
            metadata.get(
                "verifier_version"
            )
            == (
                MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
            )
            and _clean(
                metadata.get(
                    "claim_id"
                )
            )
            == claim_id
        ):
            return {
                "version": (
                    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
                ),
                "status": (
                    "persisted_verified_"
                    "machine_contradiction_"
                    "semantics"
                ),
                "persisted": True,
                "evidence": evidence,
            }

    return None


def _latest_revision(
    conn,
    *,
    claim_id: str,
):
    rows = conn.execute(
        """
        SELECT revision.*
        FROM adjudication_state_revisions revision
        WHERE revision.claim_id = ?
          AND NOT EXISTS (
            SELECT 1
            FROM adjudication_state_revisions child
            WHERE child.previous_revision_id
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
    ) != 1:
        return {
            "available": False,
            "ambiguous": (
                len(
                    rows
                )
                > 1
            ),
            "revision": None,
        }

    revision = _json_object(
        rows[
            0
        ][
            "revision_json"
        ]
    )

    if not revision:
        return {
            "available": False,
            "ambiguous": False,
            "revision": None,
        }

    return {
        "available": True,
        "ambiguous": False,
        "revision": revision,
    }


def _canonical_resolution_state(
    conn,
    *,
    claim_id: str,
):
    revision_state = _latest_revision(
        conn,
        claim_id=claim_id,
    )

    if not revision_state[
        "available"
    ]:
        return {
            "ready": False,
            "ambiguous_history": (
                revision_state[
                    "ambiguous"
                ]
            ),
            "evidence_id": "",
            "proof_evidence_id": "",
            "source_id": "",
            "canonical_url": "",
            "content_sha256": "",
            "captured_at": "",
            "rule_id": "",
            "blockers": (
                [
                    "adjudication_history_ambiguous"
                ]
                if revision_state[
                    "ambiguous"
                ]
                else []
            ),
        }

    revision = revision_state[
        "revision"
    ]

    adjudication = revision.get(
        "adjudication"
    )

    if not isinstance(
        adjudication,
        dict,
    ):
        return {
            "ready": False,
            "ambiguous_history": False,
            "evidence_id": "",
            "proof_evidence_id": "",
            "source_id": "",
            "canonical_url": "",
            "content_sha256": "",
            "captured_at": "",
            "rule_id": "",
            "blockers": [
                "adjudication_payload_missing"
            ],
        }

    runs = adjudication.get(
        "evaluators"
    )

    if not isinstance(
        runs,
        list,
    ):
        runs = []

    matching = []

    for run in runs:
        if not isinstance(
            run,
            dict,
        ):
            continue

        if (
            _key(
                run.get(
                    "derivation_mode"
                )
            )
            != "machine_verified"
        ):
            continue

        judgments = run.get(
            "judgments",
            [],
        )

        if not isinstance(
            judgments,
            list,
        ):
            continue

        for judgment in judgments:
            if not isinstance(
                judgment,
                dict,
            ):
                continue

            if (
                _key(
                    judgment.get(
                        "field"
                    )
                )
                == "stance"
                and _key(
                    judgment.get(
                        "value"
                    )
                )
                == "contradicts"
                and _key(
                    judgment.get(
                        "basis_class"
                    )
                )
                == "canonical_resolution"
            ):
                matching.append(
                    judgment
                )

    if len(
        matching
    ) != 1:
        return {
            "ready": False,
            "ambiguous_history": False,
            "evidence_id": "",
            "proof_evidence_id": "",
            "source_id": "",
            "canonical_url": "",
            "content_sha256": "",
            "captured_at": "",
            "rule_id": "",
            "blockers": (
                [
                    "canonical_resolution_machine_stance_ambiguous"
                ]
                if len(
                    matching
                )
                > 1
                else []
            ),
        }

    evidence_ids = sorted(
        {
            _clean(
                value
            )
            for value
            in matching[
                0
            ].get(
                "evidence_ids",
                [],
            )
            if _clean(
                value
            )
        }
    )

    if len(
        evidence_ids
    ) != 1:
        return {
            "ready": False,
            "ambiguous_history": False,
            "evidence_id": "",
            "proof_evidence_id": "",
            "source_id": "",
            "canonical_url": "",
            "content_sha256": "",
            "captured_at": "",
            "rule_id": "",
            "blockers": [
                "canonical_resolution_machine_evidence_ambiguous"
            ],
        }

    resolution_evidence_id = (
        evidence_ids[
            0
        ]
    )

    evidence_row = conn.execute(
        """
        SELECT *
        FROM evidence_records
        WHERE id = ?
        """,
        (
            resolution_evidence_id,
        ),
    ).fetchone()

    if evidence_row is None:
        return {
            "ready": False,
            "ambiguous_history": False,
            "evidence_id": (
                resolution_evidence_id
            ),
            "proof_evidence_id": "",
            "source_id": "",
            "canonical_url": "",
            "content_sha256": "",
            "captured_at": "",
            "rule_id": "",
            "blockers": [
                "canonical_resolution_machine_evidence_missing"
            ],
        }

    evidence = dict(
        evidence_row
    )

    metadata = _json_object(
        evidence.get(
            "metadata_json"
        )
    )

    proof_evidence_id = _clean(
        metadata.get(
            "proof_evidence_id"
        )
    )

    canonical_url = _clean(
        evidence.get(
            "canonical_url"
        )
    )

    content_sha256 = _key(
        metadata.get(
            "content_sha256"
        )
    )

    canonical_resolution = metadata.get(
        "canonical_resolution"
    )

    canonical_resolution = (
        canonical_resolution
        if isinstance(
            canonical_resolution,
            dict,
        )
        else {}
    )

    rule_id = _clean(
        canonical_resolution.get(
            "rule_id"
        )
    )

    blockers = []

    if (
        _key(
            evidence.get(
                "evidence_type"
            )
        )
        != _MACHINE_REFERENCE_EVIDENCE_TYPE
    ):
        blockers.append(
            "canonical_resolution_machine_evidence_type_mismatch"
        )

    if (
        _key(
            evidence.get(
                "verification_status"
            )
        )
        != "verified"
    ):
        blockers.append(
            "canonical_resolution_machine_evidence_not_verified"
        )

    if (
        metadata.get(
            "canonical_outcome_resolution_verifier_version"
        )
        != (
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
        )
    ):
        blockers.append(
            "canonical_resolution_verifier_version_mismatch"
        )

    if (
        metadata.get(
            "canonical_outcome_resolution_verified"
        )
        is not True
    ):
        blockers.append(
            "canonical_resolution_not_verified"
        )

    if (
        metadata.get(
            "resolved_against_claim"
        )
        is not True
    ):
        blockers.append(
            "canonical_resolution_not_against_claim"
        )

    if (
        metadata.get(
            "claim_truth_established"
        )
        is not False
    ):
        blockers.append(
            "canonical_resolution_truth_boundary_violated"
        )

    if (
        metadata.get(
            "live_merit_changed"
        )
        is not False
    ):
        blockers.append(
            "canonical_resolution_live_merit_boundary_violated"
        )

    if not proof_evidence_id:
        blockers.append(
            "canonical_resolution_proof_evidence_missing"
        )

    if not _is_https(
        canonical_url
    ):
        blockers.append(
            "canonical_resolution_url_invalid"
        )

    if not _is_sha256(
        content_sha256
    ):
        blockers.append(
            "canonical_resolution_content_hash_invalid"
        )

    if not rule_id:
        blockers.append(
            "canonical_resolution_rule_missing"
        )

    proof = None

    if proof_evidence_id:
        proof_row = conn.execute(
            """
            SELECT *
            FROM evidence_records
            WHERE id = ?
            """,
            (
                proof_evidence_id,
            ),
        ).fetchone()

        if proof_row is not None:
            proof = dict(
                proof_row
            )

    source_id = ""

    if proof is None:
        if proof_evidence_id:
            blockers.append(
                "canonical_resolution_proof_record_missing"
            )

    else:
        proof_metadata = _json_object(
            proof.get(
                "metadata_json"
            )
        )

        source_id = _clean(
            proof_metadata.get(
                "source_id"
            )
        )

        if (
            _key(
                proof.get(
                    "evidence_type"
                )
            )
            != CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE
        ):
            blockers.append(
                "canonical_resolution_proof_type_mismatch"
            )

        if (
            _key(
                proof.get(
                    "verification_status"
                )
            )
            != "verified"
        ):
            blockers.append(
                "canonical_resolution_proof_not_verified"
            )

        if (
            _key(
                proof_metadata.get(
                    "proof_kind"
                )
            )
            != CANONICAL_OUTCOME_PROOF_KIND
        ):
            blockers.append(
                "canonical_resolution_proof_kind_mismatch"
            )

        if (
            _clean(
                proof_metadata.get(
                    "claim_id"
                )
            )
            != claim_id
        ):
            blockers.append(
                "canonical_resolution_proof_claim_mismatch"
            )

        if (
            _key(
                proof_metadata.get(
                    "content_sha256"
                )
            )
            != content_sha256
        ):
            blockers.append(
                "canonical_resolution_proof_hash_mismatch"
            )

        if (
            _clean(
                proof.get(
                    "canonical_url"
                )
            )
            != canonical_url
        ):
            blockers.append(
                "canonical_resolution_proof_url_mismatch"
            )

        if not source_id:
            blockers.append(
                "canonical_resolution_source_identity_missing"
            )

    return {
        "ready": (
            len(
                blockers
            )
            == 0
        ),
        "ambiguous_history": False,
        "evidence_id": (
            resolution_evidence_id
        ),
        "proof_evidence_id": (
            proof_evidence_id
        ),
        "source_id": (
            source_id
        ),
        "canonical_url": (
            canonical_url
        ),
        "content_sha256": (
            content_sha256
        ),
        "captured_at": _clean(
            evidence.get(
                "recorded_at"
            )
        ),
        "rule_id": (
            rule_id
        ),
        "blockers": blockers,
    }


def _article_capture_state(
    *,
    media_item: Optional[
        Dict[str, Any]
    ],
    snapshot: Optional[
        Dict[str, Any]
    ],
):
    if not isinstance(
        media_item,
        dict,
    ):
        return {
            "ready": False,
            "source_id": "",
            "url": "",
            "content_sha256": "",
            "captured_at": "",
            "blockers": [
                "media_item_missing"
            ],
        }

    source_id = _clean(
        media_item.get(
            "source_id"
        )
    )

    url = _clean(
        media_item.get(
            "canonical_url"
        )
    )

    content_sha256 = _key(
        media_item.get(
            "latest_content_hash"
        )
    )

    captured_at = ""

    if isinstance(
        snapshot,
        dict,
    ):
        captured_at = _clean(
            snapshot.get(
                "analyzed_at"
            )
        )

    if not captured_at:
        captured_at = _clean(
            media_item.get(
                "last_seen_at"
            )
        )

    blockers = []

    if not source_id:
        blockers.append(
            "article_source_identity_missing"
        )

    if not _is_https(
        url
    ):
        blockers.append(
            "article_canonical_url_invalid"
        )

    if not _is_sha256(
        content_sha256
    ):
        blockers.append(
            "article_content_hash_invalid"
        )

    if not captured_at:
        blockers.append(
            "article_capture_time_missing"
        )

    return {
        "ready": (
            len(
                blockers
            )
            == 0
        ),
        "source_id": source_id,
        "url": url,
        "content_sha256": (
            content_sha256
        ),
        "captured_at": (
            captured_at
        ),
        "blockers": blockers,
    }


def _classification(
    *,
    authority_gate: bool,
    semantic_gate: bool,
    resolution_ready: bool,
) -> str:
    if (
        authority_gate
        and semantic_gate
        and resolution_ready
    ):
        return (
            "resolved_against_claim_observation"
        )

    if (
        authority_gate
        and semantic_gate
    ):
        return (
            "two_gate_observation"
        )

    if authority_gate:
        return (
            "authority_only_control"
        )

    if semantic_gate:
        return (
            "semantic_only_control"
        )

    return (
        "no_negative_evidence_control"
    )


def build_negative_merit_real_case_inventory(
    *,
    db_path: Path,
) -> Dict[str, Any]:
    path = Path(
        db_path
    ).resolve()

    conn = _connect_read_only(
        path
    )

    try:
        missing_schema = (
            _required_schema_available(
                conn
            )
        )

        if missing_schema:
            raise ValueError(
                "Negative Merit inventory "
                "database is missing tables: "
                + ", ".join(
                    missing_schema
                )
            )

        claim_rows = conn.execute(
            """
            SELECT *
            FROM intelligence_claims
            WHERE canonical_key
                  LIKE 'article-primary|%'
            ORDER BY
              first_seen_at,
              id
            """
        ).fetchall()

        cases = []

        metrics = {
            "primary_claims": 0,
            "media_items_found": 0,
            "analysis_snapshots_found": 0,
            "legacy_scores_ready": 0,
            "article_captures_ready": 0,
            "authority_gate_ready": 0,
            "semantic_gate_ready": 0,
            "two_gate_ready": 0,
            "resolved_verifications_ready": 0,
            "corpus_export_ready": 0,
            "exclusive_controls_machine_classified": 0,
            "exclusive_controls_requiring_curation": 0,
        }

        class_counts = {
            "resolved_against_claim_observation": 0,
            "two_gate_observation": 0,
            "authority_only_control": 0,
            "semantic_only_control": 0,
            "no_negative_evidence_control": 0,
        }

        for claim_row in claim_rows:
            claim = dict(
                claim_row
            )

            claim_id = _clean(
                claim.get(
                    "id"
                )
            )

            media_item_id = (
                _media_item_id_from_primary_claim(
                    claim.get(
                        "canonical_key"
                    )
                )
            )

            metrics[
                "primary_claims"
            ] += 1

            media_item = None

            if media_item_id:
                media_row = conn.execute(
                    """
                    SELECT *
                    FROM media_items
                    WHERE id = ?
                    """,
                    (
                        media_item_id,
                    ),
                ).fetchone()

                if media_row is not None:
                    media_item = dict(
                        media_row
                    )

                    metrics[
                        "media_items_found"
                    ] += 1

            snapshot = None

            if media_item_id:
                snapshot = _latest_snapshot(
                    conn,
                    media_item_id=(
                        media_item_id
                    ),
                )

            if snapshot is not None:
                metrics[
                    "analysis_snapshots_found"
                ] += 1

            legacy = (
                _legacy_total_from_snapshot(
                    snapshot
                )
            )

            if legacy[
                "available"
            ]:
                metrics[
                    "legacy_scores_ready"
                ] += 1

            article_capture = (
                _article_capture_state(
                    media_item=(
                        media_item
                    ),
                    snapshot=(
                        snapshot
                    ),
                )
            )

            if article_capture[
                "ready"
            ]:
                metrics[
                    "article_captures_ready"
                ] += 1

            authority = (
                _authority_verification(
                    conn,
                    claim_id=claim_id,
                )
            )

            semantics = (
                _semantic_verification(
                    conn,
                    claim_id=claim_id,
                )
            )

            score_for_gate_check = (
                legacy[
                    "total"
                ]
                if legacy[
                    "available"
                ]
                else 50.0
            )

            shadow = (
                build_negative_merit_shadow(
                    legacy_score={
                        "total": (
                            score_for_gate_check
                        ),
                    },
                    claim_id=(
                        claim_id
                    ),
                    contradiction_verification=(
                        authority
                    ),
                    semantic_verification=(
                        semantics
                    ),
                )
            )

            gates = shadow[
                "evidence_gates"
            ]

            authority_gate = bool(
                gates[
                    "direct_authority_"
                    "contradiction_lineage"
                ]
            )

            semantic_gate = bool(
                gates[
                    "machine_verified_"
                    "contradiction_semantics"
                ]
            )

            if authority_gate:
                metrics[
                    "authority_gate_ready"
                ] += 1

            if semantic_gate:
                metrics[
                    "semantic_gate_ready"
                ] += 1

            if (
                authority_gate
                and semantic_gate
            ):
                metrics[
                    "two_gate_ready"
                ] += 1

            resolution = (
                _canonical_resolution_state(
                    conn,
                    claim_id=claim_id,
                )
            )

            if resolution[
                "ready"
            ]:
                metrics[
                    "resolved_verifications_ready"
                ] += 1

            suggested_class = (
                _classification(
                    authority_gate=(
                        authority_gate
                    ),
                    semantic_gate=(
                        semantic_gate
                    ),
                    resolution_ready=(
                        resolution[
                            "ready"
                        ]
                    ),
                )
            )

            class_counts[
                suggested_class
            ] += 1

            blockers = []

            if not media_item_id:
                blockers.append(
                    "primary_claim_media_identity_unavailable"
                )

            if media_item is None:
                blockers.append(
                    "media_item_missing"
                )

            if snapshot is None:
                blockers.append(
                    "analysis_snapshot_missing"
                )

            if not legacy[
                "available"
            ]:
                blockers.append(
                    "legacy_merit_total_unavailable"
                )

            blockers.extend(
                article_capture[
                    "blockers"
                ]
            )

            if (
                suggested_class
                == (
                    "resolved_against_claim_observation"
                )
            ):
                blockers.extend(
                    resolution[
                        "blockers"
                    ]
                )

            export_ready = bool(
                legacy[
                    "available"
                ]
                and article_capture[
                    "ready"
                ]
                and (
                    suggested_class
                    != (
                        "resolved_against_claim_observation"
                    )
                    or resolution[
                        "ready"
                    ]
                )
            )

            if export_ready:
                metrics[
                    "corpus_export_ready"
                ] += 1

            exclusive_review = bool(
                suggested_class
                == "no_negative_evidence_control"
                and export_ready
            )

            if exclusive_review:
                metrics[
                    "exclusive_controls_requiring_curation"
                ] += 1

            case = {
                "claim_id": claim_id,
                "canonical_key": _clean(
                    claim.get(
                        "canonical_key"
                    )
                ),
                "canonical_text": _clean(
                    claim.get(
                        "canonical_text"
                    )
                ),
                "claim_type": _clean(
                    claim.get(
                        "claim_type"
                    )
                ),
                "subject_key": _clean(
                    claim.get(
                        "subject_key"
                    )
                ),
                "media_item_id": (
                    media_item_id
                ),
                "article": {
                    "url": (
                        _clean(
                            media_item.get(
                                "canonical_url"
                            )
                        )
                        if isinstance(
                            media_item,
                            dict,
                        )
                        else ""
                    ),
                    "title": (
                        _clean(
                            media_item.get(
                                "title"
                            )
                        )
                        if isinstance(
                            media_item,
                            dict,
                        )
                        else ""
                    ),
                    "source_id": (
                        _clean(
                            media_item.get(
                                "source_id"
                            )
                        )
                        if isinstance(
                            media_item,
                            dict,
                        )
                        else ""
                    ),
                },
                "snapshot": {
                    "id": (
                        snapshot.get(
                            "id"
                        )
                        if isinstance(
                            snapshot,
                            dict,
                        )
                        else None
                    ),
                    "analyzed_at": (
                        _clean(
                            snapshot.get(
                                "analyzed_at"
                            )
                        )
                        if isinstance(
                            snapshot,
                            dict,
                        )
                        else ""
                    ),
                    "stored_merit_total": (
                        _number(
                            snapshot.get(
                                "merit_score"
                            )
                        )
                        if isinstance(
                            snapshot,
                            dict,
                        )
                        else None
                    ),
                    "legacy_merit": legacy,
                },
                "article_capture": (
                    article_capture
                ),
                "evidence_gates": {
                    "authority": (
                        authority_gate
                    ),
                    "semantics": (
                        semantic_gate
                    ),
                    "both": bool(
                        authority_gate
                        and semantic_gate
                    ),
                },
                "canonical_resolution": (
                    resolution
                ),
                "suggested_observation_class": (
                    suggested_class
                ),
                "corpus_export_ready": (
                    export_ready
                ),
                "exclusive_control_review": {
                    "required": (
                        exclusive_review
                    ),
                    "reason": (
                        (
                            "No negative-evidence gates "
                            "are present, but legitimate "
                            "early-exclusive status cannot "
                            "be inferred from absence of "
                            "evidence alone."
                        )
                        if exclusive_review
                        else ""
                    ),
                    "machine_classified_as_exclusive": False,
                },
                "blockers": sorted(
                    set(
                        blocker
                        for blocker
                        in blockers
                        if blocker
                    )
                ),
            }

            cases.append(
                case
            )

        metrics[
            "exclusive_controls_machine_classified"
        ] = 0

        report_core = {
            "version": (
                NEGATIVE_MERIT_REAL_CASE_INVENTORY_REPORT_VERSION
            ),
            "inventory_version": (
                NEGATIVE_MERIT_REAL_CASE_INVENTORY_VERSION
            ),
            "status": (
                "ready"
                if cases
                else "empty"
            ),
            "database": {
                "read_only": True,
                "path": str(
                    path
                ),
            },
            "metrics": metrics,
            "suggested_class_counts": (
                class_counts
            ),
            "cases": cases,
            "policy": {
                "database_opened_read_only": True,
                "provider_call_performed": False,
                "live_merit_changed": False,
                "inventory_does_not_persist_verification": True,
                "inventory_does_not_admit_corpus_cases": True,
                "suggested_class_is_not_a_release_label": True,
                "legacy_total_is_recovered_before_live_positive_overlay": True,
                "resolved_candidate_requires_persisted_canonical_resolution_lineage": True,
                "no_negative_evidence_is_not_falsehood": True,
                "no_negative_evidence_is_not_exclusive_reporting": True,
                "exclusive_control_requires_separate_curation": True,
                "numeric_negative_penalty_authorized": False,
                "live_negative_merit_authorized": False,
            },
        }

        digest_payload = {
            "version": report_core[
                "version"
            ],
            "inventory_version": (
                report_core[
                    "inventory_version"
                ]
            ),
            "metrics": metrics,
            "suggested_class_counts": (
                class_counts
            ),
            "cases": cases,
        }

        return {
            **report_core,
            "report_digest": _digest(
                digest_payload
            ),
        }

    finally:
        conn.close()


def write_inventory_json(
    path: Path,
    report: Dict[str, Any],
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
            report,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
