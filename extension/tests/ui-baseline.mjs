import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

import {
  fileURLToPath,
} from "node:url";

import {
  chromium,
} from "playwright";


const TEST_DIR = path.dirname(
  fileURLToPath(
    import.meta.url
  )
);

const EXTENSION_ROOT = path.resolve(
  TEST_DIR,
  ".."
);

const BASELINE_DIR = path.join(
  EXTENSION_ROOT,
  "ui-audit",
  "baseline"
);


const ARTICLE_HTML = `
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sportabase Controlled Article</title>
</head>

<body>
  <main>
    <article>
      <h1>
        Arsenal complete major summer signing after weeks of negotiations
      </h1>

      <p>
        Arsenal have completed the signing of a senior international
        player following several weeks of negotiations between the clubs.
        The agreement was formally announced after the player completed
        a medical examination and signed a long-term contract.
      </p>

      <p>
        The club said the player will join first-team training immediately.
        The sporting director described the deal as part of the club's
        longer-term squad plan, while the manager said the new arrival
        adds experience, technical quality and tactical flexibility.
      </p>

      <p>
        The transfer had previously been discussed by several publications,
        although the club did not publicly confirm negotiations until its
        formal announcement. Supporters are expected to see the player
        presented before the team's next pre-season fixture.
      </p>

      <p>
        This controlled local article exists only for Sportabase visual
        baseline testing. It contains sufficient readable text for the
        extension to render the normal article-ready interface without
        contacting the Sportabase API or Google Gemini.
      </p>
    </article>
  </main>
</body>
</html>
`;


const VIDEO_HTML = `
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sportabase Controlled Video</title>
</head>

<body>
  <ytd-watch-flexy>
    <main>
      <h1>
        <yt-formatted-string>
          Transfer window analysis: what actually happened
        </yt-formatted-string>
      </h1>

      <div id="description">
        <yt-formatted-string>
          Controlled YouTube-style fixture used only
          for Sportabase visual baseline testing.
        </yt-formatted-string>
      </div>
    </main>
  </ytd-watch-flexy>
</body>
</html>
`;


function startFixtureServer() {
  return new Promise(
    (
      resolve,
      reject
    ) => {
      const server =
        http.createServer(
          (
            request,
            response
          ) => {
            const url =
              new URL(
                request.url || "/",
                "http://127.0.0.1"
              );

            const body =
              url.pathname === "/video"
                ? VIDEO_HTML
                : ARTICLE_HTML;

            response.writeHead(
              200,
              {
                "content-type":
                  "text/html; charset=utf-8",

                "cache-control":
                  "no-store",
              }
            );

            response.end(
              body
            );
          }
        );

      server.once(
        "error",
        reject
      );

      server.listen(
        0,
        "127.0.0.1",
        () => {
          const address =
            server.address();

          if (
            !address ||
            typeof address === "string"
          ) {
            reject(
              new Error(
                "Fixture server did not expose a TCP port."
              )
            );

            return;
          }

          resolve({
            server,

            baseUrl:
              `http://127.0.0.1:${address.port}`,
          });
        }
      );
    }
  );
}


function buildTemporaryExtension() {
  const extensionDir =
    fs.mkdtempSync(
      path.join(
        os.tmpdir(),
        "sportabase-ui-extension-"
      )
    );

  const requiredEntries = [
    "manifest.json",
    "background.js",
    "dist",
    "icons",
    "assets",
  ];

  for (
    const entry
    of requiredEntries
  ) {
    const source =
      path.join(
        EXTENSION_ROOT,
        entry
      );

    if (
      !fs.existsSync(
        source
      )
    ) {
      throw new Error(
        `Required extension entry missing: ${entry}`
      );
    }

    fs.cpSync(
      source,
      path.join(
        extensionDir,
        entry
      ),
      {
        recursive: true,
      }
    );
  }

  const manifestPath =
    path.join(
      extensionDir,
      "manifest.json"
    );

  const manifest =
    JSON.parse(
      fs.readFileSync(
        manifestPath,
        "utf8"
      )
    );

  manifest.host_permissions = [
    ...new Set([
      ...(
        manifest.host_permissions ||
        []
      ),

      "http://127.0.0.1/*",
    ]),
  ];

  fs.writeFileSync(
    manifestPath,
    JSON.stringify(
      manifest,
      null,
      2
    )
    + "\n",
    "utf8"
  );

  return extensionDir;
}


async function waitForExtensionWorker(
  context
) {
  let [
    worker,
  ] = context.serviceWorkers();

  if (!worker) {
    worker =
      await context.waitForEvent(
        "serviceworker",
        {
          timeout: 15_000,
        }
      );
  }

  assert.ok(
    worker.url().startsWith(
      "chrome-extension://"
    ),
    "Manifest V3 service worker did not load."
  );

  return worker;
}


async function injectSportabase({
  page,
  worker,
}) {
  const pageUrl =
    page.url();

  const tabId =
    await worker.evaluate(
      async (
        expectedUrl
      ) => {
        const tabs =
          await chrome.tabs.query({});

        const exact =
          tabs.find(
            (
              tab
            ) =>
              tab.url ===
              expectedUrl
          );

        return exact?.id ?? null;
      },
      pageUrl
    );

  assert.ok(
    tabId,
    `Could not resolve Chromium tab for ${pageUrl}`
  );

  const bootConfig = {
    api:
      "http://127.0.0.1:9",

    maxArticleChars:
      6000,

    cacheTtlMs:
      21_600_000,

    fetchTimeoutMs:
      1000,

    preferences: {
      sportabaseAppearance:
        "dark",

      sportabaseAccentMode:
        "custom",

      sportabaseAccentColor:
        "#1ed760",

      sportabaseGlowLevel:
        "reduced",

      sportabaseMotionLevel:
        "reduced",

      sportabaseHighContrast:
        false,

      sportabaseTextScale:
        "medium",

      sportabaseDensity:
        "comfortable",

      sportabasePanelPosition:
        "top-right",

      sportabaseSizeMode:
        "comfort",

      sportabaseCustomWidth:
        null,

      sportabaseCustomHeight:
        null,

      sportabaseLeft:
        null,

      sportabaseTop:
        null,

      sportabaseRememberPosition:
        false,

      sportabaseDetailLevel:
        "full",

      sportabaseAutoTranscript:
        false,

      sportabaseRememberSections:
        false,

      sportabaseKeepOpenOnNavigation:
        false,
    },
  };

  await worker.evaluate(
    async ({
      id,
      config,
    }) => {
      await chrome.scripting.executeScript({
        target: {
          tabId: id,
        },

        func: (
          bootConfig
        ) => {
          globalThis
            .__SPORTABASE_BOOT_CONFIG__ =
            bootConfig;
        },

        args: [
          config,
        ],
      });

      await chrome.scripting.insertCSS({
        target: {
          tabId: id,
        },

        files: [
          "dist/content.css",
        ],
      });

      await chrome.scripting.executeScript({
        target: {
          tabId: id,
        },

        files: [
          "dist/content.js",
        ],
      });
    },
    {
      id: tabId,
      config: bootConfig,
    }
  );

  const root =
    page.locator(
      "#sportabase-root"
    );

  await root.waitFor({
    state:
      "visible",

    timeout:
      15_000,
  });

  return root;
}


async function captureArticleBaseline({
  context,
  worker,
  baseUrl,
}) {
  const page =
    await context.newPage();

  try {
    await page.goto(
      `${baseUrl}/article`,
      {
        waitUntil:
          "domcontentloaded",
      }
    );

    const root =
      await injectSportabase({
        page,
        worker,
      });

    const text =
      await root.innerText();

    assert.match(
      text,
      /ARTICLE INTELLIGENCE/i
    );

    assert.match(
      text,
      /ARTICLE READY/i
    );

    assert.match(
      text,
      /Analyze article/i
    );

    await root.screenshot({
      path:
        path.join(
          BASELINE_DIR,
          "article-landing.png"
        ),

      animations:
        "disabled",
    });

    const settingsButton =
      root.locator(
        "[data-sb-settings]"
      );

    await settingsButton.click();

    const settingsLayer =
      root.locator(
        ".sb-settings-layer"
      );

    await settingsLayer.waitFor({
      state:
        "visible",

      timeout:
        5_000,
    });

    await page.waitForFunction(
      () =>
        document
          .querySelector(
            "#sportabase-root [data-sb-settings]"
          )
          ?.getAttribute(
            "aria-expanded"
          )
        === "true"
    );

    const settingsText =
      await settingsLayer.innerText();

    assert.match(
      settingsText,
      /Configure your Sportabase workspace/i
    );

    await root.screenshot({
      path:
        path.join(
          BASELINE_DIR,
          "article-settings.png"
        ),

      animations:
        "disabled",
    });

    console.log(
      "ARTICLE_BASELINE=PASS"
    );

    console.log(
      "SETTINGS_BASELINE=PASS"
    );
  }
  finally {
    await page.close();
  }
}


async function captureVideoBaseline({
  context,
  worker,
  baseUrl,
}) {
  const page =
    await context.newPage();

  try {
    await page.goto(
      `${baseUrl}/video`,
      {
        waitUntil:
          "domcontentloaded",
      }
    );

    const root =
      await injectSportabase({
        page,
        worker,
      });

    const text =
      await root.innerText();

    assert.match(
      text,
      /VIDEO INTELLIGENCE/i
    );

    assert.match(
      text,
      /VIDEO READY/i
    );

    assert.match(
      text,
      /Analyze video/i
    );

    await root.screenshot({
      path:
        path.join(
          BASELINE_DIR,
          "video-landing.png"
        ),

      animations:
        "disabled",
    });

    console.log(
      "VIDEO_BASELINE=PASS"
    );
  }
  finally {
    await page.close();
  }
}


async function main() {
  fs.mkdirSync(
    BASELINE_DIR,
    {
      recursive:
        true,
    }
  );

  const {
    server,
    baseUrl,
  } =
    await startFixtureServer();

  const extensionDir =
    buildTemporaryExtension();

  const profileDir =
    fs.mkdtempSync(
      path.join(
        os.tmpdir(),
        "sportabase-ui-profile-"
      )
    );

  let context;

  try {
    context =
      await chromium
        .launchPersistentContext(
          profileDir,
          {
            channel:
              "chromium",

            headless:
              true,

            viewport: {
              width:
                1440,

              height:
                1000,
            },

            colorScheme:
              "dark",

            reducedMotion:
              "reduce",

            args: [
              `--disable-extensions-except=${extensionDir}`,
              `--load-extension=${extensionDir}`,
            ],
          }
        );

    const worker =
      await waitForExtensionWorker(
        context
      );

    console.log(
      "EXTENSION_SERVICE_WORKER="
      + worker.url()
    );

    await captureArticleBaseline({
      context,
      worker,
      baseUrl,
    });

    await captureVideoBaseline({
      context,
      worker,
      baseUrl,
    });

    console.log(
      "PLAYWRIGHT_EXTENSION_BASELINE=PASS"
    );
  }
  finally {
    if (context) {
      await context.close();
    }

    await new Promise(
      (
        resolve
      ) => {
        server.close(
          resolve
        );
      }
    );

    fs.rmSync(
      extensionDir,
      {
        recursive:
          true,

        force:
          true,
      }
    );

    fs.rmSync(
      profileDir,
      {
        recursive:
          true,

        force:
          true,
      }
    );
  }
}


main().catch(
  (
    error
  ) => {
    console.error(
      error
    );

    process.exitCode =
      1;
  }
);
