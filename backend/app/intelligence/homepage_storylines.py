from __future__ import annotations

import base64
import json
from collections import defaultdict, deque
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from app.intelligence.claim_evolution import claim_evolution_family
from app.intelligence import story_evolution
from app.story import story_claim_graph_materialization as story_graph


HOMEPAGE_STORYLINES_VERSION = "homepage-storyline-v1"
_RELATIONSHIPS = frozenset({"progresses_to", "resolves_to", "contradicts"})
_TERMINAL_STATES = {
    "transfer": frozenset({"completed", "failed", "cancelled"}),
    "contract": frozenset({"signed", "extended", "expired", "terminated"}),
    "tenure": frozenset({"appointed", "remaining", "departed", "dismissed"}),
    "retirement": frozenset({"retired"}),
    "injury": frozenset({"returned"}),
    "availability": frozenset({"available"}),
    "disciplinary": frozenset({"overturned", "cleared"}),
}


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _json(value: Any, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " metadata is invalid."
        ) from error
    if not isinstance(parsed, dict):
        raise story_graph.StoryClaimGraphMaterializationIntegrityError(
            label + " metadata is invalid."
        )
    return dict(parsed)


def _time(value: Any, *, label: str) -> datetime:
    text = _clean(value, 128)
    try:
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
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


def _structured(row: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = _json(row.get("metadata_json"), label="Canonical claim")
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
    return dict(candidate), family


def _cursor_encode(
    latest_activity_at: str,
    first_appearance_at: str,
    storyline_id: str,
) -> str:
    payload = json.dumps(
        [latest_activity_at, first_appearance_at, storyline_id],
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _cursor_decode(value: Any) -> tuple[str, str, str] | None:
    text = _clean(value, 4096)
    if not text:
        return None
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Homepage storyline cursor is invalid.") from error
    if (
        not isinstance(parsed, list)
        or len(parsed) != 3
        or not all(isinstance(item, str) and item for item in parsed)
    ):
        raise ValueError("Homepage storyline cursor is invalid.")
    try:
        _time(parsed[0], label="Homepage storyline cursor")
        _time(parsed[1], label="Homepage storyline cursor")
    except story_graph.StoryClaimGraphMaterializationIntegrityError as error:
        raise ValueError("Homepage storyline cursor is invalid.") from error
    if not (
        parsed[2].startswith(HOMEPAGE_STORYLINES_VERSION + "|evolution-root|")
        or parsed[2].startswith(HOMEPAGE_STORYLINES_VERSION + "|exact-story|")
    ) or not parsed[2].rsplit("|", 1)[-1]:
        raise ValueError("Homepage storyline cursor is invalid.")
    return parsed[0], parsed[1], parsed[2]


def _load_canonical_claims(conn) -> dict[str, dict[str, Any]]:
    production_ids = {
        str(row[0])
        for row in conn.execute(
            "SELECT production_claim_id FROM claim_identity_mappings"
        ).fetchall()
    }
    claims: dict[str, dict[str, Any]] = {}
    for raw in conn.execute("SELECT * FROM intelligence_claims ORDER BY id").fetchall():
        row = dict(raw)
        claim_id = str(row["id"])
        metadata = _json(row.get("metadata_json"), label="Claim")
        if claim_id in production_ids:
            continue
        if "structured_claim" not in metadata:
            continue
        _time(row.get("first_seen_at"), label="Canonical claim first seen")
        _time(row.get("last_seen_at"), label="Canonical claim last seen")
        _structured(row)
        claims[claim_id] = row
    return claims


def _components(conn, claims: dict[str, dict[str, Any]]):
    rows = [dict(row) for row in conn.execute(
        "SELECT * FROM claim_evolution_links ORDER BY observed_at, id"
    ).fetchall()]
    adjacency: dict[str, set[str]] = defaultdict(set)
    links_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        relationship = _clean(row.get("relationship_type"), 64)
        if relationship not in _RELATIONSHIPS:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution relationship is unsupported."
            )
        left = _clean(row.get("predecessor_claim_id"), 128)
        right = _clean(row.get("successor_claim_id"), 128)
        if left not in claims or right not in claims:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution link has a dangling endpoint."
            )
        if left == right:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution link is cyclic."
            )
        _time(row.get("observed_at"), label="Canonical claim evolution")
        _json(row.get("metadata_json"), label="Canonical claim evolution")
        if not _clean(row.get("family_key"), 1024):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution family key is missing."
            )
        adjacency[left].add(right)
        adjacency[right].add(left)
        links_by_claim[left].append(row)
        links_by_claim[right].append(row)

    output = []
    visited: set[str] = set()
    for start in sorted(adjacency):
        if start in visited:
            continue
        member_ids: set[str] = set()
        pending = [start]
        while pending:
            claim_id = pending.pop()
            if claim_id in member_ids:
                continue
            member_ids.add(claim_id)
            pending.extend(adjacency[claim_id] - member_ids)
        visited.update(member_ids)
        component_links = {
            str(row["id"]): row
            for claim_id in member_ids
            for row in links_by_claim[claim_id]
            if str(row["predecessor_claim_id"]) in member_ids
            and str(row["successor_claim_id"]) in member_ids
        }
        families = {_clean(row.get("family_key"), 1024) for row in component_links.values()}
        subjects = {_clean(claims[claim_id].get("subject_key"), 256) for claim_id in member_ids}
        if len(families) != 1:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution component crosses families."
            )
        if len(subjects) != 1:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution component crosses subjects."
            )
        family_key = next(iter(families))
        for claim_id in member_ids:
            _, family = _structured(claims[claim_id])
            if family.get("status") != "ready" or family.get("family_key") != family_key:
                raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                    "Canonical claim evolution component family identity is inconsistent."
                )

        incoming = {claim_id: 0 for claim_id in member_ids}
        directed: dict[str, list[str]] = defaultdict(list)
        for row in component_links.values():
            left = str(row["predecessor_claim_id"])
            right = str(row["successor_claim_id"])
            directed[left].append(right)
            incoming[right] += 1
        roots = sorted(claim_id for claim_id, count in incoming.items() if count == 0)
        if len(roots) != 1:
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution component must have exactly one root."
            )
        queue = deque([claim_id for claim_id, count in incoming.items() if count == 0])
        remaining = dict(incoming)
        seen = 0
        while queue:
            claim_id = queue.popleft()
            seen += 1
            for successor in directed[claim_id]:
                remaining[successor] -= 1
                if remaining[successor] == 0:
                    queue.append(successor)
        if seen != len(member_ids):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Canonical claim evolution component contains a cycle."
            )
        output.append({
            "claim_ids": sorted(member_ids),
            "links": list(component_links.values()),
            "family_key": family_key,
            "root_claim_id": roots[0],
        })
    return output, visited


def _load_entities(conn, claim_ids: list[str]):
    if not claim_ids:
        return {}
    marks = story_evolution._placeholders(claim_ids)
    rows = [dict(row) for row in conn.execute(
        f"""
        SELECT p.claim_id, p.participant_role, p.confidence, p.observed_at,
               e.id AS entity_id, e.entity_key, e.entity_type, e.sport_key,
               e.canonical_name
        FROM verified_claim_entity_participants p
        JOIN canonical_entities e ON e.id = p.entity_id
        WHERE p.claim_id IN ({marks}) AND p.verification_status = 'verified'
        ORDER BY p.claim_id, p.participant_role, e.id
        """, tuple(claim_ids)).fetchall()]
    by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        _time(row.get("observed_at"), label="Verified claim entity participant")
        by_claim[str(row["claim_id"])].append({
            "entity_id": str(row["entity_id"]),
            "entity_key": _clean(row.get("entity_key"), 256),
            "entity_type": _clean(row.get("entity_type"), 64),
            "canonical_name": _clean(row.get("canonical_name"), 512),
            "participant_role": _clean(row.get("participant_role"), 64),
            **({"sport_key": _clean(row.get("sport_key"), 64)} if _clean(row.get("sport_key"), 64) else {}),
        })
    return by_claim


def _load_official_evidence(conn, claim_ids: list[str]) -> set[str]:
    if not claim_ids:
        return set()
    marks = story_evolution._placeholders(claim_ids)
    return {str(row[0]) for row in conn.execute(
        f"""
        SELECT DISTINCT cl.claim_id
        FROM claim_links cl JOIN evidence_records e ON e.id=cl.evidence_id
        WHERE cl.claim_id IN ({marks}) AND e.verification_status='verified'
          AND e.evidence_type='official_statement'
        """, tuple(claim_ids)).fetchall()}


def _card(component, claims, stories, media_by_claim, observations, dependent,
          independent, revisions, transitions, corrections, entities_by_claim,
          official_claim_ids):
    claim_ids = component["claim_ids"]
    links = component["links"]
    candidates = {claim_id: _structured(claims[claim_id])[0] for claim_id in claim_ids}
    semantic_times: list[tuple[datetime, str, str]] = []
    claim_activity: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    published_first: list[tuple[datetime, str]] = []
    observed_first: list[tuple[datetime, str]] = []
    representative_published: list[tuple[datetime, str]] = []
    representative_observed: list[tuple[datetime, str]] = []
    media_items: dict[str, dict[str, Any]] = {}
    dependency_by_media: dict[str, bool] = {}
    independence_by_media: dict[str, bool] = {}
    source_ids: set[str] = set()
    for claim_id in claim_ids:
        reports = media_by_claim.get(claim_id, {})
        for media_id, report in reports.items():
            observed_values = [observations[key]["observed_value"] for key in report["observations"]]
            observed_at = max(observed_values)
            observed_text = max(
                (observations[key]["observed_at"] for key in report["observations"]),
                key=lambda value: _time(value, label="Reporting observation"),
            )
            observed_first_text = min(
                (observations[key]["observed_at"] for key in report["observations"]),
                key=lambda value: _time(value, label="Reporting observation"),
            )
            observed_first.append((min(observed_values), observed_first_text))
            report_activities = [(observed_at, observed_text)]
            representative_observed.append((observed_at, media_id))
            if report["published_value"]:
                report_activities.append((report["published_value"], report["published_at"]))
                published_first.append((report["published_value"], report["published_at"]))
                representative_published.append((report["published_value"], media_id))
            for value, text in report_activities:
                semantic_times.append((value, text, media_id))
                claim_activity[claim_id].append((value, text))
            keys = set(report["observations"])
            if keys & dependent:
                dependency_by_media[media_id] = True
                independence_by_media[media_id] = False
            elif keys & independent:
                dependency_by_media.setdefault(media_id, False)
                independence_by_media.setdefault(media_id, True)
            else:
                dependency_by_media.setdefault(media_id, False)
                independence_by_media.setdefault(media_id, False)
            if report["source_id"]:
                source_ids.add(report["source_id"])
            media_items[media_id] = {
                "media_item_id": media_id,
                **({"title": _clean(observations[next(iter(keys))].get("title"), 1000)} if keys and _clean(observations[next(iter(keys))].get("title"), 1000) else {}),
                **({"canonical_url": _clean(observations[next(iter(keys))].get("canonical_url"), 2048)} if keys and _clean(observations[next(iter(keys))].get("canonical_url"), 2048) else {}),
                **({"published_at": report["published_at"]} if report["published_at"] else {"observed_at": observed_text}),
                **({"source_id": report["source_id"]} if report["source_id"] else {}),
            }
    for row in links:
        value = _time(row["observed_at"], label="Canonical claim evolution")
        semantic_times.append((value, str(row["observed_at"]), str(row["id"])))
        claim_activity[str(row["successor_claim_id"])].append((value, str(row["observed_at"])))
    relevant_transitions = [row for row in transitions if str(row["claim_id"]) in claim_ids]
    relevant_corrections = [row for row in corrections if str(row["claim_id"]) in claim_ids]
    for row in relevant_transitions:
        revision = revisions.get(str(row["revision_id"]))
        if revision is None or str(revision["claim_id"]) != str(row["claim_id"]):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Adjudication transition revision is missing."
            )
        value = _time(revision.get("as_of"), label="Adjudication revision")
        semantic_times.append((value, str(revision["as_of"]), str(row["id"])))
        claim_activity[str(row["claim_id"])].append((value, str(revision["as_of"])))
    for row in relevant_corrections:
        current = revisions.get(str(row["current_revision_id"]))
        previous = revisions.get(str(row["previous_revision_id"]))
        if current is None or previous is None or str(current["claim_id"]) != str(row["claim_id"]) or str(previous["claim_id"]) != str(row["claim_id"]):
            raise story_graph.StoryClaimGraphMaterializationIntegrityError(
                "Automatic correction revision is missing."
            )
        _json(row.get("event_json"), label="Automatic correction event")
        value = _time(current.get("as_of"), label="Automatic correction")
        semantic_times.append((value, str(current["as_of"]), str(row["id"])))
        claim_activity[str(row["claim_id"])].append((value, str(current["as_of"])))

    for claim_id in claim_ids:
        value = _time(claims[claim_id]["first_seen_at"], label="Canonical claim first seen")
        semantic_times.append((value, str(claims[claim_id]["first_seen_at"]), claim_id))
        claim_activity[claim_id].append((value, str(claims[claim_id]["first_seen_at"])))
    _, latest_text, _ = max(semantic_times)
    current_claim_id = max(claim_ids, key=lambda claim_id: (
        max(claim_activity[claim_id])[0],
        claim_id,
    ))
    incoming_to_current = [row for row in links if str(row["successor_claim_id"]) == current_claim_id]
    previous_state = None
    if incoming_to_current:
        latest_link = max(incoming_to_current, key=lambda row: (_time(row["observed_at"], label="Canonical claim evolution"), str(row["id"])))
        previous_state = candidates[str(latest_link["predecessor_claim_id"])]["state"]
    story = stories[current_claim_id]
    title = _clean(claims[current_claim_id].get("canonical_text"), 1000) or _clean(story.get("canonical_title"), 1000)
    all_entities = {item["entity_id"]: item for claim_id in claim_ids for item in entities_by_claim.get(claim_id, [])}
    if not title:
        subject_entity = next((item for item in all_entities.values() if item["participant_role"] == "subject"), None)
        subject_label = (subject_entity or {}).get("canonical_name") or _clean(claims[current_claim_id].get("subject_key"), 256)
        title = " ".join(part.replace("_", " ").title() for part in (candidates[current_claim_id]["event_type"], candidates[current_claim_id]["state"])) + " — " + subject_label
    representative = None
    if media_items:
        representative_id = max(
            representative_published or representative_observed,
            key=lambda item: (item[0], item[1]),
        )[1]
        representative = media_items[representative_id]
    current_event = candidates[current_claim_id]["event_type"]
    current_state = candidates[current_claim_id]["state"]
    report_count = len(media_items)
    dependency_count = sum(dependency_by_media.values())
    independence_count = sum(
        independent and not dependency_by_media.get(media_id, False)
        for media_id, independent in independence_by_media.items()
    )
    storyline_id = (
        HOMEPAGE_STORYLINES_VERSION + "|evolution-root|" + component["root_claim_id"]
        if links else HOMEPAGE_STORYLINES_VERSION + "|exact-story|" + str(stories[current_claim_id]["id"])
    )
    item = {
        "storyline_id": storyline_id,
        "storyline_kind": "evolution_component" if links else "singleton",
        **({"family_key": component["family_key"]} if links else {}),
        "title": title,
        "subject_key": _clean(claims[current_claim_id].get("subject_key"), 256),
        "claims": [{
            "claim_id": claim_id,
            **({"canonical_text": _clean(claims[claim_id].get("canonical_text"), 1000)} if _clean(claims[claim_id].get("canonical_text"), 1000) else {}),
            "event_type": candidates[claim_id]["event_type"],
            "state": candidates[claim_id]["state"],
            "first_seen_at": _clean(claims[claim_id].get("first_seen_at"), 128),
            "exact_story_id": str(stories[claim_id]["id"]),
        } for claim_id in sorted(claim_ids, key=lambda value: (_time(claims[value]["first_seen_at"], label="Canonical claim first seen"), value))],
        "exact_stories": [{"story_id": str(stories[c]["id"]), "claim_id": c} for c in sorted(claim_ids)],
        "current_claim_id": current_claim_id,
        "current_state": current_state,
        **({"previous_state": previous_state} if previous_state else {}),
        "first_appearance_at": min(
            published_first
            or observed_first
            or [
                (
                    _time(claims[c]["first_seen_at"], label="Canonical claim first seen"),
                    str(claims[c]["first_seen_at"]),
                )
                for c in claim_ids
            ]
        )[1],
        "latest_activity_at": latest_text,
        **({"representative_media": representative} if representative else {}),
        "report_count": report_count,
        "distinct_source_count": len(source_ids),
        "verified_independent_reporting_present": independence_count > 0,
        "verified_independent_report_count": independence_count,
        "known_dependency_present": dependency_count > 0,
        "known_dependency_report_count": dependency_count,
        "contradiction_present": any(row["relationship_type"] == "contradicts" for row in links),
        "adjudication_correction_present": bool(relevant_corrections),
        "official_evidence_present": bool(set(claim_ids) & official_claim_ids),
        "evolution_transition_count": len(links),
        **({"terminal_state": current_state} if current_state in _TERMINAL_STATES.get(current_event, ()) else {}),
        **({"entities": sorted(all_entities.values(), key=lambda value: (value["entity_type"], value["canonical_name"].casefold(), value["entity_id"]))} if all_entities else {}),
    }
    sports = sorted({value.get("sport_key") for value in all_entities.values() if value.get("sport_key")})
    if len(sports) == 1:
        item["sport_key"] = sports[0]
    return item


def build_homepage_storylines(*, connection_factory, limit: int = 50, cursor: str = "") -> dict[str, Any]:
    if connection_factory is None:
        raise ValueError("Homepage storylines require database access.")
    try:
        bounded_limit = int(limit)
    except (TypeError, ValueError) as error:
        raise ValueError("Homepage storyline limit must be an integer.") from error
    if bounded_limit < 1 or bounded_limit > 200:
        raise ValueError("Homepage storyline limit must be between 1 and 200.")
    decoded_cursor = _cursor_decode(cursor)
    conn = connection_factory()
    try:
        claims = _load_canonical_claims(conn)
        if not claims:
            cards = []
        else:
            components, linked = _components(conn, claims)
            components.extend({"claim_ids": [claim_id], "links": [], "family_key": "", "root_claim_id": claim_id} for claim_id in sorted(set(claims) - linked))
            stories = story_evolution._load_stories(conn, claims)
            legacy_by_claim, all_scope_ids = story_evolution._legacy_scope(conn, sorted(claims))
            observations, media_by_claim = story_evolution._load_reports(conn, claims, stories, legacy_by_claim, all_scope_ids)
            dependent, independent, _ = story_evolution._report_classification(conn, observations)
            revisions, transitions, corrections = story_evolution._load_adjudication(conn, sorted(claims))
            entities = _load_entities(conn, sorted(claims))
            official = _load_official_evidence(conn, sorted(claims))
            cards = [_card(component, claims, stories, media_by_claim, observations, dependent, independent, revisions, transitions, corrections, entities, official) for component in components]
    finally:
        conn.close()
    cards.sort(key=lambda item: (
        -_time(item["latest_activity_at"], label="Homepage storyline activity").timestamp(),
        -_time(item["first_appearance_at"], label="Homepage storyline appearance").timestamp(),
        item["storyline_id"],
    ))
    if decoded_cursor:
        cursor_time, cursor_first, cursor_id = decoded_cursor
        cursor_key = (
            -_time(cursor_time, label="Homepage storyline cursor").timestamp(),
            -_time(cursor_first, label="Homepage storyline cursor").timestamp(),
            cursor_id,
        )
        cards = [item for item in cards if (
            -_time(item["latest_activity_at"], label="Homepage storyline activity").timestamp(),
            -_time(item["first_appearance_at"], label="Homepage storyline appearance").timestamp(),
            item["storyline_id"],
        ) > cursor_key]
    page = cards[:bounded_limit]
    has_more = len(cards) > bounded_limit
    next_cursor = _cursor_encode(
        page[-1]["latest_activity_at"],
        page[-1]["first_appearance_at"],
        page[-1]["storyline_id"],
    ) if has_more and page else None
    return {
        "version": HOMEPAGE_STORYLINES_VERSION,
        "status": "ok",
        "storylines": page,
        "pagination": {"limit": bounded_limit, "returned": len(page), "has_more": has_more, **({"next_cursor": next_cursor} if next_cursor else {})},
        "policy": {
            "exact_story_identity_preserved": True,
            "family_key_alone_does_not_define_storyline": True,
            "shared_subject_does_not_define_storyline": True,
            "shared_entities_do_not_define_storyline": True,
            "cross_family_grouping_not_inferred": True,
            "source_count_is_not_independent_source_count": True,
            "independence_requires_verified_evidence": True,
            "report_volume_does_not_establish_truth": True,
            "merit_score_is_not_truth_probability": True,
            "historical_backfill_may_change_root_based_storyline_identity": True,
            "read_path_performs_writes": False,
            "provider_call_performed": False,
        },
    }


__all__ = ["HOMEPAGE_STORYLINES_VERSION", "build_homepage_storylines"]
