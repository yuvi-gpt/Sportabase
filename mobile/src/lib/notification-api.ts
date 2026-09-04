import { SportabaseApiError } from './api';
import { getSportabaseClientId } from './client-identity';

const API_BASE_URL = 'https://sportabase-api.onrender.com';
const REQUEST_TIMEOUT_MS = 22000;

export type NotificationPlatform = 'ios' | 'android';

export type NotificationDevice = {
  id: string;
  provider: 'expo';
  platform: NotificationPlatform;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type NotificationDeviceListResponse = {
  version: string;
  items: NotificationDevice[];
  count: number;
  limit: number;
};

export type NotificationDeviceCreateResponse = {
  version: string;
  device: NotificationDevice;
  registered: boolean;
};

async function readErrorDetail(response: Response) {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    return typeof payload.detail === 'string' ? payload.detail : '';
  } catch {
    return '';
  }
}

async function privateRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const clientId = await getSportabaseClientId();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...init.headers,
        'x-sportabase-client-id': clientId,
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await readErrorDetail(response);
      throw new SportabaseApiError(
        detail || `Sportabase API returned HTTP ${response.status}.`,
        response.status,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof SportabaseApiError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new SportabaseApiError('Sportabase notification request timed out.');
    }
    throw new SportabaseApiError(
      error instanceof Error
        ? error.message
        : 'Could not reach Sportabase notification services.',
    );
  } finally {
    clearTimeout(timeout);
  }
}

export function listNotificationDevices() {
  return privateRequest<NotificationDeviceListResponse>(
    '/notifications/devices',
  );
}

export function registerNotificationDevice(
  pushToken: string,
  platform: NotificationPlatform,
) {
  return privateRequest<NotificationDeviceCreateResponse>(
    '/notifications/devices',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        push_token: pushToken,
        platform,
      }),
    },
  );
}

export function unregisterNotificationDevice(deviceId: string) {
  return privateRequest<void>(
    `/notifications/devices/${encodeURIComponent(deviceId)}`,
    { method: 'DELETE' },
  );
}
