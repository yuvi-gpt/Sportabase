import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const [homeRoute, analyze, webAnalyze, loader, result, resultView, resultGeometry, primitives, watermark, css, header, wordmark, tokens] = await Promise.all([
  '../src/app/index.tsx', '../src/product-ui/ProductAnalyze.tsx', '../src/product-ui/ProductAnalyze.web.tsx', '../src/product-ui/ProductAnalysisLoader.web.tsx', '../src/product-ui/ProductAnalysisResult.web.tsx', '../src/result-ui/AnalysisResultView.web.tsx', '../src/result-ui/AnalysisResultGeometry.web.tsx', '../src/product-ui/ProductPrimitives.tsx', '../src/product-ui/ProductWatermark.tsx', '../src/global.css', '../src/product-ui/ProductHeader.tsx', '../src/product-ui/ProductWordmark.tsx', '../src/product-ui/tokens.ts',
].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));

test('production home is product-owned and contains no Design Lab fixtures or mock result adapter', () => {
  assert.match(homeRoute, /ProductAnalyze/); assert.doesNotMatch(homeRoute, /design-lab|SportabaseProduct/);
  for (const forbidden of ['fixtureByPath', 'mockResults', 'Top storylines', 'Across Sportabase', 'Design Lab']) assert.doesNotMatch(analyze, new RegExp(forbidden));
});

test('production header owns the selected Sportabase wordmark and complete primary navigation', () => {
  assert.match(header, /ProductWordmark/); assert.doesNotMatch(header, /DesignLabHeader|UppercaseSportabaseWordmark/);
  for (const label of ['Analyze', 'Discover', 'Watches', 'Alerts', 'Activity', 'Settings']) assert.match(header, new RegExp(`label: '${label}'`));
  assert.match(tokens, /body: Platform\.OS === 'web' \? 'SportabaseBarlowRegular'/); assert.match(tokens, /wordmark: 'SportabaseArchivoBlack'/);
  assert.match(wordmark, /fontFamily: productFonts\.wordmark/); assert.match(wordmark, />sportabase\.<\/Text>/); assert.doesNotMatch(wordmark, /styles\.cut|skewX/);
});

test('dialog and global interaction styling retain keyboard and focus requirements', () => {
  assert.match(primitives, /event\.key === 'Escape'/); assert.match(primitives, /event\.key !== 'Tab'/); assert.match(primitives, /previousFocus\.current\?\.focus/);
  assert.match(css, /#sportabase-main \[role='button'\]:focus-visible/); assert.match(css, /#sportabase-main input:focus-visible/); assert.doesNotMatch(css, /\*\s*:\s*focus[^\{]*\{[^}]*outline\s*:\s*(?:none|0)/s);
});

test('watermark preserves normal motion and resolves to a static treatment for reduced motion', () => {
  assert.match(watermark, /Animated\.loop/); assert.match(watermark, /if \(reduceMotion\)/); assert.match(watermark, /animation\.stop/);
  assert.match(watermark, /testID="stationary-sb-watermark"/); assert.match(watermark, /testID="product-watermark-satin"/);
  assert.doesNotMatch(watermark, /translateY|rotate:/); assert.match(watermark, /right: -size \* 0\.055/); assert.match(watermark, /right: -size \* 0\.1/);
});

test('production web analysis uses a full product-owned loader for both active phases', () => {
  assert.match(webAnalyze, /import \{ ProductAnalysisLoader \} from '\.\/ProductAnalysisLoader\.web'/);
  assert.match(webAnalyze, /if \(busy\) \{/);
  assert.match(webAnalyze, /<ProductAnalysisLoader mobile=\{mobile\} phase=\{phase\} url=\{url\} \/>/);
  assert.match(loader, /phase === 'resolving' \? 'Reading the source\.\.\.' : 'Analyzing\.\.\.'/);
  assert.match(loader, /Sportabase is extracting the article or transcript\./);
  assert.match(loader, /Reading the claim and checking what supports it\./);
  assert.match(loader, /VerificationLane/);
});

test('production loader retains its verification composition when motion is reduced', () => {
  assert.match(loader, /if \(reduceMotion\)/);
  assert.match(loader, /progress\.setValue\(frozenLaneProgress\[index\]\)/);
  assert.match(loader, /<VerificationField/);
});

test('production product UI does not import Design Lab loaders, themes, or fixtures', () => {
  for (const source of [analyze, webAnalyze, loader, result, resultView, resultGeometry]) {
    assert.doesNotMatch(source, /from ['"][^'"]*design-lab/i);
    assert.doesNotMatch(source, /fixtureByPath|mockResults|DesignLabAnalyzing|design-lab-theme/);
  }
});
