import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const api = await readFile(new URL('../src/lib/api.ts', import.meta.url), 'utf8');

test('content resolution has a dedicated longer timeout while generic requests stay unchanged', () => {
  assert.match(api, /const REQUEST_TIMEOUT_MS = 22000;/);
  assert.match(api, /const CONTENT_RESOLVE_TIMEOUT_MS = 60000;/);
  assert.match(api, /const ANALYSIS_TIMEOUT_MS = 60000;/);
  assert.match(api, /timeoutMs: number = REQUEST_TIMEOUT_MS/);
  assert.match(api, /export function resolveContent[\s\S]*?'\/resolve-content'[\s\S]*?CONTENT_RESOLVE_TIMEOUT_MS,[\s\S]*?\n\s*\);/);
});
