from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from app.knowledge.entities import normalize_entity_alias


PRODUCT_INTELLIGENCE_VERSION = "product-intelligence-v1"
SEARCH_KINDS = frozenset({"entity", "story", "claim", "media", "source", "reporter"})
_MATCH_ORDER = {"exact": 0, "alias": 1, "prefix": 2, "text": 3, "related": 4}
_MAX_CURSOR_BYTES = 2048


class ProductIntelligenceIntegrityError(RuntimeError):
    pass


def _clean(value: Any, maximum: int = 2048) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _time(value: Any, *, label: str) -> str:
    text = _clean(value, 128)
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        offset = parsed.utcoffset()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a valid ISO-8601 timestamp.") from exc
    if offset is None:
        raise ValueError(f"{label} must include a timezone.")
    return parsed.astimezone(timezone.utc).isoformat()


def _json_list(value: Any) -> list[Any]:
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return list(parsed) if isinstance(parsed, list) else []


def _cursor_encode(scope: str, key: list[Any]) -> str:
    raw = json.dumps([PRODUCT_INTELLIGENCE_VERSION, scope, key], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _cursor_decode(value: str, *, scope: str, key_length: int) -> list[Any] | None:
    text = _clean(value, 4096)
    if not text:
        return None
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
        if len(raw) > _MAX_CURSOR_BYTES:
            raise ValueError
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cursor is invalid.") from exc
    if (
        not isinstance(parsed, list) or len(parsed) != 3
        or parsed[0] != PRODUCT_INTELLIGENCE_VERSION or parsed[1] != scope
        or not isinstance(parsed[2], list) or len(parsed[2]) != key_length
    ):
        raise ValueError("Cursor is invalid.")
    return parsed[2]


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _match(query: str, value: Any, *, alias: bool = False) -> str | None:
    candidate = _clean(value).casefold()
    if not candidate:
        return None
    if candidate == query:
        return "alias" if alias else "exact"
    if candidate.startswith(query):
        return "prefix"
    if query in candidate:
        return "text"
    return None


def _best(current: dict[str, Any] | None, candidate: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return candidate
    left = (_MATCH_ORDER[candidate["match_type"]], candidate["matched_field"])
    right = (_MATCH_ORDER[current["match_type"]], current["matched_field"])
    return candidate if left < right else current


def search_intelligence(
    *, q: str, connection_factory, kinds: Iterable[str] | None = None,
    sport_key: str = "", limit: int = 20, cursor: str = "",
) -> dict[str, Any]:
    query_text = _clean(q, 201)
    if len(query_text) < 1:
        raise ValueError("Search query must not be blank.")
    if len(query_text) > 200:
        raise ValueError("Search query must contain at most 200 characters.")
    selected = tuple(sorted(set(kinds or SEARCH_KINDS)))
    if not selected or any(kind not in SEARCH_KINDS for kind in selected):
        raise ValueError("Search kind is invalid.")
    normalized_sport = _clean(sport_key, 64).casefold()
    scope = "search:" + query_text.casefold() + ":" + ",".join(selected) + ":" + normalized_sport
    cursor_key = _cursor_decode(cursor, scope=scope, key_length=5)
    folded_query = query_text.casefold()
    pattern = _like(folded_query)
    candidates: dict[tuple[str, str], dict[str, Any]] = {}

    def add(kind: str, row: Mapping[str, Any], title: Any, field: str, value: Any, **extra: Any) -> None:
        match_type = _match(query_text.casefold(), value, alias=field == "alias")
        if match_type is None:
            return
        item = {
            "kind": kind, "id": _clean(row.get("id"), 128), "title": _clean(title, 1000),
            "matched_field": field, "match_type": match_type,
            "first_seen_at": _clean(row.get("first_seen_at"), 128),
            "last_seen_at": _clean(row.get("last_seen_at"), 128), **extra,
        }
        key = (kind, item["id"])
        candidates[key] = _best(candidates.get(key), item)

    def add_related(kind: str, row: Mapping[str, Any], title: Any, subtitle: Any = "", **extra: Any) -> None:
        item = {
            "kind": kind, "id": _clean(row.get("id"), 128), "title": _clean(title, 1000),
            "matched_field": "verified_entity", "match_type": "related",
            "subtitle": _clean(subtitle, 256),
            "first_seen_at": _clean(row.get("first_seen_at"), 128),
            "last_seen_at": _clean(row.get("last_seen_at"), 128), **extra,
        }
        key = (kind, item["id"])
        candidates[key] = _best(candidates.get(key), item)

    conn = connection_factory()
    try:
        conn.create_function("sportabase_casefold", 1, lambda value: str(value or "").casefold(), deterministic=True)
        matched_entity_ids: set[str] = set()
        if "entity" in selected or any(kind in selected for kind in ("claim", "story", "media")):
            normalized_alias_query = normalize_entity_alias(query_text)
            clauses = ["(sportabase_casefold(e.canonical_name) LIKE ? ESCAPE '\\' OR sportabase_casefold(a.alias_text) LIKE ? ESCAPE '\\' OR a.normalized_alias LIKE ? ESCAPE '\\')"]
            params: list[Any] = [pattern, pattern, _like(normalized_alias_query)]
            if normalized_sport:
                clauses.append("e.sport_key = ?")
                params.append(normalized_sport)
            rows = conn.execute("""
                SELECT e.*, a.alias_text FROM canonical_entities e
                LEFT JOIN entity_aliases a ON a.entity_id = e.id
                WHERE """ + " AND ".join(clauses) + " ORDER BY e.id, a.id", params).fetchall()
            for row in rows:
                data = dict(row)
                canonical_match = _match(folded_query, data["canonical_name"])
                alias_match = _match(folded_query, data.get("alias_text"), alias=True)
                if canonical_match == "exact" or alias_match == "alias":
                    matched_entity_ids.add(data["id"])
                if "entity" in selected:
                    add("entity", data, data["canonical_name"], "canonical_name", data["canonical_name"],
                        subtitle=_clean(data["entity_type"], 64), sport_key=_clean(data["sport_key"], 64))
                    add("entity", data, data["canonical_name"], "alias", data.get("alias_text"),
                        subtitle=_clean(data["entity_type"], 64), sport_key=_clean(data["sport_key"], 64))

        if matched_entity_ids:
            marks = ",".join("?" for _ in matched_entity_ids)
            ids = sorted(matched_entity_ids)
            related_claims = [dict(row) for row in conn.execute(f"""
                SELECT DISTINCT c.* FROM verified_claim_entity_participants p
                JOIN intelligence_claims c ON c.id=p.claim_id
                WHERE p.entity_id IN ({marks}) ORDER BY c.id
            """, ids)]
            if "claim" in selected:
                for row in related_claims:
                    add_related("claim", row, row["canonical_text"], row["subject_key"])
            claim_ids = [row["id"] for row in related_claims]
            related_stories: list[dict[str, Any]] = []
            if claim_ids:
                claim_marks = ",".join("?" for _ in claim_ids)
                related_stories = [dict(row) for row in conn.execute(f"""
                    SELECT DISTINCT s.* FROM story_claim_links l
                    JOIN intelligence_stories s ON s.id=l.story_id
                    WHERE l.claim_id IN ({claim_marks}) ORDER BY s.id
                """, claim_ids)]
                if "story" in selected:
                    for row in related_stories:
                        add_related("story", row, row["canonical_title"], row["status"])
            story_ids = [row["id"] for row in related_stories]
            if story_ids and "media" in selected:
                story_marks = ",".join("?" for _ in story_ids)
                for row in conn.execute(f"""
                    SELECT DISTINCT m.* FROM story_media_links l JOIN media_items m ON m.id=l.media_item_id
                    WHERE l.story_id IN ({story_marks}) ORDER BY m.id
                """, story_ids):
                    data = dict(row)
                    add_related("media", data, data["title"], data["mode"],
                                canonical_url=_clean(data["canonical_url"], 2048), source_type=_clean(data["mode"], 64))

        definitions = {
            "story": ("intelligence_stories", "canonical_title", "canonical_title", "status"),
            "claim": ("intelligence_claims", "canonical_text", "canonical_text", "subject_key"),
            "media": ("media_items", "title", "title", "mode"),
            "source": ("intelligence_sources", "display_name", "display_name", "source_type"),
            "reporter": ("intelligence_reporters", "display_name", "display_name", "identity_key"),
        }
        for kind, (table, title_col, field, subtitle_col) in definitions.items():
            if kind not in selected:
                continue
            search_cols = [title_col]
            if kind == "claim": search_cols.append("subject_key")
            if kind == "source": search_cols.append("canonical_domain")
            where = " OR ".join(f"sportabase_casefold({col}) LIKE ? ESCAPE '\\'" for col in search_cols)
            rows = conn.execute(f"SELECT * FROM {table} WHERE ({where}) ORDER BY id", [pattern] * len(search_cols)).fetchall()
            for raw in rows:
                row = dict(raw)
                if normalized_sport and kind not in {"claim"}:
                    continue
                if normalized_sport and kind == "claim" and not _clean(row.get("subject_key")).casefold().startswith(normalized_sport + ":"):
                    continue
                extras = {"subtitle": _clean(row.get(subtitle_col), 256)}
                if kind == "media": extras.update(canonical_url=_clean(row.get("canonical_url"), 2048), source_type=_clean(row.get("mode"), 64))
                if kind == "source": extras.update(source_type=_clean(row.get("source_type"), 64))
                for col in search_cols:
                    add(kind, row, row.get(title_col), col, row.get(col), **extras)
    finally:
        conn.close()

    # Reverse time is represented separately to keep the opaque cursor simple and exact.
    ordered = sorted(candidates.values(), key=lambda item: (
        _MATCH_ORDER[item["match_type"]], "".join(chr(0x10ffff - ord(c)) for c in _clean(item.get("last_seen_at"), 128)),
        item["kind"], item["id"]))
    keyed = [([_MATCH_ORDER[x["match_type"]], x.get("last_seen_at", ""), x["kind"], x["id"], x["matched_field"]], x) for x in ordered]
    if cursor_key is not None:
        try:
            start = next(index + 1 for index, (key, _) in enumerate(keyed) if key == cursor_key)
        except StopIteration as exc:
            raise ValueError("Cursor is invalid for the current result set.") from exc
    else:
        start = 0
    page = keyed[start:start + limit]
    more = start + limit < len(keyed)
    return {
        "version": PRODUCT_INTELLIGENCE_VERSION, "query": query_text,
        "results": [item for _, item in page],
        "pagination": {"limit": limit, "next_cursor": _cursor_encode(scope, page[-1][0]) if more and page else None},
    }


def _page_events(events: list[dict[str, Any]], *, scope: str, after: str, before: str, limit: int, cursor: str) -> dict[str, Any]:
    after_value = _time(after, label="after") if after else ""
    before_value = _time(before, label="before") if before else ""
    for event in events:
        try:
            event["occurred_at"] = _time(event.get("occurred_at"), label="History event timestamp")
        except ValueError as exc:
            raise ProductIntelligenceIntegrityError(str(exc)) from exc
    filtered = [event for event in events if (not after_value or event["occurred_at"] > after_value) and (not before_value or event["occurred_at"] < before_value)]
    filtered.sort(key=lambda event: (event["occurred_at"], event["type"], str(event["id"])))
    bound_scope = f"{scope}:{after_value}:{before_value}"
    cursor_key = _cursor_decode(cursor, scope=bound_scope, key_length=3)
    keyed = [([event["occurred_at"], event["type"], str(event["id"])], event) for event in filtered]
    if cursor_key is not None:
        try:
            start = next(i + 1 for i, (key, _) in enumerate(keyed) if key == cursor_key)
        except StopIteration as exc:
            raise ValueError("Cursor is invalid for the current history.") from exc
    else:
        start = 0
    page = keyed[start:start + limit]
    more = start + limit < len(keyed)
    return {"events": [event for _, event in page], "pagination": {"limit": limit, "next_cursor": _cursor_encode(bound_scope, page[-1][0]) if more and page else None}}


def _identity(conn, table: str, resource_id: str) -> dict[str, Any] | None:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (resource_id,)).fetchone()
    return dict(row) if row else None


def entity_history(*, entity_id: str, connection_factory, after: str = "", before: str = "", limit: int = 100, cursor: str = "") -> dict[str, Any] | None:
    conn = connection_factory()
    try:
        entity = _identity(conn, "canonical_entities", entity_id)
        if entity is None: return None
        aliases = [dict(r) for r in conn.execute("SELECT alias_text, alias_type, first_seen_at, last_seen_at FROM entity_aliases WHERE entity_id=? ORDER BY normalized_alias, id", (entity_id,))]
        participants = [dict(r) for r in conn.execute("""SELECT p.id,p.claim_id,p.participant_role,p.evidence_id,p.verification_status,p.confidence,p.observed_at,p.recorded_at,c.canonical_text FROM verified_claim_entity_participants p JOIN intelligence_claims c ON c.id=p.claim_id WHERE p.entity_id=? ORDER BY p.observed_at,p.id""", (entity_id,))]
        events = [{"type":"verified_claim_participation","id":r["id"],"occurred_at":r["observed_at"],"claim_id":r["claim_id"],"claim_text":r["canonical_text"],"participant_role":r["participant_role"],"verification_status":r["verification_status"],"evidence_id":r["evidence_id"]} for r in participants]
        claims = sorted({r["claim_id"] for r in participants})
        stories=[]; media=[]
        if claims:
            marks=",".join("?" for _ in claims)
            stories=[dict(r) for r in conn.execute(f"SELECT DISTINCT s.id,s.canonical_title,s.status,s.first_seen_at,s.last_seen_at,l.relationship_type,l.link_basis,l.linked_at FROM story_claim_links l JOIN intelligence_stories s ON s.id=l.story_id WHERE l.claim_id IN ({marks}) ORDER BY l.linked_at,s.id", claims)]
            events += [{"type":"story_link","id":r["id"],"occurred_at":r["linked_at"],"story_id":r["id"],"relationship_type":r["relationship_type"],"link_basis":r["link_basis"]} for r in stories]
            story_ids=[r["id"] for r in stories]
            if story_ids:
                marks=",".join("?" for _ in story_ids)
                media=[dict(r) for r in conn.execute(f"SELECT DISTINCT m.id,m.title,m.mode,m.canonical_url,m.first_seen_at,m.last_seen_at,l.story_id,l.relationship_type,l.linked_at FROM story_media_links l JOIN media_items m ON m.id=l.media_item_id WHERE l.story_id IN ({marks}) ORDER BY l.linked_at,m.id", story_ids)]
                events += [{"type":"media_link","id":r["id"],"occurred_at":r["linked_at"],"media_item_id":r["id"],"story_id":r["story_id"],"relationship_type":r["relationship_type"]} for r in media]
    finally: conn.close()
    page=_page_events(events,scope="entity:"+entity_id,after=after,before=before,limit=limit,cursor=cursor)
    return {"version":PRODUCT_INTELLIGENCE_VERSION,"entity":{"id":entity["id"],"entity_key":entity["entity_key"],"entity_type":entity["entity_type"],"sport_key":entity["sport_key"],"canonical_name":entity["canonical_name"],"first_seen_at":entity["first_seen_at"],"last_seen_at":entity["last_seen_at"],"aliases":aliases},"claims":claims,"stories":stories,"media":media,**page,"policy":{"verified_relationships_only":True,"chronology_is_not_truth":True}}


def story_history(*, story_id: str, connection_factory, after: str = "", before: str = "", limit: int = 100, cursor: str = "") -> dict[str, Any] | None:
    conn=connection_factory()
    try:
        story=_identity(conn,"intelligence_stories",story_id)
        if story is None:return None
        claims=[dict(r) for r in conn.execute("SELECT c.id,c.canonical_text,c.subject_key,c.claim_type,c.first_seen_at,c.last_seen_at,l.relationship_type,l.link_basis,l.linked_at FROM story_claim_links l JOIN intelligence_claims c ON c.id=l.claim_id WHERE l.story_id=? ORDER BY l.linked_at,c.id",(story_id,))]
        media=[dict(r) for r in conn.execute("SELECT m.id,m.title,m.mode,m.canonical_url,m.source_id,m.reporter_id,m.first_seen_at,m.last_seen_at,l.relationship_type,l.linked_at FROM story_media_links l JOIN media_items m ON m.id=l.media_item_id WHERE l.story_id=? ORDER BY l.linked_at,m.id",(story_id,))]
        source_obs=[dict(r) for r in conn.execute("SELECT id,source_id,media_item_id,observation_type,status,claim_summary,provenance_url,observed_at FROM source_observations WHERE story_id=? ORDER BY observed_at,id",(story_id,))]
        reporter_obs=[dict(r) for r in conn.execute("SELECT id,reporter_id,source_id,media_item_id,observation_type,status,claim_summary,provenance_url,observed_at FROM reporter_observations WHERE story_id=? ORDER BY observed_at,id",(story_id,))]
        evidence=[dict(r) for r in conn.execute("SELECT e.id,e.evidence_type,e.subject_key,e.claim_summary,e.canonical_url,e.reference_key,e.verification_status,e.published_at,e.observed_at,l.id link_id,l.relationship_type,l.linked_at FROM evidence_links l JOIN evidence_records e ON e.id=l.evidence_id WHERE l.story_id=? ORDER BY e.observed_at,e.id,l.id",(story_id,))]
        snapshots=[dict(r) for r in conn.execute("SELECT id,media_item_id,analyzed_at,mode,analysis_version,scoring_version FROM analysis_snapshots WHERE story_id=? ORDER BY analyzed_at,id",(story_id,))]
    finally:conn.close()
    events=[{"type":"claim_link","id":r["id"],"occurred_at":r["linked_at"],"claim_id":r["id"],"relationship_type":r["relationship_type"],"link_basis":r["link_basis"]} for r in claims]
    events += [{"type":"media_link","id":r["id"],"occurred_at":r["linked_at"],"media_item_id":r["id"],"relationship_type":r["relationship_type"]} for r in media]
    events += [{"type":"source_observation","occurred_at":r.pop("observed_at"),**r} for r in source_obs]
    events += [{"type":"reporter_observation","occurred_at":r.pop("observed_at"),**r} for r in reporter_obs]
    events += [{"type":"evidence","occurred_at":r.pop("observed_at"),**r} for r in evidence]
    events += [{"type":"analysis_snapshot","occurred_at":r.pop("analyzed_at"),**r} for r in snapshots]
    page=_page_events(events,scope="story:"+story_id,after=after,before=before,limit=limit,cursor=cursor)
    public_story={k:story[k] for k in ("id","canonical_key","canonical_title","status","first_seen_at","last_seen_at")}
    return {"version":PRODUCT_INTELLIGENCE_VERSION,"story":public_story,"claims":claims,"media":media,**page,"policy":{"chronology_is_not_truth":True,"relationships_are_persisted":True}}


def claim_history(*, claim_id: str, connection_factory, after: str = "", before: str = "", limit: int = 100, cursor: str = "") -> dict[str, Any] | None:
    conn=connection_factory()
    try:
        claim=_identity(conn,"intelligence_claims",claim_id)
        if claim is None:return None
        links=[dict(r) for r in conn.execute("""
            SELECT cl.id,cl.source_observation_id,cl.reporter_observation_id,cl.evidence_id,
              cl.relationship_type,cl.confidence,cl.observed_at,
              so.source_id,so.media_item_id AS source_media_item_id,so.provenance_url AS source_provenance_url,
              ro.reporter_id,ro.source_id AS reporter_source_id,ro.media_item_id AS reporter_media_item_id,
              ro.provenance_url AS reporter_provenance_url,
              er.evidence_type,er.verification_status AS evidence_verification_status,
              er.canonical_url AS evidence_canonical_url,er.reference_key AS evidence_reference_key
            FROM claim_links cl
            LEFT JOIN source_observations so ON so.id=cl.source_observation_id
            LEFT JOIN reporter_observations ro ON ro.id=cl.reporter_observation_id
            LEFT JOIN evidence_records er ON er.id=cl.evidence_id
            WHERE cl.claim_id=? ORDER BY cl.observed_at,cl.id
        """,(claim_id,))]
        participants=[dict(r) for r in conn.execute("SELECT p.id,p.entity_id,p.participant_role,p.evidence_id,p.verification_status,p.observed_at,e.canonical_name,e.entity_type,e.sport_key FROM verified_claim_entity_participants p JOIN canonical_entities e ON e.id=p.entity_id WHERE p.claim_id=? ORDER BY p.observed_at,p.id",(claim_id,))]
        stories=[dict(r) for r in conn.execute("SELECT s.id,s.canonical_title,s.status,l.relationship_type,l.link_basis,l.linked_at FROM story_claim_links l JOIN intelligence_stories s ON s.id=l.story_id WHERE l.claim_id=? ORDER BY l.linked_at,s.id",(claim_id,))]
        revisions=[dict(r) for r in conn.execute("SELECT id,state_version,adjudication_version,adjudication_sha256,as_of,previous_revision_id,trigger_type,trigger_evidence_ids_json,recorded_at FROM adjudication_state_revisions WHERE claim_id=? ORDER BY recorded_at,id",(claim_id,))]
        transitions=[dict(r) for r in conn.execute("SELECT id,revision_id,field,kind,recorded_at FROM adjudication_state_transitions WHERE claim_id=? ORDER BY recorded_at,id",(claim_id,))]
        obs_ids=[r["source_observation_id"] for r in links if r["source_observation_id"]]+[r["reporter_observation_id"] for r in links if r["reporter_observation_id"]]
        dependencies=[]
        if obs_ids:
            marks=",".join("?" for _ in obs_ids)
            dependencies=[dict(r) for r in conn.execute(f"SELECT id,downstream_source_observation_id,downstream_reporter_observation_id,upstream_source_observation_id,upstream_reporter_observation_id,upstream_source_id,upstream_reporter_id,relationship_type,confidence,observed_at FROM observation_dependencies WHERE downstream_source_observation_id IN ({marks}) OR downstream_reporter_observation_id IN ({marks}) ORDER BY observed_at,id",obs_ids+obs_ids)]
    finally:conn.close()
    events=[{"type":"claim_link","occurred_at":r.pop("observed_at"),**r} for r in links]
    events += [{"type":"verified_entity_participant","occurred_at":r.pop("observed_at"),**r} for r in participants]
    events += [{"type":"story_link","id":r["id"],"occurred_at":r["linked_at"],"story_id":r["id"],"relationship_type":r["relationship_type"],"link_basis":r["link_basis"]} for r in stories]
    events += [{"type":"adjudication_revision","occurred_at":r.pop("recorded_at"),"trigger_evidence_ids":_json_list(r.pop("trigger_evidence_ids_json")),**r} for r in revisions]
    events += [{"type":"adjudication_transition","occurred_at":r.pop("recorded_at"),**r} for r in transitions]
    events += [{"type":"observation_dependency","occurred_at":r.pop("observed_at"),**r} for r in dependencies]
    page=_page_events(events,scope="claim:"+claim_id,after=after,before=before,limit=limit,cursor=cursor)
    public_claim={k:claim[k] for k in ("id","canonical_key","subject_key","canonical_text","claim_type","first_seen_at","last_seen_at")}
    return {"version":PRODUCT_INTELLIGENCE_VERSION,"claim":public_claim,"stories":stories,"verified_participants":participants,**page,"policy":{"chronology_is_not_truth":True,"evidence_quantity_is_not_probability":True,"dependencies_remain_distinct":True}}


def media_history(*, media_item_id: str, connection_factory, after: str = "", before: str = "", limit: int = 100, cursor: str = "") -> dict[str, Any] | None:
    conn=connection_factory()
    try:
        media=_identity(conn,"media_items",media_item_id)
        if media is None:return None
        rows=[dict(r) for r in conn.execute("SELECT id,story_id,analyzed_at,mode,analysis_version,scoring_version,content_hash,merit_score,evidence_score,logic_score,badge,verdict,article_type,score_components_json,reasons_json FROM analysis_snapshots WHERE media_item_id=? ORDER BY analyzed_at,id",(media_item_id,))]
    finally:conn.close()
    events=[]
    for row in rows:
        event={"type":"analysis_snapshot","id":row["id"],"occurred_at":row["analyzed_at"],"media_item_id":media_item_id,"story_id":row["story_id"],"mode":row["mode"],"analysis_version":row["analysis_version"],"scoring_version":row["scoring_version"],"content_hash":row["content_hash"],"badge":row["badge"],"article_type":row["article_type"],"reasons":[_clean(x,1000) for x in _json_list(row["reasons_json"]) if isinstance(x,str)]}
        if row["mode"] == "article": event["merit_score"]=row["merit_score"]
        if row["mode"] == "video": event.update(evidence_score=row["evidence_score"],logic_score=row["logic_score"],verdict=row["verdict"])
        events.append(event)
    page=_page_events(events,scope="media:"+media_item_id,after=after,before=before,limit=limit,cursor=cursor)
    public_media={k:media[k] for k in ("id","canonical_url","mode","source_id","reporter_id","title","published_at","first_seen_at","last_seen_at")}
    return {"version":PRODUCT_INTELLIGENCE_VERSION,"media":public_media,**page,"policy":{"article_merit_is_reporting_quality_not_truth":True,"video_scores_are_not_combined":True,"versions_are_not_assumed_comparable":True}}
