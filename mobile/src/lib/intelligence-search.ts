import { SportabaseApiError } from './api';
import type { IntelligenceKind } from './intelligence-kinds';

const API_BASE_URL = 'https://sportabase-api.onrender.com';
const REQUEST_TIMEOUT_MS = 22000;

export type IntelligenceSearchResult = {
  kind: IntelligenceKind;
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

async function readErrorDetail(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    return '';
  }
}

export async function searchInspectableIntelligence(
  query: string,
  options: {
    limit?: number;
    cursor?: string;
    sportKey?: string;
  } = {},
): Promise<IntelligenceSearchResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS,
  );

  const params = [
    `q=${encodeURIComponent(query.trim())}`,
    'kind=entity',
    'kind=story',
    'kind=claim',
    'kind=media',
    'kind=source',
    'kind=reporter',
    `limit=${options.limit ?? 30}`,
  ];

  if (options.cursor) {
    params.push(`cursor=${encodeURIComponent(options.cursor)}`);
  }
  if (options.sportKey?.trim()) {
    params.push(
      `sport_key=${encodeURIComponent(options.sportKey.trim())}`,
    );
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}/intelligence/search?${params.join('&')}`,
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

    return (await response.json()) as IntelligenceSearchResponse;
  } catch (error) {
    if (error instanceof SportabaseApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === 'AbortError') {
      throw new SportabaseApiError('Sportabase intelligence search timed out.');
    }
    throw new SportabaseApiError(
      error instanceof Error
        ? error.message
        : 'Could not reach Sportabase intelligence search.',
    );
  } finally {
    clearTimeout(timeout);
  }
}
