import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const activitySource = await readFile(new URL('../src/app/activity.tsx', import.meta.url), 'utf8');
const generationSource = await readFile(new URL('../src/lib/request-generation.ts', import.meta.url), 'utf8');

function loadGenerationModule() {
  const compiled = ts.transpileModule(generationSource, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(compiled, { module, exports: module.exports });
  return module.exports;
}

test('Activity reloads on each focus without polling or clearing the existing list', () => {
  assert.match(activitySource, /useFocusEffect\(useCallback\(\(\) => \{/);
  assert.match(activitySource, /void loadRef\.current\(\)/);
  assert.match(activitySource, /return \(\) => \{/);
  assert.doesNotMatch(activitySource, /setInterval|setTimeout/);
  assert.doesNotMatch(activitySource, /setItems\(\[\]\)/);
});

test('Activity filter and explicit search loads remain wired', () => {
  assert.match(activitySource, /previousKind\.current === kind/);
  assert.match(activitySource, /if \(focused\.current\) void loadRef\.current\(\)/);
  assert.match(activitySource, /onSubmitEditing=\{\(\) => void load\(\)\}/);
  assert.match(activitySource, /onPress=\{\(\) => void load\(\)\}/);
  assert.match(activitySource, /append && next/);
});

test('an older Activity response cannot overwrite a newer load', async () => {
  const { createRequestGeneration } = loadGenerationModule();
  const requests = createRequestGeneration();
  const applied = [];
  let resolveOlder;
  let resolveNewer;
  const older = new Promise((resolve) => { resolveOlder = resolve; });
  const newer = new Promise((resolve) => { resolveNewer = resolve; });

  const olderIsCurrent = requests.begin();
  const olderLoad = older.then((value) => { if (olderIsCurrent()) applied.push(value); });
  const newerIsCurrent = requests.begin();
  const newerLoad = newer.then((value) => { if (newerIsCurrent()) applied.push(value); });

  resolveNewer('new analysis');
  await newerLoad;
  resolveOlder('stale empty list');
  await olderLoad;

  assert.deepEqual(applied, ['new analysis']);
  assert.match(activitySource, /if \(!isCurrent\(\)\) return/);
  assert.match(activitySource, /if \(isCurrent\(\)\) setError/);
  assert.match(activitySource, /if \(isCurrent\(\)\) setBusy\(false\)/);
});

test('leaving Activity invalidates an in-flight response before revisit', () => {
  const { createRequestGeneration } = loadGenerationModule();
  const requests = createRequestGeneration();
  const firstFocusRequest = requests.begin();
  requests.invalidate();
  const revisitRequest = requests.begin();

  assert.equal(firstFocusRequest(), false);
  assert.equal(revisitRequest(), true);
  assert.match(activitySource, /requests\.invalidate\(\); activeRequest\.current = null/);
});

test('duplicate loads in one focus lifecycle share the active promise', () => {
  assert.match(activitySource, /activeRequest\.current\?\.focus === focus && activeRequest\.current\.key === key/);
  assert.match(activitySource, /return activeRequest\.current\.promise/);
});
