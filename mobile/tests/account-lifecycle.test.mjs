import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const [contextSource, sessionSource, resyncSource, accountGateSource, protectedGateSource, settingsSource] = await Promise.all([
  '../src/lib/account-context.tsx',
  '../src/lib/account-session.ts',
  '../src/lib/account-resync.ts',
  '../src/components/account-gate.tsx',
  '../src/product-ui/ProtectedWebDestination.tsx',
  '../src/app/settings.tsx',
].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));

function loadTypeScriptModule(source) {
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(compiled, { module, exports: module.exports });
  return module.exports;
}

test('signed-in account bootstrap uses the stable Clerk auth session and stays pending', () => {
  const { planAccountSession } = loadTypeScriptModule(sessionSource);
  assert.deepEqual(
    { ...planAccountSession(true, true, 'user_stable', 'sess_stable') },
    { status: 'bootstrap', identity: 'user_stable', sessionId: 'sess_stable', key: 'user_stable:sess_stable' },
  );
  assert.match(contextSource, /const \{ isLoaded, isSignedIn, userId, sessionId, getToken, signOut \} = useAuth\(\)/);
  assert.match(contextSource, /planAccountSession\(isLoaded, isSignedIn, userId, sessionId\)/);
  assert.doesNotMatch(contextSource, /isSignedIn \? user\?\.id/);
  const installToken = contextSource.indexOf('setTokenGetter(()=>getTokenRef.current())');
  const bootstrap = contextSource.indexOf('void refreshRef.current().catch', installToken);
  assert.ok(installToken >= 0 && bootstrap > installToken);
});

test('a Clerk account or session identity failure is terminal instead of loading forever', () => {
  const { planAccountSession, ACCOUNT_IDENTITY_ERROR } = loadTypeScriptModule(sessionSource);
  for (const [userId, sessionId] of [[null, 'sess'], ['user', null]]) {
    assert.deepEqual(
      { ...planAccountSession(true, true, userId, sessionId) },
      { status: 'identity-error', identity: '', error: ACCOUNT_IDENTITY_ERROR },
    );
  }
  assert.match(contextSource, /session\.status !== 'loading'\) setReady\(true\)/);
  assert.match(contextSource, /currentSession\.status === 'identity-error' \? currentSession\.error/);
});

test('all retry surfaces use the authoritative account refresh and clear local stale errors', () => {
  assert.match(accountGateSource, /setError\(''\); void \(account\.signedIn \? account\.refresh\(\)/);
  assert.match(protectedGateSource, /setMessage\(''\); if \(account\.signedIn\) void account\.refresh\(\)/);
  assert.match(settingsSource, /onPress=\{\(\) => void run\(account\.refresh\)\}/);
  assert.match(protectedGateSource, /if \(account\.ready && account\.signedIn && account\.state\) return children/);
  assert.match(accountGateSource, /if \(account\.ready && account\.signedIn && account\.state\) return children/);
  assert.match(contextSource, /acceptBootstrap\(next, expectedSessionKey\); setError\(''\)/);
});

test('account resync is single-flight for one session and rejects stale prior-session work', async () => {
  const { createAccountResyncCoordinator } = loadTypeScriptModule(resyncSource);
  const coordinator = createAccountResyncCoordinator();
  let calls = 0;
  let releaseCurrent;
  const blocked = new Promise((resolve) => { releaseCurrent = resolve; });
  const first = coordinator.run('user:sess', async () => { calls += 1; await blocked; return 'state'; });
  const duplicate = coordinator.run('user:sess', async () => { calls += 1; return 'duplicate'; });

  assert.strictEqual(first, duplicate);
  assert.equal(calls, 0);
  await Promise.resolve();
  assert.equal(calls, 1);
  releaseCurrent();
  assert.equal(await first, 'state');

  const applied = [];
  let releaseOld;
  const oldBlocked = new Promise((resolve) => { releaseOld = resolve; });
  const old = coordinator.run('old-user:old-session', async (isCurrent) => {
    await oldBlocked;
    if (isCurrent()) applied.push('old');
  });
  const current = coordinator.run('new-user:new-session', async (isCurrent) => {
    if (isCurrent()) applied.push('new');
  });
  await current;
  releaseOld();
  await old;
  assert.deepEqual(applied, ['new']);
});

test('returning from account management reconciles once across focus and visibility events', () => {
  const { createWebAccountReturnTracker } = loadTypeScriptModule(resyncSource);
  let reconciliations = 0;
  const tracker = createWebAccountReturnTracker(() => { reconciliations += 1; });

  tracker.beginAccountManagement();
  assert.equal(tracker.reconcileIfReturned(true), true);
  assert.equal(tracker.reconcileIfReturned(true), false);
  assert.equal(reconciliations, 1);

  tracker.markAway();
  assert.equal(tracker.reconcileIfReturned(false), false);
  assert.equal(tracker.reconcileIfReturned(true), true);
  assert.equal(tracker.reconcileIfReturned(true), false);
  assert.equal(reconciliations, 2);

  assert.match(contextSource, /window\.addEventListener\('focus',reconcile\)/);
  assert.match(contextSource, /document\.addEventListener\('visibilitychange',visibility\)/);
  assert.match(contextSource, /window\.addEventListener\('pageshow',reconcile\)/);
  assert.doesNotMatch(contextSource, /setInterval/);
});

test('signed-out transitions cancel pending web reconciliation and never bootstrap', () => {
  const { createWebAccountReturnTracker } = loadTypeScriptModule(resyncSource);
  let reconciliations = 0;
  const tracker = createWebAccountReturnTracker(() => { reconciliations += 1; });
  tracker.beginAccountManagement(); tracker.markAway(); tracker.reset();
  assert.equal(tracker.reconcileIfReturned(true), false);
  assert.equal(reconciliations, 0);
  assert.match(contextSource, /if\(sessionRef\.current\.status === 'bootstrap'\) void refreshRef\.current\(\)/);
});

test('a usable matching account state stays available during background resync', () => {
  assert.match(contextSource, /const hasUsableState = stateSessionKey\.current === expectedSessionKey/);
  assert.match(contextSource, /if\(!hasUsableState\) setReady\(false\)/);
  const refreshStart = contextSource.indexOf('async function refresh()');
  const refreshEnd = contextSource.indexOf('refreshRef.current = refresh;');
  assert.doesNotMatch(contextSource.slice(refreshStart, refreshEnd), /setState\(null\)/);
});

test('mobile attempts legacy migration once and persists every current terminal outcome', () => {
  assert.match(contextSource, /!complete\?\{legacy_client_id:legacyClientId\}/);
  assert.match(contextSource, /status\s*!==\s*'not_requested'/);
  assert.match(contextSource, /AsyncStorage\.setItem\(LEGACY_MIGRATION_KEY,'complete'\)/);
});

test('mobile revokes current-device backend push ownership before Clerk sign-out', () => {
  const revoke = contextSource.indexOf("accountRequest('/account/device/sign-out','POST')");
  const clear = contextSource.indexOf('clearPushRegistrationAfterBackendRevocation()');
  const signOut = contextSource.indexOf('await signOut();');
  assert.ok(revoke >= 0 && clear > revoke && signOut > clear);
});

test('account/session changes hide old state and late bootstrap responses cannot populate them', () => {
  assert.match(contextSource, /accountSessionKey\.current !== expectedSessionKey/);
  assert.match(contextSource, /stateSessionKey\.current === session\.key \? state : null/);
  assert.match(contextSource, /resync\.run\(expectedSessionKey/);
  assert.match(contextSource, /resync\.invalidate\(\)/);
  assert.match(contextSource, /next\.account\.id !== currentAccountId\.current/);
  assert.match(contextSource, /currentAccountId\.current = ''/);
});
