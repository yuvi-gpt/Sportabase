import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PRODUCTION_API_ORIGIN = "https://sportabase-api.onrender.com";

function readBoolean(name) {
  return /^(1|true|yes)$/i.test(
    String(process.env[name] || "").trim()
  );
}

function exactHttpsOrigin(
  value,
  name,
  { required = false } = {}
) {
  const raw = String(value || "").trim();

  if (!raw) {
    if (required) {
      throw new Error(`${name} is required.`);
    }

    return "";
  }

  const parsed = new URL(raw);

  if (
    parsed.protocol !== "https:" ||
    parsed.origin !== raw.replace(/\/$/, "")
  ) {
    throw new Error(
      `${name} must be an exact HTTPS origin.`
    );
  }

  return parsed.origin;
}

const deployment = String(
  process.env.SPORTABASE_WEB_DEPLOYMENT || ""
)
  .trim()
  .toLowerCase();

if (!["staging", "production"].includes(deployment)) {
  throw new Error(
    "SPORTABASE_WEB_DEPLOYMENT must be staging or production."
  );
}

const apiBase = exactHttpsOrigin(
  process.env.SPORTABASE_WEB_API_BASE,
  "SPORTABASE_WEB_API_BASE",
  { required: true }
);

const clerkPublishableKey = String(
  process.env.SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY || ""
).trim();

const canonicalWebOrigin = exactHttpsOrigin(
  process.env.SPORTABASE_WEB_CANONICAL_ORIGIN || "",
  "SPORTABASE_WEB_CANONICAL_ORIGIN"
);

const landingAnalyticsEnabled = readBoolean(
  "SPORTABASE_WEB_LANDING_ANALYTICS_ENABLED"
);

const cspDeploymentConfigured = readBoolean(
  "SPORTABASE_WEB_CSP_CONFIGURED"
);

if (deployment === "staging") {
  if (apiBase === PRODUCTION_API_ORIGIN) {
    throw new Error(
      "Staging must not use the production Sportabase API origin."
    );
  }

  if (!clerkPublishableKey.startsWith("pk_test_")) {
    throw new Error(
      "Staging requires SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY with a Clerk test key."
    );
  }
}

if (deployment === "production") {
  if (!clerkPublishableKey.startsWith("pk_live_")) {
    throw new Error(
      "Production requires SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY with a live Clerk key."
    );
  }

  if (!canonicalWebOrigin) {
    throw new Error(
      "Production requires SPORTABASE_WEB_CANONICAL_ORIGIN."
    );
  }

  if (!cspDeploymentConfigured) {
    throw new Error(
      "Production requires SPORTABASE_WEB_CSP_CONFIGURED=true."
    );
  }
}

const config = {
  apiBase,
  clerkPublishableKey,
  canonicalWebOrigin,
  deployment,
  landingAnalyticsEnabled,
  cspDeploymentConfigured,
};

const scriptsDir = fileURLToPath(
  new URL(".", import.meta.url)
);

const frontendDir = resolve(scriptsDir, "..");

const output = resolve(
  frontendDir,
  process.argv[2] || "product-config.mjs"
);

const contents =
  `// Generated deployment configuration. Public values only.\n` +
  `// No query-string overrides for authenticated API destinations.\n` +
  `export default Object.freeze(${JSON.stringify(config, null, 2)});\n`;

writeFileSync(output, contents, "utf8");

console.log(
  `Generated ${output} for ${deployment}.`
);