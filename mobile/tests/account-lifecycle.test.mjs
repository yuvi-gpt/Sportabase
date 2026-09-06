import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const contextSource = await readFile(new URL('../src/lib/account-context.tsx', import.meta.url), 'utf8');

test('mobile attempts legacy migration once and persists every terminal outcome', () => {
  assert.match(contextSource, /complete\s*\?\s*\{\s*legacy_client_id/);
  assert.match(contextSource, /status\s*!==\s*'not_requested'/);
  assert.match(contextSource, /AsyncStorage\.setItem\(LEGACY_MIGRATION_KEY,'complete'\)/);
});

test('mobile revokes current-device backend push ownership before Clerk sign-out', () => {
  const revoke = contextSource.indexOf("accountRequest('/account/device/sign-out','POST')");
  const clear = contextSource.indexOf('clearPushRegistrationAfterBackendRevocation()');
  const signOut = contextSource.indexOf('await signOut();');
  assert.ok(revoke >= 0 && clear > revoke && signOut > clear);
});

test('mobile discards a late bootstrap response after the signed-in account changes', () => {
  assert.match(contextSource, /const accountIdentity = useRef\(''\)/);
  assert.match(contextSource, /const refreshEpoch = useRef\(0\)/);
  assert.match(contextSource, /epoch === refreshEpoch\.current/);
  assert.match(contextSource, /accountIdentity\.current === expectedIdentity/);
  const staleGuard = contextSource.indexOf('if(!isCurrent()) return;');
  const accept = contextSource.indexOf('accept(next);');
  assert.ok(staleGuard >= 0 && accept > staleGuard);
});
