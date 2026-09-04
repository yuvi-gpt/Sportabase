import {
  SportabaseApiError,
  type WatchTargetKind,
} from './api';

const API_BASE_URL = 'https://sportabase-api.onrender.com';
const REQUEST_TIMEOUT_MS = 22000;

export type IntelligenceHistoryEvent = {
  type: string;
  occurred_at: string;
  id?: string;
  [key: string]: unknown;
};

export type IntelligenceIdentity = {
  title: string;
  subtitle: string;
  firstSeenAt: string;
  lastSeenAt: string;
  canonicalUrl?: string;
};

export type IntelligenceRelation = {
  kind: WatchTargetKind;
  id: string;
  title: string;
  subtitle?: string;
};

type HistoryPage = {
  version: string;
  events: IntelligenceHistoryEvent[];
  pagination: {
    limit: number;
    next_cursor: string | null;
  };
  policy: Record<string, boolean>;
};

type EntityIdentity = {
  id: string;
  entity_key: string;
  entity_type: string;
  sport_key: string;
  canonical_name: string;
  first_seen_at: string;
  last_seen_at: string;
  aliases?: Array<{
    alias_text: string;
    alias_type: string;
    first_seen_at: string;
    last_seen_at: string;
  }>;
};

type StoryIdentity = {
  id: string;
  canonical_key: string;
  canonical_title: string;
  status: string;
  first_seen_at: string;
  last_seen_at: string;
};

type ClaimIdentity = {
  id: string;
  canonical_key: string;
  subject_key: string;
  canonical_text: string;
  claim_type: string;
  first_seen_at: string;
  last_seen_at: string;
};

type MediaIdentity = {
  id: string;
  canonical_url: string;
  mode: string;
  source_id: string | null;
  reporter_id: string | null;
  title: string;
  published_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

type RelatedRecord = {
  id: string;
  canonical_title?: string;
  canonical_text?: string;
  title?: string;
  status?: string;
  subject_key?: string;
  claim_type?: string;
  mode?: string;
  canonical_url?: string;
  entity_id?: string;
  canonical_name?: string;
  entity_type?: string;
  sport_key?: string;
  [key: string]: unknown;
};

export type EntityHistoryResponse = HistoryPage & {
  entity: EntityIdentity;
  claims: string[];
  stories: RelatedRecord[];
  media: RelatedRecord[];
};

export type StoryHistoryResponse = HistoryPage & {
  story: StoryIdentity;
  claims: RelatedRecord[];
  media: RelatedRecord[];
};

export type ClaimHistoryResponse = HistoryPage & {
  claim: ClaimIdentity;
  stories: RelatedRecord[];
  verified_participants: RelatedRecord[];
};

export type MediaHistoryResponse = HistoryPage & {
  media: MediaIdentity;
};

export type IntelligenceHistoryResponse =
  | EntityHistoryResponse
  | StoryHistoryResponse
  | ClaimHistoryResponse
  | MediaHistoryResponse;

const HISTORY_PATHS: Record<WatchTargetKind, string> = {
  entity: 'entities',
  story: 'stories',
  claim: 'claims',
  media: 'media',
};

export function isWatchTargetKind(
  value: string | undefined,
): value is WatchTargetKind {
  return (
    value === 'entity' ||
    value === 'story' ||
    value === 'claim' ||
    value === 'media'
  );
}

export function intelligenceRoute(
  kind: WatchTargetKind,
  id: string,
) {
  return {
    pathname: '/intelligence' as const,
    params: { kind, id },
  };
}

async function readErrorDetail(response: Response) {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
    };

    return typeof payload.detail === 'string'
      ? payload.detail
      : '';
  } catch {
    return '';
  }
}

export async function getIntelligenceHistory(
  kind: WatchTargetKind,
  id: string,
  options: {
    limit?: number;
    cursor?: string;
  } = {},
): Promise<IntelligenceHistoryResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS,
  );

  const params = [`limit=${options.limit ?? 50}`];
  if (options.cursor) {
    params.push(
      `cursor=${encodeURIComponent(options.cursor)}`,
    );
  }

  const path =
    `/intelligence/${HISTORY_PATHS[kind]}/` +
    `${encodeURIComponent(id)}/history?${params.join('&')}`;

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new SportabaseApiError(
        detail ||
          `Sportabase API returned HTTP ${response.status}.`,
        response.status,
      );
    }

    return (await response.json()) as IntelligenceHistoryResponse;
  } catch (error) {
    if (error instanceof SportabaseApiError) {
      throw error;
    }

    if (
      error instanceof Error &&
      error.name === 'AbortError'
    ) {
      throw new SportabaseApiError(
        'Sportabase intelligence history request timed out.',
      );
    }

    throw new SportabaseApiError(
      error instanceof Error
        ? error.message
        : 'Could not reach Sportabase intelligence history.',
    );
  } finally {
    clearTimeout(timeout);
  }
}

export function intelligenceIdentity(
  kind: WatchTargetKind,
  response: IntelligenceHistoryResponse,
): IntelligenceIdentity {
  if (kind === 'entity') {
    const entity = (response as EntityHistoryResponse).entity;
    return {
      title: entity.canonical_name,
      subtitle: [entity.entity_type, entity.sport_key]
        .filter(Boolean)
        .join(' · '),
      firstSeenAt: entity.first_seen_at,
      lastSeenAt: entity.last_seen_at,
    };
  }

  if (kind === 'story') {
    const story = (response as StoryHistoryResponse).story;
    return {
      title: story.canonical_title,
      subtitle: story.status || 'Persisted story',
      firstSeenAt: story.first_seen_at,
      lastSeenAt: story.last_seen_at,
    };
  }

  if (kind === 'claim') {
    const claim = (response as ClaimHistoryResponse).claim;
    return {
      title: claim.canonical_text,
      subtitle: [claim.claim_type, claim.subject_key]
        .filter(Boolean)
        .join(' · '),
      firstSeenAt: claim.first_seen_at,
      lastSeenAt: claim.last_seen_at,
    };
  }

  const media = (response as MediaHistoryResponse).media;
  return {
    title: media.title || 'Untitled media',
    subtitle: media.mode || 'Persisted media',
    firstSeenAt: media.first_seen_at,
    lastSeenAt: media.last_seen_at,
    canonicalUrl: media.canonical_url,
  };
}

function text(value: unknown) {
  return typeof value === 'string' ? value : '';
}

export function intelligenceRelations(
  kind: WatchTargetKind,
  response: IntelligenceHistoryResponse,
): IntelligenceRelation[] {
  const relations: IntelligenceRelation[] = [];

  const add = (relation: IntelligenceRelation) => {
    if (
      relation.id &&
      !relations.some(
        (item) =>
          item.kind === relation.kind &&
          item.id === relation.id,
      )
    ) {
      relations.push(relation);
    }
  };

  if (kind === 'entity') {
    const data = response as EntityHistoryResponse;

    for (const story of data.stories) {
      add({
        kind: 'story',
        id: story.id,
        title:
          text(story.canonical_title) ||
          `Story ${story.id}`,
        subtitle: text(story.status),
      });
    }

    for (const media of data.media) {
      add({
        kind: 'media',
        id: media.id,
        title: text(media.title) || `Media ${media.id}`,
        subtitle: text(media.mode),
      });
    }

    for (const event of data.events) {
      const claimId = text(event.claim_id);
      if (claimId) {
        add({
          kind: 'claim',
          id: claimId,
          title:
            text(event.claim_text) || `Claim ${claimId}`,
        });
      }
    }
  }

  if (kind === 'story') {
    const data = response as StoryHistoryResponse;

    for (const claim of data.claims) {
      add({
        kind: 'claim',
        id: claim.id,
        title:
          text(claim.canonical_text) ||
          `Claim ${claim.id}`,
        subtitle: text(claim.claim_type),
      });
    }

    for (const media of data.media) {
      add({
        kind: 'media',
        id: media.id,
        title: text(media.title) || `Media ${media.id}`,
        subtitle: text(media.mode),
      });
    }
  }

  if (kind === 'claim') {
    const data = response as ClaimHistoryResponse;

    for (const story of data.stories) {
      add({
        kind: 'story',
        id: story.id,
        title:
          text(story.canonical_title) ||
          `Story ${story.id}`,
        subtitle: text(story.status),
      });
    }

    for (const participant of data.verified_participants) {
      const entityId = text(participant.entity_id);
      if (entityId) {
        add({
          kind: 'entity',
          id: entityId,
          title:
            text(participant.canonical_name) ||
            `Entity ${entityId}`,
          subtitle: text(participant.entity_type),
        });
      }
    }
  }

  if (kind === 'media') {
    const data = response as MediaHistoryResponse;

    for (const event of data.events) {
      const storyId = text(event.story_id);
      if (storyId) {
        add({
          kind: 'story',
          id: storyId,
          title: `Story ${storyId}`,
        });
      }
    }
  }

  return relations;
}

const POLICY_COPY: Record<string, string> = {
  verified_relationships_only:
    'Entity relationships shown here come from verified persisted relationships.',
  chronology_is_not_truth:
    'Chronology records when intelligence occurred; it is not a truth or credibility score.',
  relationships_are_persisted:
    'Story relationships shown here are persisted graph relationships, not temporary text matches.',
  evidence_quantity_is_not_probability:
    'More evidence records do not automatically mean a claim is more likely to be true.',
  dependencies_remain_distinct:
    'Repeated or dependent reporting remains distinct from independent corroboration.',
  article_merit_is_reporting_quality_not_truth:
    'Article Merit measures reporting and informational quality, not truth probability.',
  video_scores_are_not_combined:
    'Video Evidence Score, Logic Score and Verdict remain separate; there is no composite credibility score.',
  versions_are_not_assumed_comparable:
    'Analysis versions are not assumed to be directly comparable across time.',
};

export function intelligencePolicyNotes(
  policy: Record<string, boolean>,
) {
  return Object.entries(policy)
    .filter(([, enabled]) => enabled)
    .map(
      ([key]) =>
        POLICY_COPY[key] || key.replace(/_/g, ' '),
    );
}

const DETAIL_FIELDS: Array<[string, string]> = [
  ['claim_text', 'Claim'],
  ['canonical_name', 'Entity'],
  ['participant_role', 'Participant role'],
  ['verification_status', 'Verification status'],
  ['relationship_type', 'Relationship'],
  ['link_basis', 'Link basis'],
  ['claim_summary', 'Observation'],
  ['trigger_type', 'Revision trigger'],
  ['field', 'Field'],
  ['kind', 'Transition'],
  ['mode', 'Mode'],
  ['badge', 'Article badge'],
  ['article_type', 'Article type'],
  ['merit_score', 'Merit · reporting quality'],
  ['evidence_score', 'Video evidence score'],
  ['logic_score', 'Video logic score'],
  ['verdict', 'Video verdict'],
  ['analysis_version', 'Analysis version'],
  ['scoring_version', 'Scoring version'],
];

export function intelligenceEventDetails(
  event: IntelligenceHistoryEvent,
) {
  const pairs: Array<{ label: string; value: string }> = [];

  for (const [key, label] of DETAIL_FIELDS) {
    const value = event[key];
    if (
      typeof value === 'string' ||
      typeof value === 'number'
    ) {
      const rendered = String(value).trim();
      if (rendered) {
        pairs.push({ label, value: rendered });
      }
    }
  }

  if (Array.isArray(event.reasons)) {
    const reasons = event.reasons
      .filter((value): value is string =>
        typeof value === 'string',
      )
      .join(' · ');
    if (reasons) {
      pairs.push({ label: 'Reasons', value: reasons });
    }
  }

  return pairs;
}
