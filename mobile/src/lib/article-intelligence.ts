import type {
  ArticleIntelligencePublic,
} from './api';


export const ARTICLE_INTELLIGENCE_PUBLIC_VERSION =
  'article-intelligence-public-v1';


export type NormalizedArticleIntelligence = {
  status: 'available' | 'unavailable';
  label: string;
  detail: string;
  candidateCount: number;
  verificationPairs: number;
  corroborationStatus: string;
  corroborationLabel: string;
  independenceStatus: string;
  independenceLabel: string;
  contested: boolean;
  provisional: boolean;
  affectsMeritScore: boolean;
};


function clean(
  value: unknown,
) {
  return String(
    value ?? '',
  )
    .trim()
    .replace(/\s+/g, ' ');
}


function count(
  value: unknown,
) {
  const numeric = Number(
    value,
  );

  if (!Number.isFinite(numeric)) {
    return 0;
  }

  return Math.max(
    0,
    Math.trunc(numeric),
  );
}


function humanize(
  value: unknown,
) {
  const normalized = clean(
    value,
  )
    .replace(/[_-]+/g, ' ');

  if (!normalized) {
    return 'Unknown';
  }

  return normalized.replace(
    /\b\w/g,
    (character) =>
      character.toUpperCase(),
  );
}


export function normalizeArticleIntelligence(
  value:
    | ArticleIntelligencePublic
    | undefined
    | null,
): NormalizedArticleIntelligence | null {
  if (
    !value ||
    typeof value !== 'object'
  ) {
    return null;
  }

  if (
    clean(value.version) !==
    ARTICLE_INTELLIGENCE_PUBLIC_VERSION
  ) {
    return null;
  }

  const status =
    clean(
      value.status,
    ).toLowerCase();

  if (
    status !== 'available' &&
    status !== 'unavailable'
  ) {
    return null;
  }

  const independenceStatus =
    clean(
      value.independence_status,
    ).toLowerCase() ||
    'unknown';

  const corroborationStatus =
    clean(
      value.corroboration_status,
    ).toLowerCase() ||
    'unknown';

  return {
    status,

    label:
      clean(
        value.label,
      ) ||
      (
        status === 'available'
          ? 'Evidence intelligence'
          : 'Evidence check unavailable'
      ),

    detail:
      clean(
        value.detail,
      ),

    candidateCount:
      count(
        value.candidate_count,
      ),

    verificationPairs:
      count(
        value.verification_pairs,
      ),

    corroborationStatus,

    corroborationLabel:
      humanize(
        corroborationStatus,
      ),

    independenceStatus,

    independenceLabel:
      humanize(
        independenceStatus,
      ),

    contested:
      Boolean(
        value.contested,
      ),

    provisional:
      value.provisional !== false,

    affectsMeritScore:
      value.affects_merit_score === true,
  };
}
