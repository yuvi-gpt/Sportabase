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
      throw new SportabaseApiError(
        `Sportabase API returned HTTP ${response.status}.`,
        response.status,
      );
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
