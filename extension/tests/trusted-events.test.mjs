import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { trustedUserAction } from '../src/content/trusted-events.mjs';

test('synthetic host-page events cannot invoke trusted extension actions', () => {
  const calls = [];
  const receiver = { name: 'control' };
  const handler = trustedUserAction(function (event, value) {
    calls.push([this, event.isTrusted, value]);
    return 'handled';
  });

  assert.equal(handler.call(receiver, { isTrusted: false }, 'synthetic'), undefined);
  assert.equal(handler.call(receiver, {}, 'missing'), undefined);
  assert.deepEqual(calls, []);
  assert.equal(handler.call(receiver, { isTrusted: true }, 'keyboard-or-pointer'), 'handled');
  assert.deepEqual(calls, [[receiver, true, 'keyboard-or-pointer']]);
});

test('every host-page action that can spend quota or mutate account state requires trust', async () => {
  const article = await readFile(new URL('../src/content/article-mode.js', import.meta.url), 'utf8');
  const video = await readFile(new URL('../src/content/video-mode.js', import.meta.url), 'utf8');
  const intelligence = await readFile(new URL('../src/content/persistent-intelligence.js', import.meta.url), 'utf8');
  const settings = await readFile(new URL('../src/ui/settings.js', import.meta.url), 'utf8');

  assert.equal((article.match(/trustedUserAction\(runAnalysis\)/g) || []).length, 3);
  assert.equal((video.match(/trustedUserAction\(runAnalysis\)/g) || []).length, 3);
  assert.match(intelligence, /data-sb-pi-watch[\s\S]*trustedUserAction\(\(\) => \{[\s\S]*addWatch\(\)/);
  assert.match(intelligence, /data-sb-pi-activity[\s\S]*trustedUserAction\(\(\) => \{[\s\S]*checkActivity\(\)/);
  assert.match(settings, /accountButton\.addEventListener\('click',trustedUserAction/);
});
