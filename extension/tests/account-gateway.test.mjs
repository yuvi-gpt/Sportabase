import test from 'node:test';
import assert from 'node:assert/strict';

import { createAccountGateway, localPreferences, presentationPreferences, validateApiMessage, validExtensionPageSender, validSender } from '../src/background/account-gateway.mjs';

const sender = { id: 'extension-id', tab: { id: 7 }, frameId: 0, url: 'https://example.com/story' };
const extensionSender = { id: 'extension-id', url: 'chrome-extension://extension-id/settings.html' };

test('gateway accepts only the top-level extension content script and allowlisted operations', () => {
  assert.equal(validSender(sender, 'extension-id'), true);
  for (const changed of [
    { ...sender, id: 'other' },
    { ...sender, frameId: 1 },
    { ...sender, url: 'chrome-extension://extension-id/page.html' },
    { id: 'extension-id', frameId: 0, url: 'https://example.com/' },
  ]) assert.equal(validSender(changed, 'extension-id'), false);
  assert.equal(validExtensionPageSender(extensionSender, 'extension-id', extensionSender.url), true);
  assert.equal(validExtensionPageSender(sender, 'extension-id', extensionSender.url), false);

  assert.equal(validateApiMessage({ type: 'SPORTABASE_API_REQUEST', requestId: 'one', method: 'POST', path: '/analyze', body: { url: 'https://example.com/' } }).path, '/analyze');
  for (const path of ['/account/export', '/admin/product-analytics', '/https://attacker.test', '/watchlists/../../account']) {
    assert.throws(() => validateApiMessage({ type: 'SPORTABASE_API_REQUEST', requestId: 'one', method: 'GET', path }), /Unsupported/);
  }
  assert.throws(() => validateApiMessage({ type: 'SPORTABASE_API_REQUEST', requestId: 'one', method: 'GET', path: '/watchlists', token: 'secret' }), /Invalid request/);
});

test('presentation cache maps only shared display values and never extension geometry', () => {
  assert.deepEqual(presentationPreferences({appearance:'dark',contrast:'high',analysis_detail:'essential',panel_size:'large'}), {
    sportabaseAppearance:'dark',sportabaseHighContrast:true,sportabaseDetailLevel:'essential',
  });
  assert.equal(Object.hasOwn(presentationPreferences({appearance:'light'}),'sportabaseLeft'),false);
});

test('overlay preference writes reject arbitrary storage keys and complex values', () => {
  assert.deepEqual(localPreferences({ sportabaseAppearance: 'dark', sportabaseCustomWidth: 520 }), { sportabaseAppearance: 'dark', sportabaseCustomWidth: 520 });
  assert.throws(() => localPreferences({ clerkToken: 'secret' }), /Unsupported/);
  assert.throws(() => localPreferences({ sportabaseAppearance: { nested: true } }), /Invalid/);
});

test('service worker mediates bearer tokens without returning them to content scripts', async () => {
  const saved = {};
  const calls = [];
  let created = 0;
  const chrome = {
    runtime: { id: 'extension-id', getURL(path) { return `chrome-extension://extension-id/${path}`; } },
    storage: { local: {
      async get(key) { return key === 'sportabaseClientId' ? { sportabaseClientId: 'legacy-installation-capability' } : { [key]: saved[key] }; },
      async set(value) { Object.assign(saved, value); },
    } },
    tabs: { async create() {} },
  };
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { status: 200, async text() { return JSON.stringify(url.endsWith('/account/bootstrap') ? {
      account: { id: 'acct' }, effective: {appearance:'dark'}, legacy_migration:{status:'claimed'},
    } : { items: [] }); } };
  };
  const gateway = createAccountGateway({
    chrome,
    config: { publishableKey: 'pk_test_local', syncHost: 'https://app.example.test', apiBase: 'https://api.example.test' },
    createClient: async () => { created += 1; return { session: { getToken: async () => 'jwt-private' }, signOut: async () => {} }; },
    fetchImpl,
  });

  const response = await gateway.handle({ type: 'SPORTABASE_API_REQUEST', requestId: 'request-1', method: 'GET', path: '/watchlists' }, sender);
  assert.equal(response.ok, true);
  assert.equal(JSON.stringify(response).includes('jwt-private'), false);
  assert.equal(calls.at(-1).options.headers.Authorization, 'Bearer jwt-private');
  assert.match(calls[0].options.body, /legacy_client_id/);
  await gateway.handle({ type: 'SPORTABASE_ACCOUNT_STATE' }, extensionSender);
  assert.equal(created, 1, 'one Clerk client is retained by the service worker gateway');
  assert.equal(calls.filter(call=>call.url.endsWith('/account/bootstrap')).length,2);
  assert.doesNotMatch(calls.filter(call=>call.url.endsWith('/account/bootstrap')).at(-1).options.body,/legacy_client_id/);
  assert.equal(saved.sportabaseAppearance,'dark');
  await assert.rejects(() => gateway.handle({ type: 'SPORTABASE_API_REQUEST', requestId: 'bad', method: 'GET', path: '/account/export' }, sender), /Unsupported/);
  await assert.rejects(() => gateway.handle({ type: 'SPORTABASE_ACCOUNT_UPDATE', body: {} }, sender), /Unsupported/);
  await assert.rejects(() => gateway.handle({ type: 'SPORTABASE_SIGN_OUT' }, sender), /Unsupported/);
  await assert.rejects(() => gateway.handle({ type: 'SPORTABASE_ACCOUNT_STATE' }, { ...extensionSender, id: 'attacker' }), /Untrusted/);
});

test('extension sign-out revokes the backend device before ending Clerk session', async () => {
  const order=[];
  const chrome={runtime:{id:'extension-id',getURL:path=>`chrome-extension://extension-id/${path}`},
    storage:{local:{async get(){return{}},async set(){}}},tabs:{async create(){}}};
  const gateway=createAccountGateway({chrome,config:{publishableKey:'pk_test_local',syncHost:'https://app.example.test',apiBase:'https://api.example.test'},
    createClient:async()=>({session:{id:'session',getToken:async()=> 'token'},signOut:async()=>order.push('clerk')}),
    fetchImpl:async url=>{order.push(new URL(url).pathname);return{status:200,async text(){return '{}'}};}});
  assert.deepEqual(await gateway.handle({type:'SPORTABASE_SIGN_OUT'},extensionSender),{ok:true});
  assert.deepEqual(order,['/account/device/sign-out','clerk']);
});
