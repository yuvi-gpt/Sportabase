from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.analysis.features import OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY
from app.intelligence.claim_evolution import claim_evolution_family
from app.intelligence.stories import story_id_for_canonical_key
from app.story import story_claim_graph_materialization as story_graph


STORY_EVOLUTION_VERSION = "story-evolution-v1"
_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500
_EVOLUTION_TYPES = {
    "progresses_to": "claim_progresses_to",
    "resolves_to": "claim_resolves_to",
    "contradicts": "claim_contradiction_observed",
}


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _timestamp(value: Any, *, label: str, optional: bool = False) -> datetime | None:
    text = _clean(value, 128)
    if optional and not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        offset = parsed.utcoffset()
    except (TypeError, ValueError, OverflowError) as error:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " timestamp is invalid."
        ) from error
    if offset is None:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " timestamp must include a timezone."
        )
    return parsed


def _valid_timestamp(value: Any) -> bool:
    try:
        return _timestamp(value, label="Dependency") is not None
    except story_graph.StoryClaimGraphMaterializationIntegrityError:
        return False


def _valid_json_object(value: Any) -> bool:
    try:
        _json(value, label="Dependency metadata")
    except story_graph.StoryClaimGraphMaterializationIntegrityError:
        return False
    return True


def _json(value: Any, *, label: str, expected=dict):
    try:
        parsed = json.loads(str(value if value is not None else "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " JSON is invalid."
        ) from error
    if not isinstance(parsed, expected):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " JSON has an invalid shape."
        )
    return parsed


def _event_id(event_type: str, *parts: Any) -> str:
    identity = "|".join([STORY_EVOLUTION_VERSION, event_type, *(_clean(p, 512) for p in parts)])
    return "story-evolution-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:40]


def _placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def _event_sort_key(event: Mapping[str, Any]):
    return (
        _timestamp(event.get("event_time"), label="Story evolution event"),
        _clean(event.get("event_type"), 64),
        _clean(event.get("event_id"), 128),
    )


def _structured_claim(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _json(row.get("metadata_json"), label="Canonical claim metadata")
    candidate = metadata.get("structured_claim")
    if not isinstance(candidate, Mapping):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical structured claim identity is unavailable."
        )
    try:
        family = claim_evolution_family(candidate)
    except Exception as error:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical structured claim identity is invalid."
        ) from error
    return family


def _load_scope(conn, requested_id: str):
    requested = conn.execute(
        "SELECT * FROM intelligence_claims WHERE id = ?", (requested_id,)
    ).fetchone()
    if requested is None:
        return None
    requested = dict(requested)
    requested_family = _structured_claim(requested)

    incident = [
        dict(row)
        for row in conn.execute(
            """
            SELECT * FROM claim_evolution_links
            WHERE predecessor_claim_id = ? OR successor_claim_id = ?
            ORDER BY observed_at, id
            """,
            (requested_id, requested_id),
        ).fetchall()
    ]
    family_keys = {_clean(row.get("family_key"), 1024) for row in incident}
    if "" in family_keys or len(family_keys) > 1:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical claim evolution family membership is inconsistent."
        )
    persisted_family = next(iter(family_keys), "")
    if persisted_family:
        if requested_family.get("status") != "ready" or persisted_family != requested_family.get("family_key"):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution family key is inconsistent."
            )
        links = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM claim_evolution_links WHERE family_key = ? ORDER BY observed_at, id",
                (persisted_family,),
            ).fetchall()
        ]
        claim_ids = sorted(
            {requested_id}
            | {str(row["predecessor_claim_id"]) for row in links}
            | {str(row["successor_claim_id"]) for row in links}
        )
    else:
        links = []
        claim_ids = [requested_id]

    rows = [
        dict(row)
        for row in conn.execute(
            f"SELECT * FROM intelligence_claims WHERE id IN ({_placeholders(claim_ids)})",
            tuple(claim_ids),
        ).fetchall()
    ]
    if len(rows) != len(claim_ids):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Canonical claim evolution family contains a dangling claim."
        )
    claims = {row["id"]: row for row in rows}
    subject = _clean(requested.get("subject_key"), 256)
    for claim_id, claim in claims.items():
        if _clean(claim.get("subject_key"), 256) != subject:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution family crosses subjects."
            )
        family = _structured_claim(claim)
        if persisted_family and (
            family.get("status") != "ready" or family.get("family_key") != persisted_family
        ):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution family contains inconsistent identity."
            )
    for link in links:
        relationship = _clean(link.get("relationship_type"), 64)
        if relationship not in _EVOLUTION_TYPES:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution relationship is unsupported."
            )
        if link["predecessor_claim_id"] not in claims or link["successor_claim_id"] not in claims:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution link is malformed."
            )
        if _clean(link.get("subject_key"), 256) != subject or _clean(link.get("family_key"), 1024) != persisted_family:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution link scope is inconsistent."
            )
        _json(link.get("metadata_json"), label="Claim evolution metadata")
        _timestamp(link.get("observed_at"), label="Claim evolution")
    return requested, persisted_family, claims, links


def _load_stories(conn, claims: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    claim_ids = sorted(claims)
    links = [
        dict(row)
        for row in conn.execute(
            f"SELECT * FROM story_claim_links WHERE claim_id IN ({_placeholders(claim_ids)}) ORDER BY story_id, claim_id",
            tuple(claim_ids),
        ).fetchall()
    ]
    by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in links:
        by_claim[str(link["claim_id"])].append(link)
    story_ids = sorted({str(row["story_id"]) for row in links})
    stories = {}
    if story_ids:
        stories = {
            str(row["id"]): dict(row)
            for row in conn.execute(
                f"SELECT * FROM intelligence_stories WHERE id IN ({_placeholders(story_ids)})",
                tuple(story_ids),
            ).fetchall()
        }
    result = {}
    for claim_id, claim in claims.items():
        canonical_key = story_graph.STORY_CANONICAL_KEY_PREFIX + "|claim:" + claim_id
        expected_id = story_id_for_canonical_key(canonical_key)
        claim_links = by_claim.get(claim_id, [])
        if len(claim_links) != 1:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story claim scope is inconsistent."
            )
        link = claim_links[0]
        story = stories.get(expected_id)
        if story is None or str(link["story_id"]) != expected_id or _clean(story.get("canonical_key")) != canonical_key:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Deterministic canonical story identity is inconsistent."
            )
        if _clean(link.get("relationship_type"), 64) != story_graph.STORY_CLAIM_RELATIONSHIP_TYPE or _clean(link.get("link_basis"), 128) != story_graph.STORY_CLAIM_LINK_BASIS:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story claim provenance is inconsistent."
            )
        metadata = _json(story.get("metadata_json"), label="Canonical story metadata")
        if (
            _clean(metadata.get("claim_id"), 128) != claim_id
            or _clean(metadata.get("subject_key"), 256) != _clean(claim.get("subject_key"), 256)
            or _clean(metadata.get("materialization_basis"), 128) != story_graph.STORY_CLAIM_LINK_BASIS
            or _clean(metadata.get("canonical_claim_story_materialization_version"), 128)
            != story_graph.CANONICAL_CLAIM_STORY_MATERIALIZATION_VERSION
        ):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story provenance is inconsistent."
            )
        link_metadata = _json(link.get("metadata_json"), label="Canonical story claim link metadata")
        if _clean(link_metadata.get("materialization_version"), 128) != story_graph.STORY_CLAIM_GRAPH_MATERIALIZATION_VERSION:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story claim path provenance is inconsistent."
            )
        result[claim_id] = story
    return result


def _legacy_scope(conn, claim_ids: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    rows = [
        dict(row)
        for row in conn.execute(
            f"SELECT * FROM claim_identity_mappings WHERE canonical_claim_id IN ({_placeholders(claim_ids)}) OR production_claim_id IN ({_placeholders(claim_ids)})",
            tuple(claim_ids) + tuple(claim_ids),
        ).fetchall()
    ]
    family_set = set(claim_ids)
    by_claim = {claim_id: [] for claim_id in claim_ids}
    all_ids = list(claim_ids)
    for row in rows:
        production = _clean(row.get("production_claim_id"), 128)
        canonical = _clean(row.get("canonical_claim_id"), 128)
        if production in family_set:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "A canonical structured claim cannot act as a legacy mapping source."
            )
        if canonical not in family_set or _clean(row.get("mapping_status"), 64) != "verified_equivalent":
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Claim identity mapping is inconsistent."
            )
        by_claim[canonical].append(production)
        all_ids.append(production)
    legacy_ids = sorted(set(all_ids) - family_set)
    if legacy_ids and conn.execute(
        f"SELECT 1 FROM claim_identity_mappings WHERE canonical_claim_id IN ({_placeholders(legacy_ids)}) LIMIT 1",
        tuple(legacy_ids),
    ).fetchone() is not None:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            "Claim identity mapping chain or cycle is not allowed."
        )
    return by_claim, sorted(set(all_ids))


def _load_reports(conn, claims, stories, legacy_by_claim, all_scope_ids):
    ids = sorted(all_scope_ids)
    rows = [
        dict(row)
        for row in conn.execute(
            f"""
            SELECT cl.claim_id, cl.id AS claim_link_id, 'source' AS observation_kind,
                   o.id AS observation_id, o.subject_key, o.media_item_id,
                   o.source_id, NULL AS reporter_id, o.observed_at, o.recorded_at,
                   m.published_at, m.title, m.canonical_url,
                   m.source_id AS media_source_id, m.reporter_id AS media_reporter_id
            FROM claim_links cl JOIN source_observations o ON o.id=cl.source_observation_id
            LEFT JOIN media_items m ON m.id=o.media_item_id
            WHERE cl.claim_id IN ({_placeholders(ids)}) AND cl.relationship_type='reports'
            UNION ALL
            SELECT cl.claim_id, cl.id, 'reporter', o.id, o.subject_key, o.media_item_id,
                   o.source_id, o.reporter_id, o.observed_at, o.recorded_at,
                   m.published_at, m.title, m.canonical_url, m.source_id, m.reporter_id
            FROM claim_links cl JOIN reporter_observations o ON o.id=cl.reporter_observation_id
            LEFT JOIN media_items m ON m.id=o.media_item_id
            WHERE cl.claim_id IN ({_placeholders(ids)}) AND cl.relationship_type='reports'
            ORDER BY media_item_id, observation_kind, observation_id
            """,
            tuple(ids) + tuple(ids),
        ).fetchall()
    ]
    owner = {claim_id: claim_id for claim_id in claims}
    for canonical, legacy_ids in legacy_by_claim.items():
        for legacy in legacy_ids:
            owner[legacy] = canonical
    observations = {}
    media_by_claim: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        claim_id = owner.get(str(row["claim_id"]))
        if claim_id is None or _clean(row.get("subject_key"), 256) != _clean(claims[claim_id].get("subject_key"), 256):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Claim-linked observation subject is inconsistent."
            )
        media_id = _clean(row.get("media_item_id"), 128)
        if not media_id:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Claim-linked reporting media item is missing."
            )
        observed_at = _clean(row.get("observed_at"), 128)
        observed_value = _timestamp(observed_at, label="Reporting observation")
        published_at = _clean(row.get("published_at"), 128)
        published_value = _timestamp(published_at, label="Media publication", optional=True)
        key = str(row["observation_kind"]) + "_observation:" + str(row["observation_id"])
        observations[key] = {
            **row,
            "claim_id": claim_id,
            "observation_key": key,
            "observed_value": observed_value,
            "published_value": published_value,
        }
        _timestamp(row.get("recorded_at"), label="Reporting observation audit")
        item = media_by_claim[claim_id].setdefault(
            media_id,
            {
                "claim_id": claim_id,
                "story_id": stories[claim_id]["id"],
                "media_item_id": media_id,
                "published_at": published_at,
                "published_value": published_value,
                "observations": [],
                "recorded_at": _clean(row.get("recorded_at"), 128),
                "source_id": _clean(row.get("media_source_id") or row.get("source_id"), 128),
                "reporter_id": _clean(row.get("media_reporter_id") or row.get("reporter_id"), 128),
            },
        )
        item["observations"].append(key)

    persisted_story_media = [
        dict(row)
        for row in conn.execute(
            f"SELECT * FROM story_media_links WHERE story_id IN ({_placeholders([s['id'] for s in stories.values()])})",
            tuple(s["id"] for s in stories.values()),
        ).fetchall()
    ]
    actual: dict[str, set[str]] = defaultdict(set)
    for row in persisted_story_media:
        if _clean(row.get("relationship_type"), 64) != story_graph.STORY_MEDIA_RELATIONSHIP_TYPE:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story media semantics are inconsistent."
            )
        try:
            confidence = float(row.get("confidence"))
        except (TypeError, ValueError) as error:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story media confidence is invalid."
            ) from error
        if abs(confidence - story_graph.STORY_MEDIA_STRUCTURAL_CONFIDENCE) > 1e-9:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical story media confidence is invalid."
            )
        actual[str(row["story_id"])].add(str(row["media_item_id"]))
    for claim_id, story in stories.items():
        if actual.get(str(story["id"]), set()) != set(media_by_claim.get(claim_id, {})):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical reporting graph and story media graph are inconsistent."
            )
    return observations, media_by_claim


def _report_classification(conn, observations):
    if not observations:
        return set(), set(), {}
    source_ids = [str(v["observation_id"]) for v in observations.values() if v["observation_kind"] == "source"]
    reporter_ids = [str(v["observation_id"]) for v in observations.values() if v["observation_kind"] == "reporter"]
    conditions, params = [], []
    if source_ids:
        conditions.append(f"downstream_source_observation_id IN ({_placeholders(source_ids)})")
        params.extend(source_ids)
    if reporter_ids:
        conditions.append(f"downstream_reporter_observation_id IN ({_placeholders(reporter_ids)})")
        params.extend(reporter_ids)
    dependencies = [dict(row) for row in conn.execute("SELECT * FROM observation_dependencies WHERE " + " OR ".join(conditions), tuple(params)).fetchall()]
    dependent_keys = set()
    dependency_pairs = set()
    potential_dependency_pairs = set()
    recognized = set(OBSERVATION_DEPENDENCY_RELATIONSHIP_VOCABULARY)
    by_source: dict[str, list[str]] = defaultdict(list)
    by_reporter: dict[str, list[str]] = defaultdict(list)
    for observation_key, observation in observations.items():
        source_id = _clean(observation.get("source_id"), 128)
        reporter_id = _clean(observation.get("reporter_id"), 128)
        if source_id:
            by_source[source_id].append(observation_key)
        if reporter_id:
            by_reporter[reporter_id].append(observation_key)
    for row in dependencies:
        active_downstream = sum(
            bool(row[column])
            for column in (
                "downstream_source_observation_id",
                "downstream_reporter_observation_id",
            )
        )
        active_upstream = sum(
            bool(row[column])
            for column in (
                "upstream_source_observation_id",
                "upstream_reporter_observation_id",
                "upstream_source_id",
                "upstream_reporter_id",
            )
        )
        kind = "source_observation" if row["downstream_source_observation_id"] else "reporter_observation"
        downstream = kind + ":" + str(row["downstream_source_observation_id"] or row["downstream_reporter_observation_id"])
        if downstream not in observations:
            continue
        relationship_recognized = _clean(row.get("relationship_type"), 64) in recognized
        structurally_valid = (
            active_downstream == 1
            and active_upstream == 1
            and _valid_timestamp(row.get("observed_at"))
            and _valid_timestamp(row.get("recorded_at"))
            and _valid_json_object(row.get("metadata_json"))
        )
        resolved: list[str] = []
        if row["upstream_source_observation_id"]:
            candidate = "source_observation:" + str(row["upstream_source_observation_id"])
            if candidate in observations:
                resolved = [candidate]
        elif row["upstream_reporter_observation_id"]:
            candidate = "reporter_observation:" + str(row["upstream_reporter_observation_id"])
            if candidate in observations:
                resolved = [candidate]
        elif row["upstream_source_id"]:
            resolved = sorted(by_source.get(_clean(row["upstream_source_id"], 128), ()))
        elif row["upstream_reporter_id"]:
            resolved = sorted(by_reporter.get(_clean(row["upstream_reporter_id"], 128), ()))
        candidate_pairs = {
            tuple(sorted((downstream, upstream)))
            for upstream in resolved
            if upstream != downstream
        }
        if len(resolved) == 1 and relationship_recognized and structurally_valid:
            dependent_keys.add(downstream)
            dependency_pairs.update(candidate_pairs)
        else:
            potential_dependency_pairs.update(candidate_pairs)

    assertion_conditions, assertion_params = [], []
    for column, values in (("observation_a_source_observation_id", source_ids), ("observation_b_source_observation_id", source_ids), ("observation_a_reporter_observation_id", reporter_ids), ("observation_b_reporter_observation_id", reporter_ids)):
        if values:
            assertion_conditions.append(f"a.{column} IN ({_placeholders(values)})")
            assertion_params.extend(values)
    assertions = [dict(row) for row in conn.execute(
        "SELECT a.*, e.verification_status AS evidence_verification_status, e.metadata_json AS evidence_metadata_json FROM observation_independence_assertions a LEFT JOIN evidence_records e ON e.id=a.provenance_evidence_id WHERE " + " OR ".join(assertion_conditions),
        tuple(assertion_params),
    ).fetchall()]
    independent_keys = set()
    evidence_by_key: dict[str, set[str]] = defaultdict(set)
    for row in assertions:
        def endpoint(side):
            source = row[f"observation_{side}_source_observation_id"]
            reporter = row[f"observation_{side}_reporter_observation_id"]
            return ("source_observation:" + str(source)) if source else ("reporter_observation:" + str(reporter)) if reporter else ""
        left, right = endpoint("a"), endpoint("b")
        pair = tuple(sorted((left, right)))
        if left not in observations or right not in observations or left == right:
            continue
        _timestamp(row.get("observed_at"), label="Independence assertion")
        _timestamp(row.get("recorded_at"), label="Independence assertion audit")
        _json(row.get("metadata_json"), label="Independence assertion metadata")
        evidence_metadata = _json(row.get("evidence_metadata_json"), label="Independence evidence metadata")
        distinct_sources = bool(observations[left].get("source_id") and observations[right].get("source_id") and observations[left]["source_id"] != observations[right]["source_id"])
        qualified = (
            _clean(row.get("verification_status"), 64) == "verified"
            and _clean(row.get("evidence_verification_status"), 64) == "verified"
            and distinct_sources
            and pair not in dependency_pairs
            and pair not in potential_dependency_pairs
        )
        if qualified:
            later = max((left, right), key=lambda key: (observations[key]["published_value"] or observations[key]["observed_value"], key))
            if later not in dependent_keys:
                independent_keys.add(later)
                evidence_by_key[later].add(str(row["provenance_evidence_id"]))
    return dependent_keys, independent_keys, evidence_by_key


def _load_adjudication(conn, claim_ids):
    placeholders = _placeholders(claim_ids)
    revisions = {str(row["id"]): dict(row) for row in conn.execute(f"SELECT * FROM adjudication_state_revisions WHERE claim_id IN ({placeholders})", tuple(claim_ids)).fetchall()}
    transitions = [dict(row) for row in conn.execute(f"SELECT * FROM adjudication_state_transitions WHERE claim_id IN ({placeholders})", tuple(claim_ids)).fetchall()]
    corrections = [dict(row) for row in conn.execute(f"SELECT * FROM automatic_correction_events WHERE claim_id IN ({placeholders})", tuple(claim_ids)).fetchall()]
    return revisions, transitions, corrections


def build_story_evolution(*, canonical_claim_id: str, connection_factory, limit: int = _DEFAULT_LIMIT) -> dict[str, Any]:
    requested_id = _clean(canonical_claim_id, 128)
    if not requested_id:
        raise ValueError("Story evolution canonical_claim_id is required.")
    if connection_factory is None:
        raise ValueError("Story evolution requires database access.")
    try:
        bounded_limit = int(limit)
    except (TypeError, ValueError) as error:
        raise ValueError("Story evolution limit must be an integer.") from error
    if bounded_limit < 1 or bounded_limit > _MAX_LIMIT:
        raise ValueError(f"Story evolution limit must be between 1 and {_MAX_LIMIT}.")

    conn = connection_factory()
    try:
        scope = _load_scope(conn, requested_id)
        if scope is None:
            return {"version": STORY_EVOLUTION_VERSION, "status": "not_found", "canonical_claim_id": requested_id}
        requested, family_key, claims, evolution_links = scope
        stories = _load_stories(conn, claims)
        legacy_by_claim, all_scope_ids = _legacy_scope(conn, sorted(claims))
        observations, media_by_claim = _load_reports(conn, claims, stories, legacy_by_claim, all_scope_ids)
        dependent, independent, independence_evidence = _report_classification(conn, observations)
        revisions, transitions, corrections = _load_adjudication(conn, sorted(claims))
    finally:
        conn.close()

    events = []
    reports_count = 0
    dependent_count = 0
    independent_count = 0
    for claim_id in sorted(claims):
        media = list(media_by_claim.get(claim_id, {}).values())
        media.sort(key=lambda item: (item["published_value"] or min(observations[key]["observed_value"] for key in item["observations"]), item["media_item_id"]))
        for index, report in enumerate(media):
            observed_at = min((_clean(observations[key]["observed_at"], 128) for key in report["observations"]), key=lambda value: _timestamp(value, label="Reporting observation"))
            observation_keys = sorted(report["observations"])
            dependent_basis = [key for key in observation_keys if key in dependent]
            independent_basis = [key for key in observation_keys if key in independent]
            event_type = "first_report_observed" if index == 0 else "additional_report_observed"
            event_time = report["published_at"] or observed_at
            basis_key = ",".join(observation_keys)
            event = {
                "event_id": _event_id(event_type, claim_id, report["media_item_id"], basis_key),
                "event_type": event_type,
                "event_time": event_time,
                "claim_id": claim_id,
                "story_id": report["story_id"],
                "media_item_id": report["media_item_id"],
                "observed_at": observed_at,
                "recorded_at": report["recorded_at"],
                "observation_ids": [key.split(":", 1)[1] for key in observation_keys],
            }
            if report["published_at"]:
                event["published_at"] = report["published_at"]
            if report["source_id"]:
                event["source_id"] = report["source_id"]
            if report["reporter_id"]:
                event["reporter_id"] = report["reporter_id"]
            events.append(event)
            if dependent_basis:
                dependent_count += 1
                events.append({
                    **event,
                    "event_id": _event_id("dependent_report_observed", claim_id, report["media_item_id"], basis_key),
                    "event_type": "dependent_report_observed",
                    "dependency_observation_keys": dependent_basis,
                })
            elif independent_basis:
                independent_count += 1
                events.append({
                    **event,
                    "event_id": _event_id("verified_independent_report_observed", claim_id, report["media_item_id"], basis_key),
                    "event_type": "verified_independent_report_observed",
                    "independence_evidence_ids": sorted({evidence for key in independent_basis for evidence in independence_evidence[key]}),
                })
            reports_count += 1

    for link in evolution_links:
        event_type = _EVOLUTION_TYPES[str(link["relationship_type"])]
        events.append({
            "event_id": _event_id(event_type, link["id"]),
            "event_type": event_type,
            "event_time": str(link["observed_at"]),
            "observed_at": str(link["observed_at"]),
            "predecessor_claim_id": str(link["predecessor_claim_id"]),
            "successor_claim_id": str(link["successor_claim_id"]),
            "relationship_type": str(link["relationship_type"]),
            "evolution_link_id": str(link["id"]),
        })

    for transition in transitions:
        revision = revisions.get(str(transition["revision_id"]))
        if revision is None or str(revision["claim_id"]) != str(transition["claim_id"]):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError("Adjudication transition revision is missing.")
        as_of = _clean(revision.get("as_of"), 128)
        _timestamp(as_of, label="Adjudication revision")
        before = None if transition.get("from_state_json") is None else _json(transition["from_state_json"], label="Adjudication before state")
        after = _json(transition.get("to_state_json"), label="Adjudication after state")
        evidence_ids = _json(revision.get("trigger_evidence_ids_json", "[]"), label="Adjudication evidence IDs", expected=list)
        event = {
            "event_id": _event_id("adjudication_state_transition", transition["id"]),
            "event_type": "adjudication_state_transition",
            "event_time": as_of,
            "as_of": as_of,
            "recorded_at": _clean(transition.get("recorded_at"), 128),
            "claim_id": str(transition["claim_id"]),
            "revision_id": str(transition["revision_id"]),
            "transition_id": str(transition["id"]),
            "field": str(transition["field"]),
            "transition_kind": str(transition["kind"]),
            "after": after,
        }
        _timestamp(event["recorded_at"], label="Adjudication transition audit")
        if before is not None:
            event["before"] = before
        if evidence_ids:
            event["evidence_ids"] = evidence_ids
        events.append(event)

    for correction in corrections:
        payload = _json(correction.get("event_json"), label="Automatic correction event")
        current_revision = revisions.get(str(correction["current_revision_id"]))
        previous_revision = revisions.get(str(correction["previous_revision_id"]))
        if (
            current_revision is None
            or previous_revision is None
            or str(current_revision["claim_id"]) != str(correction["claim_id"])
            or str(previous_revision["claim_id"]) != str(correction["claim_id"])
        ):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError("Automatic correction revision is missing.")
        event_time = _clean(current_revision.get("as_of"), 128)
        _timestamp(event_time, label="Automatic correction")
        events.append({
            "event_id": _event_id("automatic_correction_recorded", correction["id"]),
            "event_type": "automatic_correction_recorded",
            "event_time": event_time,
            "as_of": event_time,
            "recorded_at": _clean(correction.get("recorded_at"), 128),
            "claim_id": str(correction["claim_id"]),
            "correction_event_id": str(correction["id"]),
            "previous_revision_id": str(correction["previous_revision_id"]),
            "current_revision_id": str(correction["current_revision_id"]),
            "field": str(correction["field"]),
            "before": payload.get("previous_state"),
            "after": payload.get("corrected_state"),
            "correction_scope": "adjudication_system",
        })
        _timestamp(correction.get("recorded_at"), label="Automatic correction audit")

    events.sort(key=_event_sort_key)
    total_events = len(events)
    timeline = events[:bounded_limit]
    claim_items = [{
        "claim_id": claim_id,
        "canonical_text": _clean(claims[claim_id].get("canonical_text"), 1000),
        "claim_type": _clean(claims[claim_id].get("claim_type"), 64),
        "subject_key": _clean(claims[claim_id].get("subject_key"), 256),
        "first_seen_at": _clean(claims[claim_id].get("first_seen_at"), 128),
        "last_seen_at": _clean(claims[claim_id].get("last_seen_at"), 128),
        "exact_story_id": str(stories[claim_id]["id"]),
    } for claim_id in sorted(claims, key=lambda value: (_clean(claims[value].get("first_seen_at"), 128), value))]
    return {
        "version": STORY_EVOLUTION_VERSION,
        "status": "ok",
        "requested_claim": {
            "claim_id": requested_id,
            "canonical_text": _clean(requested.get("canonical_text"), 1000),
            "subject_key": _clean(requested.get("subject_key"), 256),
            "exact_story_id": str(stories[requested_id]["id"]),
        },
        "evolution_family": {
            "family_key": family_key or None,
            "claims": claim_items,
            "exact_stories": [{"story_id": str(stories[item["claim_id"]]["id"]), "claim_id": item["claim_id"]} for item in claim_items],
        },
        "summary": {
            "family_claims": len(claims),
            "reports": reports_count,
            "evolution_transitions": len(evolution_links),
            "verified_independent_reports": independent_count,
            "known_dependent_reports": dependent_count,
            "adjudication_transitions": len(transitions),
            "persisted_correction_events": len(corrections),
            "total_events": total_events,
            "returned_events": len(timeline),
        },
        "timeline": timeline,
        "pagination": {"limit": bounded_limit, "total_events": total_events, "truncated": total_events > bounded_limit},
        "policy": {
            "exact_story_is_not_evolution_family": True,
            "evolution_events_do_not_establish_truth": True,
            "absence_of_dependency_is_not_independence": True,
            "independence_requires_verified_evidence": True,
            "corrections_are_adjudication_corrections_unless_explicitly_otherwise": True,
            "unsupported_retractions_not_inferred": True,
            "unsupported_supersession_not_inferred": True,
            "unsupported_refinement_not_inferred": True,
            "read_path_performs_writes": False,
            "get_reconciles_evolution": False,
            "provider_call_performed": False,
        },
    }


__all__ = ["STORY_EVOLUTION_VERSION", "build_story_evolution"]
