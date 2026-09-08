export const AUTH_RETURN_DESTINATIONS = [
  '/',
  '/explore',
  '/watchlists',
  '/alerts',
  '/activity',
  '/notifications',
  '/settings',
] as const;

export const PROTECTED_WEB_DESTINATIONS = [
  '/watchlists',
  '/alerts',
  '/activity',
  '/notifications',
] as const;

export type AuthReturnDestination =
  (typeof AUTH_RETURN_DESTINATIONS)[number];

export type ProtectedWebDestination =
  (typeof PROTECTED_WEB_DESTINATIONS)[number];

const AUTH_RETURN_DESTINATION_SET = new Set<string>(
  AUTH_RETURN_DESTINATIONS,
);

export function allowlistedAuthDestination(
  candidate: string | null | undefined,
): AuthReturnDestination {
  const normalized = candidate?.trim() ?? '';

  return AUTH_RETURN_DESTINATION_SET.has(normalized)
    ? (normalized as AuthReturnDestination)
    : '/';
}

export function absoluteAuthDestination(
  destination: AuthReturnDestination,
): string {
  const safeDestination = allowlistedAuthDestination(destination);

  if (
    typeof window === 'undefined' ||
    !window.location?.origin
  ) {
    return safeDestination;
  }

  return new URL(
    safeDestination,
    window.location.origin,
  ).toString();
}
