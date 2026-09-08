import { test, expect } from '@playwright/test';
import { mkdir, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { expoStaticRoot, startExpoServer, stopExpoServer } from '../../serve-expo.mjs';

const API_ORIGIN = 'https://sportabase-e2e.invalid';
const screenshotSet = process.env.SPORTABASE_SCREENSHOT_SET || 'current';
const screenshotRoot = fileURLToPath(new URL(`../../artifacts/expo/${screenshotSet}/`, import.meta.url));
let staticServer;
test.beforeAll(async () => { staticServer = await startExpoServer(); });
test.afterAll(async () => { await stopExpoServer(staticServer); });

const articleResult = {
  url: 'https://example.test/story', title: 'A carefully reported final told through a very long but still readable match headline',
  tldr: ['The report identifies the decisive tactical change.', 'Named evidence supports the timeline while one attribution remains limited.'],
  merit_score: 82, badge: 'Strong reporting', article_type: 'match_report', article_type_label: 'Match report', article_subtype: 'analysis', type_confidence: 0.93, type_signals: ['timeline'],
  reasons: ['The account separates direct observation from attributed reporting.', 'The central sequence is supported by named evidence.'],
  score_components: { reporting_quality: 42, evidential_support: 40 }, score_calculation: {}, language: {}, localized_article_type: 'Match report', localized_reasons: [], ui_labels: {},
  intelligence: { version: '1', status: 'resolved', label: 'Developing signal', detail: 'Two persisted objects are connected by recorded evidence.', signal: 'Independence remains unverified where provenance is missing.', candidate_count: 2, verification_pairs: 1, corroboration_status: 'limited', independence_status: 'unverified', contested: false, provisional: true, affects_merit_score: false }, debug: {},
};
const videoResult = { content_type: 'sports commentary', claim: 'The presenter argues that the tactical change decided the match.', evidence_used: ['A timestamped sequence from the second half.', 'A direct quotation from the post-match interview.'], logic_check: 'The conclusion follows from the examples but does not exclude other causes.', hype_check: 'One superlative is not supported by comparison data.', evidence_score: 71, logic_score: 66, verdict: 'Partially supported', language: {}, localized_content_type: 'Sports commentary', localized_verdict: 'Partially supported', ui_labels: {}, debug: {} };
const searchResults = { version: '1', query: 'club', results: [
  { kind: 'entity', id: 'entity-1', title: 'A club name with enough descriptive context to verify long-title wrapping at the narrowest supported viewport without clipping', subtitle: 'Football club · persisted identity', matched_field: 'canonical_name', match_type: 'prefix', first_seen_at: '2026-08-01T10:00:00Z', last_seen_at: '2026-09-01T10:00:00Z' },
  { kind: 'source', id: 'source-1', title: 'Example Sports Desk', subtitle: 'Inspectable provenance profile', matched_field: 'display_name', match_type: 'exact', first_seen_at: '2026-08-01T10:00:00Z', last_seen_at: '2026-09-01T10:00:00Z' },
] };

async function installNetworkBoundary(page, options = {}) {
  const unexpected = [];
  await page.route('**/*', async (route) => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin === 'http://127.0.0.1:4174') return route.continue();
    if (url.origin === API_ORIGIN) {
      if (options.api) return options.api(route, url);
      return route.fulfill({ status: 503, json: { detail: 'Local browser fixture has no response for this request.' } });
    }
    if (options.youtube && url.hostname.endsWith('youtube.com')) return options.youtube(route, url);
    unexpected.push(request.url());
    return route.abort('blockedbyclient');
  });
  return unexpected;
}

async function assertNoHorizontalOverflow(page) {
  const report = await page.evaluate(() => ({ document: document.documentElement.scrollWidth - innerWidth, body: document.body.scrollWidth - innerWidth }));
  expect(report, JSON.stringify(report)).toEqual({ document: 0, body: 0 });
}

const routeCases = [
  ['/', 'Know what backs the story.'], ['/explore', 'Discover'], ['/intelligence', 'Intelligence'], ['/settings', 'Settings'],
  ['/watchlists', 'Watches'], ['/alerts', 'Alerts'], ['/notifications', 'Notifications'], ['/activity', 'Activity'],
];

test('release export excludes Design Lab routes', async ({ page }) => {
  const exportedRoutes = (await readdir(expoStaticRoot, { withFileTypes: true }))
    .filter((entry) => entry.isFile() && entry.name.endsWith('.html'))
    .map((entry) => entry.name === 'index.html' ? '/' : `/${entry.name.slice(0, -5)}`)
    .sort();

  expect(exportedRoutes).toEqual([
    '/',
    '/+not-found',
    '/_sitemap',
    '/activity',
    '/alerts',
    '/explore',
    '/handle-share',
    '/intelligence',
    '/notifications',
    '/settings',
    '/watchlists',
  ]);

  for (const route of ['/design-lab', '/design-lab-analyzing']) {
    const response = await page.goto(route);
    expect(response?.status()).toBe(404);
    await expect(page.locator('body')).not.toContainText(/Design Lab|Analyzing\.\.\.|design-lab-fixtures/);
  }
});

for (const viewport of [
  { label: '1440 desktop', width: 1440, height: 1000 }, { label: '768 tablet', width: 768, height: 1024 },
  { label: '390 mobile', width: 390, height: 844 }, { label: '320 narrow', width: 320, height: 760 },
]) {
  test(`route shell and overflow matrix at ${viewport.label}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height }); await installNetworkBoundary(page);
    for (const [route, heading] of routeCases) {
      await page.goto(route);
      await expect(page.locator('#sportabase-product-header')).toHaveCount(1);
      await expect(page.getByRole('navigation', { name: 'Primary' }).getByText('Activity', { exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: heading, exact: false }).first()).toBeVisible();
      await assertNoHorizontalOverflow(page);
      if (viewport.width === 320) {
        const navTargets = await page.getByRole('navigation', { name: 'Primary' }).getByRole('link').evaluateAll((nodes) => nodes.map((node) => {
          const rect = node.getBoundingClientRect();
          return { height: rect.height, left: rect.left, right: rect.right, width: rect.width };
        }));
        expect(navTargets.every((target) => target.height >= 44 && target.width >= 44 && target.left >= 0 && target.right <= viewport.width), JSON.stringify(navTargets)).toBe(true);
      }
    }
  });
}

test('keyboard focus, skip link, controls, and reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' }); await installNetworkBoundary(page); await page.goto('/');
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  expect(await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle)).toBe('solid');
  await page.keyboard.press('Enter'); expect(await page.evaluate(() => location.hash)).toBe('#sportabase-main');
  const controls = await page.locator('#sportabase-main [role="button"]:visible').evaluateAll((nodes) => nodes.map((node) => ({ width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height, name: node.getAttribute('aria-label') || node.textContent })));
  expect(controls.every((control) => control.width >= 40 && control.height >= 44), JSON.stringify(controls)).toBe(true);
  const movingTransform = await page.locator('[data-testid="product-watermark"] > div').first().evaluate((node) => getComputedStyle(node).transform);
  expect(movingTransform).toBe('none');
});

test('Discover exposes loading, long-result, empty, and error states without inventing linkage', async ({ page }) => {
  let mode = 'results';
  await installNetworkBoundary(page, { api: async (route, url) => {
    if (url.pathname !== '/intelligence/search') return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    if (mode === 'error') return route.fulfill({ status: 503, json: { detail: 'Mock intelligence index unavailable.' } });
    await new Promise((resolve) => setTimeout(resolve, 120));
    return route.fulfill({ json: mode === 'empty' ? { ...searchResults, results: [] } : searchResults });
  } });
  await page.setViewportSize({ width: 320, height: 900 }); await page.goto('/explore');
  await page.getByLabel('Search term').fill('club'); await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Searching persisted intelligence')).toBeVisible(); await expect(page.getByText(searchResults.results[0].title)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in to watch' })).toBeVisible(); await expect(page.getByText('Profile only')).toHaveCount(0); await assertNoHorizontalOverflow(page);
  mode = 'empty'; await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByText('No persisted intelligence matched')).toBeVisible();
  mode = 'error'; await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByText('Mock intelligence index unavailable.')).toBeVisible();
});

test('signed-out analysis enters supported account flow before any API request', async ({ page }) => {
  let apiRequests = 0;
  await installNetworkBoundary(page, { api: async (route) => { apiRequests += 1; return route.fulfill({ status: 500, json: { detail: 'Unexpected API request.' } }); } });
  await page.goto('/'); await page.getByLabel('Article or YouTube URL').fill('https://example.test/story'); await page.getByRole('button', { name: 'Analyze', exact: true }).click();
  await expect(page.getByText('Account sign-in is not configured for this installation.')).toBeVisible();
  expect(apiRequests).toBe(0);
});

test('intelligence detail keeps provenance and chronology boundaries', async ({ page }) => {
  await installNetworkBoundary(page, { api: (route, url) => {
    if (url.pathname === '/intelligence/claims/claim-1/history') return route.fulfill({ json: { version: '1', claim: { id: 'claim-1', canonical_key: 'claim:1', subject_key: 'team:a', canonical_text: 'The tactical change decided the match.', claim_type: 'analysis', first_seen_at: '2026-08-01T10:00:00Z', last_seen_at: '2026-09-01T10:00:00Z' }, stories: [], verified_participants: [], events: [{ id: 'event-1', type: 'claim_observed', occurred_at: '2026-09-01T10:00:00Z', claim_summary: 'A persisted observation was recorded.' }], pagination: { limit: 50, next_cursor: null }, policy: { chronology_is_not_truth: true, evidence_quantity_is_not_probability: true, dependencies_remain_distinct: true } } });
    return route.fulfill({ status: 401, json: { detail: 'Sign in' } });
  } });
  await page.goto('/intelligence?kind=claim&id=claim-1'); await expect(page.getByRole('heading', { name: 'The tactical change decided the match.' })).toBeVisible(); await expect(page.getByText(/Chronology records when intelligence occurred/)).toBeVisible(); await expect(page.getByText(/Ordering records when intelligence occurred/)).toBeVisible();
});

test('Settings uses desktop workspace and narrow two-stage navigation', async ({ page }) => {
  await installNetworkBoundary(page); await page.goto('/settings');
  await expect(page.getByText('Choose a Settings section')).toBeVisible(); await page.getByRole('button', { name: 'Support/About' }).click(); await expect(page.getByText(/Article bodies, transcripts, and credentials/)).toBeVisible();
  await page.setViewportSize({ width: 320, height: 760 }); await page.goto('/settings'); await page.getByRole('button', { name: 'Support/About' }).click(); await expect(page.getByRole('button', { name: 'Back to Settings' })).toBeVisible(); await assertNoHorizontalOverflow(page);
});

test('current-run rendered audit screenshots', async ({ page }) => {
  await mkdir(screenshotRoot, { recursive: true });
  await installNetworkBoundary(page, { api: async (route, url) => {
    if (url.pathname === '/intelligence/search') return route.fulfill({ json: searchResults });
    if (url.pathname === '/intelligence/claims/claim-1/history') return route.fulfill({ json: { version: '1', claim: { id: 'claim-1', canonical_key: 'claim:1', subject_key: 'team:a', canonical_text: 'The tactical change decided the match.', claim_type: 'analysis', first_seen_at: '2026-08-01T10:00:00Z', last_seen_at: '2026-09-01T10:00:00Z' }, stories: [], verified_participants: [], events: [{ id: 'event-1', type: 'claim_observed', occurred_at: '2026-09-01T10:00:00Z', claim_summary: 'A persisted observation was recorded.' }], pagination: { limit: 50, next_cursor: null }, policy: { chronology_is_not_truth: true, evidence_quantity_is_not_probability: true } } });
    return route.fulfill({ status: 503, json: { detail: 'No fixture for this route.' } });
  } });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto('/'); await expect(page.getByRole('heading', { name: 'Know what backs the story.' })).toBeVisible(); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/home-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto('/'); await expect(page.getByRole('heading', { name: 'Know what backs the story.' })).toBeVisible(); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/home-mobile.png`, fullPage: true });
  await page.setViewportSize({ width: 768, height: 1000 }); await page.goto('/explore'); await page.getByLabel('Search term').fill('club'); await page.getByRole('button', { name: 'Search', exact: true }).click(); await expect(page.getByText(searchResults.results[0].title)).toBeVisible(); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/discover.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto('/settings'); await page.getByRole('button', { name: 'Support/About' }).click(); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/settings-desktop.png`, fullPage: true });
  await page.setViewportSize({ width: 320, height: 760 }); await page.goto('/settings'); await page.getByRole('button', { name: 'Support/About' }).click(); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/settings-narrow.png`, fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto('/watchlists'); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/watches-account-gate.png`, fullPage: true }); await page.goto('/alerts'); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/alerts-account-gate.png`, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto('/intelligence?kind=claim&id=claim-1'); await expect(page.getByRole('heading', { name: 'The tactical change decided the match.' })).toBeVisible(); await page.waitForTimeout(200); await page.screenshot({ path: `${screenshotRoot}/intelligence-result.png`, fullPage: true });
});
