"""Read-only, actor-centric reporting history profiles.

The profile deliberately describes persisted observations.  It does not turn
coverage, dependency, or evidence counts into judgments about an actor.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Literal

from app.intelligence.claims.identity import (
    CanonicalClaimError,
    normalize_canonical_claim,
)
from app.story.story_claim_graph_materialization import (
    StoryClaimGraphMaterializationIntegrityError,
)


PROFILE_VERSION = "source-profile-v1"
_CLAIM_RELATIONSHIPS = {"reports", "supports", "contradicts", "aligned_to"}
_DEPENDENCY_RELATIONSHIPS = {"attributed_to", "derived_from"}
_CHUNK_SIZE = 350
_METADATA_MAX_BYTES = 16_384
_METADATA_MAX_DEPTH = 6
_METADATA_MAX_ITEMS = 256


def _clean(value: Any, maximum: int = 2048) -> str:
    return str(value or "").strip()[:maximum]


def _timestamp(value: Any) -> str:
    text = _clean(value, 128)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        return ""
    return text


def _json_object(value: Any) -> tuple[dict[str, Any], bool]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}, False
    return (parsed, True) if isinstance(parsed, dict) else ({}, False)


def _bounded_json_object(value: Any) -> tuple[dict[str, Any], bool]:
    parsed, valid = _json_object(value)
    if not valid or len(str(value or "").encode("utf-8")) > _METADATA_MAX_BYTES:
        return {}, False
    items = 0

    def inspect(item: Any, depth: int) -> bool:
        nonlocal items
        if depth > _METADATA_MAX_DEPTH:
            return False
        if item is None or isinstance(item, (bool, int, float, str)):
            return True
        if isinstance(item, dict):
            items += len(item)
            return items <= _METADATA_MAX_ITEMS and all(
                isinstance(key, str) and inspect(child, depth + 1)
                for key, child in item.items()
            )
        if isinstance(item, list):
            items += len(item)
            return items <= _METADATA_MAX_ITEMS and all(
                inspect(child, depth + 1) for child in item
            )
        return False

    return (parsed, True) if inspect(parsed, 0) else ({}, False)


def _anomaly(kind: str, stable_id: str, **details: Any) -> dict[str, Any]:
    return {"type": kind, "stable_id": stable_id, **details}


def _rows(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _chunks(values: Any):
    ordered = sorted(set(values))
    for index in range(0, len(ordered), _CHUNK_SIZE):
        yield ordered[index:index + _CHUNK_SIZE]


def _rows_by_ids(conn, table: str, values: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(values):
        marks = ",".join("?" for _ in chunk)
        result.update({
            row["id"]: row for row in _rows(
                conn, f"SELECT * FROM {table} WHERE id IN ({marks}) ORDER BY id", tuple(chunk)
            )
        })
    return result


def _validated_structured_claim(row: dict[str, Any]) -> dict[str, Any] | None:
    metadata, valid = _json_object(row.get("metadata_json") or row.get("claim_metadata_json"))
    if not valid:
        raise StoryClaimGraphMaterializationIntegrityError("Claim metadata is malformed.")
    candidate = metadata.get("structured_claim")
    if candidate is None:
        return None
    if not isinstance(candidate, dict):
        raise StoryClaimGraphMaterializationIntegrityError("Structured canonical claim is malformed.")
    try:
        normalized = normalize_canonical_claim(candidate)
    except CanonicalClaimError as exc:
        raise StoryClaimGraphMaterializationIntegrityError(
            "Structured canonical claim is malformed."
        ) from exc
    if _clean(normalized.get("subject_key"), 256) != _clean(row.get("subject_key"), 256):
        raise StoryClaimGraphMaterializationIntegrityError(
            "Structured canonical claim subject is inconsistent."
        )
    return normalized


def _mapping_scope(conn, claims: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Return exact -> canonical, rejecting unsafe mapping topology."""
    if not claims:
        return {}
    ids = sorted(claims)
    mapping_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for chunk in _chunks(ids):
        marks = ",".join("?" for _ in chunk)
        for row in _rows(
            conn,
            "SELECT * FROM claim_identity_mappings WHERE production_claim_id IN ("
            + marks + ") OR canonical_claim_id IN (" + marks + ") ORDER BY production_claim_id",
            tuple(chunk + chunk),
        ):
            mapping_by_key[(row["production_claim_id"], row["canonical_claim_id"])] = row
    mappings = [mapping_by_key[key] for key in sorted(mapping_by_key)]
    by_production = {row["production_claim_id"]: row for row in mappings}
    target_ids = {_clean(row.get("canonical_claim_id"), 128) for row in mappings}
    targets = _rows_by_ids(conn, "intelligence_claims", target_ids)
    result: dict[str, str] = {}
    for claim_id in ids:
        row = by_production.get(claim_id)
        if row is None:
            result[claim_id] = claim_id
            continue
        canonical_id = _clean(row.get("canonical_claim_id"), 128)
        if (
            _clean(row.get("mapping_status"), 64) != "verified_equivalent"
            or not canonical_id
            or canonical_id == claim_id
            or canonical_id in by_production
        ):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Claim identity mapping is malformed, chained, or cyclic."
            )
        canonical = targets.get(canonical_id)
        if canonical is None:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Claim identity mapping canonical target is missing."
            )
        if _clean(row.get("subject_key"), 256) != _clean(claims[claim_id].get("subject_key"), 256) or _clean(
            canonical.get("subject_key"), 256
        ) != _clean(claims[claim_id].get("subject_key"), 256):
            raise StoryClaimGraphMaterializationIntegrityError(
                "Verified legacy claim subject is inconsistent."
            )
        metadata, valid = _json_object(row.get("metadata_json"))
        if not valid:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Claim identity mapping metadata is malformed."
            )
        if _validated_structured_claim(canonical) is None:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Canonical mapping target lacks structured identity."
            )
        result[claim_id] = canonical_id
    # A canonical claim reached directly must never simultaneously be a legacy source.
    for row in mappings:
        if row["canonical_claim_id"] in claims and row["canonical_claim_id"] in by_production:
            raise StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim acts as a legacy mapping source."
            )
    return result


def _actor_endpoint(row: dict[str, Any], side: str) -> tuple[str, str]:
    active: list[tuple[str, str]] = []
    for kind in ("source", "reporter"):
        value = _clean(row.get(f"{side}_{kind}_observation_id"), 128)
        if value:
            active.append((kind, value))
    return active[0] if len(active) == 1 else ("", "")


def _cyclic_nodes(adjacency: dict[str, set[str]]) -> set[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    cyclic: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            position = stack.index(node)
            cyclic.update(stack[position:])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for target in sorted(adjacency.get(node, set())):
            visit(target)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(adjacency):
        visit(node)
    return cyclic


def build_actor_profile(
    *,
    actor_type: Literal["source", "reporter"],
    actor_id: str,
    connection_factory,
    recent_limit: int = 25,
) -> dict[str, Any]:
    if actor_type not in {"source", "reporter"}:
        raise ValueError("Actor type must be source or reporter.")
    actor_id = _clean(actor_id, 128)
    if not actor_id:
        raise ValueError("Actor ID is required.")
    if isinstance(recent_limit, bool) or not 1 <= int(recent_limit) <= 100:
        raise ValueError("Recent activity limit must be between 1 and 100.")
    recent_limit = int(recent_limit)
    table = "intelligence_sources" if actor_type == "source" else "intelligence_reporters"
    observation_table = "source_observations" if actor_type == "source" else "reporter_observations"
    actor_column = "source_id" if actor_type == "source" else "reporter_id"
    observation_fk = "source_observation_id" if actor_type == "source" else "reporter_observation_id"
    anomalies: list[dict[str, Any]] = []

    conn = connection_factory()
    try:
        actor_row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (actor_id,)).fetchone()
        if actor_row is None:
            return {"version": PROFILE_VERSION, "status": "not_found"}
        actor = dict(actor_row)
        metadata, metadata_valid = _bounded_json_object(actor.get("metadata_json"))
        if not metadata_valid:
            anomalies.append(_anomaly("malformed_actor_metadata", actor_id))

        observations = _rows(
            conn,
            f"""SELECT o.*, m.id AS persisted_media_id, m.canonical_url,
                       m.title, m.published_at, m.source_id AS media_source_id,
                       m.reporter_id AS media_reporter_id
                FROM {observation_table} AS o
                LEFT JOIN media_items AS m ON m.id=o.media_item_id
                WHERE o.{actor_column}=?
                  AND (julianday(m.published_at) IS NOT NULL OR julianday(o.observed_at) IS NOT NULL)
                ORDER BY COALESCE(julianday(m.published_at),julianday(o.observed_at)) DESC,o.id DESC
                LIMIT ?""",
            (actor_id, recent_limit + 1),
        )
        observation_summary = dict(conn.execute(
            f"""SELECT COUNT(DISTINCT o.id) AS observation_count,
              COUNT(DISTINCT CASE WHEN julianday(m.published_at) IS NOT NULL
                    OR julianday(o.observed_at) IS NOT NULL THEN o.id END) AS eligible_activity_count
              FROM {observation_table} o LEFT JOIN media_items m ON m.id=o.media_item_id
              WHERE o.{actor_column}=?""",
            (actor_id,),
        ).fetchone())
        observation_count = int(observation_summary["observation_count"])
        observation_ids = {row["id"] for row in observations}
        subject_rows = _rows(
            conn,
            f"SELECT subject_key,COUNT(DISTINCT id) AS observation_count FROM {observation_table} "
            f"WHERE {actor_column}=? GROUP BY subject_key ORDER BY observation_count DESC,subject_key",
            (actor_id,),
        )
        observed_bounds = dict(conn.execute(
            f"""SELECT
              (SELECT observed_at FROM {observation_table} WHERE {actor_column}=?
               AND julianday(observed_at) IS NOT NULL ORDER BY julianday(observed_at),id LIMIT 1) AS first_observed_at,
              (SELECT observed_at FROM {observation_table} WHERE {actor_column}=?
               AND julianday(observed_at) IS NOT NULL ORDER BY julianday(observed_at) DESC,id DESC LIMIT 1) AS latest_observed_at""",
            (actor_id, actor_id),
        ).fetchone())
        if actor_type == "reporter":
            conflict_rows = _rows(conn, """SELECT ro.id,ro.media_item_id FROM reporter_observations ro
                JOIN media_items m ON m.id=ro.media_item_id WHERE ro.reporter_id=? AND
                ((ro.source_id IS NOT NULL AND m.source_id IS NOT NULL AND ro.source_id<>m.source_id)
                 OR (m.reporter_id IS NOT NULL AND m.reporter_id<>ro.reporter_id)) ORDER BY ro.id""", (actor_id,))
            eligible_sql = """SELECT DISTINCT m.id,m.published_at,m.source_id AS counterpart_id
                FROM media_items m WHERE (m.reporter_id=? OR EXISTS
                  (SELECT 1 FROM reporter_observations ro WHERE ro.media_item_id=m.id AND ro.reporter_id=?))
                AND NOT EXISTS (SELECT 1 FROM reporter_observations ro WHERE ro.media_item_id=m.id
                  AND ro.reporter_id=? AND ((ro.source_id IS NOT NULL AND m.source_id IS NOT NULL AND ro.source_id<>m.source_id)
                  OR (m.reporter_id IS NOT NULL AND m.reporter_id<>ro.reporter_id)))"""
            eligible_params = (actor_id, actor_id, actor_id)
            observation_facts = """SELECT COALESCE(ro.source_id,m.source_id) counterpart_id,ro.id observation_id,
                ro.media_item_id,ro.observed_at association_at FROM reporter_observations ro
                LEFT JOIN media_items m ON m.id=ro.media_item_id WHERE ro.reporter_id=? AND
                (ro.source_id IS NULL OR m.source_id IS NULL OR ro.source_id=m.source_id)
                AND (m.reporter_id IS NULL OR m.reporter_id=ro.reporter_id)"""
        else:
            conflict_rows = _rows(conn, """SELECT o.id,o.media_item_id FROM source_observations o JOIN media_items m
                ON m.id=o.media_item_id WHERE o.source_id=? AND m.source_id IS NOT NULL AND m.source_id<>o.source_id
                UNION SELECT ro.id,ro.media_item_id FROM reporter_observations ro JOIN media_items m ON m.id=ro.media_item_id
                WHERE ro.source_id=? AND ((m.reporter_id IS NOT NULL AND m.reporter_id<>ro.reporter_id)
                  OR (m.source_id IS NOT NULL AND m.source_id<>ro.source_id)) ORDER BY 1""", (actor_id, actor_id))
            eligible_sql = """SELECT DISTINCT m.id,m.published_at,m.reporter_id AS counterpart_id
                FROM media_items m WHERE (m.source_id=? OR EXISTS
                  (SELECT 1 FROM source_observations o WHERE o.media_item_id=m.id AND o.source_id=?))
                AND NOT EXISTS (SELECT 1 FROM source_observations o WHERE o.media_item_id=m.id AND o.source_id=?
                  AND m.source_id IS NOT NULL AND m.source_id<>o.source_id)
                AND NOT EXISTS (SELECT 1 FROM reporter_observations ro WHERE ro.media_item_id=m.id AND ro.source_id=?
                  AND m.reporter_id IS NOT NULL AND m.reporter_id<>ro.reporter_id)"""
            eligible_params = (actor_id, actor_id, actor_id, actor_id)
            observation_facts = """SELECT ro.reporter_id counterpart_id,ro.id observation_id,ro.media_item_id,
                ro.observed_at association_at FROM reporter_observations ro LEFT JOIN media_items m ON m.id=ro.media_item_id
                WHERE ro.source_id=? AND (m.reporter_id IS NULL OR m.reporter_id=ro.reporter_id)
                AND (m.source_id IS NULL OR m.source_id=ro.source_id)"""
        conflicted_media_ids = {_clean(row.get("media_item_id"), 128) for row in conflict_rows if _clean(row.get("media_item_id"), 128)}
        anomalies.extend(_anomaly("actor_association_mismatch", row["id"]) for row in conflict_rows)
        media_summary = dict(conn.execute(
            "SELECT COUNT(DISTINCT id) media_count,"
            "MIN(CASE WHEN julianday(published_at) IS NOT NULL THEN published_at END) first_published_at,"
            "MAX(CASE WHEN julianday(published_at) IS NOT NULL THEN published_at END) latest_published_at "
            "FROM (" + eligible_sql + ")",
            eligible_params,
        ).fetchone())
        association_rows = _rows(
            conn,
            "WITH eligible AS (" + eligible_sql + "), facts AS (" + observation_facts +
            " UNION ALL SELECT counterpart_id,NULL,id,published_at FROM eligible) "
            "SELECT counterpart_id,COUNT(DISTINCT observation_id) observations_recorded,"
            "COUNT(DISTINCT media_item_id) media_items_reported,"
            "MIN(CASE WHEN julianday(association_at) IS NOT NULL THEN association_at END) first_observed_at,"
            "MAX(CASE WHEN julianday(association_at) IS NOT NULL THEN association_at END) latest_observed_at "
            "FROM facts WHERE counterpart_id IS NOT NULL GROUP BY counterpart_id ORDER BY counterpart_id",
            eligible_params + (actor_id,),
        )

        valid_observed = [value for value in (
            _timestamp(observed_bounds.get("first_observed_at")),
            _timestamp(observed_bounds.get("latest_observed_at")),
        ) if value]
        media_count = int(media_summary["media_count"])
        published = [value for value in (_timestamp(media_summary.get("first_published_at")), _timestamp(media_summary.get("latest_published_at"))) if value]
        subjects = Counter({
            _clean(row.get("subject_key"), 256): int(row["observation_count"])
            for row in subject_rows if _clean(row.get("subject_key"), 256)
        })
        story_ids: set[str] = set()
        for row in observations:
            oid = row["id"]
            observed = _timestamp(row.get("observed_at"))
            if not observed:
                anomalies.append(_anomaly("malformed_observation_timestamp", oid))
            media_id = _clean(row.get("media_item_id"), 128)
            if media_id and not row.get("persisted_media_id"):
                anomalies.append(_anomaly("dangling_optional_media", oid, media_item_id=media_id))
            elif media_id and media_id not in conflicted_media_ids:
                published_at = _timestamp(row.get("published_at"))
                if row.get("published_at") and not published_at:
                    anomalies.append(_anomaly("malformed_publication_timestamp", media_id))
            if _clean(row.get("story_id"), 128):
                story_ids.add(_clean(row.get("story_id"), 128))

        relationship_rows = _rows(conn, f"""SELECT cl.relationship_type,COUNT(DISTINCT cl.id) AS link_count
            FROM claim_links cl JOIN {observation_table} o ON o.id=cl.{observation_fk}
            WHERE o.{actor_column}=? GROUP BY cl.relationship_type ORDER BY cl.relationship_type""", (actor_id,))
        relationship_counts = Counter({
            _clean(row["relationship_type"], 64).casefold(): int(row["link_count"])
            for row in relationship_rows
            if _clean(row["relationship_type"], 64).casefold() in _CLAIM_RELATIONSHIPS
        })
        unknown_links = _rows(conn, f"""SELECT cl.id,cl.relationship_type
            FROM claim_links cl JOIN {observation_table} o ON o.id=cl.{observation_fk}
            WHERE o.{actor_column}=? AND cl.relationship_type NOT IN ('reports','supports','contradicts','aligned_to')
            ORDER BY cl.id""", (actor_id,))
        anomalies.extend(_anomaly("unrecognized_claim_relationship", row["id"], relationship_type=_clean(row["relationship_type"], 64).casefold()) for row in unknown_links)
        reached_claim_ids = [row["claim_id"] for row in _rows(conn, f"""SELECT DISTINCT cl.claim_id
            FROM claim_links cl JOIN {observation_table} o ON o.id=cl.{observation_fk}
            WHERE o.{actor_column}=? ORDER BY cl.claim_id""", (actor_id,))]
        claims = _rows_by_ids(conn, "intelligence_claims", reached_claim_ids)
        if len(claims) != len(set(reached_claim_ids)):
            raise StoryClaimGraphMaterializationIntegrityError("Claim link target is missing.")
        links_by_observation: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for chunk in _chunks(observation_ids):
            marks = ",".join("?" for _ in chunk)
            for row in _rows(conn, f"SELECT * FROM claim_links WHERE {observation_fk} IN ({marks}) ORDER BY id", tuple(chunk)):
                links_by_observation[_clean(row.get(observation_fk), 128)].append(row)
        claim_type_rows = _rows(conn, f"""SELECT c.claim_type,COUNT(DISTINCT cl.id) AS relationship_count
            FROM claim_links cl JOIN {observation_table} o ON o.id=cl.{observation_fk}
            JOIN intelligence_claims c ON c.id=cl.claim_id WHERE o.{actor_column}=?
            GROUP BY c.claim_type ORDER BY c.claim_type""", (actor_id,))
        claim_types = Counter({_clean(row["claim_type"], 64): int(row["relationship_count"]) for row in claim_type_rows})
        event_types: Counter[str] = Counter()
        canonical_map = _mapping_scope(conn, claims)
        canonical_ids = set(canonical_map.values())
        canonical_claim_rows = _rows_by_ids(conn, "intelligence_claims", canonical_ids)
        for canonical_id in sorted(canonical_ids):
            row = canonical_claim_rows.get(canonical_id)
            if row is None:
                raise StoryClaimGraphMaterializationIntegrityError(
                    "Canonical claim target is missing."
                )
            normalized = _validated_structured_claim(row)
            if normalized is not None:
                event_types[_clean(normalized.get("event_type"), 64)] += 1
        all_claim_ids = sorted(set(claims) | canonical_ids)
        family_keys: set[str] = set()
        entity_by_id: dict[str, dict[str, Any]] = {}
        for chunk in _chunks(all_claim_ids):
            marks = ",".join("?" for _ in chunk)
            story_rows = _rows(conn, "SELECT * FROM story_claim_links WHERE claim_id IN (" + marks + ")", tuple(chunk))
            for row in story_rows:
                if row.get("relationship_type") != "exact_claim_group" or row.get("link_basis") != "downstream_exact_common_claim_id":
                    raise StoryClaimGraphMaterializationIntegrityError("Exact story claim provenance is inconsistent.")
                story_ids.add(row["story_id"])
            evolution_rows = _rows(conn, "SELECT * FROM claim_evolution_links WHERE predecessor_claim_id IN (" + marks + ") OR successor_claim_id IN (" + marks + ")", tuple(chunk + chunk))
            family_keys.update(_clean(row.get("family_key"), 256) for row in evolution_rows if _clean(row.get("family_key"), 256))
            for row in _rows(conn, """SELECT DISTINCT e.* FROM verified_claim_entity_participants AS p
                JOIN canonical_entities AS e ON e.id=p.entity_id
                WHERE p.verification_status='verified' AND p.claim_id IN (""" + marks + ") ORDER BY e.id", tuple(chunk)):
                entity_by_id[row["id"]] = row
        entity_rows = [entity_by_id[key] for key in sorted(entity_by_id)]

        if story_ids:
            existing_story_ids: set[str] = set()
            for chunk in _chunks(story_ids):
                marks = ",".join("?" for _ in chunk)
                existing_story_ids.update(row["id"] for row in _rows(
                    conn, "SELECT id FROM intelligence_stories WHERE id IN (" + marks + ")", tuple(chunk)))
            for missing_story_id in sorted(story_ids - existing_story_ids):
                anomalies.append(_anomaly("dangling_optional_story", missing_story_id))
            story_ids = existing_story_ids

        entities = [{"id": r["id"], "entity_key": r["entity_key"], "entity_type": r["entity_type"], "canonical_name": r["canonical_name"], **({"sport_key": r["sport_key"]} if r.get("sport_key") else {})} for r in entity_rows]
        sports = Counter(_clean(r.get("sport_key"), 64) for r in entity_rows if _clean(r.get("sport_key"), 64))

        dependencies = _rows(
            conn,
            f"""WITH RECURSIVE relevant(kind,id) AS (
              SELECT '{actor_type}',id FROM {observation_table} WHERE {actor_column}=?
              UNION SELECT 'source',a.observation_b_source_observation_id
                FROM observation_independence_assertions a
                WHERE a.observation_a_{actor_type}_observation_id IN
                  (SELECT id FROM {observation_table} WHERE {actor_column}=?)
                  AND a.observation_b_source_observation_id IS NOT NULL
              UNION SELECT 'reporter',a.observation_b_reporter_observation_id
                FROM observation_independence_assertions a
                WHERE a.observation_a_{actor_type}_observation_id IN
                  (SELECT id FROM {observation_table} WHERE {actor_column}=?)
                  AND a.observation_b_reporter_observation_id IS NOT NULL
              UNION SELECT 'source',a.observation_a_source_observation_id
                FROM observation_independence_assertions a
                WHERE a.observation_b_{actor_type}_observation_id IN
                  (SELECT id FROM {observation_table} WHERE {actor_column}=?)
                  AND a.observation_a_source_observation_id IS NOT NULL
              UNION SELECT 'reporter',a.observation_a_reporter_observation_id
                FROM observation_independence_assertions a
                WHERE a.observation_b_{actor_type}_observation_id IN
                  (SELECT id FROM {observation_table} WHERE {actor_column}=?)
                  AND a.observation_a_reporter_observation_id IS NOT NULL
              UNION
              SELECT 'source',d.upstream_source_observation_id
                FROM observation_dependencies d JOIN relevant r
                ON (r.kind='source' AND d.downstream_source_observation_id=r.id)
                OR (r.kind='reporter' AND d.downstream_reporter_observation_id=r.id)
                WHERE d.upstream_source_observation_id IS NOT NULL
              UNION
              SELECT 'reporter',d.upstream_reporter_observation_id
                FROM observation_dependencies d JOIN relevant r
                ON (r.kind='source' AND d.downstream_source_observation_id=r.id)
                OR (r.kind='reporter' AND d.downstream_reporter_observation_id=r.id)
                WHERE d.upstream_reporter_observation_id IS NOT NULL
              UNION
              SELECT 'source',d.downstream_source_observation_id
                FROM observation_dependencies d JOIN relevant r
                ON (r.kind='source' AND d.upstream_source_observation_id=r.id)
                OR (r.kind='reporter' AND d.upstream_reporter_observation_id=r.id)
                WHERE d.downstream_source_observation_id IS NOT NULL
              UNION
              SELECT 'reporter',d.downstream_reporter_observation_id
                FROM observation_dependencies d JOIN relevant r
                ON (r.kind='source' AND d.upstream_source_observation_id=r.id)
                OR (r.kind='reporter' AND d.upstream_reporter_observation_id=r.id)
                WHERE d.downstream_reporter_observation_id IS NOT NULL
            )
            SELECT d.*,
              dso.source_id AS downstream_source_actor,
              dro.reporter_id AS downstream_reporter_actor,
              uso.source_id AS upstream_source_observation_actor,
              uro.reporter_id AS upstream_reporter_observation_actor,
              uso.id AS existing_upstream_source_observation,
              uro.id AS existing_upstream_reporter_observation,
              us.id AS existing_upstream_source,
              ur.id AS existing_upstream_reporter
            FROM observation_dependencies d
            LEFT JOIN source_observations dso ON dso.id=d.downstream_source_observation_id
            LEFT JOIN reporter_observations dro ON dro.id=d.downstream_reporter_observation_id
            LEFT JOIN source_observations uso ON uso.id=d.upstream_source_observation_id
            LEFT JOIN reporter_observations uro ON uro.id=d.upstream_reporter_observation_id
            LEFT JOIN intelligence_sources us ON us.id=d.upstream_source_id
            LEFT JOIN intelligence_reporters ur ON ur.id=d.upstream_reporter_id
            WHERE d.downstream_source_observation_id IN (SELECT id FROM relevant WHERE kind='source')
               OR d.downstream_reporter_observation_id IN (SELECT id FROM relevant WHERE kind='reporter')
               OR d.upstream_source_observation_id IN (SELECT id FROM relevant WHERE kind='source')
               OR d.upstream_reporter_observation_id IN (SELECT id FROM relevant WHERE kind='reporter')
               OR d.upstream_{actor_type}_id=?
            ORDER BY d.id""",
            (actor_id, actor_id, actor_id, actor_id, actor_id, actor_id),
        )
        known_dependency_observations: set[str] = set()
        dependency_relationships: Counter[str] = Counter()
        upstream: list[dict[str, Any]] = []
        downstream: list[dict[str, Any]] = []
        valid_dependency_pairs: set[tuple[str, str]] = set()
        dependency_conflicts: list[dict[str, Any]] = []
        adjacency: defaultdict[str, set[str]] = defaultdict(set)
        dependency_blocked_observations: set[str] = set()
        actor_graph_observations: set[str] = set()
        actor_target_candidates: dict[tuple[str, str], list[str]] = {}
        for target_kind in ("source", "reporter"):
            target_ids = {
                _clean(row.get(f"upstream_{target_kind}_id"), 128)
                for row in dependencies
                if _clean(row.get(f"upstream_{target_kind}_id"), 128)
            }
            target_table = f"{target_kind}_observations"
            target_column = f"{target_kind}_id"
            for chunk in _chunks(target_ids):
                marks = ",".join("?" for _ in chunk)
                candidate_rows = _rows(
                    conn,
                    f"SELECT {target_column} AS actor_id,id FROM {target_table} "
                    f"WHERE {target_column} IN ({marks}) ORDER BY {target_column},id",
                    tuple(chunk),
                )
                grouped: defaultdict[str, list[str]] = defaultdict(list)
                for candidate in candidate_rows:
                    grouped[candidate["actor_id"]].append(candidate["id"])
                for target_id in chunk:
                    actor_target_candidates[(target_kind, target_id)] = grouped[target_id]
        for row in dependencies:
            dep_id = row["id"]
            downstream_active = [(k, _clean(row.get(f"downstream_{k}_observation_id"), 128)) for k in ("source", "reporter") if _clean(row.get(f"downstream_{k}_observation_id"), 128)]
            upstream_active = [(k, _clean(row.get(f"upstream_{k}_observation_id"), 128)) for k in ("source", "reporter") if _clean(row.get(f"upstream_{k}_observation_id"), 128)]
            upstream_active += [(k, _clean(row.get(f"upstream_{k}_id"), 128)) for k in ("source", "reporter") if _clean(row.get(f"upstream_{k}_id"), 128)]
            relationship = _clean(row.get("relationship_type"), 64).casefold()
            dependency_metadata, metadata_valid = _json_object(row.get("metadata_json"))
            observed_valid = bool(_timestamp(row.get("observed_at")))
            recorded_valid = bool(_timestamp(row.get("recorded_at")))
            if (
                len(downstream_active) != 1
                or len(upstream_active) != 1
                or relationship not in _DEPENDENCY_RELATIONSHIPS
                or not metadata_valid
                or not observed_valid
                or not recorded_valid
            ):
                anomalies.append(_anomaly("malformed_dependency", dep_id, relationship_type=relationship))
                for kind, oid in downstream_active:
                    if kind == actor_type and _clean(row.get(f"downstream_{actor_type}_actor"), 128) == actor_id:
                        dependency_blocked_observations.add(oid)
                continue
            down_kind, down_id = downstream_active[0]
            up_kind, up_id = upstream_active[0]
            relevant_down = bool(
                down_kind == actor_type
                and _clean(row.get(f"downstream_{actor_type}_actor"), 128) == actor_id
            )
            relevant_actor_up = f"upstream_{actor_type}_id" in row and _clean(row.get(f"upstream_{actor_type}_id"), 128) == actor_id
            relevant_obs_up = bool(
                up_kind == actor_type
                and row.get(f"upstream_{up_kind}_observation_id")
                and _clean(row.get(f"upstream_{actor_type}_observation_actor"), 128) == actor_id
            )
            relevant = bool(relevant_down or relevant_actor_up or relevant_obs_up)
            if relevant_down:
                actor_graph_observations.add(down_id)
            if relevant_obs_up:
                actor_graph_observations.add(up_id)
            existence_column = (
                f"existing_upstream_{up_kind}_observation"
                if row.get(f"upstream_{up_kind}_observation_id")
                else f"existing_upstream_{up_kind}"
            )
            if not row.get(existence_column):
                anomalies.append(_anomaly("dangling_dependency_target", dep_id))
                if relevant_down:
                    dependency_blocked_observations.add(down_id)
                continue
            if not relevant:
                if row.get(f"upstream_{up_kind}_observation_id"):
                    adjacency[f"{down_kind}:{down_id}"].add(f"{up_kind}:{up_id}")
                continue
            dependency_relationships[relationship] += 1
            item = {"dependency_id": dep_id, "relationship_type": relationship, "target_type": up_kind, "target_id": up_id, "observed_at": _timestamp(row.get("observed_at")) or None}
            if relevant_down:
                known_dependency_observations.add(down_id)
                upstream.append(item)
            if relevant_actor_up or relevant_obs_up:
                downstream.append({**item, "downstream_type": down_kind, "downstream_id": down_id})
            if row.get(f"upstream_{up_kind}_observation_id"):
                adjacency[f"{down_kind}:{down_id}"].add(f"{up_kind}:{up_id}")
                valid_dependency_pairs.add(tuple(sorted((f"{down_kind}:{down_id}", f"{up_kind}:{up_id}"))))
            else:
                candidates = actor_target_candidates.get((up_kind, up_id), [])
                if len(candidates) == 1:
                    upstream_node = f"{up_kind}:{candidates[0]}"
                    adjacency[f"{down_kind}:{down_id}"].add(upstream_node)
                    valid_dependency_pairs.add(tuple(sorted((f"{down_kind}:{down_id}", upstream_node))))
                elif relevant_down:
                    dependency_blocked_observations.add(down_id)
                    anomalies.append(_anomaly(
                        "unresolved_actor_dependency", dep_id,
                        matching_observation_ids=candidates,
                    ))

        cyclic = _cyclic_nodes(adjacency)
        for node in sorted(cyclic):
            kind, oid = node.split(":", 1)
            if kind == actor_type and oid in actor_graph_observations:
                dependency_blocked_observations.add(oid)
        if cyclic:
            anomalies.append(_anomaly("dependency_cycle", "|".join(sorted(cyclic)), observation_keys=sorted(cyclic)))

        assertions = _rows(conn, f"""SELECT a.*, e.verification_status AS evidence_verification_status,
            e.subject_key AS evidence_subject_key,
            e.metadata_json AS evidence_metadata_json,
            e.observed_at AS evidence_observed_at,
            e.recorded_at AS evidence_recorded_at,
            aso.source_id AS observation_a_source_actor_id,
            aro.reporter_id AS observation_a_reporter_actor_id,
            bso.source_id AS observation_b_source_actor_id,
            bro.reporter_id AS observation_b_reporter_actor_id,
            COALESCE(aso.source_id,aro.source_id) AS observation_a_source_identity,
            COALESCE(bso.source_id,bro.source_id) AS observation_b_source_identity,
            COALESCE(aso.subject_key,aro.subject_key) AS observation_a_subject_key,
            COALESCE(bso.subject_key,bro.subject_key) AS observation_b_subject_key,
            CASE WHEN aso.id IS NOT NULL OR aro.id IS NOT NULL THEN 1 ELSE 0 END AS observation_a_exists,
            CASE WHEN bso.id IS NOT NULL OR bro.id IS NOT NULL THEN 1 ELSE 0 END AS observation_b_exists
            FROM observation_independence_assertions AS a
            LEFT JOIN evidence_records AS e ON e.id=a.provenance_evidence_id
            LEFT JOIN source_observations aso ON aso.id=a.observation_a_source_observation_id
            LEFT JOIN reporter_observations aro ON aro.id=a.observation_a_reporter_observation_id
            LEFT JOIN source_observations bso ON bso.id=a.observation_b_source_observation_id
            LEFT JOIN reporter_observations bro ON bro.id=a.observation_b_reporter_observation_id
            WHERE a.observation_a_{actor_type}_observation_id IN
                    (SELECT id FROM {observation_table} WHERE {actor_column}=?)
               OR a.observation_b_{actor_type}_observation_id IN
                    (SELECT id FROM {observation_table} WHERE {actor_column}=?)
            ORDER BY a.id""", (actor_id, actor_id))
        qualified_pairs: list[dict[str, Any]] = []
        independent_observations: set[str] = set()
        counterparts: dict[tuple[str, str], dict[str, Any]] = {}
        independence_conflicts: list[dict[str, Any]] = []
        for row in assertions:
            assertion_id = row["id"]
            a = _actor_endpoint(row, "observation_a")
            b = _actor_endpoint(row, "observation_b")
            involved = []
            for side, current, other in (("observation_a", a, b), ("observation_b", b, a)):
                actor_value = _clean(row.get(f"{side}_{actor_type}_actor_id"), 128)
                if current[0] == actor_type and actor_value == actor_id:
                    involved.append((current[0], current[1], other))
            if not involved:
                continue
            assertion_metadata, assertion_metadata_valid = _json_object(row.get("metadata_json"))
            evidence_metadata, evidence_metadata_valid = _json_object(row.get("evidence_metadata_json"))
            endpoints_valid = bool(
                all(a) and all(b) and a != b
                and row.get("observation_a_exists")
                and row.get("observation_b_exists")
            )
            source_a = _clean(row.get("observation_a_source_identity"), 128)
            source_b = _clean(row.get("observation_b_source_identity"), 128)
            subject_a = _clean(row.get("observation_a_subject_key"), 256)
            subject_b = _clean(row.get("observation_b_subject_key"), 256)
            evidence_subject = _clean(row.get("evidence_subject_key"), 256)
            structurally_valid = bool(
                endpoints_valid
                and source_a and source_b and source_a != source_b
                and subject_a and subject_a == subject_b == evidence_subject
                and assertion_metadata_valid and evidence_metadata_valid
                and _timestamp(row.get("observed_at"))
                and _timestamp(row.get("recorded_at"))
                and _timestamp(row.get("evidence_observed_at"))
                and _timestamp(row.get("evidence_recorded_at"))
            )
            if (
                not structurally_valid
                or row.get("verification_status") != "verified"
                or row.get("evidence_verification_status") != "verified"
            ):
                anomalies.append(_anomaly("unqualified_independence_assertion", assertion_id))
                continue
            pair_key = tuple(sorted((f"{a[0]}:{a[1]}", f"{b[0]}:{b[1]}")))
            if pair_key in valid_dependency_pairs:
                conflict = {"assertion_id": assertion_id, "observation_pair": list(pair_key)}
                independence_conflicts.append(conflict)
                dependency_conflicts.append(conflict)
                continue
            pair_actor_observations = sorted({oid for _, oid, _ in involved})
            if dependency_blocked_observations.intersection(pair_actor_observations) or any(node in cyclic for node in pair_key):
                anomalies.append(_anomaly("independence_dependency_blocker", assertion_id))
                continue
            independent_observations.update(pair_actor_observations)
            pair = {"assertion_id": assertion_id, "actor_observation_ids": pair_actor_observations, "observed_at": _timestamp(row.get("observed_at")) or None}
            qualified_pairs.append(pair)
            for _, _, other in involved:
                side = "observation_a" if other == a else "observation_b"
                other_actor_id = _clean(row.get(f"{side}_{other[0]}_actor_id"), 128)
                if other_actor_id:
                    counterparts[(other[0], other_actor_id)] = {"actor_type": other[0], "actor_id": other_actor_id}

        counterpart_table = "intelligence_sources" if actor_type == "reporter" else "intelligence_reporters"
        counterpart_ids = sorted({_clean(row.get("counterpart_id"), 128) for row in association_rows if _clean(row.get("counterpart_id"), 128)})
        counterpart_names: dict[str, str] = {}
        for chunk in _chunks(counterpart_ids):
            marks = ",".join("?" for _ in chunk)
            counterpart_names.update({row["id"]: row["display_name"] for row in _rows(
                conn, f"SELECT id,display_name FROM {counterpart_table} WHERE id IN (" + marks + ")", tuple(chunk))})
        association_items = []
        for row in association_rows:
            counterpart_id = _clean(row.get("counterpart_id"), 128)
            if counterpart_id not in counterpart_names:
                anomalies.append(_anomaly("dangling_actor_association", counterpart_id))
                continue
            association_items.append({"id": counterpart_id, "display_name": counterpart_names[counterpart_id], "first_observed_at": _timestamp(row.get("first_observed_at")) or None, "latest_observed_at": _timestamp(row.get("latest_observed_at")) or None, "observations_recorded": int(row["observations_recorded"]), "media_items_reported": int(row["media_items_reported"])})

        activity = []
        for row in observations:
            published_at = _timestamp(row.get("published_at"))
            observed_at = _timestamp(row.get("observed_at"))
            if not (published_at or observed_at):
                continue
            oid = row["id"]
            related = links_by_observation.get(oid, [])
            item = {"observation_id": oid, "actor_type": actor_type, "observed_at": observed_at or None, "published_at": published_at or None, "time_basis": "published_at" if published_at else "observed_at", "claim_ids": sorted({_clean(link.get("claim_id"), 128) for link in related}), "canonical_claim_ids": sorted({canonical_map.get(_clean(link.get("claim_id"), 128), _clean(link.get("claim_id"), 128)) for link in related}), "claim_relationships": sorted({_clean(link.get("relationship_type"), 64) for link in related})}
            if row.get("persisted_media_id"):
                item["media"] = {"id": row["persisted_media_id"], "title": _clean(row.get("title"), 512), "canonical_url": _clean(row.get("canonical_url"), 2048)}
            if row.get("story_id"):
                item["story_id"] = row["story_id"]
            activity.append((published_at or observed_at, oid, item))
        activity.sort(key=lambda value: (value[0], value[1]), reverse=True)
        eligible_activity_count = int(observation_summary["eligible_activity_count"])

        actor_payload = {"actor_type": actor_type, "id": actor_id, "canonical_key": actor["source_key"] if actor_type == "source" else actor["identity_key"], "display_name": actor.get("display_name", ""), "first_seen_at": actor.get("first_seen_at"), "last_seen_at": actor.get("last_seen_at")}
        if metadata:
            actor_payload["metadata"] = metadata
        if actor_type == "source":
            actor_payload.update({"source_type": actor.get("source_type"), "canonical_domain": actor.get("canonical_domain")})

        result = {
            "version": PROFILE_VERSION,
            "status": "ok",
            "actor": actor_payload,
            "summary": {
                "observations_recorded": observation_count, "media_items_reported": media_count,
                "claim_report_relationships": relationship_counts["reports"], "exact_claims_reported": len(claims),
                "canonical_claims_reported": len(canonical_ids), "exact_stories_reported": len(story_ids),
                "evolution_families_touched": len(family_keys), "known_dependency_observations": len(known_dependency_observations),
                "verified_independent_observations": len(independent_observations), "verified_independence_pairs": len(qualified_pairs),
                "claim_support_relationships": relationship_counts["supports"], "claim_contradiction_relationships": relationship_counts["contradicts"],
                "claim_alignment_relationships": relationship_counts["aligned_to"],
                "first_observed_activity_at": min(valid_observed) if valid_observed else None,
                "latest_observed_activity_at": max(valid_observed) if valid_observed else None,
                "first_published_at": min(published) if published else None, "latest_published_at": max(published) if published else None,
            },
            "coverage": {
                "subjects": [{"subject_key": k, "observation_count": v} for k, v in sorted(subjects.items(), key=lambda x: (-x[1], x[0]))],
                "sports": [{"sport_key": k, "entity_count": v} for k, v in sorted(sports.items())], "entities": entities,
                "claim_types": [{"claim_type": k, "relationship_count": v} for k, v in sorted(claim_types.items())],
                "event_types": [{"event_type": k, "relationship_count": v} for k, v in sorted(event_types.items())],
                "sample_size_status": "limited" if observation_count < 5 else "sufficient_for_descriptive_counts",
            },
            "associations": {"observed_sources" if actor_type == "reporter" else "observed_reporters": association_items},
            "dependency_context": {"relationship_counts": dict(sorted(dependency_relationships.items())), "upstream": sorted(upstream, key=lambda x: x["dependency_id"]), "downstream": sorted(downstream, key=lambda x: x["dependency_id"]), "observations_with_no_known_dependency_record": max(0, observation_count - len(known_dependency_observations)), "conflicts": dependency_conflicts},
            "independence_context": {"qualified_pairs": sorted(qualified_pairs, key=lambda x: x["assertion_id"]), "counterpart_actors": [counterparts[k] for k in sorted(counterparts)], "conflicts": independence_conflicts},
            "recent_activity": {"items": [x[2] for x in activity[:recent_limit]], "limit": recent_limit, "has_more": eligible_activity_count > recent_limit},
            "anomalies": sorted(anomalies, key=lambda x: (x["type"], x["stable_id"])),
            "policy": {
                "profile_reflects_only_sportabase_observed_persisted_content": True,
                "missing_relationships_do_not_prove_real_world_absence": True,
                "no_dependency_record_does_not_establish_originality_or_independence": True,
                "verified_independence_requires_evidence_backed_pairwise_qualification": True,
                "counts_do_not_establish_reliability_accuracy_influence_authority_or_truth": True,
                "observed_reporting_association_does_not_establish_employment": True,
                "historical_ingestion_and_identity_resolution_may_be_incomplete": True,
                "percentages_and_actor_scores_are_not_computed": True,
            },
        }
        return result
    finally:
        conn.close()


def build_source_profile(*, source_id: str, connection_factory, recent_limit: int = 25):
    return build_actor_profile(actor_type="source", actor_id=source_id, connection_factory=connection_factory, recent_limit=recent_limit)


def build_reporter_profile(*, reporter_id: str, connection_factory, recent_limit: int = 25):
    return build_actor_profile(actor_type="reporter", actor_id=reporter_id, connection_factory=connection_factory, recent_limit=recent_limit)
