SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  sport TEXT NOT NULL,
  title TEXT NOT NULL,
  link TEXT NOT NULL,
  published TEXT,
  summary TEXT,
  tldr_json TEXT,
  merit_score INTEGER,
  badge TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at);
CREATE INDEX IF NOT EXISTS idx_stories_sport ON stories(sport);
CREATE INDEX IF NOT EXISTS idx_stories_source ON stories(source);

CREATE TABLE IF NOT EXISTS analysis_cache (
  cache_key TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  request_url TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  analysis_version TEXT NOT NULL,
  response_json TEXT NOT NULL,
  article_type TEXT,
  created_at TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires_at
ON analysis_cache(expires_at);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_mode
ON analysis_cache(mode);

CREATE TABLE IF NOT EXISTS gemini_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  usage_day TEXT NOT NULL,
  client_key TEXT NOT NULL,
  mode TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  thought_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  cache_hit INTEGER NOT NULL DEFAULT 0,
  inflight_join INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  failure_status_code INTEGER,
  failure_type TEXT NOT NULL DEFAULT '',
  failure_detail TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_gemini_usage_day
ON gemini_usage(usage_day);

CREATE INDEX IF NOT EXISTS idx_gemini_usage_client_day
ON gemini_usage(client_key, usage_day);

CREATE TABLE IF NOT EXISTS intelligence_sources (
  id TEXT PRIMARY KEY,
  source_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL DEFAULT '',
  source_type TEXT NOT NULL DEFAULT 'publisher',
  canonical_domain TEXT,
  publication_founded_at TEXT,
  domain_registered_at TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_intelligence_sources_domain
ON intelligence_sources(canonical_domain);

CREATE INDEX IF NOT EXISTS idx_intelligence_sources_type
ON intelligence_sources(source_type);

CREATE TABLE IF NOT EXISTS intelligence_reporters (
  id TEXT PRIMARY KEY,
  identity_key TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL DEFAULT '',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_intelligence_reporters_name
ON intelligence_reporters(display_name);

CREATE TABLE IF NOT EXISTS media_items (
  id TEXT PRIMARY KEY,
  canonical_url TEXT NOT NULL UNIQUE,
  mode TEXT NOT NULL,
  source_id TEXT,
  reporter_id TEXT,
  title TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  latest_content_hash TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(source_id)
    REFERENCES intelligence_sources(id),
  FOREIGN KEY(reporter_id)
    REFERENCES intelligence_reporters(id)
);

CREATE INDEX IF NOT EXISTS idx_media_items_source
ON media_items(source_id);

CREATE INDEX IF NOT EXISTS idx_media_items_reporter
ON media_items(reporter_id);

CREATE INDEX IF NOT EXISTS idx_media_items_mode
ON media_items(mode);

CREATE TABLE IF NOT EXISTS intelligence_stories (
  id TEXT PRIMARY KEY,
  canonical_key TEXT NOT NULL UNIQUE,
  canonical_title TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'developing',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_intelligence_stories_status
ON intelligence_stories(status);

CREATE TABLE IF NOT EXISTS intelligence_claims (
  id TEXT PRIMARY KEY,
  canonical_key TEXT NOT NULL UNIQUE,
  subject_key TEXT NOT NULL,
  canonical_text TEXT NOT NULL DEFAULT '',
  claim_type TEXT NOT NULL DEFAULT 'assertion',
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_intelligence_claims_subject
ON intelligence_claims(subject_key);

CREATE INDEX IF NOT EXISTS idx_intelligence_claims_type
ON intelligence_claims(claim_type);


CREATE TABLE IF NOT EXISTS story_claim_links (
  story_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL DEFAULT 'exact_claim_group',
  link_basis TEXT NOT NULL DEFAULT 'downstream_exact_common_claim_id',
  linked_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (
    story_id,
    claim_id
  ),
  CHECK (
    relationship_type = 'exact_claim_group'
  ),
  CHECK (
    link_basis = 'downstream_exact_common_claim_id'
  ),
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE CASCADE,
  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_story_claim_links_claim
ON story_claim_links(claim_id);


CREATE TABLE IF NOT EXISTS canonical_entities (
  id TEXT PRIMARY KEY,
  entity_key TEXT NOT NULL UNIQUE,
  entity_type TEXT NOT NULL,
  sport_key TEXT NOT NULL DEFAULT '',
  canonical_name TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    entity_type IN (
      'player',
      'club',
      'team',
      'league',
      'competition',
      'country',
      'governing_body',
      'reporter',
      'channel',
      'organization',
      'person'
    )
  )
);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_type
ON canonical_entities(entity_type);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_sport
ON canonical_entities(
  sport_key,
  entity_type
);

CREATE INDEX IF NOT EXISTS idx_canonical_entities_name
ON canonical_entities(canonical_name);


CREATE TABLE IF NOT EXISTS entity_aliases (
  id TEXT PRIMARY KEY,
  entity_id TEXT NOT NULL,
  alias_text TEXT NOT NULL,
  normalized_alias TEXT NOT NULL,
  alias_type TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (
    entity_id,
    alias_type,
    normalized_alias
  ),
  CHECK (
    alias_type IN (
      'canonical_name',
      'common_name',
      'short_name',
      'abbreviation',
      'former_name',
      'handle',
      'external_name'
    )
  ),
  FOREIGN KEY(entity_id)
    REFERENCES canonical_entities(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_entity
ON entity_aliases(entity_id);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_normalized
ON entity_aliases(normalized_alias);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_lookup
ON entity_aliases(
  normalized_alias,
  alias_type
);


CREATE TABLE IF NOT EXISTS verified_source_entity_bindings (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  binding_type TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'verified',
  confidence REAL NOT NULL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    binding_type IN (
      'official_site',
      'official_publication',
      'official_channel',
      'official_account',
      'controlled_domain'
    )
  ),
  CHECK (
    verification_status = 'verified'
  ),
  CHECK (
    confidence >= 0.95
    AND confidence <= 1.0
  ),
  FOREIGN KEY(source_id)
    REFERENCES intelligence_sources(id)
    ON DELETE CASCADE,
  FOREIGN KEY(entity_id)
    REFERENCES canonical_entities(id)
    ON DELETE CASCADE,
  FOREIGN KEY(evidence_id)
    REFERENCES evidence_records(id)
);

CREATE INDEX IF NOT EXISTS
idx_verified_source_entity_source
ON verified_source_entity_bindings(source_id);

CREATE INDEX IF NOT EXISTS
idx_verified_source_entity_entity
ON verified_source_entity_bindings(entity_id);

CREATE INDEX IF NOT EXISTS
idx_verified_source_entity_evidence
ON verified_source_entity_bindings(evidence_id);


CREATE TABLE IF NOT EXISTS verified_claim_entity_participants (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  participant_role TEXT NOT NULL,
  evidence_id TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'verified',
  confidence REAL NOT NULL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    participant_role IN (
      'subject',
      'actor',
      'counterparty',
      'origin',
      'destination',
      'affected_party',
      'governing_body',
      'competition',
      'other_party'
    )
  ),
  CHECK (
    verification_status = 'verified'
  ),
  CHECK (
    confidence >= 0.95
    AND confidence <= 1.0
  ),
  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE,
  FOREIGN KEY(entity_id)
    REFERENCES canonical_entities(id)
    ON DELETE CASCADE,
  FOREIGN KEY(evidence_id)
    REFERENCES evidence_records(id
  )
);

CREATE INDEX IF NOT EXISTS
idx_verified_claim_entity_claim
ON verified_claim_entity_participants(claim_id);

CREATE INDEX IF NOT EXISTS
idx_verified_claim_entity_entity
ON verified_claim_entity_participants(entity_id);

CREATE INDEX IF NOT EXISTS
idx_verified_claim_entity_evidence
ON verified_claim_entity_participants(evidence_id);


CREATE TABLE IF NOT EXISTS story_media_links (
  story_id TEXT NOT NULL,
  media_item_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL DEFAULT 'reports',
  confidence REAL NOT NULL DEFAULT 0.0,
  linked_at TEXT NOT NULL,
  PRIMARY KEY(story_id, media_item_id),
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE CASCADE,
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_story_media_links_media
ON story_media_links(media_item_id);

CREATE TABLE IF NOT EXISTS source_observations (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  media_item_id TEXT,
  story_id TEXT,
  subject_key TEXT NOT NULL,
  observation_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unresolved',
  claim_summary TEXT NOT NULL DEFAULT '',
  provenance_url TEXT NOT NULL DEFAULT '',
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(source_id)
    REFERENCES intelligence_sources(id)
    ON DELETE CASCADE,
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE SET NULL,
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_source_observations_source_time
ON source_observations(source_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_source_observations_subject_time
ON source_observations(subject_key, observed_at);

CREATE INDEX IF NOT EXISTS idx_source_observations_media
ON source_observations(media_item_id);

CREATE INDEX IF NOT EXISTS idx_source_observations_story
ON source_observations(story_id);

CREATE TABLE IF NOT EXISTS reporter_observations (
  id TEXT PRIMARY KEY,
  reporter_id TEXT NOT NULL,
  source_id TEXT,
  media_item_id TEXT,
  story_id TEXT,
  subject_key TEXT NOT NULL,
  observation_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unresolved',
  claim_summary TEXT NOT NULL DEFAULT '',
  provenance_url TEXT NOT NULL DEFAULT '',
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(reporter_id)
    REFERENCES intelligence_reporters(id)
    ON DELETE CASCADE,
  FOREIGN KEY(source_id)
    REFERENCES intelligence_sources(id)
    ON DELETE SET NULL,
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE SET NULL,
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_reporter_observations_reporter_time
ON reporter_observations(reporter_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_reporter_observations_source_time
ON reporter_observations(source_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_reporter_observations_subject_time
ON reporter_observations(subject_key, observed_at);

CREATE INDEX IF NOT EXISTS idx_reporter_observations_media
ON reporter_observations(media_item_id);

CREATE INDEX IF NOT EXISTS idx_reporter_observations_story
ON reporter_observations(story_id);

CREATE TABLE IF NOT EXISTS evidence_records (
  id TEXT PRIMARY KEY,
  evidence_key TEXT NOT NULL UNIQUE,
  evidence_type TEXT NOT NULL,
  subject_key TEXT NOT NULL,
  claim_summary TEXT NOT NULL DEFAULT '',
  canonical_url TEXT NOT NULL DEFAULT '',
  reference_key TEXT NOT NULL DEFAULT '',
  verification_status TEXT NOT NULL DEFAULT 'unverified',
  published_at TEXT,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_evidence_records_type
ON evidence_records(evidence_type);

CREATE INDEX IF NOT EXISTS idx_evidence_records_subject_time
ON evidence_records(subject_key, observed_at);

CREATE INDEX IF NOT EXISTS idx_evidence_records_url
ON evidence_records(canonical_url);

CREATE INDEX IF NOT EXISTS idx_evidence_records_verification
ON evidence_records(verification_status);

CREATE TABLE IF NOT EXISTS evidence_links (
  id TEXT PRIMARY KEY,
  evidence_id TEXT NOT NULL,
  media_item_id TEXT,
  story_id TEXT,
  source_id TEXT,
  reporter_id TEXT,
  relationship_type TEXT NOT NULL DEFAULT 'supports',
  confidence REAL,
  linked_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    confidence IS NULL
    OR (
      confidence >= 0.0
      AND confidence <= 1.0
    )
  ),
  CHECK (
    (media_item_id IS NOT NULL)
    + (story_id IS NOT NULL)
    + (source_id IS NOT NULL)
    + (reporter_id IS NOT NULL)
    = 1
  ),
  FOREIGN KEY(evidence_id)
    REFERENCES evidence_records(id)
    ON DELETE CASCADE,
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE CASCADE,
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE CASCADE,
  FOREIGN KEY(source_id)
    REFERENCES intelligence_sources(id)
    ON DELETE CASCADE,
  FOREIGN KEY(reporter_id)
    REFERENCES intelligence_reporters(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evidence_links_evidence
ON evidence_links(evidence_id);

CREATE INDEX IF NOT EXISTS idx_evidence_links_media
ON evidence_links(media_item_id);

CREATE INDEX IF NOT EXISTS idx_evidence_links_story
ON evidence_links(story_id);

CREATE INDEX IF NOT EXISTS idx_evidence_links_source
ON evidence_links(source_id);

CREATE INDEX IF NOT EXISTS idx_evidence_links_reporter
ON evidence_links(reporter_id);

CREATE TABLE IF NOT EXISTS claim_links (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  source_observation_id TEXT,
  reporter_observation_id TEXT,
  evidence_id TEXT,
  relationship_type TEXT NOT NULL,
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    confidence IS NULL
    OR (
      confidence >= 0.0
      AND confidence <= 1.0
    )
  ),
  CHECK (
    (source_observation_id IS NOT NULL)
    + (reporter_observation_id IS NOT NULL)
    + (evidence_id IS NOT NULL)
    = 1
  ),
  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id),
  FOREIGN KEY(source_observation_id)
    REFERENCES source_observations(id),
  FOREIGN KEY(reporter_observation_id)
    REFERENCES reporter_observations(id),
  FOREIGN KEY(evidence_id)
    REFERENCES evidence_records(id)
);

CREATE INDEX IF NOT EXISTS idx_claim_links_claim
ON claim_links(claim_id);

CREATE INDEX IF NOT EXISTS idx_claim_links_source_observation
ON claim_links(source_observation_id);

CREATE INDEX IF NOT EXISTS idx_claim_links_reporter_observation
ON claim_links(reporter_observation_id);

CREATE INDEX IF NOT EXISTS idx_claim_links_evidence
ON claim_links(evidence_id);

CREATE TABLE IF NOT EXISTS observation_dependencies (
  id TEXT PRIMARY KEY,
  downstream_source_observation_id TEXT,
  downstream_reporter_observation_id TEXT,
  upstream_source_observation_id TEXT,
  upstream_reporter_observation_id TEXT,
  upstream_source_id TEXT,
  upstream_reporter_id TEXT,
  relationship_type TEXT NOT NULL,
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    confidence IS NULL
    OR (
      confidence >= 0.0
      AND confidence <= 1.0
    )
  ),
  CHECK (
    (downstream_source_observation_id IS NOT NULL)
    + (downstream_reporter_observation_id IS NOT NULL)
    = 1
  ),
  CHECK (
    (upstream_source_observation_id IS NOT NULL)
    + (upstream_reporter_observation_id IS NOT NULL)
    + (upstream_source_id IS NOT NULL)
    + (upstream_reporter_id IS NOT NULL)
    = 1
  ),
  FOREIGN KEY(downstream_source_observation_id)
    REFERENCES source_observations(id),
  FOREIGN KEY(downstream_reporter_observation_id)
    REFERENCES reporter_observations(id),
  FOREIGN KEY(upstream_source_observation_id)
    REFERENCES source_observations(id),
  FOREIGN KEY(upstream_reporter_observation_id)
    REFERENCES reporter_observations(id),
  FOREIGN KEY(upstream_source_id)
    REFERENCES intelligence_sources(id),
  FOREIGN KEY(upstream_reporter_id)
    REFERENCES intelligence_reporters(id)
);

CREATE INDEX IF NOT EXISTS idx_observation_dependencies_downstream_source
ON observation_dependencies(
  downstream_source_observation_id
);

CREATE INDEX IF NOT EXISTS idx_observation_dependencies_downstream_reporter
ON observation_dependencies(
  downstream_reporter_observation_id
);

CREATE INDEX IF NOT EXISTS idx_observation_dependencies_upstream_source_observation
ON observation_dependencies(
  upstream_source_observation_id
);

CREATE INDEX IF NOT EXISTS idx_observation_dependencies_upstream_reporter_observation
ON observation_dependencies(
  upstream_reporter_observation_id
);

CREATE INDEX IF NOT EXISTS idx_observation_dependencies_upstream_source
ON observation_dependencies(
  upstream_source_id
);

CREATE INDEX IF NOT EXISTS idx_observation_dependencies_upstream_reporter
ON observation_dependencies(
  upstream_reporter_id
);

CREATE TABLE IF NOT EXISTS
observation_independence_assertions (
  id TEXT PRIMARY KEY,
  observation_a_source_observation_id TEXT,
  observation_a_reporter_observation_id TEXT,
  observation_b_source_observation_id TEXT,
  observation_b_reporter_observation_id TEXT,
  provenance_evidence_id TEXT NOT NULL,
  verification_status TEXT NOT NULL DEFAULT 'unverified',
  confidence REAL,
  observed_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    confidence IS NULL
    OR (
      confidence >= 0.0
      AND confidence <= 1.0
    )
  ),
  CHECK (
    verification_status IN (
      'unverified',
      'verified'
    )
  ),
  CHECK (
    (observation_a_source_observation_id IS NOT NULL)
    + (observation_a_reporter_observation_id IS NOT NULL)
    = 1
  ),
  CHECK (
    (observation_b_source_observation_id IS NOT NULL)
    + (observation_b_reporter_observation_id IS NOT NULL)
    = 1
  ),
  CHECK (
    observation_a_source_observation_id IS NULL
    OR observation_b_source_observation_id IS NULL
    OR (
      observation_a_source_observation_id
      <> observation_b_source_observation_id
    )
  ),
  CHECK (
    observation_a_reporter_observation_id IS NULL
    OR observation_b_reporter_observation_id IS NULL
    OR (
      observation_a_reporter_observation_id
      <> observation_b_reporter_observation_id
    )
  ),
  FOREIGN KEY(observation_a_source_observation_id)
    REFERENCES source_observations(id),
  FOREIGN KEY(observation_a_reporter_observation_id)
    REFERENCES reporter_observations(id),
  FOREIGN KEY(observation_b_source_observation_id)
    REFERENCES source_observations(id),
  FOREIGN KEY(observation_b_reporter_observation_id)
    REFERENCES reporter_observations(id),
  FOREIGN KEY(provenance_evidence_id)
    REFERENCES evidence_records(id)
);

CREATE INDEX IF NOT EXISTS
idx_observation_independence_a_source
ON observation_independence_assertions(
  observation_a_source_observation_id
);

CREATE INDEX IF NOT EXISTS
idx_observation_independence_a_reporter
ON observation_independence_assertions(
  observation_a_reporter_observation_id
);

CREATE INDEX IF NOT EXISTS
idx_observation_independence_b_source
ON observation_independence_assertions(
  observation_b_source_observation_id
);

CREATE INDEX IF NOT EXISTS
idx_observation_independence_b_reporter
ON observation_independence_assertions(
  observation_b_reporter_observation_id
);

CREATE INDEX IF NOT EXISTS
idx_observation_independence_evidence
ON observation_independence_assertions(
  provenance_evidence_id
);

CREATE INDEX IF NOT EXISTS
idx_observation_independence_verification
ON observation_independence_assertions(
  verification_status
);

CREATE TABLE IF NOT EXISTS corpus_records (
  id TEXT PRIMARY KEY,
  origin_type TEXT NOT NULL,
  data_family TEXT NOT NULL,
  dataset_name TEXT NOT NULL,
  external_record_id TEXT NOT NULL,
  adapter_version TEXT NOT NULL,
  sport_key TEXT NOT NULL DEFAULT '',
  competition_key TEXT NOT NULL DEFAULT '',
  season_key TEXT NOT NULL DEFAULT '',
  event_type TEXT NOT NULL DEFAULT '',
  granularity TEXT NOT NULL DEFAULT 'record',
  measurement_kind TEXT NOT NULL DEFAULT 'raw',
  canonical_url TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  occurred_at TEXT,
  payload_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL DEFAULT '{}',
  ingested_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_corpus_records_external_identity
ON corpus_records(
  origin_type,
  dataset_name,
  external_record_id
);

CREATE INDEX IF NOT EXISTS idx_corpus_records_dataset_time
ON corpus_records(
  dataset_name,
  ingested_at
);

CREATE INDEX IF NOT EXISTS idx_corpus_records_sport_scope
ON corpus_records(
  sport_key,
  competition_key,
  season_key
);

CREATE INDEX IF NOT EXISTS idx_corpus_records_event_type
ON corpus_records(
  sport_key,
  event_type,
  granularity
);

CREATE INDEX IF NOT EXISTS idx_corpus_records_occurred_at
ON corpus_records(occurred_at);

CREATE INDEX IF NOT EXISTS idx_corpus_records_payload_hash
ON corpus_records(payload_hash);


CREATE TABLE IF NOT EXISTS corpus_record_links (
  id TEXT PRIMARY KEY,
  corpus_record_id TEXT NOT NULL,
  story_id TEXT,
  media_item_id TEXT,
  claim_id TEXT,
  relationship_type TEXT NOT NULL DEFAULT 'materializes',
  linked_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (
    (story_id IS NOT NULL)
    + (media_item_id IS NOT NULL)
    + (claim_id IS NOT NULL)
    = 1
  ),
  FOREIGN KEY(corpus_record_id)
    REFERENCES corpus_records(id)
    ON DELETE CASCADE,
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE CASCADE,
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE CASCADE,
  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_corpus_record_links_record
ON corpus_record_links(corpus_record_id);

CREATE INDEX IF NOT EXISTS idx_corpus_record_links_story
ON corpus_record_links(story_id);

CREATE INDEX IF NOT EXISTS idx_corpus_record_links_media
ON corpus_record_links(media_item_id);

CREATE INDEX IF NOT EXISTS idx_corpus_record_links_claim
ON corpus_record_links(claim_id);



CREATE TABLE IF NOT EXISTS adjudication_state_revisions (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  state_version TEXT NOT NULL,
  adjudication_version TEXT NOT NULL,
  adjudication_sha256 TEXT NOT NULL,
  as_of TEXT NOT NULL,
  previous_revision_id TEXT,
  trigger_type TEXT NOT NULL,
  trigger_evidence_ids_json TEXT NOT NULL DEFAULT '[]',
  revision_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,

  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE,

  FOREIGN KEY(previous_revision_id)
    REFERENCES adjudication_state_revisions(id)
    ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS
idx_adjudication_state_revisions_claim
ON adjudication_state_revisions(
  claim_id,
  as_of
);

CREATE INDEX IF NOT EXISTS
idx_adjudication_state_revisions_previous
ON adjudication_state_revisions(
  previous_revision_id
);

CREATE INDEX IF NOT EXISTS
idx_adjudication_state_revisions_trigger
ON adjudication_state_revisions(
  trigger_type
);


CREATE TABLE IF NOT EXISTS adjudication_state_transitions (
  id TEXT PRIMARY KEY,
  revision_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  field TEXT NOT NULL,
  kind TEXT NOT NULL,
  from_state_json TEXT,
  to_state_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,

  FOREIGN KEY(revision_id)
    REFERENCES adjudication_state_revisions(id)
    ON DELETE CASCADE,

  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS
idx_adjudication_state_transitions_revision
ON adjudication_state_transitions(
  revision_id
);

CREATE INDEX IF NOT EXISTS
idx_adjudication_state_transitions_claim
ON adjudication_state_transitions(
  claim_id,
  field
);

CREATE UNIQUE INDEX IF NOT EXISTS
idx_adjudication_state_transition_field
ON adjudication_state_transitions(
  revision_id,
  field
);



CREATE TABLE IF NOT EXISTS automatic_correction_events (
  id TEXT PRIMARY KEY,
  claim_id TEXT NOT NULL,
  field TEXT NOT NULL,
  signature TEXT NOT NULL,
  previous_revision_id TEXT NOT NULL,
  current_revision_id TEXT NOT NULL,
  event_version TEXT NOT NULL,
  event_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,

  UNIQUE(current_revision_id, field),

  FOREIGN KEY(claim_id)
    REFERENCES intelligence_claims(id)
    ON DELETE CASCADE,

  FOREIGN KEY(previous_revision_id)
    REFERENCES adjudication_state_revisions(id)
    ON DELETE RESTRICT,

  FOREIGN KEY(current_revision_id)
    REFERENCES adjudication_state_revisions(id)
    ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS
idx_automatic_correction_events_signature
ON automatic_correction_events(
  signature,
  claim_id
);

CREATE INDEX IF NOT EXISTS
idx_automatic_correction_events_claim
ON automatic_correction_events(
  claim_id
);

CREATE INDEX IF NOT EXISTS
idx_automatic_correction_events_current_revision
ON automatic_correction_events(
  current_revision_id
);


CREATE TABLE IF NOT EXISTS automatic_memory_candidates (
  id TEXT PRIMARY KEY,
  signature TEXT NOT NULL UNIQUE,
  field TEXT NOT NULL,
  candidate_version TEXT NOT NULL,
  status TEXT NOT NULL,
  support_count INTEGER NOT NULL,
  supporting_claim_ids_json TEXT NOT NULL DEFAULT '[]',
  supporting_correction_ids_json TEXT NOT NULL DEFAULT '[]',
  candidate_json TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,

  CHECK (
    status IN (
      'case_memory',
      'pattern_candidate'
    )
  ),

  CHECK (
    support_count >= 1
  )
);

CREATE INDEX IF NOT EXISTS
idx_automatic_memory_candidates_status
ON automatic_memory_candidates(
  status,
  support_count
);

CREATE INDEX IF NOT EXISTS
idx_automatic_memory_candidates_field
ON automatic_memory_candidates(
  field
);


CREATE TABLE IF NOT EXISTS analysis_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  media_item_id TEXT NOT NULL,
  story_id TEXT,
  analyzed_at TEXT NOT NULL,
  mode TEXT NOT NULL,
  analysis_version TEXT NOT NULL,
  scoring_version TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL,
  context_hash TEXT NOT NULL DEFAULT '',
  merit_score INTEGER,
  evidence_score INTEGER,
  logic_score INTEGER,
  badge TEXT NOT NULL DEFAULT '',
  verdict TEXT NOT NULL DEFAULT '',
  article_type TEXT NOT NULL DEFAULT '',
  score_components_json TEXT NOT NULL DEFAULT '{}',
  score_calculation_json TEXT NOT NULL DEFAULT '{}',
  reasons_json TEXT NOT NULL DEFAULT '[]',
  response_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE CASCADE,
  FOREIGN KEY(story_id)
    REFERENCES intelligence_stories(id)
    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_media_time
ON analysis_snapshots(media_item_id, analyzed_at);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_story_time
ON analysis_snapshots(story_id, analyzed_at);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_analysis_version
ON analysis_snapshots(analysis_version);

CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_scoring_version
ON analysis_snapshots(scoring_version);
CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_snapshots_identity
ON analysis_snapshots(
  media_item_id,
  mode,
  content_hash,
  analysis_version,
  scoring_version
);

CREATE TABLE IF NOT EXISTS user_history (
  client_key TEXT NOT NULL,
  media_item_id TEXT NOT NULL,
  first_analyzed_at TEXT NOT NULL,
  last_analyzed_at TEXT NOT NULL,
  analysis_count INTEGER NOT NULL DEFAULT 1,
  last_snapshot_id INTEGER,
  PRIMARY KEY(client_key, media_item_id),
  FOREIGN KEY(media_item_id)
    REFERENCES media_items(id)
    ON DELETE CASCADE,
  FOREIGN KEY(last_snapshot_id)
    REFERENCES analysis_snapshots(id)
    ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_user_history_recent
ON user_history(client_key, last_analyzed_at);

CREATE TABLE IF NOT EXISTS browser_capture_inbox (
  id TEXT PRIMARY KEY,
  capture_hash TEXT NOT NULL UNIQUE,
  canonical_url TEXT NOT NULL,
  platform TEXT NOT NULL,
  platform_surface TEXT NOT NULL DEFAULT '',
  normalized_item_id TEXT NOT NULL,
  normalized_content_hash TEXT NOT NULL,
  observed_at TEXT NOT NULL,
  first_received_at TEXT NOT NULL,
  last_received_at TEXT NOT NULL,
  receive_count INTEGER NOT NULL DEFAULT 1,
  capture_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  CHECK (receive_count >= 1)
);

CREATE INDEX IF NOT EXISTS idx_browser_capture_inbox_url
ON browser_capture_inbox(canonical_url);

CREATE INDEX IF NOT EXISTS idx_browser_capture_inbox_platform
ON browser_capture_inbox(platform);

CREATE INDEX IF NOT EXISTS idx_browser_capture_inbox_observed
ON browser_capture_inbox(observed_at);

CREATE TABLE IF NOT EXISTS browser_capture_automation_jobs (
  id TEXT PRIMARY KEY,
  capture_record_id TEXT NOT NULL,
  analysis_version TEXT NOT NULL,
  scoring_version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 24,
  available_at_epoch INTEGER NOT NULL,
  lease_owner TEXT NOT NULL DEFAULT '',
  lease_expires_at_epoch INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  last_outcome TEXT NOT NULL DEFAULT '',
  error_type TEXT NOT NULL DEFAULT '',
  error_detail TEXT NOT NULL DEFAULT '',
  result_json TEXT NOT NULL DEFAULT '{}',
  UNIQUE (
    capture_record_id,
    analysis_version,
    scoring_version
  ),
  CHECK (
    status IN (
      'pending',
      'running',
      'completed',
      'failed'
    )
  ),
  CHECK (attempts >= 0),
  CHECK (max_attempts >= 1),
  CHECK (available_at_epoch >= 0),
  CHECK (lease_expires_at_epoch >= 0),
  FOREIGN KEY(capture_record_id)
    REFERENCES browser_capture_inbox(id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_browser_capture_automation_ready
ON browser_capture_automation_jobs(
  status,
  available_at_epoch
);

CREATE INDEX IF NOT EXISTS idx_browser_capture_automation_capture
ON browser_capture_automation_jobs(capture_record_id);

CREATE INDEX IF NOT EXISTS idx_browser_capture_automation_versions
ON browser_capture_automation_jobs(
  analysis_version,
  scoring_version,
  status
);

"""
