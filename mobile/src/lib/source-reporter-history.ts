import { SportabaseApiError } from './api';
import {
  inspectableIntelligenceRoute,
  type IntelligenceKind,
} from './intelligence-kinds';

const API_BASE_URL = 'https://sportabase-api.onrender.com';
const REQUEST_TIMEOUT_MS = 22000;

export type SourceReporterKind = 'source' | 'reporter';

export type SourceReporterHistoryEvent = {
  type: string;
  occurred_at: string;
  id?: string;
  [key: string]: unknown;
};

type RelatedRecord = {
  id: string;
  display_name?: string;
  canonical_title?: string;
  canonical_text?: string;
  title?: string;
  source_type?: string;
  canonical_domain?: string;
  identity_key?: string;
  status?: string;
  claim_type?: string;
  mode?: string;
  [key: string]: unknown;
};

export type SourceReporterHistoryResponse = {
  version: string;
  source?: {
    id: string;
    source_key: string;
    display_name: string;
    source_type: string;
    canonical_domain: string | null;
    publication_founded_at: string | null;
    domain_registered_at: string | null;
    first_seen_at: string;
    last_seen_at: string;
  };
  reporter?: {
    id: string;
    identity_key: string;
    display_name: string;
    first_seen_at: string;
    last_seen_at: string;
  };
  counts: Record<string, number>;
  media: RelatedRecord[];
  claims: RelatedRecord[];
  stories: RelatedRecord[];
  reporters?: RelatedRecord[];
  sources?: RelatedRecord[];
  dependencies: RelatedRecord[];
  independence_assertions: RelatedRecord[];
  evidence_links: RelatedRecord[];
  events: SourceReporterHistoryEvent[];
  pagination: {
    limit: number;
    next_cursor: string | null;
  };
  policy: Record<string, boolean>;
};

export type SourceReporterRelation = {
  kind: IntelligenceKind;
  id: string;
  title: string;
  subtitle?: string;
};

async function readErrorDetail(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    return '';
  }
}

export async function getSourceReporterHistory(
  kind: SourceReporterKind,
  id: string,
  options: { limit?: number; cursor?: string } = {},
): Promise<SourceReporterHistoryResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const segment = kind === 'source' ? 'sources' : 'reporters';
  const params = [`limit=${options.limit ?? 50}`];
  if (options.cursor) {
    params.push(`cursor=${encodeURIComponent(options.cursor)}`);
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/intelligence/${segment}/${encodeURIComponent(id)}/history?${params.join('&')}`,
      {
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new SportabaseApiError(
        detail || `Sportabase API returned HTTP ${response.status}.`,
        response.status,
      );
    }
    return (await response.json()) as SourceReporterHistoryResponse;
  } catch (error) {
    if (error instanceof SportabaseApiError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new SportabaseApiError('Sportabase source/reporter history request timed out.');
    }
    throw new SportabaseApiError(
      error instanceof Error
        ? error.message
        : 'Could not reach Sportabase source/reporter history.',
    );
  } finally {
    clearTimeout(timeout);
  }
}

function text(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}

export function sourceReporterIdentity(
  kind: SourceReporterKind,
  response: SourceReporterHistoryResponse,
) {
  if (kind === 'source') {
    const source = response.source;
    if (!source) throw new Error('Source identity is missing.');
    return {
      title: source.display_name || source.canonical_domain || 'Persisted source',
      subtitle: [source.source_type, source.canonical_domain]
        .filter(Boolean)
        .join(' · '),
      firstSeenAt: source.first_seen_at,
      lastSeenAt: source.last_seen_at,
    };
  }

  const reporter = response.reporter;
  if (!reporter) throw new Error('Reporter identity is missing.');
  return {
    title: reporter.display_name || 'Persisted reporter',
    subtitle: reporter.identity_key || 'Persisted reporter',
    firstSeenAt: reporter.first_seen_at,
    lastSeenAt: reporter.last_seen_at,
  };
}

export function sourceReporterRelations(
  kind: SourceReporterKind,
  response: SourceReporterHistoryResponse,
): SourceReporterRelation[] {
  const relations: SourceReporterRelation[] = [];
  const add = (relation: SourceReporterRelation) => {
    if (
      relation.id &&
      !relations.some(
        (item) => item.kind === relation.kind && item.id === relation.id,
      )
    ) {
      relations.push(relation);
    }
  };

  for (const media of response.media || []) {
    add({
      kind: 'media',
      id: media.id,
      title: text(media.title) || `Media ${media.id}`,
      subtitle: text(media.mode),
    });
  }
  for (const story of response.stories || []) {
    add({
      kind: 'story',
      id: story.id,
      title: text(story.canonical_title) || `Story ${story.id}`,
      subtitle: text(story.status),
    });
  }
  for (const claim of response.claims || []) {
    const claimId = text(claim.claim_id) || claim.id;
    add({
      kind: 'claim',
      id: claimId,
      title: text(claim.canonical_text) || `Claim ${claimId}`,
      subtitle: text(claim.claim_type),
    });
  }

  if (kind === 'source') {
    for (const reporter of response.reporters || []) {
      add({
        kind: 'reporter',
        id: reporter.id,
        title: text(reporter.display_name) || `Reporter ${reporter.id}`,
        subtitle: text(reporter.identity_key),
      });
    }
  } else {
    for (const source of response.sources || []) {
      add({
        kind: 'source',
        id: source.id,
        title:
          text(source.display_name) ||
          text(source.canonical_domain) ||
          `Source ${source.id}`,
        subtitle: text(source.source_type),
      });
    }
  }

  return relations;
}

export function sourceReporterRoute(kind: IntelligenceKind, id: string) {
  return inspectableIntelligenceRoute(kind, id);
}

const POLICY_COPY: Record<string, string> = {
  chronology_is_not_truth:
    'Chronology records persisted activity; it is not a truth or credibility score.',
  reporting_volume_is_not_reliability:
    'Reporting volume is descriptive activity, not a reliability rating.',
  source_count_is_not_independence:
    'Multiple sources do not automatically represent independent corroboration.',
  dependency_is_not_falsehood:
    'A persisted dependency relationship does not mean the reporting is false.',
  absence_of_verified_independence_is_not_dependence:
    'Missing verified independence evidence is not evidence of dependence.',
  evidence_quantity_is_not_probability:
    'More evidence records do not automatically make a claim more likely to be true.',
};

export function sourceReporterPolicyNotes(policy: Record<string, boolean>) {
  return Object.entries(policy)
    .filter(([, enabled]) => enabled)
    .map(([key]) => POLICY_COPY[key] || key.replace(/_/g, ' '));
}

const DETAIL_FIELDS: Array<[string, string]> = [
  ['claim_summary', 'Observation'],
  ['observation_type', 'Observation type'],
  ['status', 'Status'],
  ['subject_key', 'Subject'],
  ['relationship_type', 'Relationship'],
  ['canonical_text', 'Claim'],
  ['verification_status', 'Verification status'],
  ['provenance_evidence_type', 'Independence provenance'],
  ['title', 'Media'],
  ['mode', 'Mode'],
];

export function sourceReporterEventDetails(event: SourceReporterHistoryEvent) {
  const result: Array<{ label: string; value: string }> = [];
  for (const [key, label] of DETAIL_FIELDS) {
    const value = event[key];
    if (typeof value === 'string' || typeof value === 'number') {
      const rendered = String(value).trim();
      if (rendered) result.push({ label, value: rendered });
    }
  }
  return result;
}
