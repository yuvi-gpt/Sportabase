import assert from "node:assert/strict";
import test from "node:test";

import {
  assertBrowserDeployment,
} from "../deployment-config.mjs";

test(
  "browser deployment configuration fails closed off localhost",
  () => {
    assert.doesNotThrow(() =>
      assertBrowserDeployment(
        { deployment: "development" },
        new URL("http://localhost:4173/")
      )
    );

    assert.throws(
      () =>
        assertBrowserDeployment(
          { deployment: "development" },
          new URL("https://sportabase.example/")
        ),
      /explicit/
    );

    assert.throws(
      () =>
        assertBrowserDeployment(
          {
            deployment: "staging",
            clerkPublishableKey: "",
            apiBase:
              "https://sportabase-staging-api.onrender.com",
          },
          new URL(
            "https://staging.sportabase.example/"
          )
        ),
      /Staging Clerk/
    );

    assert.throws(
      () =>
        assertBrowserDeployment(
          {
            deployment: "staging",
            clerkPublishableKey: "pk_test_x",
            apiBase:
              "https://sportabase-api.onrender.com",
          },
          new URL(
            "https://staging.sportabase.example/"
          )
        ),
      /production Sportabase API/
    );

    assert.doesNotThrow(() =>
      assertBrowserDeployment(
        {
          deployment: "staging",
          clerkPublishableKey: "pk_test_x",
          apiBase:
            "https://sportabase-staging-api.onrender.com",
        },
        new URL(
          "https://staging.sportabase.example/"
        )
      )
    );

    assert.throws(
      () =>
        assertBrowserDeployment(
          {
            deployment: "production",
            clerkPublishableKey: "pk_test_x",
            canonicalWebOrigin:
              "https://sportabase.example",
            apiBase: "https://api.example",
          },
          new URL(
            "https://sportabase.example/"
          )
        ),
      /Clerk/
    );

    assert.throws(
      () =>
        assertBrowserDeployment(
          {
            deployment: "production",
            clerkPublishableKey: "pk_live_x",
            canonicalWebOrigin:
              "https://sportabase.example",
            apiBase: "https://api.example",
          },
          new URL(
            "https://sportabase.example/"
          )
        ),
      /CSP/
    );

    assert.doesNotThrow(() =>
      assertBrowserDeployment(
        {
          deployment: "production",
          clerkPublishableKey: "pk_live_x",
          canonicalWebOrigin:
            "https://sportabase.example",
          apiBase: "https://api.example",
          cspDeploymentConfigured: true,
        },
        new URL(
          "https://sportabase.example/"
        )
      )
    );
  }
);