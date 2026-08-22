from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


CLAIM_SUPPORT_GRAPH_VERSION = "claim-support-graph-v1"
STORY_SUPPORT_OVERVIEW_VERSION = "story-support-overview-v1"

_MAX_OBSERVATIONS = 400


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


def build_claim_support_graph(
    *,
    claim_id: str,
    connection_factory,
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

    return {
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
        },
    }


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
    "STORY_SUPPORT_OVERVIEW_VERSION",
    "build_claim_support_graph",
    "build_story_support_overview",
]
