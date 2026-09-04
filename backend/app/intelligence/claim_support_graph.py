from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import hashlib
import json
from typing import Any, Iterable

from app.analysis.features import OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY


CLAIM_SUPPORT_GRAPH_VERSION = "claim-support-graph-v1"
CLAIM_EVIDENCE_GRAPH_VERSION = "claim-evidence-graph-v1"
STORY_SUPPORT_OVERVIEW_VERSION = "story-support-overview-v1"

_MAX_OBSERVATIONS = 400
_GRAPH_LIMITS = {
    "claim_links": 800,
    "observations": 400,
    "evidence_records": 400,
    "evidence_links": 800,
    "dependency_records": 800,
    "independence_assertions": 800,
}
_CANONICAL_CLAIM_RELATIONSHIPS = {
    "reports", "supports", "contradicts", "aligned_to",
}
_SUPPORT_ALIASES = {
    "support", "confirms", "confirm", "corroborates", "corroborate",
    "verifies", "verify",
}
_CONFLICT_ALIASES = {
    "contradict", "refutes", "refute", "disputes", "dispute", "denies",
    "deny", "counterevidence", "counter_evidence",
}
_RECOGNIZED_EVIDENCE_TYPES = {
    "independent_report", "official_statement", "primary_document", "quote",
    "multimodal_claim_candidate", "claim_evidence_snapshot",
    "independence_verification", "direct_stakeholder_independence_reference",
    "machine_verified_semantic_reference", "claim_entity_participant_reference",
}
_RECOGNIZED_EVIDENCE_LINK_RELATIONSHIPS = {
    "supports", "contradicts", "published_by", "provenance",
}


def _integrity_error(message: str):
    from app.story.story_claim_graph_materialization import (
        StoryClaimGraphMaterializationIntegrityError,
    )

    return StoryClaimGraphMaterializationIntegrityError(message)


def _clean(value: Any, maximum: int = 512) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _row(value: Any) -> dict[str, Any]:
    return dict(value) if value is not None else {}


def _observation_key(observation_type: str, observation_id: str) -> str:
    return observation_type + ":" + observation_id


def _pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _chunks(values: Iterable[str], size: int = 350):
    items = list(values)
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _claim_record(*, claim_id: str, connection_factory) -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        row = conn.execute(
            "SELECT * FROM intelligence_claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _claim_link_rows(*, claim_id: str, connection_factory) -> list[dict[str, Any]]:
    conn = connection_factory()
    try:
        rows = conn.execute(
            """
            SELECT
              cl.*,
              so.source_id AS source_observation_source_id,
              so.subject_key AS source_observation_subject_key,
              so.observation_type AS source_observation_type,
              so.status AS source_observation_status,
              so.observed_at AS source_observation_observed_at,
              ro.source_id AS reporter_observation_source_id,
              ro.reporter_id AS reporter_observation_reporter_id,
              ro.subject_key AS reporter_observation_subject_key,
              ro.observation_type AS reporter_observation_type,
              ro.status AS reporter_observation_status,
              ro.observed_at AS reporter_observation_observed_at,
              e.evidence_type AS evidence_type,
              e.verification_status AS evidence_verification_status,
              e.subject_key AS evidence_subject_key,
              e.observed_at AS evidence_observed_at
            FROM claim_links AS cl
            LEFT JOIN source_observations AS so
              ON so.id = cl.source_observation_id
            LEFT JOIN reporter_observations AS ro
              ON ro.id = cl.reporter_observation_id
            LEFT JOIN evidence_records AS e
              ON e.id = cl.evidence_id
            WHERE cl.claim_id = ?
            ORDER BY cl.observed_at, cl.id
            """,
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _observation_nodes(
    link_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    nodes: dict[str, dict[str, Any]] = {}
    direct_evidence: dict[str, dict[str, Any]] = {}
    truncated = False

    for row in link_rows:
        source_observation_id = _clean(row.get("source_observation_id"), 128)
        reporter_observation_id = _clean(row.get("reporter_observation_id"), 128)
        evidence_id = _clean(row.get("evidence_id"), 128)
        relationship_type = _clean(row.get("relationship_type"), 64).casefold()

        if source_observation_id:
            key = _observation_key("source_observation", source_observation_id)
            if key not in nodes and len(nodes) >= _MAX_OBSERVATIONS:
                truncated = True
            else:
                node = nodes.setdefault(
                    key,
                    {
                        "key": key,
                        "observation_type": "source_observation",
                        "observation_id": source_observation_id,
                        "source_id": _clean(
                            row.get("source_observation_source_id"), 128
                        ),
                        "reporter_id": "",
                        "subject_key": _clean(
                            row.get("source_observation_subject_key"), 256
                        ),
                        "record_type": _clean(
                            row.get("source_observation_type"), 64
                        ),
                        "status": _clean(
                            row.get("source_observation_status"), 64
                        ),
                        "observed_at": _clean(
                            row.get("source_observation_observed_at"), 128
                        ),
                        "claim_relationship_types": [],
                    },
                )
                if relationship_type and relationship_type not in node[
                    "claim_relationship_types"
                ]:
                    node["claim_relationship_types"].append(relationship_type)

        if reporter_observation_id:
            key = _observation_key("reporter_observation", reporter_observation_id)
            if key not in nodes and len(nodes) >= _MAX_OBSERVATIONS:
                truncated = True
            else:
                node = nodes.setdefault(
                    key,
                    {
                        "key": key,
                        "observation_type": "reporter_observation",
                        "observation_id": reporter_observation_id,
                        "source_id": _clean(
                            row.get("reporter_observation_source_id"), 128
                        ),
                        "reporter_id": _clean(
                            row.get("reporter_observation_reporter_id"), 128
                        ),
                        "subject_key": _clean(
                            row.get("reporter_observation_subject_key"), 256
                        ),
                        "record_type": _clean(
                            row.get("reporter_observation_type"), 64
                        ),
                        "status": _clean(
                            row.get("reporter_observation_status"), 64
                        ),
                        "observed_at": _clean(
                            row.get("reporter_observation_observed_at"), 128
                        ),
                        "claim_relationship_types": [],
                    },
                )
                if relationship_type and relationship_type not in node[
                    "claim_relationship_types"
                ]:
                    node["claim_relationship_types"].append(relationship_type)

        if evidence_id:
            direct_evidence[evidence_id] = {
                "evidence_id": evidence_id,
                "evidence_type": _clean(row.get("evidence_type"), 64),
                "verification_status": _clean(
                    row.get("evidence_verification_status"), 64
                ).casefold(),
                "subject_key": _clean(row.get("evidence_subject_key"), 256),
                "observed_at": _clean(row.get("evidence_observed_at"), 128),
                "claim_relationship_type": relationship_type,
            }

    ordered_nodes = sorted(nodes.values(), key=lambda item: item["key"])
    ordered_evidence = sorted(
        direct_evidence.values(), key=lambda item: item["evidence_id"]
    )
    return ordered_nodes, ordered_evidence, truncated


def _dependency_rows(
    *,
    source_ids: list[str],
    reporter_ids: list[str],
    connection_factory,
) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    for kind, values in (
        ("source", source_ids),
        ("reporter", reporter_ids),
    ):
        for chunk in _chunks(values):
            if not chunk:
                continue
            placeholders = ",".join("?" for _ in chunk)
            column = (
                "downstream_source_observation_id"
                if kind == "source"
                else "downstream_reporter_observation_id"
            )
            conn = connection_factory()
            try:
                rows = conn.execute(
                    "SELECT * FROM observation_dependencies WHERE "
                    + column
                    + f" IN ({placeholders}) ORDER BY observed_at, id",
                    tuple(chunk),
                ).fetchall()
            finally:
                conn.close()
            for row in rows:
                item = dict(row)
                results[_clean(item.get("id"), 128)] = item

    return [results[key] for key in sorted(results)]


def _dependency_graph(
    *,
    nodes: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    by_key = {item["key"]: item for item in nodes}
    by_source: dict[str, list[str]] = defaultdict(list)
    by_reporter: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        if node["source_id"]:
            by_source[node["source_id"]].append(node["key"])
        if node["reporter_id"]:
            by_reporter[node["reporter_id"]].append(node["key"])

    edges: list[dict[str, Any]] = []
    dependency_pairs: set[tuple[str, str]] = set()

    for row in rows:
        downstream_key = ""
        if row.get("downstream_source_observation_id"):
            downstream_key = _observation_key(
                "source_observation",
                _clean(row.get("downstream_source_observation_id"), 128),
            )
        elif row.get("downstream_reporter_observation_id"):
            downstream_key = _observation_key(
                "reporter_observation",
                _clean(row.get("downstream_reporter_observation_id"), 128),
            )
        if downstream_key not in by_key:
            continue

        upstream_type = ""
        upstream_id = ""
        resolved_keys: list[str] = []
        if row.get("upstream_source_observation_id"):
            upstream_type = "source_observation"
            upstream_id = _clean(row.get("upstream_source_observation_id"), 128)
            candidate = _observation_key(upstream_type, upstream_id)
            if candidate in by_key:
                resolved_keys = [candidate]
        elif row.get("upstream_reporter_observation_id"):
            upstream_type = "reporter_observation"
            upstream_id = _clean(row.get("upstream_reporter_observation_id"), 128)
            candidate = _observation_key(upstream_type, upstream_id)
            if candidate in by_key:
                resolved_keys = [candidate]
        elif row.get("upstream_source_id"):
            upstream_type = "source"
            upstream_id = _clean(row.get("upstream_source_id"), 128)
            resolved_keys = list(by_source.get(upstream_id, ()))
        elif row.get("upstream_reporter_id"):
            upstream_type = "reporter"
            upstream_id = _clean(row.get("upstream_reporter_id"), 128)
            resolved_keys = list(by_reporter.get(upstream_id, ()))

        pair_keys: list[list[str]] = []
        for upstream_key in sorted(set(resolved_keys)):
            if upstream_key == downstream_key:
                continue
            pair = _pair(downstream_key, upstream_key)
            dependency_pairs.add(pair)
            pair_keys.append(list(pair))

        edges.append(
            {
                "dependency_id": _clean(row.get("id"), 128),
                "downstream_observation_key": downstream_key,
                "upstream_target_type": upstream_type,
                "upstream_target_id": upstream_id,
                "relationship_type": _clean(
                    row.get("relationship_type"), 64
                ).casefold(),
                "confidence": row.get("confidence"),
                "observed_at": _clean(row.get("observed_at"), 128),
                "linked_observation_pairs": pair_keys,
            }
        )

    return edges, dependency_pairs


def _independence_rows(
    *,
    source_ids: list[str],
    reporter_ids: list[str],
    connection_factory,
) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}

    for kind, values in (("source", source_ids), ("reporter", reporter_ids)):
        for chunk in _chunks(values):
            if not chunk:
                continue
            placeholders = ",".join("?" for _ in chunk)
            columns = (
                (
                    "observation_a_source_observation_id",
                    "observation_b_source_observation_id",
                )
                if kind == "source"
                else (
                    "observation_a_reporter_observation_id",
                    "observation_b_reporter_observation_id",
                )
            )
            conn = connection_factory()
            try:
                rows = conn.execute(
                    """
                    SELECT
                      a.*,
                      e.evidence_type AS provenance_evidence_type,
                      e.verification_status AS provenance_evidence_verification_status,
                      e.observed_at AS provenance_evidence_observed_at
                    FROM observation_independence_assertions AS a
                    LEFT JOIN evidence_records AS e
                      ON e.id = a.provenance_evidence_id
                    WHERE """
                    + columns[0]
                    + f" IN ({placeholders}) OR "
                    + columns[1]
                    + f" IN ({placeholders}) ORDER BY a.observed_at, a.id",
                    tuple(chunk) + tuple(chunk),
                ).fetchall()
            finally:
                conn.close()
            for row in rows:
                item = dict(row)
                results[_clean(item.get("id"), 128)] = item

    return [results[key] for key in sorted(results)]


def _endpoint(row: dict[str, Any], side: str) -> str:
    source = _clean(row.get(f"observation_{side}_source_observation_id"), 128)
    if source:
        return _observation_key("source_observation", source)
    reporter = _clean(
        row.get(f"observation_{side}_reporter_observation_id"), 128
    )
    if reporter:
        return _observation_key("reporter_observation", reporter)
    return ""


def _independence_graph(
    *,
    nodes: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    dependency_pairs: set[tuple[str, str]],
) -> tuple[list[dict[str, Any]], list[list[str]], list[dict[str, Any]], int]:
    node_keys = {item["key"] for item in nodes}
    assertions: list[dict[str, Any]] = []
    qualified_pairs: set[tuple[str, str]] = set()
    conflicts: list[dict[str, Any]] = []
    verification_gap_count = 0

    for row in rows:
        left = _endpoint(row, "a")
        right = _endpoint(row, "b")
        if not left or not right or left not in node_keys or right not in node_keys:
            continue

        pair = _pair(left, right)
        assertion_status = _clean(row.get("verification_status"), 64).casefold()
        evidence_status = _clean(
            row.get("provenance_evidence_verification_status"), 64
        ).casefold()
        assertion_verified = assertion_status == "verified"
        evidence_verified = evidence_status == "verified"
        qualified = assertion_verified and evidence_verified
        verification_gap = assertion_verified and not evidence_verified
        if qualified:
            qualified_pairs.add(pair)
        if verification_gap:
            verification_gap_count += 1

        conflict = assertion_verified and pair in dependency_pairs
        item = {
            "assertion_id": _clean(row.get("id"), 128),
            "observation_pair": list(pair),
            "verification_status": assertion_status,
            "confidence": row.get("confidence"),
            "observed_at": _clean(row.get("observed_at"), 128),
            "provenance_evidence": {
                "evidence_id": _clean(row.get("provenance_evidence_id"), 128),
                "evidence_type": _clean(
                    row.get("provenance_evidence_type"), 64
                ),
                "verification_status": evidence_status,
                "observed_at": _clean(
                    row.get("provenance_evidence_observed_at"), 128
                ),
            },
            "qualified_verified_independence": qualified,
            "verification_gap": verification_gap,
            "dependency_conflict": conflict,
        }
        assertions.append(item)
        if conflict:
            conflicts.append(
                {
                    "observation_pair": list(pair),
                    "assertion_id": item["assertion_id"],
                    "reason": "verified_independence_assertion_conflicts_with_recorded_dependency",
                    "provenance_evidence_verified": evidence_verified,
                }
            )

    return (
        sorted(assertions, key=lambda item: item["assertion_id"]),
        [list(pair) for pair in sorted(qualified_pairs)],
        conflicts,
        verification_gap_count,
    )


def _graph_id(*parts: str) -> str:
    payload = "|".join(parts)
    return "structural:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _metadata(value: Any, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _integrity_error(
            label + " metadata is invalid."
        ) from exc
    if not isinstance(parsed, dict):
        raise _integrity_error(
            label + " metadata is invalid."
        )
    return dict(parsed)


def _timestamp(value: Any, *, label: str, optional: bool = False) -> str:
    text = _clean(value, 128)
    if optional and not text:
        return ""
    try:
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
        offset = parsed.utcoffset()
    except (TypeError, ValueError, OverflowError) as exc:
        raise _integrity_error(
            label + " timestamp is invalid."
        ) from exc
    if offset is None:
        raise _integrity_error(
            label + " timestamp must include a timezone."
        )
    return text


def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _relationship_class(value: Any) -> str:
    relationship = _clean(value, 64).casefold()
    if relationship in _CANONICAL_CLAIM_RELATIONSHIPS:
        return "canonical"
    if relationship in _SUPPORT_ALIASES or relationship in _CONFLICT_ALIASES:
        return "recognized_aggregation_alias"
    return "unrecognized"


def _bounded_rows(conn, sql: str, params: tuple[Any, ...], limit: int):
    rows = [dict(row) for row in conn.execute(sql, params + (limit + 1,)).fetchall()]
    return rows[:limit], len(rows) > limit


def _cycle_nodes(adjacency: dict[str, set[str]]) -> set[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    cyclic: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = stack.index(node)
            cyclic.update(stack[start:])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for target in sorted(adjacency.get(node, ())):
            visit(target)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(adjacency):
        visit(node)
    return cyclic


def _claim_scope(conn, claim_id: str, fallback_claim: dict[str, Any]):
    if not _table_exists(conn, "claim_identity_mappings"):
        return fallback_claim, []
    from app.story import story_claim_graph_materialization as story_graph

    claim = story_graph._validated_structured_claim(conn, claim_id)
    mapping_rows = [dict(row) for row in conn.execute(
        "SELECT * FROM claim_identity_mappings "
        "WHERE canonical_claim_id=? OR production_claim_id=? "
        "ORDER BY production_claim_id",
        (claim_id, claim_id),
    ).fetchall()]
    if any(_clean(row.get("production_claim_id"), 128) == claim_id for row in mapping_rows):
        raise _integrity_error(
            "A canonical structured claim cannot act as a legacy mapping source."
        )
    direct_rows = [
        row for row in mapping_rows
        if _clean(row.get("canonical_claim_id"), 128) == claim_id
    ]
    legacy_ids = sorted(_clean(row.get("production_claim_id"), 128) for row in direct_rows)
    if any(
        not legacy_id
        or _clean(row.get("mapping_status"), 64) != "verified_equivalent"
        or _clean(row.get("subject_key"), 256) != _clean(claim.get("subject_key"), 256)
        for legacy_id, row in zip(legacy_ids, direct_rows)
    ):
        raise _integrity_error("Claim identity mapping is malformed or unverified.")
    if not legacy_ids:
        return claim, []
    marks = ",".join("?" for _ in legacy_ids)
    legacy_claims = [dict(row) for row in conn.execute(
        f"SELECT * FROM intelligence_claims WHERE id IN ({marks}) ORDER BY id",
        tuple(legacy_ids),
    ).fetchall()]
    if len(legacy_claims) != len(legacy_ids) or any(
        _clean(row.get("subject_key"), 256) != _clean(claim.get("subject_key"), 256)
        for row in legacy_claims
    ):
        raise _integrity_error("Verified legacy claim subject is inconsistent.")
    for row in legacy_claims:
        metadata = _metadata(row.get("metadata_json"), label="Legacy claim")
        if isinstance(metadata.get("structured_claim"), dict):
            raise _integrity_error(
                "A canonical structured claim cannot act as a legacy mapping source."
            )
    if conn.execute(
        f"SELECT 1 FROM claim_identity_mappings "
        f"WHERE canonical_claim_id IN ({marks}) LIMIT 1",
        tuple(legacy_ids),
    ).fetchone() is not None:
        raise _integrity_error("Claim identity mapping chain or cycle is not allowed.")
    return claim, legacy_ids


def _rows_by_ids(conn, table: str, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(sorted(set(ids))):
        if not chunk:
            continue
        marks = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"SELECT * FROM {table} WHERE id IN ({marks}) ORDER BY id",
            tuple(chunk),
        ).fetchall():
            item = dict(row)
            result[_clean(item.get("id"), 128)] = item
    return result


def _build_evidence_graph(*, claim: dict[str, Any], claim_id: str, connection_factory):
    conn = connection_factory()
    try:
        canonical_claim, legacy_ids = _claim_scope(conn, claim_id, claim)
        subject_key = _clean(canonical_claim.get("subject_key"), 256)
        scope_ids = [claim_id, *legacy_ids]
        placeholders = ",".join("?" for _ in scope_ids)
        all_link_rows = [dict(row) for row in conn.execute(
            f"SELECT * FROM claim_links WHERE claim_id IN ({placeholders}) "
            "ORDER BY observed_at, id",
            tuple(scope_ids),
        ).fetchall()]
        claim_links_truncated = len(all_link_rows) > _GRAPH_LIMITS["claim_links"]
        link_rows = all_link_rows[:_GRAPH_LIMITS["claim_links"]]

        all_target_ids = {"source_observation": set(), "reporter_observation": set(), "evidence": set()}
        anomalies: list[dict[str, Any]] = []
        for row in all_link_rows:
            active = [
                ("source_observation", _clean(row.get("source_observation_id"), 128)),
                ("reporter_observation", _clean(row.get("reporter_observation_id"), 128)),
                ("evidence", _clean(row.get("evidence_id"), 128)),
            ]
            active = [(kind, value) for kind, value in active if value]
            if len(active) != 1:
                raise _integrity_error(
                    "Claim link target cardinality is invalid."
                )
            all_target_ids[active[0][0]].add(active[0][1])
            _metadata(row.get("metadata_json"), label="Claim link")
            _timestamp(row.get("observed_at"), label="Claim link")
            _timestamp(row.get("recorded_at"), label="Claim link")

        all_rows_by_kind = {
            kind: _rows_by_ids(conn, table, all_target_ids[kind])
            for kind, table in (
                ("source_observation", "source_observations"),
                ("reporter_observation", "reporter_observations"),
                ("evidence", "evidence_records"),
            )
        }
        for kind in all_target_ids:
            if set(all_rows_by_kind[kind]) != all_target_ids[kind]:
                raise _integrity_error("Claim link target is missing.")
            for row in all_rows_by_kind[kind].values():
                if _clean(row.get("subject_key"), 256) != subject_key:
                    raise _integrity_error(
                        "Claim-linked graph target subject is inconsistent."
                    )
                _metadata(row.get("metadata_json"), label="Claim graph target")
                _timestamp(row.get("observed_at"), label="Claim graph target")
                _timestamp(row.get("recorded_at"), label="Claim graph target")

        retained_target_ids = {
            "source_observation": set(), "reporter_observation": set(), "evidence": set()
        }
        for row in link_rows:
            for kind, column in (
                ("source_observation", "source_observation_id"),
                ("reporter_observation", "reporter_observation_id"),
                ("evidence", "evidence_id"),
            ):
                target_id = _clean(row.get(column), 128)
                if target_id:
                    retained_target_ids[kind].add(target_id)

        rows_by_kind: dict[str, dict[str, dict[str, Any]]] = {}
        combined_observation_ids = sorted(
            [("source_observation", value) for value in retained_target_ids["source_observation"]]
            + [("reporter_observation", value) for value in retained_target_ids["reporter_observation"]]
        )
        observations_truncated = len(combined_observation_ids) > _GRAPH_LIMITS["observations"]
        retained_observations = set(combined_observation_ids[:_GRAPH_LIMITS["observations"]])
        for kind in ("source_observation", "reporter_observation"):
            rows_by_kind[kind] = {
                record_id: all_rows_by_kind[kind][record_id]
                for record_kind, record_id in retained_observations
                if record_kind == kind
            }
        evidence_ids_eligible = sorted(retained_target_ids["evidence"])
        evidence_truncated = len(evidence_ids_eligible) > _GRAPH_LIMITS["evidence_records"]
        evidence_ids_retained = evidence_ids_eligible[:_GRAPH_LIMITS["evidence_records"]]
        rows_by_kind["evidence"] = {
            record_id: all_rows_by_kind["evidence"][record_id]
            for record_id in evidence_ids_retained
        }

        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        claim_node_id = "claim:" + claim_id
        nodes[claim_node_id] = {
            "id": claim_node_id, "node_type": "claim", "claim_id": claim_id,
            "canonical_key": _clean(canonical_claim.get("canonical_key")),
            "subject_key": subject_key,
            "canonical_text": _clean(canonical_claim.get("canonical_text"), 1000),
            "claim_type": _clean(canonical_claim.get("claim_type"), 64),
        }

        actor_ids = {"source": set(), "reporter": set(), "media": set(), "story": set()}
        for kind in ("source_observation", "reporter_observation"):
            for record_id, row in rows_by_kind[kind].items():
                if _clean(row.get("subject_key"), 256) != subject_key:
                    raise _integrity_error(
                        "Claim-linked observation subject is inconsistent."
                    )
                metadata = _metadata(row.get("metadata_json"), label="Observation")
                observed_at = _timestamp(row.get("observed_at"), label="Observation")
                recorded_at = _timestamp(row.get("recorded_at"), label="Observation")
                node_id = kind + ":" + record_id
                source_id = _clean(row.get("source_id"), 128)
                reporter_id = _clean(row.get("reporter_id"), 128)
                media_id = _clean(row.get("media_item_id"), 128)
                story_id = _clean(row.get("story_id"), 128)
                nodes[node_id] = {
                    "id": node_id, "node_type": kind, "observation_id": record_id,
                    "observation_type": _clean(row.get("observation_type"), 64),
                    "subject_key": subject_key, "source_id": source_id or None,
                    "reporter_id": reporter_id or None, "media_item_id": media_id or None,
                    "story_id": story_id or None, "claim_summary": _clean(row.get("claim_summary"), 2000),
                    "provenance_url": _clean(row.get("provenance_url"), 2048),
                    "status": _clean(row.get("status"), 64), "confidence": row.get("confidence"),
                    "observed_at": observed_at, "recorded_at": recorded_at, "metadata": metadata,
                }
                for actor_kind, actor_id, relationship in (
                    ("source", source_id, "observed_by_source"),
                    ("reporter", reporter_id, "observed_by_reporter"),
                    ("media", media_id, "reported_in_media"),
                    ("story", story_id, "associated_exact_story"),
                ):
                    if not actor_id:
                        continue
                    actor_ids[actor_kind].add(actor_id)
                    target = actor_kind + ":" + actor_id
                    edge_id = _graph_id("context", relationship, node_id, target)
                    edges.append({"id": edge_id, "edge_category": "structural_context", "relationship_type": relationship, "source": node_id, "target": target, "persisted": False})

        for evidence_id, row in rows_by_kind["evidence"].items():
            if _clean(row.get("subject_key"), 256) != subject_key:
                raise _integrity_error(
                    "Claim-linked evidence subject is inconsistent."
                )
            evidence_type = _clean(row.get("evidence_type"), 64).casefold()
            node_id = "evidence:" + evidence_id
            nodes[node_id] = {
                "id": node_id, "node_type": "evidence", "evidence_id": evidence_id,
                "evidence_key": _clean(row.get("evidence_key"), 256),
                "evidence_type": evidence_type,
                "recognized_evidence_type": evidence_type in _RECOGNIZED_EVIDENCE_TYPES,
                "subject_key": subject_key, "claim_summary": _clean(row.get("claim_summary"), 2000),
                "canonical_url": _clean(row.get("canonical_url"), 2048),
                "reference_key": _clean(row.get("reference_key"), 512),
                "verification_status": _clean(row.get("verification_status"), 64).casefold(),
                "published_at": _timestamp(row.get("published_at"), label="Evidence publication", optional=True),
                "observed_at": _timestamp(row.get("observed_at"), label="Evidence"),
                "recorded_at": _timestamp(row.get("recorded_at"), label="Evidence"),
                "metadata": _metadata(row.get("metadata_json"), label="Evidence"),
            }
            if evidence_type not in _RECOGNIZED_EVIDENCE_TYPES:
                anomalies.append({"anomaly_type": "unrecognized_evidence_type", "stable_id": evidence_id, "evidence_type": evidence_type})

        semantic_counts = defaultdict(int)
        for row in link_rows:
            active = [(kind, _clean(row.get(column), 128)) for kind, column in (
                ("source_observation", "source_observation_id"),
                ("reporter_observation", "reporter_observation_id"), ("evidence", "evidence_id"),
            ) if _clean(row.get(column), 128)]
            kind, target_id = active[0]
            target_node = kind + ":" + target_id
            if target_node not in nodes:
                continue
            relationship = _clean(row.get("relationship_type"), 64).casefold()
            classification = _relationship_class(relationship)
            metadata = _metadata(row.get("metadata_json"), label="Claim link")
            edge_id = _clean(row.get("id"), 128)
            edges.append({
                "id": "claim_link:" + edge_id, "persisted_id": edge_id,
                "edge_category": "claim_link", "relationship_type": relationship,
                "relationship_classification": classification, "source": claim_node_id,
                "target": target_node, "target_type": kind, "target_id": target_id,
                "confidence": row.get("confidence"),
                "observed_at": _timestamp(row.get("observed_at"), label="Claim link"),
                "recorded_at": _timestamp(row.get("recorded_at"), label="Claim link"),
                "metadata": metadata, "source_claim_id": _clean(row.get("claim_id"), 128),
                "legacy_scoped": _clean(row.get("claim_id"), 128) != claim_id,
            })
            if classification == "canonical": semantic_counts[relationship] += 1
            elif classification == "unrecognized":
                anomalies.append({"anomaly_type": "unrecognized_claim_relationship", "stable_id": edge_id, "relationship_type": relationship})

        evidence_ids = sorted(rows_by_kind["evidence"])
        all_evidence_link_rows: list[dict[str, Any]] = []
        for chunk in _chunks(sorted(all_target_ids["evidence"])):
            if not chunk:
                continue
            marks = ",".join("?" for _ in chunk)
            all_evidence_link_rows.extend(
                dict(row) for row in conn.execute(
                    f"SELECT * FROM evidence_links WHERE evidence_id IN ({marks}) "
                    "ORDER BY linked_at, id",
                    tuple(chunk),
                ).fetchall()
            )
        all_evidence_link_rows.sort(
            key=lambda row: (_clean(row.get("linked_at"), 128), _clean(row.get("id"), 128))
        )
        all_evidence_context_ids = {kind: set() for kind in ("media", "story", "source", "reporter")}
        for row in all_evidence_link_rows:
            active = [(kind, _clean(row.get(column), 128)) for kind, column in (
                ("media", "media_item_id"), ("story", "story_id"),
                ("source", "source_id"), ("reporter", "reporter_id"),
            ) if _clean(row.get(column), 128)]
            if len(active) != 1:
                raise _integrity_error("Evidence link target cardinality is invalid.")
            all_evidence_context_ids[active[0][0]].add(active[0][1])
            _metadata(row.get("metadata_json"), label="Evidence link")
            _timestamp(row.get("linked_at"), label="Evidence link")
        for kind, table in (
            ("media", "media_items"), ("story", "intelligence_stories"),
            ("source", "intelligence_sources"), ("reporter", "intelligence_reporters"),
        ):
            if set(_rows_by_ids(conn, table, all_evidence_context_ids[kind])) != all_evidence_context_ids[kind]:
                raise _integrity_error(kind.capitalize() + " graph target is missing.")
        eligible_evidence_link_rows = [
            row for row in all_evidence_link_rows
            if _clean(row.get("evidence_id"), 128) in evidence_ids
        ]
        evidence_links_truncated = len(eligible_evidence_link_rows) > _GRAPH_LIMITS["evidence_links"]
        evidence_link_rows = eligible_evidence_link_rows[:_GRAPH_LIMITS["evidence_links"]]
        for row in evidence_link_rows:
            active = [(kind, _clean(row.get(column), 128)) for kind, column in (
                ("media", "media_item_id"), ("story", "story_id"),
                ("source", "source_id"), ("reporter", "reporter_id"),
            ) if _clean(row.get(column), 128)]
            if len(active) != 1:
                raise _integrity_error(
                    "Evidence link target cardinality is invalid."
                )
            kind, target_id = active[0]
            actor_ids[kind].add(target_id)
            link_id = _clean(row.get("id"), 128)
            edges.append({
                "id": "evidence_link:" + link_id, "persisted_id": link_id,
                "edge_category": "evidence_context", "relationship_type": _clean(row.get("relationship_type"), 64).casefold(),
                "source": "evidence:" + _clean(row.get("evidence_id"), 128),
                "target": kind + ":" + target_id, "target_type": kind, "target_id": target_id,
                "confidence": row.get("confidence"), "linked_at": _timestamp(row.get("linked_at"), label="Evidence link"),
                "metadata": _metadata(row.get("metadata_json"), label="Evidence link"),
            })
            if _clean(row.get("relationship_type"), 64).casefold() not in _RECOGNIZED_EVIDENCE_LINK_RELATIONSHIPS:
                anomalies.append({
                    "anomaly_type": "unrecognized_evidence_link_relationship",
                    "stable_id": link_id,
                    "relationship_type": _clean(row.get("relationship_type"), 64).casefold(),
                })

        table_by_actor = {"source": "intelligence_sources", "reporter": "intelligence_reporters", "media": "media_items", "story": "intelligence_stories"}
        expected_story_id = ""
        if actor_ids["story"] and _table_exists(conn, "claim_identity_mappings"):
            from app.intelligence import reporting_coverage

            expected_story = reporting_coverage._validated_story(
                conn, claim=canonical_claim
            )
            expected_story_id = _clean(expected_story.get("id"), 128)
            if actor_ids["story"] != {expected_story_id}:
                raise _integrity_error(
                    "Exact story identity is outside canonical claim scope."
                )
        story_claims: dict[str, set[str]] = defaultdict(set)
        if actor_ids["story"]:
            story_marks = ",".join("?" for _ in actor_ids["story"])
            for row in conn.execute(
                f"SELECT story_id, claim_id FROM story_claim_links "
                f"WHERE story_id IN ({story_marks}) ORDER BY story_id, claim_id",
                tuple(sorted(actor_ids["story"])),
            ).fetchall():
                story_claims[_clean(row["story_id"], 128)].add(
                    _clean(row["claim_id"], 128)
                )
        for kind, table in table_by_actor.items():
            ids = sorted(actor_ids[kind])
            if not ids: continue
            marks = ",".join("?" for _ in ids)
            loaded = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE id IN ({marks}) ORDER BY id", tuple(ids)).fetchall()]
            found = {_clean(row.get("id"), 128) for row in loaded}
            if set(ids) != found:
                raise _integrity_error(kind.capitalize() + " graph target is missing.")
            for row in loaded:
                record_id = _clean(row.get("id"), 128)
                metadata = _metadata(row.get("metadata_json"), label=kind.capitalize())
                node = {"id": kind + ":" + record_id, "node_type": kind, kind + "_id": record_id, "metadata": metadata}
                for field in ("source_key", "identity_key", "display_name", "source_type", "canonical_domain", "canonical_url", "mode", "title", "reporter_id", "canonical_key", "canonical_title", "status"):
                    if field in row.keys(): node[field] = row.get(field)
                nodes[node["id"]] = node
                if kind == "story":
                    if not story_claims[record_id].intersection(scope_ids):
                        raise _integrity_error("Exact story claim provenance is inconsistent.")
                    if expected_story_id and record_id != expected_story_id:
                        raise _integrity_error("Exact story identity is inconsistent.")

        observation_keys = sorted(node_id for node_id, node in nodes.items() if node["node_type"] in {"source_observation", "reporter_observation"})
        observation_ids = [item.split(":", 1)[1] for item in observation_keys]
        dependency_rows = []
        dependency_eligible_count = 0
        dependency_truncated = False
        assertion_rows = []
        independence_eligible_count = 0
        independence_truncated = False
        if observation_ids:
            marks = ",".join("?" for _ in observation_ids)
            params = tuple(observation_ids) * 4
            dependency_where = "downstream_source_observation_id IN ("+marks+") OR downstream_reporter_observation_id IN ("+marks+") OR upstream_source_observation_id IN ("+marks+") OR upstream_reporter_observation_id IN ("+marks+")"
            assertion_where = "observation_a_source_observation_id IN ("+marks+") OR observation_a_reporter_observation_id IN ("+marks+") OR observation_b_source_observation_id IN ("+marks+") OR observation_b_reporter_observation_id IN ("+marks+")"
            dependency_eligible_count = int(conn.execute(
                "SELECT COUNT(*) FROM observation_dependencies WHERE " + dependency_where,
                params,
            ).fetchone()[0])
            independence_eligible_count = int(conn.execute(
                "SELECT COUNT(*) FROM observation_independence_assertions WHERE " + assertion_where,
                params,
            ).fetchone()[0])
            dependency_rows, dependency_truncated = _bounded_rows(
                conn, "SELECT * FROM observation_dependencies WHERE "+dependency_where+" ORDER BY observed_at,id LIMIT ?",
                params, _GRAPH_LIMITS["dependency_records"],
            )
            assertion_rows, independence_truncated = _bounded_rows(
                conn, "SELECT a.*,e.verification_status AS provenance_status,e.subject_key AS provenance_subject_key,e.observed_at AS provenance_observed_at,e.recorded_at AS provenance_recorded_at,e.metadata_json AS provenance_metadata_json FROM observation_independence_assertions a LEFT JOIN evidence_records e ON e.id=a.provenance_evidence_id WHERE "+assertion_where+" ORDER BY a.observed_at,a.id LIMIT ?",
                params, _GRAPH_LIMITS["independence_assertions"],
            )

        dependency_pairs: set[tuple[str, str]] = set()
        blocked_pairs: set[tuple[str, str]] = set()
        blocked_observations: set[str] = set()
        adjacency: dict[str, set[str]] = defaultdict(set)
        qualified_dependency_count = 0
        potential_dependency_count = 0
        by_source = defaultdict(list); by_reporter = defaultdict(list)
        for key in observation_keys:
            node = nodes[key]
            if node.get("source_id"): by_source[node["source_id"]].append(key)
            if node.get("reporter_id"): by_reporter[node["reporter_id"]].append(key)
        dependency_actor_ids = {
            "source": {
                _clean(row.get("upstream_source_id"), 128)
                for row in dependency_rows if _clean(row.get("upstream_source_id"), 128)
            },
            "reporter": {
                _clean(row.get("upstream_reporter_id"), 128)
                for row in dependency_rows if _clean(row.get("upstream_reporter_id"), 128)
            },
        }
        dependency_actors = {
            "source": _rows_by_ids(conn, "intelligence_sources", dependency_actor_ids["source"]),
            "reporter": _rows_by_ids(conn, "intelligence_reporters", dependency_actor_ids["reporter"]),
        }
        for actor_kind in ("source", "reporter"):
            for actor_id, actor in dependency_actors[actor_kind].items():
                node_id = actor_kind + ":" + actor_id
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id, "node_type": actor_kind,
                        actor_kind + "_id": actor_id,
                        "metadata": _metadata(actor.get("metadata_json"), label=actor_kind.capitalize()),
                        "display_name": actor.get("display_name"),
                    }
        for row in dependency_rows:
            dep_id = _clean(row.get("id"), 128)
            downstream_values = [
                ("source_observation", _clean(row.get("downstream_source_observation_id"), 128)),
                ("reporter_observation", _clean(row.get("downstream_reporter_observation_id"), 128)),
            ]
            active_downstream = [(kind, value) for kind, value in downstream_values if value]
            downstream = (
                active_downstream[0][0] + ":" + active_downstream[0][1]
                if len(active_downstream) == 1 else ""
            )
            upstream_values = [
                ("source_observation", _clean(row.get("upstream_source_observation_id"), 128)),
                ("reporter_observation", _clean(row.get("upstream_reporter_observation_id"), 128)),
                ("source", _clean(row.get("upstream_source_id"), 128)),
                ("reporter", _clean(row.get("upstream_reporter_id"), 128)),
            ]
            active_upstream = [(kind, value) for kind, value in upstream_values if value]
            upstream_kind, upstream_id = active_upstream[0] if len(active_upstream) == 1 else ("", "")
            persisted_target = upstream_kind + ":" + upstream_id if upstream_kind else ""
            resolved_observations = []
            if upstream_kind in {"source_observation", "reporter_observation"}:
                if persisted_target in nodes:
                    resolved_observations = [persisted_target]
            elif upstream_kind == "source":
                resolved_observations = list(by_source.get(upstream_id, ()))
            elif upstream_kind == "reporter":
                resolved_observations = list(by_reporter.get(upstream_id, ()))
            relationship = _clean(row.get("relationship_type"), 64).casefold()
            recognized = relationship in OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY
            dependency_metadata = _metadata(row.get("metadata_json"), label="Dependency")
            dependency_observed_at = _timestamp(row.get("observed_at"), label="Dependency")
            dependency_recorded_at = _timestamp(row.get("recorded_at"), label="Dependency")
            target_exists = bool(
                persisted_target in nodes
                if upstream_kind in {"source_observation", "reporter_observation", "source", "reporter"}
                else False
            )
            cardinality_valid = len(active_downstream) == 1 and len(active_upstream) == 1
            structurally_valid = cardinality_valid and downstream in nodes and target_exists and persisted_target != downstream
            pair_resolved = len(resolved_observations) == 1 and resolved_observations[0] != downstream
            if structurally_valid and recognized:
                qualified_dependency_count += 1
                edge = {"id": "dependency:"+dep_id, "persisted_id": dep_id, "edge_category": "observation_dependency", "relationship_type": relationship, "source": downstream, "target": persisted_target, "upstream_target_type": upstream_kind, "upstream_target_id": upstream_id, "direct_only": True, "confidence": row.get("confidence"), "observed_at": dependency_observed_at, "recorded_at": dependency_recorded_at, "metadata": dependency_metadata, "linked_observation_pairs": []}
                if pair_resolved:
                    pair_target = resolved_observations[0]
                    pair = _pair(downstream, pair_target)
                    dependency_pairs.add(pair)
                    adjacency[downstream].add(pair_target)
                    edge["linked_observation_pairs"] = [list(pair)]
                elif upstream_kind in {"source", "reporter"}:
                    blocked_observations.add(downstream)
                    potential_dependency_count += 1
                    anomalies.append({"anomaly_type": "unresolved_actor_dependency", "stable_id": dep_id, "matching_observation_keys": sorted(resolved_observations)})
                edges.append(edge)
            else:
                potential_dependency_count += 1
                if downstream in nodes:
                    blocked_observations.add(downstream)
                if len(active_downstream) != 1:
                    blocked_observations.update(
                        kind + ":" + value
                        for kind, value in active_downstream
                        if kind + ":" + value in nodes
                    )
                for target in resolved_observations:
                    if downstream in nodes and target in nodes and downstream != target:
                        blocked_pairs.add(_pair(downstream, target))
                anomalies.append({"anomaly_type": "potential_or_malformed_dependency", "stable_id": dep_id, "relationship_type": relationship, "relationship_recognized": recognized, "downstream_cardinality": len(active_downstream), "upstream_cardinality": len(active_upstream)})

        cyclic = _cycle_nodes(adjacency)
        if cyclic:
            blocked_observations.update(cyclic)
            for pair in dependency_pairs:
                if pair[0] in cyclic or pair[1] in cyclic: blocked_pairs.add(pair)
            anomalies.append({"anomaly_type": "dependency_cycle", "stable_id": "|".join(sorted(cyclic)), "observation_keys": sorted(cyclic)})

        graph_assertions = []
        verified_pairs = []
        graph_conflicts = []
        from app.story.story_claim_graph_materialization import (
            StoryClaimGraphMaterializationIntegrityError,
        )
        incomplete = any((
            claim_links_truncated, observations_truncated, evidence_truncated,
            evidence_links_truncated, dependency_truncated, independence_truncated,
        ))
        for row in assertion_rows:
            assertion_id = _clean(row.get("id"), 128)
            left_values = [
                ("source_observation", _clean(row.get("observation_a_source_observation_id"), 128)),
                ("reporter_observation", _clean(row.get("observation_a_reporter_observation_id"), 128)),
            ]
            right_values = [
                ("source_observation", _clean(row.get("observation_b_source_observation_id"), 128)),
                ("reporter_observation", _clean(row.get("observation_b_reporter_observation_id"), 128)),
            ]
            active_left = [(kind, value) for kind, value in left_values if value]
            active_right = [(kind, value) for kind, value in right_values if value]
            left = active_left[0][0] + ":" + active_left[0][1] if len(active_left) == 1 else ""
            right = active_right[0][0] + ":" + active_right[0][1] if len(active_right) == 1 else ""
            pair = _pair(left, right) if left and right else (left, right)
            assertion_metadata_valid = True
            assertion_timestamps_valid = True
            try:
                assertion_metadata = _metadata(row.get("metadata_json"), label="Independence assertion")
            except StoryClaimGraphMaterializationIntegrityError:
                assertion_metadata = {}
                assertion_metadata_valid = False
            try:
                assertion_observed_at = _timestamp(row.get("observed_at"), label="Independence assertion")
                assertion_recorded_at = _timestamp(row.get("recorded_at"), label="Independence assertion")
            except StoryClaimGraphMaterializationIntegrityError:
                assertion_observed_at = _clean(row.get("observed_at"), 128)
                assertion_recorded_at = _clean(row.get("recorded_at"), 128)
                assertion_timestamps_valid = False
            endpoints_valid = len(active_left) == 1 and len(active_right) == 1
            in_scope = endpoints_valid and left in nodes and right in nodes and left != right
            distinct = bool(in_scope and nodes[left].get("source_id") and nodes[right].get("source_id") and nodes[left]["source_id"] != nodes[right]["source_id"])
            verification_status = _clean(row.get("verification_status"), 64).casefold()
            verification_recognized = verification_status in {"verified", "unverified"}
            assertion_verified = verification_status == "verified"
            provenance_exists = bool(_clean(row.get("provenance_status"), 64))
            provenance_verified = provenance_exists and _clean(row.get("provenance_status"), 64).casefold() == "verified"
            provenance_valid = provenance_exists
            if provenance_exists:
                try:
                    _metadata(row.get("provenance_metadata_json"), label="Independence provenance evidence")
                    _timestamp(row.get("provenance_observed_at"), label="Independence provenance evidence")
                    _timestamp(row.get("provenance_recorded_at"), label="Independence provenance evidence")
                except StoryClaimGraphMaterializationIntegrityError:
                    provenance_valid = False
                if _clean(row.get("provenance_subject_key"), 256) != subject_key:
                    provenance_valid = False
            conflict = pair in dependency_pairs
            blocker = pair in blocked_pairs or left in blocked_observations or right in blocked_observations or incomplete
            structurally_valid = endpoints_valid and in_scope and assertion_metadata_valid and assertion_timestamps_valid and verification_recognized and provenance_valid
            qualified = structurally_valid and assertion_verified and provenance_verified and distinct and not conflict and not blocker
            if not structurally_valid:
                anomalies.append({"anomaly_type": "malformed_independence_assertion", "stable_id": assertion_id, "endpoints_valid": endpoints_valid, "endpoints_in_scope": in_scope, "metadata_valid": assertion_metadata_valid, "timestamps_valid": assertion_timestamps_valid, "verification_recognized": verification_recognized, "provenance_evidence_exists": provenance_exists, "provenance_evidence_valid": provenance_valid})
            item = {"assertion_id": assertion_id, "observation_pair": list(pair), "verification_status": verification_status, "provenance_evidence_id": _clean(row.get("provenance_evidence_id"),128), "provenance_evidence_verified": provenance_verified, "qualified_verified_independence": qualified, "dependency_conflict": conflict, "potential_dependency_blocker": blocker, "structurally_valid": structurally_valid, "observed_at": assertion_observed_at, "recorded_at": assertion_recorded_at, "metadata": assertion_metadata}
            graph_assertions.append(item)
            if qualified: verified_pairs.append(list(pair))
            if conflict: graph_conflicts.append({"assertion_id": assertion_id, "observation_pair": list(pair)})

        truncated_categories = [name for name, value in (
            ("claim_links", claim_links_truncated), ("observations", observations_truncated),
            ("evidence_records", evidence_truncated), ("evidence_links", evidence_links_truncated),
            ("dependency_records", dependency_truncated), ("independence_assertions", independence_truncated),
        ) if value]
        ordered_nodes = sorted(nodes.values(), key=lambda item: (item["node_type"], item["id"]))
        edges.sort(key=lambda item: (item["edge_category"], item["source"], item["target"], item["id"]))
        anomalies.sort(key=lambda item: (item["anomaly_type"], item["stable_id"]))
        counts_by_type = defaultdict(int)
        for node in ordered_nodes: counts_by_type[node["node_type"]] += 1
        return {
            "evidence_graph_version": CLAIM_EVIDENCE_GRAPH_VERSION,
            "nodes": ordered_nodes, "edges": edges, "anomalies": anomalies,
            "graph_independence_assertions": sorted(graph_assertions, key=lambda item: item["assertion_id"]),
            "graph_verified_independent_pairs": sorted(verified_pairs),
            "graph_summary": {
                "claim_links_eligible": len(all_link_rows),
                "claim_link_count": sum(edge["edge_category"] == "claim_link" for edge in edges),
                "report_edge_count": semantic_counts["reports"], "support_edge_count": semantic_counts["supports"],
                "contradiction_edge_count": semantic_counts["contradicts"], "aligned_edge_count": semantic_counts["aligned_to"],
                "evidence_node_count": counts_by_type["evidence"], "source_observation_count": counts_by_type["source_observation"],
                "reporter_observation_count": counts_by_type["reporter_observation"], "media_node_count": counts_by_type["media"],
                "source_node_count": counts_by_type["source"], "reporter_node_count": counts_by_type["reporter"],
                "exact_story_node_count": counts_by_type["story"], "qualified_dependency_count": qualified_dependency_count,
                "potential_dependency_count": potential_dependency_count, "verified_independent_pair_count": len(verified_pairs),
                "dependency_independence_conflict_count": len(graph_conflicts), "anomaly_count": len(anomalies),
                "source_observations_eligible": len(all_target_ids["source_observation"]),
                "reporter_observations_eligible": len(all_target_ids["reporter_observation"]),
                "observations_eligible": len(all_target_ids["source_observation"] | all_target_ids["reporter_observation"]),
                "observations_retained": counts_by_type["source_observation"] + counts_by_type["reporter_observation"],
                "evidence_records_eligible": len(all_target_ids["evidence"]),
                "evidence_links_eligible": len(eligible_evidence_link_rows),
                "dependency_records_eligible": dependency_eligible_count,
                "independence_assertions_eligible": independence_eligible_count,
            },
            "graph_limits": {**_GRAPH_LIMITS, "truncated_categories": truncated_categories, "dependency_independence_completeness_affected": bool(truncated_categories), "independence_completeness": "incomplete" if truncated_categories else "complete"},
            "graph_truncated": bool(truncated_categories),
        }
    finally:
        conn.close()


def build_claim_support_graph(
    *,
    claim_id: str,
    connection_factory,
    strict_graph_integrity: bool = True,
) -> dict[str, Any]:
    normalized_claim_id = _clean(claim_id, 128)
    if not normalized_claim_id:
        raise ValueError("Claim support graph requires claim_id.")
    if connection_factory is None:
        raise ValueError("Claim support graph requires database access.")

    claim = _claim_record(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )
    if claim is None:
        return {
            "version": CLAIM_SUPPORT_GRAPH_VERSION,
            "status": "not_found",
            "claim_id": normalized_claim_id,
        }

    link_rows = _claim_link_rows(
        claim_id=normalized_claim_id,
        connection_factory=connection_factory,
    )
    nodes, direct_evidence, truncated = _observation_nodes(link_rows)
    source_observation_ids = [
        item["observation_id"]
        for item in nodes
        if item["observation_type"] == "source_observation"
    ]
    reporter_observation_ids = [
        item["observation_id"]
        for item in nodes
        if item["observation_type"] == "reporter_observation"
    ]

    dependency_rows = _dependency_rows(
        source_ids=source_observation_ids,
        reporter_ids=reporter_observation_ids,
        connection_factory=connection_factory,
    )
    dependency_edges, dependency_pairs = _dependency_graph(
        nodes=nodes,
        rows=dependency_rows,
    )
    independence_rows = _independence_rows(
        source_ids=source_observation_ids,
        reporter_ids=reporter_observation_ids,
        connection_factory=connection_factory,
    )
    (
        independence_assertions,
        verified_independent_pairs,
        conflicts,
        verification_gap_count,
    ) = _independence_graph(
        nodes=nodes,
        rows=independence_rows,
        dependency_pairs=dependency_pairs,
    )

    verified_direct_evidence = sum(
        1
        for item in direct_evidence
        if item["verification_status"] == "verified"
    )
    unverified_independence = sum(
        1
        for item in independence_assertions
        if item["verification_status"] != "verified"
    )

    if conflicts:
        support_state = "provenance_conflict"
    elif verified_independent_pairs:
        support_state = "verified_independence_present"
    elif verification_gap_count:
        support_state = "independence_verification_incomplete"
    elif not nodes:
        support_state = "no_observation_support"
    elif len(nodes) == 1:
        support_state = "single_observation"
    elif dependency_pairs:
        support_state = "dependency_present"
    elif independence_assertions:
        support_state = "multiple_observations_independence_unverified"
    else:
        support_state = "multiple_observations_dependency_unknown"

    distinct_sources = {
        item["source_id"] for item in nodes if item["source_id"]
    }
    distinct_reporters = {
        item["reporter_id"] for item in nodes if item["reporter_id"]
    }

    from app.story.story_claim_graph_materialization import (
        StoryClaimGraphMaterializationIntegrityError,
    )
    integrity_blocked = False
    try:
        evidence_graph = _build_evidence_graph(
            claim=claim,
            claim_id=normalized_claim_id,
            connection_factory=connection_factory,
        )
    except StoryClaimGraphMaterializationIntegrityError as exc:
        if strict_graph_integrity:
            raise
        integrity_blocked = True
        evidence_graph = {
            "evidence_graph_version": CLAIM_EVIDENCE_GRAPH_VERSION,
            "nodes": [],
            "edges": [],
            "anomalies": [{
                "anomaly_type": "embedded_graph_integrity_blocked",
                "stable_id": normalized_claim_id,
                "detail": _clean(str(exc), 512),
            }],
            "graph_independence_assertions": [],
            "graph_verified_independent_pairs": [],
            "graph_summary": {"anomaly_count": 1},
            "graph_limits": {
                **_GRAPH_LIMITS,
                "truncated_categories": [],
                "dependency_independence_completeness_affected": True,
            },
            "graph_truncated": False,
        }
        support_state = "integrity_blocked_incomplete"
        nodes = []
        direct_evidence = []
        dependency_edges = []
        dependency_pairs = set()
        independence_assertions = []
        verified_independent_pairs = []
        conflicts = []
        source_observation_ids = []
        reporter_observation_ids = []
        distinct_sources = set()
        distinct_reporters = set()
        verified_direct_evidence = 0
        unverified_independence = 0
        verification_gap_count = 0
        truncated = True
    result = {
        "version": CLAIM_SUPPORT_GRAPH_VERSION,
        "status": "ok",
        "claim": {
            "id": _clean(claim.get("id"), 128),
            "canonical_key": _clean(claim.get("canonical_key"), 512),
            "subject_key": _clean(claim.get("subject_key"), 256),
            "canonical_text": _clean(claim.get("canonical_text"), 1000),
            "claim_type": _clean(claim.get("claim_type"), 64),
        },
        "support_state": support_state,
        "integrity_blocked": integrity_blocked,
        "observations": nodes,
        "direct_evidence": direct_evidence,
        "dependency_edges": dependency_edges,
        "dependency_pairs": [list(pair) for pair in sorted(dependency_pairs)],
        "independence_assertions": independence_assertions,
        "verified_independent_pairs": verified_independent_pairs,
        "provenance_conflicts": conflicts,
        "counts": {
            "observations": len(nodes),
            "source_observations": len(source_observation_ids),
            "reporter_observations": len(reporter_observation_ids),
            "distinct_sources": len(distinct_sources),
            "distinct_reporters": len(distinct_reporters),
            "direct_evidence": len(direct_evidence),
            "verified_direct_evidence": verified_direct_evidence,
            "dependency_edges": len(dependency_edges),
            "dependency_pairs": len(dependency_pairs),
            "independence_assertions": len(independence_assertions),
            "unverified_independence_assertions": unverified_independence,
            "qualified_verified_independent_pairs": len(
                verified_independent_pairs
            ),
            "independence_verification_gaps": verification_gap_count,
            "provenance_conflicts": len(conflicts),
        },
        "truncated": truncated,
        "policy": {
            "different_sources_do_not_imply_independence": True,
            "different_reporters_do_not_imply_independence": True,
            "verified_independence_requires_verified_assertion": True,
            "qualified_verified_independence_requires_verified_provenance_evidence": True,
            "recorded_dependency_is_not_counted_as_independent_support": True,
            "dependency_and_verified_independence_conflict_is_surfaced": True,
            "independence_is_pairwise_not_transitive": True,
            "support_state_is_provenance_state_not_claim_truth": True,
            "verified_evidence_status_does_not_establish_claim_truth": True,
            "source_count_is_not_corroboration_count": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "affects_live_merit": False,
            "reports_does_not_establish_support": True,
            "multiple_reports_do_not_establish_corroboration": True,
            "unknown_relationships_are_not_semantic": True,
            "official_or_verified_evidence_does_not_establish_truth": True,
            "dependency_edges_are_direct_only": True,
            "unknown_is_not_independent": True,
            "evidence_to_evidence_relationships_exposed": False,
            "graph_is_read_only": True,
        },
    }
    result.update(evidence_graph)
    return result


def build_story_support_overview(
    *,
    story_id: str,
    connection_factory,
) -> dict[str, Any]:
    normalized_story_id = _clean(story_id, 128)
    if not normalized_story_id:
        raise ValueError("Story support overview requires story_id.")
    if connection_factory is None:
        raise ValueError("Story support overview requires database access.")

    conn = connection_factory()
    try:
        story_row = conn.execute(
            "SELECT * FROM intelligence_stories WHERE id = ?",
            (normalized_story_id,),
        ).fetchone()
        claim_rows = conn.execute(
            """
            SELECT claim_id
            FROM story_claim_links
            WHERE story_id = ?
            ORDER BY claim_id
            """,
            (normalized_story_id,),
        ).fetchall()
    finally:
        conn.close()

    if story_row is None:
        return {
            "version": STORY_SUPPORT_OVERVIEW_VERSION,
            "status": "not_found",
            "story_id": normalized_story_id,
        }

    claim_graphs = [
        build_claim_support_graph(
            claim_id=_clean(row["claim_id"], 128),
            connection_factory=connection_factory,
        )
        for row in claim_rows
    ]
    claim_graphs = [item for item in claim_graphs if item.get("status") == "ok"]

    state_counts: dict[str, int] = defaultdict(int)
    totals = {
        "claims": len(claim_graphs),
        "observations": 0,
        "dependency_pairs": 0,
        "qualified_verified_independent_pairs": 0,
        "provenance_conflicts": 0,
        "independence_verification_gaps": 0,
    }
    for graph in claim_graphs:
        state_counts[str(graph.get("support_state") or "unknown")] += 1
        counts = graph.get("counts") or {}
        for key in tuple(totals)[1:]:
            totals[key] += int(counts.get(key) or 0)

    if totals["provenance_conflicts"]:
        overview_state = "provenance_conflict_present"
    elif totals["qualified_verified_independent_pairs"]:
        overview_state = "verified_independence_present"
    elif not claim_graphs:
        overview_state = "no_claims"
    else:
        overview_state = "no_qualified_verified_independence"

    story = dict(story_row)
    return {
        "version": STORY_SUPPORT_OVERVIEW_VERSION,
        "status": "ok",
        "story": {
            "id": _clean(story.get("id"), 128),
            "canonical_key": _clean(story.get("canonical_key"), 512),
            "canonical_title": _clean(story.get("canonical_title"), 1000),
            "status": _clean(story.get("status"), 64),
        },
        "overview_state": overview_state,
        "counts": totals,
        "claim_support_states": dict(sorted(state_counts.items())),
        "claims": claim_graphs,
        "policy": {
            "support_is_evaluated_per_exact_claim": True,
            "different_claims_are_not_collapsed_into_one_corroboration_result": True,
            "cross_claim_source_counts_do_not_establish_independence": True,
            "verified_independence_is_pairwise_and_claim_scoped": True,
            "provenance_conflicts_fail_closed_and_are_preserved": True,
            "story_support_overview_does_not_establish_story_truth": True,
            "establishes_truth": False,
            "establishes_authority": False,
            "affects_live_merit": False,
        },
    }


__all__ = [
    "CLAIM_SUPPORT_GRAPH_VERSION",
    "CLAIM_EVIDENCE_GRAPH_VERSION",
    "STORY_SUPPORT_OVERVIEW_VERSION",
    "build_claim_support_graph",
    "build_story_support_overview",
]
