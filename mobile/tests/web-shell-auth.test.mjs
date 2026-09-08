import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const read = (path) =>
  readFile(new URL(path, import.meta.url), 'utf8');

const [
  layoutSource,
  headerSource,
  shellSource,
  gateSource,
  destinationsSource,
  accountSource,
  designHeaderSource,
  homeRouteSource,
  productAnalyzeSource,
  nativeNavSource,
  watchlistsSource,
  alertsSource,
  activitySource,
  notificationsSource,
] = await Promise.all([
  read('../src/app/_layout.tsx'),
  read('../src/product-ui/ProductHeader.tsx'),
  read('../src/product-ui/ProductWebShell.web.tsx'),
  read('../src/product-ui/ProtectedWebDestination.tsx'),
  read('../src/lib/auth-destinations.ts'),
  read('../src/lib/account-context.tsx'),
  read('../src/design-lab/DesignLabHeader.tsx'),
  read('../src/app/index.tsx'),
  read('../src/product-ui/ProductAnalyze.tsx'),
  read('../src/components/product-nav.tsx'),
  read('../src/app/watchlists.tsx'),
  read('../src/app/alerts.tsx'),
  read('../src/app/activity.tsx'),
  read('../src/app/notifications.tsx'),
]);

function loadDestinationsModule() {
  const compiled = ts.transpileModule(
    destinationsSource,
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  const module = { exports: {} };

  vm.runInNewContext(compiled, {
    module,
    exports: module.exports,
    URL,
  });

  return module.exports;
}

test('web shell owns the shared production header and keeps the Design Lab as a wrapper', () => {
  assert.match(layoutSource, /<ProductWebShell>\{navigator\}<\/ProductWebShell>/);
  assert.match(shellSource, /<ProductHeader/);
  assert.match(shellSource, /href="#sportabase-main"/);
  assert.match(shellSource, /role="main"/);
  assert.match(designHeaderSource, /import \{ ProductHeader \} from '\.\.\/product-ui\/ProductHeader'/);
  assert.doesNotMatch(designHeaderSource, /const NAV_ITEMS/);
  assert.match(homeRouteSource, /import \{ ProductAnalyze \} from '\.\.\/product-ui\/ProductAnalyze'/);
  assert.match(homeRouteSource, /<ProductAnalyze \/>/);
  assert.doesNotMatch(homeRouteSource, /SportabaseProduct|design-lab/);
  assert.match(productAnalyzeSource, /useProductHomeControls\(/);
});

test('web primary navigation exposes the required product destinations', () => {
  for (const [label, route] of [
    ['Analyze', '/'],
    ['Discover', '/explore'],
    ['Watches', '/watchlists'],
    ['Alerts', '/alerts'],
    ['Activity', '/activity'],
    ['Settings', '/settings'],
  ]) {
    assert.match(
      headerSource,
      new RegExp(`label: '${label}', route: '${route.replace('/', '\\/')}'`),
    );
  }

  assert.match(headerSource, /'Manage Sportabase account'/);
  assert.doesNotMatch(headerSource, /label: 'Notifications'/);
  assert.match(headerSource, /accessibilityRole="link"/);
});

test('auth return destinations fail closed to an explicit allowlist', () => {
  const destinations = loadDestinationsModule();

  for (const destination of [
    '/',
    '/explore',
    '/watchlists',
    '/alerts',
    '/activity',
    '/notifications',
    '/settings',
  ]) {
    assert.equal(
      destinations.allowlistedAuthDestination(destination),
      destination,
    );
  }

  for (const rejected of [
    'https://example.com/steal-session',
    '//example.com',
    '/alerts?next=https://example.com',
    '/intelligence',
    '',
    undefined,
  ]) {
    assert.equal(
      destinations.allowlistedAuthDestination(rejected),
      '/',
    );
  }

  assert.deepEqual(
    Array.from(destinations.PROTECTED_WEB_DESTINATIONS),
    ['/watchlists', '/alerts', '/activity', '/notifications'],
  );
});

test('Clerk receives the allowlisted destination as both force and fallback return URL', () => {
  assert.match(accountSource, /allowlistedAuthDestination\(destination\)/);
  assert.match(accountSource, /signInForceRedirectUrl:redirectUrl/);
  assert.match(accountSource, /signInFallbackRedirectUrl:redirectUrl/);
  assert.match(accountSource, /signUpForceRedirectUrl:redirectUrl/);
  assert.match(accountSource, /signUpFallbackRedirectUrl:redirectUrl/);
});

test('direct protected web routes stay addressable and mount an intent-preserving gate', () => {
  for (const route of [
    'watchlists',
    'alerts',
    'activity',
    'notifications',
  ]) {
    assert.match(
      layoutSource,
      new RegExp(`Platform\\.OS === 'web' \\? <Stack\\.Screen name="${route}"`),
    );
  }

  for (const [source, destination] of [
    [watchlistsSource, '/watchlists'],
    [alertsSource, '/alerts'],
    [activitySource, '/activity'],
    [notificationsSource, '/notifications'],
  ]) {
    assert.match(source, /<ProtectedWebDestination/);
    assert.match(
      source,
      new RegExp(`destination="${destination.replace('/', '\\/')}"`),
    );
  }

  assert.match(gateSource, /account\.signIn\(signup, destination\)/);
  assert.match(gateSource, /window\.sessionStorage/);
  assert.match(gateSource, /Sign-in was not completed/);
  assert.doesNotMatch(gateSource, /router\.(push|replace)\('\/settings'\)/);
});

test('public routes stay outside protection while native protected navigation remains in place', () => {
  assert.match(layoutSource, /<Stack\.Screen name="settings" \/>/);
  assert.match(layoutSource, /<Stack\.Screen name="explore" \/>/);
  assert.doesNotMatch(layoutSource, /<Stack\.Screen name="index"/);
  assert.match(layoutSource, /Platform\.OS !== 'web'/);
  assert.match(layoutSource, /<Stack\.Protected guard=/);
  assert.match(nativeNavSource, /export function ProductNav/);
  assert.match(nativeNavSource, /useSafeAreaInsets/);
});
