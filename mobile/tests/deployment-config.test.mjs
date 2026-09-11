import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const [deploymentSource, accountSource, contract] =
  await Promise.all([
    readFile(
      new URL(
        '../src/lib/deployment-config.ts',
        import.meta.url,
      ),
      'utf8',
    ),
    readFile(
      new URL(
        '../src/lib/account-api.ts',
        import.meta.url,
      ),
      'utf8',
    ),
    readFile(
      new URL(
        '../../frontend/preferences-contract.json',
        import.meta.url,
      ),
      'utf8',
    ).then(JSON.parse),
  ]);

function compile(source) {
  return ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
}

function loadDeploymentModule(
  environment = {},
  fetchImplementation = () => {
    throw new Error('Unexpected fetch.');
  },
) {
  const module = { exports: {} };

  vm.runInNewContext(compile(deploymentSource), {
    module,
    exports: module.exports,
    fetch: fetchImplementation,
    process: { env: environment },
    Set,
    URL,
  });

  return module.exports;
}

function loadAccountModule(deployment) {
  const module = { exports: {} };
  const storage = {
    getItem: async () => null,
    setItem: async () => undefined,
  };

  vm.runInNewContext(compile(accountSource), {
    module,
    exports: module.exports,
    fetch,
    require: (specifier) => {
      if (
        specifier ===
        '@react-native-async-storage/async-storage'
      ) {
        return { __esModule: true, default: storage };
      }
      if (specifier === 'expo-crypto') {
        return { randomUUID: () => 'test-device-id' };
      }
      if (
        specifier ===
        '../../../frontend/preferences-contract.json'
      ) {
        return { __esModule: true, default: contract };
      }
      if (specifier === './deployment-config') {
        return deployment;
      }

      throw new Error(`Unexpected import: ${specifier}`);
    },
  });

  return module.exports;
}

async function rejectsWithoutFetch(
  configuration,
  expectedMessage,
) {
  const calls = [];
  const deployment = loadDeploymentModule();

  await assert.rejects(
    async () =>
      deployment.sportabaseFetch(
        '/health',
        {},
        {
          configuration,
          fetchImplementation: (...args) => {
            calls.push(args);
            return Promise.resolve({ ok: true });
          },
        },
      ),
    expectedMessage,
  );

  assert.equal(calls.length, 0);
}

test('missing API configuration rejects before fetch', async () => {
  await rejectsWithoutFetch(
    { deployment: 'local' },
    /Sportabase API is not configured/,
  );
});

test('unconfigured deployment rejects before fetch', async () => {
  await rejectsWithoutFetch(
    {
      deployment: 'unconfigured',
      apiUrl: 'https://staging-api.example.invalid',
    },
    /Sportabase API is not configured/,
  );
});

test('local deployment rejects the production API before fetch', async () => {
  await rejectsWithoutFetch(
    {
      deployment: 'local',
      apiUrl: 'https://sportabase-api.onrender.com',
    },
    /Local development must not use the production Sportabase API origin/,
  );
});

test('staging deployment rejects the production API before fetch', async () => {
  await rejectsWithoutFetch(
    {
      deployment: 'staging',
      apiUrl: 'https://sportabase-api.onrender.com',
    },
    /Staging must not use the production Sportabase API origin/,
  );
});

test('malformed API URL rejects before fetch', async () => {
  await rejectsWithoutFetch(
    {
      deployment: 'staging',
      apiUrl: 'not a URL',
    },
    /not a valid URL origin/,
  );
});

test('staging and non-local HTTP origins reject before fetch', async () => {
  await rejectsWithoutFetch(
    {
      deployment: 'staging',
      apiUrl: 'http://staging-api.example.invalid',
    },
    /Staging Sportabase API configuration must use HTTPS/,
  );
  await rejectsWithoutFetch(
    {
      deployment: 'local',
      apiUrl: 'http://development-api.example.invalid',
    },
    /must use HTTPS or an explicit localhost/,
  );
});

test('valid explicit non-production configurations reach only the injected fetch', async () => {
  const calls = [];
  const deployment = loadDeploymentModule();
  const response = { ok: true, status: 200 };

  const result = await deployment.sportabaseFetch(
    '/health',
    { headers: { Accept: 'application/json' } },
    {
      configuration: {
        deployment: 'staging',
        apiUrl: 'https://staging-api.example.invalid',
      },
      fetchImplementation: async (...args) => {
        calls.push(args);
        return response;
      },
    },
  );

  assert.equal(result, response);
  assert.equal(calls.length, 1);
  assert.equal(
    calls[0][0],
    'https://staging-api.example.invalid/health',
  );
  assert.equal(
    deployment.resolveSportabaseApiOrigin({
      deployment: 'local',
      apiUrl: 'http://127.0.0.1:8000',
    }),
    'http://127.0.0.1:8000',
  );
  assert.equal(
    deployment.resolveSportabaseApiOrigin({
      deployment: 'local',
      apiUrl: 'https://development-api.example.invalid',
    }),
    'https://development-api.example.invalid',
  );
  assert.equal(
    deployment.resolveSportabaseApiOrigin({
      deployment: 'production',
      apiUrl: 'https://api.example.invalid',
    }),
    'https://api.example.invalid',
  );
});

test('account bootstrap uses the same fail-closed request boundary', async () => {
  const calls = [];
  const deployment = loadDeploymentModule({}, (...args) => {
    calls.push(args);
    return Promise.resolve({ ok: true });
  });
  const account = loadAccountModule(deployment);

  account.setTokenGetter(async () => 'test-session-token');

  await assert.rejects(
    () =>
      account.accountRequest(
        '/account/bootstrap',
        'POST',
        { platform: 'web' },
      ),
    /Sportabase API is not configured/,
  );
  assert.equal(calls.length, 0);
});

test('locked private path and authentication behavior remains intact', async () => {
  const calls = [];
  const account = loadAccountModule(
    loadDeploymentModule(
      {
        EXPO_PUBLIC_SPORTABASE_DEPLOYMENT: 'staging',
        EXPO_PUBLIC_SPORTABASE_API_URL:
          'https://staging-api.example.invalid',
      },
      (...args) => {
        calls.push(args);
        return Promise.resolve({ ok: true });
      },
    ),
  );

  for (const path of [
    '/account/bootstrap',
    '/watchlists',
    '/notifications/devices',
    '/analyze',
    '/analyze/video',
    '/resolve-content',
    '/content/browser-capture',
  ]) {
    assert.equal(account.privatePath(path), true, path);
  }

  for (const path of [
    '/health',
    '/intelligence/search',
    '/watchlist',
    '//account/bootstrap',
  ]) {
    assert.equal(account.privatePath(path), false, path);
  }

  await assert.rejects(
    () => account.accountRequest('/account/bootstrap'),
    /Sign in to use Sportabase/,
  );
  assert.equal(calls.length, 0);
});

test('staging web auth accepts only a test key with an explicit HTTPS web origin', () => {
  const deployment = loadDeploymentModule();

  assert.match(
    deployment.expoAuthConfiguration({
      configuration: {
        deployment: 'staging',
        clerkPublishableKey: 'pk_test_example',
        webUrl: 'https://staging-web.example.invalid',
      },
      requireWebOrigin: true,
    }).error,
    /Sportabase API is not configured/,
  );
  assert.equal(
    deployment.expoAuthConfiguration({
      configuration: {
        deployment: 'staging',
        apiUrl: 'https://staging-api.example.invalid',
        clerkPublishableKey: 'pk_live_example',
        webUrl: 'https://staging-web.example.invalid',
      },
      requireWebOrigin: true,
    }).publishableKey,
    null,
  );
  assert.match(
    deployment.expoAuthConfiguration({
      configuration: {
        deployment: 'staging',
        apiUrl: 'https://staging-api.example.invalid',
        clerkPublishableKey: 'pk_test_example',
      },
      requireWebOrigin: true,
    }).error,
    /EXPO_PUBLIC_SPORTABASE_WEB_URL is not configured/,
  );
  assert.equal(
    deployment.expoAuthConfiguration({
      configuration: {
        deployment: 'staging',
        apiUrl: 'https://staging-api.example.invalid',
        clerkPublishableKey: 'pk_test_example',
        webUrl: 'https://staging-web.example.invalid',
      },
      requireWebOrigin: true,
    }).publishableKey,
    'pk_test_example',
  );
});

test('every Sportabase request implementation uses the shared boundary', async () => {
  const requestFiles = [
    '../src/lib/account-api.ts',
    '../src/lib/api.ts',
    '../src/lib/intelligence-history.ts',
    '../src/lib/intelligence-search.ts',
    '../src/lib/notification-api.ts',
    '../src/lib/source-reporter-history.ts',
  ];

  for (const file of requestFiles) {
    const source = await readFile(
      new URL(file, import.meta.url),
      'utf8',
    );

    assert.match(source, /sportabaseFetch/);
    assert.doesNotMatch(source, /\bfetch\s*\(/);
    assert.doesNotMatch(
      source,
      /https:\/\/sportabase-api\.onrender\.com/,
    );
  }
});
