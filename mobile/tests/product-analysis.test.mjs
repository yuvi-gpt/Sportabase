import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/product-analysis.ts', import.meta.url), 'utf8');
function load(overrides = {}) {
  const module = { exports: {} };
  const calls = [];
  const api = {
    resolveContent: async (url) => { calls.push(['resolve', url]); return overrides.resolved ?? { source: 'article', mode: 'article', normalized_url: url, title: 'Persisted match report', content: 'Article body' }; },
    analyzeArticle: async (request) => { calls.push(['article', request]); return overrides.article ?? { title: request.title, merit_score: 80 }; },
    analyzeVideo: async (request) => { calls.push(['video', request]); return overrides.video ?? { evidence_score: 70, logic_score: 60, verdict: 'Partially supported' }; },
  };
  const deployment = { resolveSportabaseApiOrigin: () => { calls.push(['validate']); if (overrides.validationError) throw new Error(overrides.validationError); return 'https://test.invalid'; } };
  const youtube = {
    fetchYouTubeTranscript: async (url) => { calls.push(['transcript', url]); return { transcript: 'Transcript', segments: [], segmentCount: 2, characterCount: 10, language: 'en' }; },
    fetchYouTubeVideoTitle: async (url) => { calls.push(['title', url]); return 'Persisted video title'; },
  };
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { esModuleInterop: true, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, {
    module, exports: module.exports, URL,
    require: (specifier) => specifier === './api' ? api : specifier === './deployment-config' ? deployment : specifier === './youtube-transcript' ? youtube : (() => { throw new Error(`Unexpected import: ${specifier}`); })(),
  });
  return { ...module.exports, calls };
}

test('article product adapter resolves content and renders the actual ArticleAnalyzeResponse', async () => {
  const harness = load(); const result = await harness.runProductAnalysis('https://example.test/story');
  assert.equal(result.kind, 'article'); assert.equal(result.data.merit_score, 80);
  assert.deepEqual(harness.calls.map(([name]) => name), ['validate', 'resolve', 'article']);
  assert.equal(harness.calls[2][1].text, 'Article body');
});

test('article analysis reports resolving before content resolution and analyzing before analysis', async () => {
  const harness = load();
  const result = await harness.runProductAnalysis(
    'https://example.test/story',
    undefined,
    (phase) => harness.calls.push(['phase', phase]),
  );
  assert.equal(result.kind, 'article');
  assert.deepEqual(harness.calls.map(([name, value]) => name === 'phase' ? `${name}:${value}` : name), [
    'validate',
    'phase:resolving',
    'resolve',
    'phase:analyzing',
    'article',
  ]);
});

test('video product adapter keeps Evidence Score, Logic Score, and Verdict separate', async () => {
  const harness = load(); const result = await harness.runProductAnalysis('https://youtu.be/abcdefghijk');
  assert.equal(result.kind, 'video'); assert.equal(result.data.evidence_score, 70); assert.equal(result.data.logic_score, 60); assert.equal(result.data.verdict, 'Partially supported');
  assert.deepEqual(harness.calls.map(([name]) => name), ['validate', 'transcript', 'title', 'video']);
  assert.equal(harness.calls[3][1].transcript_metadata.extraction_method, 'youtube-transcript');
});

test('YouTube analysis reports resolving before extraction and analyzing before analysis', async () => {
  const harness = load();
  const result = await harness.runProductAnalysis(
    'https://youtu.be/abcdefghijk',
    undefined,
    (phase) => harness.calls.push(['phase', phase]),
  );
  assert.equal(result.kind, 'video');
  assert.deepEqual(harness.calls.map(([name, value]) => name === 'phase' ? `${name}:${value}` : name), [
    'validate',
    'phase:resolving',
    'transcript',
    'title',
    'phase:analyzing',
    'video',
  ]);
});

test('analysis validates the fail-closed Sportabase boundary before any content request', async () => {
  const harness = load({ validationError: 'Sportabase API is not configured.' });
  await assert.rejects(() => harness.runProductAnalysis('https://example.test/story'), /not configured/);
  assert.deepEqual(harness.calls.map(([name]) => name), ['validate']);
});
