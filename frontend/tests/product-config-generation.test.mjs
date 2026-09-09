import assert from "node:assert/strict";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

const scriptPath = fileURLToPath(
  new URL(
    "../scripts/generate-product-config.mjs",
    import.meta.url
  )
);

function runGenerator(overrides = {}) {
  const env = { ...process.env };

  for (const name of Object.keys(env)) {
    if (name.startsWith("SPORTABASE_WEB_")) {
      delete env[name];
    }
  }

  Object.assign(env, overrides);

  const directory = mkdtempSync(
    join(
      tmpdir(),
      "sportabase-product-config-"
    )
  );

  const outputPath = join(
    directory,
    "product-config.mjs"
  );

  const result = spawnSync(
    process.execPath,
    [scriptPath, outputPath],
    {
      env,
      encoding: "utf8",
    }
  );

  const output = existsSync(outputPath)
    ? readFileSync(outputPath, "utf8")
    : "";

  rmSync(directory, {
    recursive: true,
    force: true,
  });

  return {
    status: result.status,
    stdout: result.stdout || "",
    stderr: result.stderr || "",
    output,
  };
}

function diagnostics(result) {
  return `${result.stdout}\n${result.stderr}`;
}

test(
  "staging requires an explicit API origin",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "staging",
      SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY:
        "pk_test_example",
    });

    assert.notEqual(result.status, 0);

    assert.match(
      diagnostics(result),
      /SPORTABASE_WEB_API_BASE is required/
    );
  }
);

test(
  "staging rejects the production API origin",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "staging",
      SPORTABASE_WEB_API_BASE:
        "https://sportabase-api.onrender.com",
      SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY:
        "pk_test_example",
    });

    assert.notEqual(result.status, 0);

    assert.match(
      diagnostics(result),
      /production Sportabase API/
    );
  }
);

test(
  "staging requires a Clerk test key",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "staging",
      SPORTABASE_WEB_API_BASE:
        "https://sportabase-staging-api.onrender.com",
    });

    assert.notEqual(result.status, 0);

    assert.match(
      diagnostics(result),
      /Clerk test key/
    );
  }
);

test(
  "staging rejects a live Clerk key",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "staging",
      SPORTABASE_WEB_API_BASE:
        "https://sportabase-staging-api.onrender.com",
      SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY:
        "pk_live_example",
    });

    assert.notEqual(result.status, 0);

    assert.match(
      diagnostics(result),
      /Clerk test key/
    );
  }
);

test(
  "staging succeeds with isolated destinations",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "staging",
      SPORTABASE_WEB_API_BASE:
        "https://sportabase-staging-api.onrender.com",
      SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY:
        "pk_test_example",
    });

    assert.equal(
      result.status,
      0,
      diagnostics(result)
    );

    assert.match(
      result.output,
      /"deployment": "staging"/
    );

    assert.match(
      result.output,
      /"apiBase": "https:\/\/sportabase-staging-api\.onrender\.com"/
    );

    assert.match(
      result.output,
      /"clerkPublishableKey": "pk_test_example"/
    );
  }
);

test(
  "production also requires an explicit API origin",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "production",
      SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY:
        "pk_live_example",
      SPORTABASE_WEB_CANONICAL_ORIGIN:
        "https://sportabase.example",
      SPORTABASE_WEB_CSP_CONFIGURED: "true",
    });

    assert.notEqual(result.status, 0);

    assert.match(
      diagnostics(result),
      /SPORTABASE_WEB_API_BASE is required/
    );
  }
);

test(
  "production preserves existing release gates",
  () => {
    const result = runGenerator({
      SPORTABASE_WEB_DEPLOYMENT: "production",
      SPORTABASE_WEB_API_BASE:
        "https://api.sportabase.example",
      SPORTABASE_WEB_CLERK_PUBLISHABLE_KEY:
        "pk_live_example",
      SPORTABASE_WEB_CANONICAL_ORIGIN:
        "https://sportabase.example",
      SPORTABASE_WEB_CSP_CONFIGURED: "true",
    });

    assert.equal(
      result.status,
      0,
      diagnostics(result)
    );

    assert.match(
      result.output,
      /"deployment": "production"/
    );

    assert.match(
      result.output,
      /"cspDeploymentConfigured": true/
    );
  }
);