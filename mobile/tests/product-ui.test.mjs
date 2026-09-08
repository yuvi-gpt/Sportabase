import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

const [homeRoute, analyze, primitives, watermark, css, header] = await Promise.all([
  '../src/app/index.tsx', '../src/product-ui/ProductAnalyze.tsx', '../src/product-ui/ProductPrimitives.tsx', '../src/product-ui/ProductWatermark.tsx', '../src/global.css', '../src/product-ui/ProductHeader.tsx',
].map((path) => readFile(new URL(path, import.meta.url), 'utf8')));

test('production home is product-owned and contains no Design Lab fixtures or mock result adapter', () => {
  assert.match(homeRoute, /ProductAnalyze/); assert.doesNotMatch(homeRoute, /design-lab|SportabaseProduct/);
  for (const forbidden of ['fixtureByPath', 'mockResults', 'Top storylines', 'Across Sportabase', 'Design Lab']) assert.doesNotMatch(analyze, new RegExp(forbidden));
});

test('production header owns the selected Sportabase wordmark and complete primary navigation', () => {
  assert.match(header, /ProductWordmark/); assert.doesNotMatch(header, /DesignLabHeader|UppercaseSportabaseWordmark/);
  for (const label of ['Analyze', 'Discover', 'Watches', 'Alerts', 'Activity', 'Settings']) assert.match(header, new RegExp(`label: '${label}'`));
});

test('dialog and global interaction styling retain keyboard and focus requirements', () => {
  assert.match(primitives, /event\.key === 'Escape'/); assert.match(primitives, /event\.key !== 'Tab'/); assert.match(primitives, /previousFocus\.current\?\.focus/);
  assert.match(css, /#sportabase-main \[role='button'\]:focus-visible/); assert.match(css, /#sportabase-main input:focus-visible/); assert.doesNotMatch(css, /\*\s*:\s*focus[^\{]*\{[^}]*outline\s*:\s*(?:none|0)/s);
});

test('watermark preserves normal motion and resolves to a static treatment for reduced motion', () => {
  assert.match(watermark, /Animated\.loop/); assert.match(watermark, /if \(reduceMotion\)/); assert.match(watermark, /animation\.stop/);
});
