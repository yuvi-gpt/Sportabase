import { getSportabaseClientId } from './client-identity';

const API_BASE_URL =
  'https://sportabase-api.onrender.com';

const REQUEST_TIMEOUT_MS = 22000;
const ANALYSIS_TIMEOUT_MS = 60000;

export type ApiHealthResponse = {
  ok: boolean;
  version: string;
};

export type ContentResolveResponse = {
  url: string;
  normalized_url: string;
  source: 'article' | 'youtube';
  mode: 'article' | 'video';
  title: string;
  content: string;
  content_characters: number;
  metadata: Record<string, unknown>;
};

export type ArticleAnalyzeRequest = {
  title: string;
  url: string;
  text: string;
  max_bullets?: number;
};

export type ArticleIntelligencePublic = {
  version: string;
  status: string;
  label: string;
  detail: string;
  signal: string;
  candidate_count: number;
  verification_pairs: number;
  corroboration_status: string;
  independence_status: string;
  contested: boolean;
  provisional: boolean;
  affects_merit_score: boolean;
};

export type ArticleAnalyzeResponse = {
  url: string;
  title: string;
  tldr: string[];
  merit_score: number;
  badge: string;

  article_type: string;
  article_type_label: string;
  article_subtype: string;
  type_confidence: number;
  type_signals: string[];

  reasons: string[];

  score_components: Record<string, number>;
  score_calculation: Record<string, unknown>;

  language: Record<string, unknown>;
  localized_article_type: string;
  localized_reasons: string[];
  ui_labels: Record<string, string>;

  /*
   * Optional keeps local development fixtures and
   * previously persisted responses backwards-compatible.
   * Current backend responses provide this field.
   */
  intelligence?: ArticleIntelligencePublic;

  debug: Record<string, unknown>;
};

export type VideoAnalyzeRequest = {
  title: string;
  transcript: string;
  url: string;
  transcript_metadata: {
    segment_count: number;
    character_count: number;
    language?: string;
    extraction_method: string;
  };
};

export type VideoAnalyzeResponse = {
  content_type: string;
  claim: string;
  evidence_used: string[];
  logic_check: string;
  hype_check: string;
  evidence_score: number;
  logic_score: number;
  verdict: string;

  language: Record<string, unknown>;
  localized_content_type: string;
  localized_verdict: string;
  ui_labels: Record<string, string>;
  debug: Record<string, unknown>;
};

export type WatchTargetKind =
  | 'entity'
  | 'story'
  | 'claim'
  | 'media';

export type IntelligenceSearchResult = {
  kind: WatchTargetKind;
  id: string;
  title: string;
  subtitle?: string;
  matched_field: string;
  match_type: string;
  first_seen_at: string;
  last_seen_at: string;
  sport_key?: string;
  canonical_url?: string;
  source_type?: string;
};

export type IntelligenceSearchResponse = {
  version: string;
  query: string;
  results: IntelligenceSearchResult[];
  pagination: {
    limit: number;
    next_cursor: string | null;
  };
};

export type WatchItem = {
  id: string;
  target_kind: WatchTargetKind;
  target_id: string;
  target_label: string;
  created_at: string;
  last_reconciled_at: string | null;
};

export type WatchListResponse = {
  version: string;
  items: WatchItem[];
  count: number;
  limit: number;
};

export type WatchCreateResponse = {
  watch: WatchItem;
  created: boolean;
};

export type AlertItem = {
  id: string;
  target_kind: WatchTargetKind;
  target_id: string;
  event_type: string;
  related_kind: string | null;
  related_id: string | null;
  summary: string;
  occurred_at: string;
  detected_at: string;
  read_at: string | null;
};

export type AlertListResponse = {
  version: string;
  items: AlertItem[];
  pagination: {
    limit: number;
    next_cursor: string | null;
  };
};

export type AlertReconcileResponse = {
  watches_checked: number;
  new_alerts: number;
  unchanged_watches: number;
};

export class SportabaseApiError extends Error {
  status: number | null;

  constructor(
    message: string,
    status: number | null = null,
  ) {
    super(message);
    this.name = 'SportabaseApiError';
    this.status = status;
  }
}

async function readErrorDetail(
  response: Response,
): Promise<string> {
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

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();

  const timeout = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(
      `${API_BASE_URL}${path}`,
      {
        ...init,
        headers: {
          Accept: 'application/json',
          ...init.headers,
        },
        signal: controller.signal,
      },
    );

    if (!response.ok) {
      const detail = await readErrorDetail(response);

      throw new SportabaseApiError(
        detail ||
          `Sportabase API returned HTTP ${response.status}.`,
        response.status,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof SportabaseApiError) {
      throw error;
    }

    if (
      error instanceof Error &&
      error.name === 'AbortError'
    ) {
      throw new SportabaseApiError(
        'Sportabase API request timed out.',
      );
    }

    throw new SportabaseApiError(
      error instanceof Error
        ? error.message
        : 'Could not reach the Sportabase API.',
    );
  } finally {
    clearTimeout(timeout);
  }
}

async function requestPrivateJson<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const clientId = await getSportabaseClientId();

  return requestJson<T>(
    path,
    {
      ...init,
      headers: {
        ...init.headers,
        'x-sportabase-client-id': clientId,
      },
    },
    timeoutMs,
  );
}

export function getApiHealth() {
  return requestJson<ApiHealthResponse>('/health');
}

export function resolveContent(
  url: string,
) {
  return requestJson<ContentResolveResponse>(
    '/resolve-content',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url }),
    },
  );
}

export function analyzeArticle(
  request: ArticleAnalyzeRequest,
) {
  return requestJson<ArticleAnalyzeResponse>(
    '/analyze',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    },
    ANALYSIS_TIMEOUT_MS,
  );
}

export function analyzeVideo(
  request: VideoAnalyzeRequest,
) {
  return requestJson<VideoAnalyzeResponse>(
    '/analyze/video',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    },
    ANALYSIS_TIMEOUT_MS,
  );
}

export function searchIntelligence(
  query: string,
  options: {
    limit?: number;
    cursor?: string;
    sportKey?: string;
  } = {},
) {
  const params = [
    `q=${encodeURIComponent(query.trim())}`,
    'kind=entity',
    'kind=story',
    'kind=claim',
    'kind=media',
    `limit=${options.limit ?? 30}`,
  ];

  if (options.cursor) {
    params.push(
      `cursor=${encodeURIComponent(options.cursor)}`,
    );
  }

  if (options.sportKey?.trim()) {
    params.push(
      `sport_key=${encodeURIComponent(
        options.sportKey.trim(),
      )}`,
    );
  }

  return requestJson<IntelligenceSearchResponse>(
    `/intelligence/search?${params.join('&')}`,
  );
}

export function listWatches() {
  return requestPrivateJson<WatchListResponse>(
    '/watchlists',
  );
}

export function createWatch(
  targetKind: WatchTargetKind,
  targetId: string,
) {
  return requestPrivateJson<WatchCreateResponse>(
    '/watchlists',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        target_kind: targetKind,
        target_id: targetId,
      }),
    },
  );
}

export function deleteWatch(watchId: string) {
  return requestPrivateJson<void>(
    `/watchlists/${encodeURIComponent(watchId)}`,
    {
      method: 'DELETE',
    },
  );
}

export function reconcileAlerts() {
  return requestPrivateJson<AlertReconcileResponse>(
    '/watchlists/alerts/reconcile',
    {
      method: 'POST',
    },
  );
}

export function listAlerts(
  options: {
    unreadOnly?: boolean;
    targetKind?: WatchTargetKind | '';
    limit?: number;
    cursor?: string;
  } = {},
) {
  const params = [
    `unread_only=${options.unreadOnly ? 'true' : 'false'}`,
    `limit=${options.limit ?? 50}`,
  ];

  if (options.targetKind) {
    params.push(
      `target_kind=${encodeURIComponent(
        options.targetKind,
      )}`,
    );
  }

  if (options.cursor) {
    params.push(
      `cursor=${encodeURIComponent(options.cursor)}`,
    );
  }

  return requestPrivateJson<AlertListResponse>(
    `/watchlists/alerts?${params.join('&')}`,
  );
}

export function markAlertRead(alertId: string) {
  return requestPrivateJson<AlertItem>(
    `/watchlists/alerts/${encodeURIComponent(
      alertId,
    )}/read`,
    {
      method: 'POST',
    },
  );
}
