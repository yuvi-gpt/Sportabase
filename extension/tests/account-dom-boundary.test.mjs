import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('host-page settings DOM contains no privileged account mutation controls', async () => {
  const overlay = await readFile(new URL('../src/ui/settings.js', import.meta.url), 'utf8');
  const extensionPage = await readFile(new URL('../src/extension-page/account-settings-page.js', import.meta.url), 'utf8');
  assert.equal(overlay.includes('installAccountSettings'), false);
  assert.equal(overlay.includes('SPORTABASE_ACCOUNT_UPDATE'), false);
  assert.equal(overlay.includes('SPORTABASE_SIGN_OUT'), false);
  assert.match(overlay, /SPORTABASE_OPEN_EXTENSION_SETTINGS/);
  assert.match(extensionPage, /installAccountSettings/);
});
