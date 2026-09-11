import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile, readdir } from 'node:fs/promises';

const [savedRoute, homepage, activity, api, contextHook, resultAdapter, layout, destinations] = await Promise.all([
  '../src/app/analysis.tsx',
  '../src/product-ui/ProductAnalyze.web.tsx',
  '../src/app/activity.tsx',
  '../src/lib/api.ts',
  '../src/lib/use-analysis-result-context.ts',
  '../src/product-ui/ProductAnalysisResult.web.tsx',
  '../src/app/_layout.tsx',
  '../src/lib/auth-destinations.ts',
].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));

test('fresh saved analysis replaces the homepage with the opaque canonical Activity URL', () => {
  assert.match(homepage, /analysis\.data\.saved_activity/);
  assert.match(homepage, /savedActivity\?\.restorable/);
  assert.match(homepage, /router\.replace\(\{ pathname: '\/analysis', params: \{ activity: savedActivity\.id \} \}\)/);
  assert.doesNotMatch(homepage, /account\/activity\?[^'"`]*limit=1|select newest|latest snapshot/i);
});

test('saved route loads an account-owned snapshot and never starts analysis', () => {
  assert.match(savedRoute, /getSavedAnalysis\(activityId\)/);
  assert.match(api, /\/account\/activity\/\$\{encodeURIComponent\(activityId\)\}\/analysis/);
  assert.doesNotMatch(savedRoute, /runProductAnalysis|analyzeArticle|analyzeVideo|resolveContent|\/analyze/);
  assert.match(savedRoute, /This does not run a new analysis\./);
  assert.match(savedRoute, /Analysis unavailable/);
});

test('saved article and video results use the one production result adapter', () => {
  assert.match(savedRoute, /saved\.kind === 'article'/);
  assert.match(savedRoute, /kind: 'video'/);
  assert.match(savedRoute, /<ProductAnalysisResultView/);
  assert.equal((savedRoute.match(/<ProductAnalysisResultView/g) ?? []).length, 1);
  assert.match(resultAdapter, /<AnalysisResultView/);
  assert.doesNotMatch(savedRoute, /result-ui\/AnalysisResultView|function ArticlePrimary|function EvidenceBlock/);
});

test('current intelligence hydration and retry remain independent from snapshot loading', () => {
  assert.match(savedRoute, /useAnalysisResultContext\(sourceUrl, Boolean\(saved\)\)/);
  assert.match(savedRoute, /onRetryContext=\{context\.retry\}/);
  assert.match(contextHook, /getAnalysisResultContext\(sourceUrl\)/);
  assert.doesNotMatch(contextHook, /getSavedAnalysis|runProductAnalysis|\/analyze/);
});

test('My Activity separates View analysis from Open source and hides dead restore actions', () => {
  assert.match(activity, /item\.restorable \? <ProductButton label="View analysis"/);
  assert.match(activity, /pathname: '\/analysis', params: \{ activity: item\.id \}/);
  assert.match(activity, /label="Open source"/);
  assert.match(activity, /Linking\.openURL\(item\.url\)/);
  assert.match(activity, /Snapshot unavailable/);
});

test('analysis is one static production route with an allowlisted opaque query return', async () => {
  const appFiles = await readdir(new URL('../src/app/', import.meta.url));
  assert.ok(appFiles.includes('analysis.tsx'));
  assert.equal(appFiles.some((file) => /^analysis\[|^analysis\//.test(file)), false);
  assert.match(layout, /<Stack\.Screen name="analysis"/);
  assert.match(destinations, /\/analysis\\\?activity=act_\[0-9a-f\]\{32\}/);
  assert.doesNotMatch(savedRoute, /design-lab|DesignLab/);
});
