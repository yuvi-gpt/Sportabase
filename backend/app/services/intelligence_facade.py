from __future__ import annotations

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


def source_domain_for_url_impl(url: str, *, _source_domain_for_url_impl, normalized_analysis_url) -> str:
    return _source_domain_for_url_impl(url, normalize_url=normalized_analysis_url)
source_domain_for_url_impl.__sportabase_dependencies__ = ('_source_domain_for_url_impl', 'normalized_analysis_url')


def source_key_for_url_impl(url: str, source_type: str='publisher', *, _source_key_for_url_impl, source_domain_for_url) -> str:
    return _source_key_for_url_impl(url, source_type, domain_resolver=source_domain_for_url)
source_key_for_url_impl.__sportabase_dependencies__ = ('_source_key_for_url_impl', 'source_domain_for_url')


def source_id_for_url_impl(url: str, source_type: str='publisher', *, _source_id_for_url_impl, source_key_for_url) -> str:
    return _source_id_for_url_impl(url, source_type, key_resolver=source_key_for_url)
source_id_for_url_impl.__sportabase_dependencies__ = ('_source_id_for_url_impl', 'source_key_for_url')


def upsert_intelligence_source_impl(*, url: str, display_name: str='', source_type: str='publisher', publication_founded_at: Optional[str]=None, domain_registered_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, seen_at: Optional[str]=None, _upsert_intelligence_source_impl, db_conn, source_domain_for_url) -> Dict[str, Any]:
    return _upsert_intelligence_source_impl(url=url, display_name=display_name, source_type=source_type, publication_founded_at=publication_founded_at, domain_registered_at=domain_registered_at, metadata=metadata, seen_at=seen_at, domain_resolver=source_domain_for_url, connection_factory=db_conn)
upsert_intelligence_source_impl.__sportabase_dependencies__ = ('_upsert_intelligence_source_impl', 'db_conn', 'source_domain_for_url')


def story_id_for_canonical_key_impl(canonical_key: str, *, _story_id_for_canonical_key_impl) -> str:
    return _story_id_for_canonical_key_impl(canonical_key)
story_id_for_canonical_key_impl.__sportabase_dependencies__ = ('_story_id_for_canonical_key_impl',)


def upsert_intelligence_story_impl(*, canonical_key: str, canonical_title: str='', status: str='developing', metadata: Optional[Dict[str, Any]]=None, seen_at: Optional[str]=None, _upsert_intelligence_story_impl, db_conn, story_id_for_canonical_key) -> Dict[str, Any]:
    return _upsert_intelligence_story_impl(canonical_key=canonical_key, canonical_title=canonical_title, status=status, metadata=metadata, seen_at=seen_at, id_resolver=story_id_for_canonical_key, connection_factory=db_conn)
upsert_intelligence_story_impl.__sportabase_dependencies__ = ('_upsert_intelligence_story_impl', 'db_conn', 'story_id_for_canonical_key')


def claim_id_for_canonical_key_impl(canonical_key: str, *, _claim_id_for_canonical_key_impl) -> str:
    return _claim_id_for_canonical_key_impl(canonical_key)
claim_id_for_canonical_key_impl.__sportabase_dependencies__ = ('_claim_id_for_canonical_key_impl',)


def upsert_intelligence_claim_impl(*, canonical_key: str, subject_key: str, canonical_text: str='', claim_type: str='assertion', metadata: Optional[Dict[str, Any]]=None, seen_at: Optional[str]=None, _upsert_intelligence_claim_impl, claim_id_for_canonical_key, db_conn) -> Dict[str, Any]:
    return _upsert_intelligence_claim_impl(canonical_key=canonical_key, subject_key=subject_key, canonical_text=canonical_text, claim_type=claim_type, metadata=metadata, seen_at=seen_at, id_resolver=claim_id_for_canonical_key, connection_factory=db_conn)
upsert_intelligence_claim_impl.__sportabase_dependencies__ = ('_upsert_intelligence_claim_impl', 'claim_id_for_canonical_key', 'db_conn')


def claim_link_id_for_record_impl(*, claim_id: str, relationship_type: str, observed_at: str, confidence: Optional[float]=None, source_observation_id: Optional[str]=None, reporter_observation_id: Optional[str]=None, evidence_id: Optional[str]=None, _claim_link_id_for_record_impl) -> str:
    return _claim_link_id_for_record_impl(claim_id=claim_id, relationship_type=relationship_type, observed_at=observed_at, confidence=confidence, source_observation_id=source_observation_id, reporter_observation_id=reporter_observation_id, evidence_id=evidence_id)
claim_link_id_for_record_impl.__sportabase_dependencies__ = ('_claim_link_id_for_record_impl',)


def record_claim_link_impl(*, claim_id: str, relationship_type: str, observed_at: str, confidence: Optional[float]=None, source_observation_id: Optional[str]=None, reporter_observation_id: Optional[str]=None, evidence_id: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, recorded_at: Optional[str]=None, _record_claim_link_impl, db_conn) -> Dict[str, Any]:
    return _record_claim_link_impl(claim_id=claim_id, relationship_type=relationship_type, observed_at=observed_at, confidence=confidence, source_observation_id=source_observation_id, reporter_observation_id=reporter_observation_id, evidence_id=evidence_id, metadata=metadata, recorded_at=recorded_at, connection_factory=db_conn)
record_claim_link_impl.__sportabase_dependencies__ = ('_record_claim_link_impl', 'db_conn')


def link_media_item_to_story_impl(*, story_id: str, media_item_id: str, relationship_type: str='reports', confidence: float=0.0, linked_at: Optional[str]=None, datetime, db_conn, timezone) -> Dict[str, Any]:
    normalized_story_id = str(story_id or '').strip()
    normalized_media_item_id = str(media_item_id or '').strip()
    normalized_relationship_type = str(relationship_type or '').strip().lower()
    if not normalized_story_id:
        raise ValueError('Story media link story ID is required.')
    if not normalized_media_item_id:
        raise ValueError('Story media link media item ID is required.')
    if not normalized_relationship_type:
        raise ValueError('Story media link relationship type is required.')
    try:
        normalized_confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError('Story media link confidence must be numeric.') from exc
    if not 0.0 <= normalized_confidence <= 1.0:
        raise ValueError('Story media link confidence must be between 0 and 1.')
    normalized_linked_at = str(linked_at or '').strip() or datetime.now(timezone.utc).isoformat()
    conn = db_conn()
    try:
        conn.execute('\n            INSERT INTO story_media_links (\n              story_id,\n              media_item_id,\n              relationship_type,\n              confidence,\n              linked_at\n            )\n            VALUES (\n              ?, ?, ?, ?, ?\n            )\n            ON CONFLICT(\n              story_id,\n              media_item_id\n            )\n            DO UPDATE SET\n              relationship_type =\n                excluded.relationship_type,\n              confidence =\n                excluded.confidence\n            ', (normalized_story_id, normalized_media_item_id, normalized_relationship_type, normalized_confidence, normalized_linked_at))
        row = conn.execute('\n            SELECT *\n            FROM story_media_links\n            WHERE story_id = ?\n              AND media_item_id = ?\n            ', (normalized_story_id, normalized_media_item_id)).fetchone()
        conn.commit()
    finally:
        conn.close()
    if row is None:
        raise RuntimeError('Story media link persistence failed.')
    return dict(row)
link_media_item_to_story_impl.__sportabase_dependencies__ = ('datetime', 'db_conn', 'timezone')


def reporter_id_for_identity_key_impl(identity_key: str, *, _reporter_id_for_identity_key_impl) -> str:
    return _reporter_id_for_identity_key_impl(identity_key)
reporter_id_for_identity_key_impl.__sportabase_dependencies__ = ('_reporter_id_for_identity_key_impl',)


def upsert_intelligence_reporter_impl(*, identity_key: str, display_name: str='', metadata: Optional[Dict[str, Any]]=None, seen_at: Optional[str]=None, _upsert_intelligence_reporter_impl, db_conn, reporter_id_for_identity_key) -> Dict[str, Any]:
    return _upsert_intelligence_reporter_impl(identity_key=identity_key, display_name=display_name, metadata=metadata, seen_at=seen_at, id_resolver=reporter_id_for_identity_key, connection_factory=db_conn)
upsert_intelligence_reporter_impl.__sportabase_dependencies__ = ('_upsert_intelligence_reporter_impl', 'db_conn', 'reporter_id_for_identity_key')


def record_source_observation_impl(*, source_id: str, subject_key: str, observation_type: str, observed_at: str, status: str='unresolved', claim_summary: str='', provenance_url: str='', confidence: Optional[float]=None, media_item_id: Optional[str]=None, story_id: Optional[str]=None, recorded_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, _record_source_observation_impl, db_conn, normalized_analysis_url) -> Dict[str, Any]:
    return _record_source_observation_impl(source_id=source_id, subject_key=subject_key, observation_type=observation_type, observed_at=observed_at, status=status, claim_summary=claim_summary, provenance_url=provenance_url, confidence=confidence, media_item_id=media_item_id, story_id=story_id, recorded_at=recorded_at, metadata=metadata, normalize_url=normalized_analysis_url, connection_factory=db_conn)
record_source_observation_impl.__sportabase_dependencies__ = ('_record_source_observation_impl', 'db_conn', 'normalized_analysis_url')


def record_reporter_observation_impl(*, reporter_id: str, subject_key: str, observation_type: str, observed_at: str, status: str='unresolved', claim_summary: str='', provenance_url: str='', confidence: Optional[float]=None, source_id: Optional[str]=None, media_item_id: Optional[str]=None, story_id: Optional[str]=None, recorded_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, _record_reporter_observation_impl, db_conn, normalized_analysis_url) -> Dict[str, Any]:
    return _record_reporter_observation_impl(reporter_id=reporter_id, subject_key=subject_key, observation_type=observation_type, observed_at=observed_at, status=status, claim_summary=claim_summary, provenance_url=provenance_url, confidence=confidence, source_id=source_id, media_item_id=media_item_id, story_id=story_id, recorded_at=recorded_at, metadata=metadata, normalize_url=normalized_analysis_url, connection_factory=db_conn)
record_reporter_observation_impl.__sportabase_dependencies__ = ('_record_reporter_observation_impl', 'db_conn', 'normalized_analysis_url')


def evidence_key_for_record_impl(*, evidence_type: str, subject_key: str, observed_at: str, canonical_url: str='', reference_key: str='', verification_status: str='unverified', _evidence_key_for_record_impl, normalized_analysis_url) -> str:
    return _evidence_key_for_record_impl(evidence_type=evidence_type, subject_key=subject_key, observed_at=observed_at, canonical_url=canonical_url, reference_key=reference_key, verification_status=verification_status, normalize_url=normalized_analysis_url)
evidence_key_for_record_impl.__sportabase_dependencies__ = ('_evidence_key_for_record_impl', 'normalized_analysis_url')


def record_evidence_impl(*, evidence_type: str, subject_key: str, observed_at: str, claim_summary: str='', canonical_url: str='', reference_key: str='', verification_status: str='unverified', published_at: Optional[str]=None, recorded_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, _record_evidence_impl, db_conn, normalized_analysis_url) -> Dict[str, Any]:
    return _record_evidence_impl(evidence_type=evidence_type, subject_key=subject_key, observed_at=observed_at, claim_summary=claim_summary, canonical_url=canonical_url, reference_key=reference_key, verification_status=verification_status, published_at=published_at, recorded_at=recorded_at, metadata=metadata, normalize_url=normalized_analysis_url, connection_factory=db_conn)
record_evidence_impl.__sportabase_dependencies__ = ('_record_evidence_impl', 'db_conn', 'normalized_analysis_url')


def record_evidence_link_impl(*, evidence_id: str, relationship_type: str='supports', confidence: Optional[float]=None, media_item_id: Optional[str]=None, story_id: Optional[str]=None, source_id: Optional[str]=None, reporter_id: Optional[str]=None, linked_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, _record_evidence_link_impl, db_conn) -> Dict[str, Any]:
    return _record_evidence_link_impl(evidence_id=evidence_id, relationship_type=relationship_type, confidence=confidence, media_item_id=media_item_id, story_id=story_id, source_id=source_id, reporter_id=reporter_id, linked_at=linked_at, metadata=metadata, connection_factory=db_conn)
record_evidence_link_impl.__sportabase_dependencies__ = ('_record_evidence_link_impl', 'db_conn')


def _observation_dependency_identity_impl(*, relationship_type: str, observed_at: str, confidence: Optional[float]=None, downstream_source_observation_id: Optional[str]=None, downstream_reporter_observation_id: Optional[str]=None, upstream_source_observation_id: Optional[str]=None, upstream_reporter_observation_id: Optional[str]=None, upstream_source_id: Optional[str]=None, upstream_reporter_id: Optional[str]=None, _observation_dependency_identity_impl) -> Dict[str, Any]:
    return _observation_dependency_identity_impl(relationship_type=relationship_type, observed_at=observed_at, confidence=confidence, downstream_source_observation_id=downstream_source_observation_id, downstream_reporter_observation_id=downstream_reporter_observation_id, upstream_source_observation_id=upstream_source_observation_id, upstream_reporter_observation_id=upstream_reporter_observation_id, upstream_source_id=upstream_source_id, upstream_reporter_id=upstream_reporter_id)
_observation_dependency_identity_impl.__sportabase_dependencies__ = ('_observation_dependency_identity_impl',)


def observation_dependency_id_for_record_impl(*, relationship_type: str, observed_at: str, confidence: Optional[float]=None, downstream_source_observation_id: Optional[str]=None, downstream_reporter_observation_id: Optional[str]=None, upstream_source_observation_id: Optional[str]=None, upstream_reporter_observation_id: Optional[str]=None, upstream_source_id: Optional[str]=None, upstream_reporter_id: Optional[str]=None, _observation_dependency_id_for_record_impl) -> str:
    return _observation_dependency_id_for_record_impl(relationship_type=relationship_type, observed_at=observed_at, confidence=confidence, downstream_source_observation_id=downstream_source_observation_id, downstream_reporter_observation_id=downstream_reporter_observation_id, upstream_source_observation_id=upstream_source_observation_id, upstream_reporter_observation_id=upstream_reporter_observation_id, upstream_source_id=upstream_source_id, upstream_reporter_id=upstream_reporter_id)
observation_dependency_id_for_record_impl.__sportabase_dependencies__ = ('_observation_dependency_id_for_record_impl',)


def record_observation_dependency_impl(*, relationship_type: str, observed_at: str, confidence: Optional[float]=None, downstream_source_observation_id: Optional[str]=None, downstream_reporter_observation_id: Optional[str]=None, upstream_source_observation_id: Optional[str]=None, upstream_reporter_observation_id: Optional[str]=None, upstream_source_id: Optional[str]=None, upstream_reporter_id: Optional[str]=None, recorded_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, _record_observation_dependency_impl, db_conn) -> Dict[str, Any]:
    return _record_observation_dependency_impl(relationship_type=relationship_type, observed_at=observed_at, confidence=confidence, downstream_source_observation_id=downstream_source_observation_id, downstream_reporter_observation_id=downstream_reporter_observation_id, upstream_source_observation_id=upstream_source_observation_id, upstream_reporter_observation_id=upstream_reporter_observation_id, upstream_source_id=upstream_source_id, upstream_reporter_id=upstream_reporter_id, recorded_at=recorded_at, metadata=metadata, connection_factory=db_conn)
record_observation_dependency_impl.__sportabase_dependencies__ = ('_record_observation_dependency_impl', 'db_conn')


def observation_independence_assertion_id_for_record_impl(*, observed_at: str, provenance_evidence_id: str, verification_status: str='unverified', confidence: Optional[float]=None, left_source_observation_id: Optional[str]=None, left_reporter_observation_id: Optional[str]=None, right_source_observation_id: Optional[str]=None, right_reporter_observation_id: Optional[str]=None, _observation_independence_assertion_id_for_record_impl) -> str:
    return _observation_independence_assertion_id_for_record_impl(observed_at=observed_at, provenance_evidence_id=provenance_evidence_id, verification_status=verification_status, confidence=confidence, left_source_observation_id=left_source_observation_id, left_reporter_observation_id=left_reporter_observation_id, right_source_observation_id=right_source_observation_id, right_reporter_observation_id=right_reporter_observation_id)
observation_independence_assertion_id_for_record_impl.__sportabase_dependencies__ = ('_observation_independence_assertion_id_for_record_impl',)


def record_observation_independence_assertion_impl(*, observed_at: str, provenance_evidence_id: str, verification_status: str='unverified', confidence: Optional[float]=None, left_source_observation_id: Optional[str]=None, left_reporter_observation_id: Optional[str]=None, right_source_observation_id: Optional[str]=None, right_reporter_observation_id: Optional[str]=None, recorded_at: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None, _record_observation_independence_assertion_impl, db_conn) -> Dict[str, Any]:
    return _record_observation_independence_assertion_impl(observed_at=observed_at, provenance_evidence_id=provenance_evidence_id, verification_status=verification_status, confidence=confidence, left_source_observation_id=left_source_observation_id, left_reporter_observation_id=left_reporter_observation_id, right_source_observation_id=right_source_observation_id, right_reporter_observation_id=right_reporter_observation_id, recorded_at=recorded_at, metadata=metadata, connection_factory=db_conn)
record_observation_independence_assertion_impl.__sportabase_dependencies__ = ('_record_observation_independence_assertion_impl', 'db_conn')


def load_evidence_context_for_source_impl(*, source_id: str, _load_evidence_context_for_source_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_context_for_source_impl(source_id=source_id, connection_factory=db_conn)
load_evidence_context_for_source_impl.__sportabase_dependencies__ = ('_load_evidence_context_for_source_impl', 'db_conn')


def load_evidence_context_for_reporter_impl(*, reporter_id: str, _load_evidence_context_for_reporter_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_context_for_reporter_impl(reporter_id=reporter_id, connection_factory=db_conn)
load_evidence_context_for_reporter_impl.__sportabase_dependencies__ = ('_load_evidence_context_for_reporter_impl', 'db_conn')


def load_evidence_context_for_media_item_impl(*, media_item_id: str, _load_evidence_context_for_media_item_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_context_for_media_item_impl(media_item_id=media_item_id, connection_factory=db_conn)
load_evidence_context_for_media_item_impl.__sportabase_dependencies__ = ('_load_evidence_context_for_media_item_impl', 'db_conn')


def load_expanded_evidence_context_for_media_item_impl(*, media_item_id: str, _load_expanded_evidence_context_for_media_item_impl, db_conn) -> Dict[str, Any]:
    return _load_expanded_evidence_context_for_media_item_impl(media_item_id=media_item_id, connection_factory=db_conn)
load_expanded_evidence_context_for_media_item_impl.__sportabase_dependencies__ = ('_load_expanded_evidence_context_for_media_item_impl', 'db_conn')


def evidence_context_hash_for_media_item_impl(*, media_item_id: str, _evidence_context_hash_for_media_item_impl, db_conn) -> str:
    return _evidence_context_hash_for_media_item_impl(media_item_id=media_item_id, connection_factory=db_conn)
evidence_context_hash_for_media_item_impl.__sportabase_dependencies__ = ('_evidence_context_hash_for_media_item_impl', 'db_conn')


def expanded_evidence_context_hash_for_media_item_impl(*, media_item_id: str, _expanded_evidence_context_hash_for_media_item_impl, db_conn) -> str:
    return _expanded_evidence_context_hash_for_media_item_impl(media_item_id=media_item_id, connection_factory=db_conn)
expanded_evidence_context_hash_for_media_item_impl.__sportabase_dependencies__ = ('_expanded_evidence_context_hash_for_media_item_impl', 'db_conn')


def load_evidence_context_for_story_impl(*, story_id: str, _load_evidence_context_for_story_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_context_for_story_impl(story_id=story_id, connection_factory=db_conn)
load_evidence_context_for_story_impl.__sportabase_dependencies__ = ('_load_evidence_context_for_story_impl', 'db_conn')


def load_evidence_context_for_subject_impl(*, subject_key: str, _load_evidence_context_for_subject_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_context_for_subject_impl(subject_key=subject_key, connection_factory=db_conn)
load_evidence_context_for_subject_impl.__sportabase_dependencies__ = ('_load_evidence_context_for_subject_impl', 'db_conn')


def load_evidence_analysis_bundle_for_media_item_impl(*, media_item_id: str, _load_evidence_analysis_bundle_for_media_item_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_analysis_bundle_for_media_item_impl(media_item_id=media_item_id, connection_factory=db_conn)
load_evidence_analysis_bundle_for_media_item_impl.__sportabase_dependencies__ = ('_load_evidence_analysis_bundle_for_media_item_impl', 'db_conn')


def load_evidence_analysis_state_for_media_item_impl(*, media_item_id: str, _load_evidence_analysis_state_for_media_item_impl, db_conn) -> Dict[str, Any]:
    return _load_evidence_analysis_state_for_media_item_impl(media_item_id=media_item_id, connection_factory=db_conn)
load_evidence_analysis_state_for_media_item_impl.__sportabase_dependencies__ = ('_load_evidence_analysis_state_for_media_item_impl', 'db_conn')
