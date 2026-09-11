export const EXPO_DEPLOYMENT_STATES = [
  'local',
  'staging',
  'production',
  'unconfigured',
] as const;

export type ExpoDeploymentState =
  (typeof EXPO_DEPLOYMENT_STATES)[number];

export type ExpoPublicConfiguration = {
  deployment?: string;
  apiUrl?: string;
  webUrl?: string;
  clerkPublishableKey?: string;
};

export type ExpoAuthConfiguration = {
  publishableKey: string | null;
  error: string;
};

type SportabaseFetchOptions = {
  configuration?: ExpoPublicConfiguration;
  fetchImplementation?: typeof fetch;
};

const PRODUCTION_SPORTABASE_API_ORIGIN =
  'https://sportabase-api.onrender.com';

const LOCAL_API_HOSTS = new Set([
  'localhost',
  '127.0.0.1',
  '[::1]',
]);

function runtimePublicConfiguration(): ExpoPublicConfiguration {
  return {
    deployment:
      process.env.EXPO_PUBLIC_SPORTABASE_DEPLOYMENT,
    apiUrl:
      process.env.EXPO_PUBLIC_SPORTABASE_API_URL,
    webUrl:
      process.env.EXPO_PUBLIC_SPORTABASE_WEB_URL,
    clerkPublishableKey:
      process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY,
  };
}

function rawDeployment(
  configuration: ExpoPublicConfiguration,
) {
  return String(configuration.deployment ?? '')
    .trim()
    .toLowerCase();
}

export function expoDeploymentState(
  configuration: ExpoPublicConfiguration =
    runtimePublicConfiguration(),
): ExpoDeploymentState {
  const deployment = rawDeployment(configuration);

  return EXPO_DEPLOYMENT_STATES.includes(
    deployment as ExpoDeploymentState,
  )
    ? (deployment as ExpoDeploymentState)
    : 'unconfigured';
}

function configuredDeployment(
  configuration: ExpoPublicConfiguration,
): Exclude<ExpoDeploymentState, 'unconfigured'> {
  const deployment = rawDeployment(configuration);

  if (
    deployment === '' ||
    deployment === 'unconfigured'
  ) {
    throw new Error(
      'The Sportabase API is not configured. Set EXPO_PUBLIC_SPORTABASE_DEPLOYMENT and EXPO_PUBLIC_SPORTABASE_API_URL before making a request.',
    );
  }

  if (
    deployment !== 'local' &&
    deployment !== 'staging' &&
    deployment !== 'production'
  ) {
    throw new Error(
      'The Sportabase API is not configured because EXPO_PUBLIC_SPORTABASE_DEPLOYMENT must be local, staging, or production.',
    );
  }

  return deployment;
}

function exactOrigin(rawValue: string, label: string) {
  const raw = rawValue.trim();
  let parsed: URL;

  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${label} is not a valid URL origin.`);
  }

  const normalized = raw.endsWith('/')
    ? raw.slice(0, -1)
    : raw;

  if (
    parsed.username ||
    parsed.password ||
    parsed.pathname !== '/' ||
    parsed.search ||
    parsed.hash ||
    parsed.origin !== normalized
  ) {
    throw new Error(`${label} must be an exact URL origin.`);
  }

  return parsed;
}

export function resolveSportabaseApiOrigin(
  configuration: ExpoPublicConfiguration =
    runtimePublicConfiguration(),
) {
  const deployment = configuredDeployment(configuration);
  const rawApiUrl = String(configuration.apiUrl ?? '').trim();

  if (!rawApiUrl) {
    throw new Error(
      'The Sportabase API is not configured. Set EXPO_PUBLIC_SPORTABASE_API_URL before making a request.',
    );
  }

  const api = exactOrigin(
    rawApiUrl,
    'EXPO_PUBLIC_SPORTABASE_API_URL',
  );

  if (api.origin === PRODUCTION_SPORTABASE_API_ORIGIN) {
    if (deployment !== 'production') {
      throw new Error(
        `${deployment === 'staging' ? 'Staging' : 'Local development'} must not use the production Sportabase API origin.`,
      );
    }
  }

  if (deployment === 'local') {
    const localHttp =
      api.protocol === 'http:' &&
      LOCAL_API_HOSTS.has(api.hostname.toLowerCase());

    if (api.protocol !== 'https:' && !localHttp) {
      throw new Error(
        'Local Sportabase API configuration must use HTTPS or an explicit localhost/127.0.0.1 HTTP origin.',
      );
    }
  } else if (api.protocol !== 'https:') {
    throw new Error(
      `${deployment === 'staging' ? 'Staging' : 'Production'} Sportabase API configuration must use HTTPS.`,
    );
  }

  return api.origin;
}

export function resolveSportabaseWebOrigin(
  configuration: ExpoPublicConfiguration =
    runtimePublicConfiguration(),
) {
  const rawWebUrl = String(configuration.webUrl ?? '').trim();

  if (!rawWebUrl) {
    throw new Error(
      'EXPO_PUBLIC_SPORTABASE_WEB_URL is not configured.',
    );
  }

  const web = exactOrigin(
    rawWebUrl,
    'EXPO_PUBLIC_SPORTABASE_WEB_URL',
  );

  if (web.protocol !== 'https:') {
    throw new Error(
      'EXPO_PUBLIC_SPORTABASE_WEB_URL must use HTTPS.',
    );
  }

  return web.origin;
}

export function configuredSportabaseWebOrigin(
  configuration: ExpoPublicConfiguration =
    runtimePublicConfiguration(),
) {
  try {
    return resolveSportabaseWebOrigin(configuration);
  } catch {
    return null;
  }
}

export function expoAuthConfiguration(
  options: {
    configuration?: ExpoPublicConfiguration;
    requireWebOrigin?: boolean;
  } = {},
): ExpoAuthConfiguration {
  const configuration =
    options.configuration ?? runtimePublicConfiguration();
  const deployment = expoDeploymentState(configuration);
  const publishableKey = String(
    configuration.clerkPublishableKey ?? '',
  ).trim();

  if (!publishableKey) {
    return {
      publishableKey: null,
      error:
        'Account sign-in is not configured for this installation.',
    };
  }

  if (deployment === 'unconfigured') {
    return {
      publishableKey: null,
      error:
        'Account sign-in is unavailable because this Sportabase deployment is not configured.',
    };
  }

  const expectedPrefix =
    deployment === 'production' ? 'pk_live_' : 'pk_test_';

  if (!publishableKey.startsWith(expectedPrefix)) {
    return {
      publishableKey: null,
      error:
        deployment === 'production'
          ? 'Production account sign-in requires a Clerk live publishable key.'
          : 'Local and staging account sign-in require a Clerk test publishable key.',
    };
  }

  try {
    resolveSportabaseApiOrigin(configuration);
  } catch (problem) {
    return {
      publishableKey: null,
      error:
        problem instanceof Error
          ? problem.message
          : 'The Sportabase API is not configured for account sign-in.',
    };
  }

  if (
    options.requireWebOrigin &&
    (deployment === 'staging' ||
      deployment === 'production')
  ) {
    try {
      resolveSportabaseWebOrigin(configuration);
    } catch (problem) {
      return {
        publishableKey: null,
        error:
          problem instanceof Error
            ? problem.message
            : 'The Sportabase web origin is not configured for account sign-in.',
      };
    }
  }

  return { publishableKey, error: '' };
}

function requestPath(path: string) {
  if (!/^\/(?!\/)/.test(path)) {
    throw new Error(
      'Sportabase requests require an application-relative API path.',
    );
  }

  return path;
}

export function sportabaseFetch(
  path: string,
  init: RequestInit = {},
  options: SportabaseFetchOptions = {},
) {
  const apiOrigin = resolveSportabaseApiOrigin(
    options.configuration,
  );
  const fetchImplementation =
    options.fetchImplementation ?? globalThis.fetch;

  if (typeof fetchImplementation !== 'function') {
    throw new Error(
      'The fetch implementation is unavailable in this runtime.',
    );
  }

  return fetchImplementation(
    `${apiOrigin}${requestPath(path)}`,
    init,
  );
}
