const LOCAL_HOSTS = new Set([
  "localhost",
  "127.0.0.1",
  "[::1]",
]);

const PRODUCTION_API_ORIGIN =
  "https://sportabase-api.onrender.com";

function exactBrowserApiOrigin(config, label) {
  const raw = String(config?.apiBase || "").trim();

  let api;

  try {
    api = new URL(raw);
  } catch {
    throw new Error(
      `${label} API origin is invalid.`
    );
  }

  if (
    api.protocol !== "https:" ||
    api.origin !== raw.replace(/\/$/, "")
  ) {
    throw new Error(
      `${label} API origin is invalid.`
    );
  }

  return api.origin;
}

export function assertBrowserDeployment(
  config,
  pageLocation
) {
  const deployment = String(
    config?.deployment || ""
  );

  const local = LOCAL_HOSTS.has(
    String(
      pageLocation?.hostname || ""
    ).toLowerCase()
  );

  if (
    !local &&
    !["staging", "production"].includes(deployment)
  ) {
    throw new Error(
      "This deployment is missing an explicit staging or production browser configuration."
    );
  }

  if (deployment === "staging") {
    if (
      !String(
        config?.clerkPublishableKey || ""
      ).startsWith("pk_test_")
    ) {
      throw new Error(
        "Staging Clerk sign-in is not configured with a test key."
      );
    }

    const apiOrigin = exactBrowserApiOrigin(
      config,
      "Staging"
    );

    if (apiOrigin === PRODUCTION_API_ORIGIN) {
      throw new Error(
        "Staging must not use the production Sportabase API origin."
      );
    }
  }

  if (deployment === "production") {
    if (
      !String(
        config?.clerkPublishableKey || ""
      ).startsWith("pk_live_")
    ) {
      throw new Error(
        "Production Clerk sign-in is not configured."
      );
    }

    if (
      config?.canonicalWebOrigin !==
      pageLocation?.origin
    ) {
      throw new Error(
        "Production canonical web origin is not configured."
      );
    }

    if (
      config?.cspDeploymentConfigured !== true
    ) {
      throw new Error(
        "Production CSP deployment is not confirmed."
      );
    }

    exactBrowserApiOrigin(
      config,
      "Production"
    );
  }
}