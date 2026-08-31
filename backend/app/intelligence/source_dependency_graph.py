from __future__ import annotations

import json

from collections import defaultdict
from datetime import datetime
from typing import Any, Iterable

from app.analysis.features import OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY
from app.intelligence import reporting_coverage
from app.story import story_claim_graph_materialization as story_graph


SOURCE_DEPENDENCY_GRAPH_VERSION = "source-dependency-graph-v1"
_CHUNK_SIZE = 350


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _key(kind: str, observation_id: str) -> str:
    return kind + ":" + observation_id


def _pair(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _chunks(values: Iterable[str]):
    ordered = list(values)
    for offset in range(0, len(ordered), _CHUNK_SIZE):
        yield ordered[offset : offset + _CHUNK_SIZE]


def _valid_timestamp(value: Any) -> bool:
    text = _clean(value, 128)
    try:
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
        return parsed.utcoffset() is not None
    except (TypeError, ValueError, OverflowError):
        return False


def _metadata(value: Any) -> tuple[dict[str, Any], bool]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, False
    return (dict(parsed), True) if isinstance(parsed, dict) else ({}, False)


def _anomaly(kind: str, stable_id: str, **details: Any) -> dict[str, Any]:
    return {"type": kind, "stable_id": stable_id, **details}


def _load_dependencies(conn, observation_ids: dict[str, list[str]]):
    found: dict[str, dict[str, Any]] = {}
    for kind in ("source_observation", "reporter_observation"):
        column = (
            "downstream_source_observation_id"
            if kind == "source_observation"
            else "downstream_reporter_observation_id"
        )
        for chunk in _chunks(observation_ids[kind]):
            if not chunk:
                continue
            marks = ",".join("?" for _ in chunk)
            for row in conn.execute(
                f"SELECT * FROM observation_dependencies WHERE {column} IN ({marks})",
                tuple(chunk),
            ).fetchall():
                item = dict(row)
                found[_clean(item.get("id"), 128)] = item
    return list(found.values())


def _load_assertions(conn, observation_ids: dict[str, list[str]]):
    found: dict[str, dict[str, Any]] = {}
    for kind in ("source_observation", "reporter_observation"):
        columns = (
            (
                "a.observation_a_source_observation_id",
                "a.observation_b_source_observation_id",
            )
            if kind == "source_observation"
            else (
                "a.observation_a_reporter_observation_id",
                "a.observation_b_reporter_observation_id",
            )
        )
        for chunk in _chunks(observation_ids[kind]):
            if not chunk:
                continue
            marks = ",".join("?" for _ in chunk)
            rows = conn.execute(
                "SELECT a.*, e.evidence_type AS provenance_evidence_type, "
                "e.verification_status AS provenance_evidence_verification_status, "
                "e.observed_at AS provenance_evidence_observed_at, "
                "e.recorded_at AS provenance_evidence_recorded_at, "
                "e.metadata_json AS provenance_evidence_metadata_json "
                "FROM observation_independence_assertions AS a "
                "LEFT JOIN evidence_records AS e ON e.id = a.provenance_evidence_id "
                f"WHERE {columns[0]} IN ({marks}) OR {columns[1]} IN ({marks})",
                tuple(chunk) + tuple(chunk),
            ).fetchall()
            for row in rows:
                item = dict(row)
                found[_clean(item.get("id"), 128)] = item
    return list(found.values())


def _load_existing_ids(conn, table: str, values: Iterable[str]) -> set[str]:
    existing: set[str] = set()
    for chunk in _chunks(sorted(set(values))):
        if not chunk:
            continue
        marks = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT id FROM {table} WHERE id IN ({marks})", tuple(chunk)
        ).fetchall()
        existing.update(_clean(row["id"], 128) for row in rows)
    return existing


def _endpoint(row: dict[str, Any], side: str) -> str:
    source = _clean(row.get(f"observation_{side}_source_observation_id"), 128)
    if source:
        return _key("source_observation", source)
    reporter = _clean(row.get(f"observation_{side}_reporter_observation_id"), 128)
    if reporter:
        return _key("reporter_observation", reporter)
    return ""


def _cycle_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    active: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        active.add(node)
        for target in sorted(adjacency.get(node, ())):
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component = []
            while True:
                target = stack.pop()
                active.remove(target)
                component.append(target)
                if target == node:
                    break
            if len(component) > 1:
                components.append(sorted(component))

    for node in sorted(adjacency):
        if node not in indices:
            visit(node)
    return sorted(components)


def build_claim_source_dependency_graph(
    *, canonical_claim_id: str, connection_factory
) -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError("Source dependency graph requires database access.")
    requested_id = _clean(canonical_claim_id, 128)
    if not requested_id:
        raise ValueError("Source dependency graph canonical_claim_id is required.")

    conn = connection_factory()
    try:
        if conn.execute(
            "SELECT id FROM intelligence_claims WHERE id = ?", (requested_id,)
        ).fetchone() is None:
            return {
                "version": SOURCE_DEPENDENCY_GRAPH_VERSION,
                "status": "not_found",
                "canonical_claim_id": requested_id,
            }
        claim, legacy_ids = reporting_coverage._validated_claim_scope(
            conn, canonical_claim_id=requested_id
        )
        story = reporting_coverage._validated_story(conn, claim=claim)
        rows = reporting_coverage._coverage_rows(
            conn, claim_ids=[requested_id, *legacy_ids]
        )

        observations: dict[str, dict[str, Any]] = {}
        media_ids: set[str] = set()
        for row in rows:
            if _clean(row.get("observation_subject_key"), 256) != _clean(
                claim.get("subject_key"), 256
            ):
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Claim-linked observation subject is inconsistent."
                )
            media_id = _clean(row.get("observation_media_item_id"), 128)
            persisted_media_id = _clean(row.get("media_item_id"), 128)
            if not media_id:
                continue
            if not persisted_media_id or persisted_media_id != media_id:
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Claim-linked reporting media item is missing."
                )
            kind = _clean(row.get("observation_kind"), 32) + "_observation"
            observation_id = _clean(row.get("observation_id"), 128)
            observation_key = _key(kind, observation_id)
            source_id = _clean(row.get("observation_source_id"), 128)
            reporter_id = _clean(row.get("observation_reporter_id"), 128)
            if reporter_id and reporter_id != _clean(
                row.get("persisted_observation_reporter_id"), 128
            ):
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Claim-linked reporter identity is missing."
                )
            observed_at = _clean(row.get("reporting_observed_at"), 128)
            reporting_coverage._aware_timestamp(
                observed_at, label="Reporting observation"
            )
            observations[observation_key] = {
                "observation_key": observation_key,
                "observation_type": kind,
                "observation_id": observation_id,
                "media_item_id": media_id,
                "source_id": source_id or None,
                "reporter_id": reporter_id or None,
                "observed_at": observed_at,
            }
            media_ids.add(media_id)

        reporting_coverage._validate_story_media(
            conn,
            story_id=_clean(story.get("id"), 128),
            qualifying_media_ids=media_ids,
        )
        ids = {
            kind: sorted(
                item["observation_id"]
                for item in observations.values()
                if item["observation_type"] == kind
            )
            for kind in ("source_observation", "reporter_observation")
        }
        dependency_rows = _load_dependencies(conn, ids)
        assertion_rows = _load_assertions(conn, ids)
        target_ids = {
            "source_observation": {
                _clean(row.get("upstream_source_observation_id"), 128)
                for row in dependency_rows
                if _clean(row.get("upstream_source_observation_id"), 128)
            },
            "reporter_observation": {
                _clean(row.get("upstream_reporter_observation_id"), 128)
                for row in dependency_rows
                if _clean(row.get("upstream_reporter_observation_id"), 128)
            },
            "source": {
                _clean(row.get("upstream_source_id"), 128)
                for row in dependency_rows
                if _clean(row.get("upstream_source_id"), 128)
            },
            "reporter": {
                _clean(row.get("upstream_reporter_id"), 128)
                for row in dependency_rows
                if _clean(row.get("upstream_reporter_id"), 128)
            },
        }
        existing_targets = {
            kind: _load_existing_ids(conn, table, target_ids[kind])
            for kind, table in (
                ("source_observation", "source_observations"),
                ("reporter_observation", "reporter_observations"),
                ("source", "intelligence_sources"),
                ("reporter", "intelligence_reporters"),
            )
        }
    finally:
        conn.close()

    by_source: dict[str, list[str]] = defaultdict(list)
    by_reporter: dict[str, list[str]] = defaultdict(list)
    for observation_key, item in observations.items():
        if item["source_id"]:
            by_source[item["source_id"]].append(observation_key)
        if item["reporter_id"]:
            by_reporter[item["reporter_id"]].append(observation_key)

    anomalies: list[dict[str, Any]] = []
    edges = []
    dependent_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    blocked_independence_pairs: set[tuple[str, str]] = set()
    touched_pairs: set[tuple[str, str]] = set()
    adjacency: dict[str, set[str]] = defaultdict(set)
    recognized = set(OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY)

    for row in dependency_rows:
        dependency_id = _clean(row.get("id"), 128)
        downstream_values = [
            ("source_observation", _clean(row.get("downstream_source_observation_id"), 128)),
            ("reporter_observation", _clean(row.get("downstream_reporter_observation_id"), 128)),
        ]
        active_downstream = [item for item in downstream_values if item[1]]
        downstream = ""
        if len(active_downstream) == 1:
            downstream = _key(*active_downstream[0])
        relationship = _clean(row.get("relationship_type"), 64).casefold()
        relationship_recognized = relationship in recognized
        metadata, metadata_valid = _metadata(row.get("metadata_json"))
        if not metadata_valid:
            anomalies.append(_anomaly("malformed_dependency_metadata", dependency_id))
        observed_at_valid = _valid_timestamp(row.get("observed_at"))
        recorded_at_valid = _valid_timestamp(row.get("recorded_at"))
        if not observed_at_valid or not recorded_at_valid:
            anomalies.append(_anomaly("malformed_dependency_timestamp", dependency_id))
        if not relationship_recognized:
            anomalies.append(
                _anomaly(
                    "unknown_dependency_relationship", dependency_id,
                    relationship_type=relationship,
                )
            )

        target_type = ""
        target_id = ""
        resolved: list[str] = []
        upstream_values = [
            ("source_observation", _clean(row.get("upstream_source_observation_id"), 128)),
            ("reporter_observation", _clean(row.get("upstream_reporter_observation_id"), 128)),
            ("source", _clean(row.get("upstream_source_id"), 128)),
            ("reporter", _clean(row.get("upstream_reporter_id"), 128)),
        ]
        active_upstream = [item for item in upstream_values if item[1]]
        if len(active_upstream) == 1:
            target_type, target_id = active_upstream[0]
        if target_type == "source_observation":
            candidate = _key(target_type, target_id)
            if candidate in observations:
                resolved = [candidate]
        elif target_type == "reporter_observation":
            candidate = _key(target_type, target_id)
            if candidate in observations:
                resolved = [candidate]
        elif target_type == "source":
            resolved = sorted(by_source.get(target_id, ()))
        elif target_type == "reporter":
            resolved = sorted(by_reporter.get(target_id, ()))

        endpoints_valid = (
            len(active_downstream) == 1
            and downstream in observations
            and len(active_upstream) == 1
            and bool(target_type and target_id)
        )
        target_exists = bool(
            endpoints_valid and target_id in existing_targets.get(target_type, set())
        )
        if not endpoints_valid:
            anomalies.append(_anomaly("malformed_dependency_endpoint", dependency_id))
            resolved = []
        elif not target_exists:
            anomalies.append(
                _anomaly(
                    "dangling_dependency_target",
                    dependency_id,
                    upstream_target={"type": target_type, "id": target_id},
                )
            )
        if target_type in {"source", "reporter"} and len(resolved) > 1:
            anomalies.append(
                _anomaly(
                    "ambiguous_actor_dependency_target", dependency_id,
                    matching_observation_keys=resolved,
                )
            )
        linked_pairs = []
        candidates = resolved if len(resolved) == 1 else []
        structurally_valid = bool(
            endpoints_valid
            and target_exists
            and observed_at_valid
            and recorded_at_valid
            and metadata_valid
        )
        for upstream in candidates:
            if upstream == downstream:
                anomalies.append(_anomaly("self_dependency", dependency_id))
                continue
            pair = _pair(downstream, upstream)
            linked_pairs.append(list(pair))
            touched_pairs.add(pair)
            if relationship_recognized and structurally_valid:
                dependent_pairs[pair].add(dependency_id)
                adjacency[downstream].add(upstream)
            else:
                blocked_independence_pairs.add(pair)
        if len(resolved) > 1:
            ambiguous_pairs = {
                _pair(downstream, upstream)
                for upstream in resolved
                if upstream != downstream
            }
            blocked_independence_pairs.update(ambiguous_pairs)
            touched_pairs.update(ambiguous_pairs)
        scope = (
            "dangling_target"
            if endpoints_valid and not target_exists
            else "in_scope"
            if linked_pairs
            else "external_to_claim_scope"
        )
        edges.append(
            {
                "dependency_id": dependency_id,
                "downstream_observation_key": downstream,
                "upstream_target": {"type": target_type, "id": target_id},
                "relationship_type": relationship,
                "relationship_recognized": relationship_recognized,
                "dependency_structurally_valid": structurally_valid,
                "dependency_assertion_kind": "recorded_direct_dependency",
                "scope": scope,
                "linked_observation_pairs": sorted(linked_pairs),
                "confidence": row.get("confidence"),
                "observed_at": _clean(row.get("observed_at"), 128),
                "recorded_at": _clean(row.get("recorded_at"), 128),
                "provenance": metadata,
            }
        )

    for component in _cycle_components(adjacency):
        anomalies.append(
            _anomaly("dependency_cycle", "|".join(component), observation_keys=component)
        )

    assertions = []
    independent_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    evidence_qualified_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in assertion_rows:
        assertion_id = _clean(row.get("id"), 128)
        left, right = _endpoint(row, "a"), _endpoint(row, "b")
        pair = _pair(left, right) if left and right else (left, right)
        evidence_id = _clean(row.get("provenance_evidence_id"), 128)
        assertion_verified = (
            _clean(row.get("verification_status"), 64).casefold() == "verified"
        )
        evidence_verified = (
            _clean(
                row.get("provenance_evidence_verification_status"), 64
            ).casefold()
            == "verified"
        )
        evidence_metadata, evidence_metadata_valid = _metadata(
            row.get("provenance_evidence_metadata_json")
        )
        endpoints_in_scope = left in observations and right in observations and left != right
        distinct_sources = bool(
            endpoints_in_scope
            and observations[left].get("source_id")
            and observations[right].get("source_id")
            and observations[left]["source_id"] != observations[right]["source_id"]
        )
        dependency_conflict = pair in dependent_pairs if endpoints_in_scope else False
        potential_dependency = pair in blocked_independence_pairs if endpoints_in_scope else False
        evidence_qualified = bool(
            assertion_verified
            and evidence_id
            and evidence_verified
            and evidence_metadata_valid
            and endpoints_in_scope
            and distinct_sources
            and not potential_dependency
        )
        qualified = evidence_qualified and not dependency_conflict
        if not endpoints_in_scope:
            anomalies.append(_anomaly("independence_endpoint_out_of_scope", assertion_id))
        if assertion_verified and (not evidence_id or not evidence_verified):
            anomalies.append(_anomaly("independence_verification_gap", assertion_id))
        if not evidence_metadata_valid:
            anomalies.append(_anomaly("malformed_independence_evidence", assertion_id))
        if endpoints_in_scope:
            touched_pairs.add(pair)
        if evidence_qualified:
            evidence_qualified_pairs[pair].add(assertion_id)
        if qualified:
            independent_pairs[pair].add(assertion_id)
        assertions.append(
            {
                "assertion_id": assertion_id,
                "observation_pair": list(pair),
                "verification_status": _clean(row.get("verification_status"), 64).casefold(),
                "evidence_qualified_verified_independence": evidence_qualified,
                "qualified_verified_independence": qualified,
                "provenance_evidence": {
                    "evidence_id": evidence_id,
                    "evidence_type": _clean(row.get("provenance_evidence_type"), 64),
                    "verification_status": _clean(
                        row.get("provenance_evidence_verification_status"), 64
                    ).casefold(),
                    "observed_at": _clean(
                        row.get("provenance_evidence_observed_at"), 128
                    ),
                    "recorded_at": _clean(
                        row.get("provenance_evidence_recorded_at"), 128
                    ),
                    "metadata": evidence_metadata,
                },
                "dependency_conflict": dependency_conflict,
                "observed_at": _clean(row.get("observed_at"), 128),
                "recorded_at": _clean(row.get("recorded_at"), 128),
            }
        )

    relationships = []
    classified_pairs = set(dependent_pairs) | set(evidence_qualified_pairs)
    for pair in sorted(classified_pairs):
        dependency_ids = sorted(dependent_pairs.get(pair, ()))
        assertion_ids = sorted(evidence_qualified_pairs.get(pair, ()))
        status = (
            "conflicting_evidence"
            if dependency_ids and assertion_ids
            else "dependent"
            if dependency_ids
            else "independent"
        )
        relationships.append(
            {
                "observation_pair": list(pair),
                "status": status,
                "dependency_edge_ids": dependency_ids,
                "independence_assertion_ids": assertion_ids,
            }
        )

    state_by_pair = {
        tuple(row["observation_pair"]): row["status"] for row in relationships
    }
    observations_by_media: dict[str, list[str]] = defaultdict(list)
    for observation_key, item in observations.items():
        observations_by_media[item["media_item_id"]].append(observation_key)
    candidate_media_pairs = {
        _pair(
            observations[left]["media_item_id"],
            observations[right]["media_item_id"],
        )
        for left, right in touched_pairs
        if left in observations
        and right in observations
        and observations[left]["media_item_id"] != observations[right]["media_item_id"]
    }
    media_projection = []
    for left_media, right_media in sorted(candidate_media_pairs):
        basis = sorted(
            _pair(left, right)
            for left in observations_by_media[left_media]
            for right in observations_by_media[right_media]
        )
        states = [state_by_pair.get(pair, "unknown") for pair in basis]
        known = set(states) - {"unknown"}
        if "conflicting_evidence" in known or (
            "dependent" in known and "independent" in known
        ):
            status = "conflicting_evidence"
        elif "dependent" in known:
            status = "dependent"
        elif states and all(state == "independent" for state in states):
            status = "independent"
        else:
            status = "unknown"
        media_projection.append(
            {
                "media_pair": [left_media, right_media],
                "status": status,
                "basis_observation_pairs": [list(pair) for pair in basis],
            }
        )

    ordered_observations = sorted(
        observations.values(),
        key=lambda item: (item["observation_type"], item["observation_id"]),
    )
    edges.sort(
        key=lambda item: (
            item["downstream_observation_key"],
            item["upstream_target"]["type"],
            item["upstream_target"]["id"],
            item["relationship_type"],
            item["observed_at"],
            item["dependency_id"],
        )
    )
    assertions.sort(
        key=lambda item: (
            item["observation_pair"], item["observed_at"], item["assertion_id"]
        )
    )
    anomalies.sort(key=lambda item: (item["type"], item["stable_id"]))
    observation_count = len(ordered_observations)
    total_pairs = observation_count * (observation_count - 1) // 2
    conflicting_count = sum(
        row["status"] == "conflicting_evidence" for row in relationships
    )
    return {
        "version": SOURCE_DEPENDENCY_GRAPH_VERSION,
        "status": "ok",
        "canonical_claim": {
            "id": requested_id,
            "canonical_text": _clean(claim.get("canonical_text"), 1000),
            "claim_type": _clean(claim.get("claim_type"), 64),
            "subject_key": _clean(claim.get("subject_key"), 256),
        },
        "story": {
            "id": _clean(story.get("id"), 128),
            "canonical_key": _clean(story.get("canonical_key")),
            "canonical_title": _clean(story.get("canonical_title"), 1000),
        },
        "summary": {
            "reporting_media": len(media_ids),
            "reporting_observations": observation_count,
            "known_dependency_edges": sum(
                edge["relationship_recognized"]
                and edge["dependency_structurally_valid"]
                for edge in edges
            ),
            "known_dependency_pairs": len(dependent_pairs),
            "qualified_verified_independent_pairs": len(independent_pairs),
            "conflicting_pairs": conflicting_count,
            "unknown_observation_pairs": total_pairs - len(classified_pairs),
            "anomaly_count": len(anomalies),
        },
        "observations": ordered_observations,
        "dependency_edges": edges,
        "independence_assertions": assertions,
        "classified_relationships": relationships,
        "media_projection": media_projection,
        "anomalies": anomalies,
        "policy": {
            "absence_of_dependency_is_not_independence": True,
            "independence_requires_verified_evidence": True,
            "independence_is_pairwise_not_transitive": True,
            "dependency_edges_are_direct_only": True,
            "dependency_assertions_are_not_truth_verification": True,
            "media_projection_preserves_observation_basis": True,
            "independent_source_count_exposed": False,
            "establishes_truth": False,
            "establishes_claim_verification": False,
            "establishes_source_reliability": False,
            "provider_call_performed": False,
        },
    }


__all__ = [
    "SOURCE_DEPENDENCY_GRAPH_VERSION",
    "build_claim_source_dependency_graph",
]
