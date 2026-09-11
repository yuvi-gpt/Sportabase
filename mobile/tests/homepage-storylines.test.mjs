import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const api = readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8');
const homepage = readFileSync(new URL('../src/product-ui/ProductAnalyze.web.tsx', import.meta.url), 'utf8');

test('homepage storylines use the public product endpoint', () => {
  assert.match(api, /requestJson<HomepageStorylinesResponse>\(\s*`\/intelligence\/homepage-storylines\?/);
  assert.match(homepage, /getHomepageStorylines\(\{ limit: 100 \}\)/);
});

test('sport tabs filter only by the explicit returned sport key', () => {
  assert.match(homepage, /storylines\.filter\(\(item\) => item\.sport_key === selectedSport\.sportKey\)/);
  assert.match(homepage, /No sport is inferred from titles or entities/);
  assert.doesNotMatch(homepage, /title\.(?:includes|match)|entities\.(?:some|find)/);
});

test('storyline cards map only persisted response fields with precise reporting labels', () => {
  assert.match(homepage, /storyline\.representative_media\?\.title \|\| storyline\.title/);
  for (const field of ['current_state', 'latest_activity_at', 'report_count', 'distinct_source_count']) {
    assert.match(homepage, new RegExp(`storyline\\.${field}`));
  }
  assert.match(homepage, /storyline\.verified_independent_reporting_present \?/);
  assert.match(homepage, /storyline\.verified_independent_report_count/);
  assert.match(homepage, /distinct .*source/);
  assert.doesNotMatch(homepage, /mock-results|fixtureByPath|DesignLab/);
});

test('Top Storylines has loading, populated, empty, and error branches', () => {
  for (const phase of ['loading', 'ready', 'error']) {
    assert.match(homepage, new RegExp(`storylinePhase === '${phase}'`));
  }
  assert.match(homepage, /visibleStorylines\.length/);
  assert.match(homepage, /!visibleStorylines\.length/);
});
