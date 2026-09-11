export const ACCOUNT_IDENTITY_ERROR = 'The signed-in session did not provide a stable account/session identity.';

export type AccountSessionPlan =
  | { status: 'loading'; identity: '' }
  | { status: 'signed-out'; identity: '' }
  | { status: 'identity-error'; identity: ''; error: string }
  | { status: 'bootstrap'; identity: string; sessionId: string; key: string };

export function planAccountSession(
  isLoaded: boolean,
  isSignedIn: boolean | undefined,
  userId: string | null | undefined,
  sessionId: string | null | undefined,
): AccountSessionPlan {
  if (!isLoaded) return { status: 'loading', identity: '' };
  if (!isSignedIn) return { status: 'signed-out', identity: '' };
  if (!userId || !sessionId) return { status: 'identity-error', identity: '', error: ACCOUNT_IDENTITY_ERROR };
  return { status: 'bootstrap', identity: userId, sessionId, key: `${userId}:${sessionId}` };
}
