import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";

import {
  createRequire,
} from "node:module";

import {
  fileURLToPath,
} from "node:url";


const require =
  createRequire(
    import.meta.url
  );

const {
  chromium,
} =
  require(
    "../../extension/node_modules/playwright"
  );


const AUDIT_DIR =
  path.dirname(
    fileURLToPath(
      import.meta.url
    )
  );

const FRONTEND_ROOT =
  path.resolve(
    AUDIT_DIR,
    ".."
  );

const OUTPUT_DIR =
  path.join(
    AUDIT_DIR,
    "checkpoint-1"
  );


const CONTENT_TYPES = {
  ".html":
    "text/html; charset=utf-8",

  ".css":
    "text/css; charset=utf-8",

  ".js":
    "application/javascript; charset=utf-8",

  ".mjs":
    "application/javascript; charset=utf-8",

  ".json":
    "application/json; charset=utf-8",

  ".png":
    "image/png",

  ".svg":
    "image/svg+xml",
};


function startServer() {
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
            const incoming =
              new URL(
                request.url || "/",
                "http://127.0.0.1"
              );

            const relative =
              incoming.pathname === "/"
                ? "index.html"
                : decodeURIComponent(
                    incoming.pathname.slice(1)
                  );

            const filePath =
              path.resolve(
                FRONTEND_ROOT,
                relative
              );

            if (
              filePath !==
                path.join(
                  FRONTEND_ROOT,
                  "index.html"
                )
              &&
              !filePath.startsWith(
                FRONTEND_ROOT
                + path.sep
              )
            ) {
              response.writeHead(
                403
              );

              response.end(
                "Forbidden"
              );

              return;
            }

            fs.readFile(
              filePath,
              (
                error,
                data
              ) => {
                if (error) {
                  response.writeHead(
                    404
                  );

                  response.end(
                    "Not found"
                  );

                  return;
                }

                const extension =
                  path.extname(
                    filePath
                  );

                response.writeHead(
                  200,
                  {
                    "content-type":
                      CONTENT_TYPES[
                        extension
                      ]
                      ||
                      "application/octet-stream",

                    "cache-control":
                      "no-store",
                  }
                );

                response.end(
                  data
                );
              }
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
            !address
            ||
            typeof address
              === "string"
          ) {
            reject(
              new Error(
                "Web snapshot server did not expose a TCP port."
              )
            );

            return;
          }

          resolve({
            server,

            url:
              `http://127.0.0.1:${address.port}`,
          });
        }
      );
    }
  );
}


async function configureRoutes(
  page
) {
  await page.route(
    "https://cdn.jsdelivr.net/**",
    async (
      route
    ) => {
      await route.fulfill({
        status: 200,

        contentType:
          "application/javascript",

        body:
          "window.Chart = class { constructor(){} destroy(){} };",
      });
    }
  );


  await page.route(
    "https://sportabase-api.onrender.com/**",
    async (
      route
    ) => {
      const url =
        route.request().url();

      if (
        url.endsWith(
          "/health"
        )
      ) {
        await route.fulfill({
          status: 200,

          contentType:
            "application/json",

          body:
            JSON.stringify({
              ok: true,
            }),
        });

        return;
      }

      if (
        url.includes(
          "/insights/cricket/ipl/chasing-bias"
        )
      ) {
        await route.fulfill({
          status: 200,

          contentType:
            "application/json",

          body:
            JSON.stringify({
              trend: null,

              latest_metrics: {},

              summary: {
                matches_analyzed: 0,
                current_signal_active:
                  false,
              },
            }),
        });

        return;
      }

      await route.fulfill({
        status: 404,

        contentType:
          "application/json",

        body:
          JSON.stringify({
            detail:
              "Not available in visual snapshot fixture.",
          }),
      });
    }
  );
}


async function capture({
  browser,
  url,
  name,
  viewport,
}) {
  const context =
    await browser.newContext({
      viewport,

      colorScheme:
        "dark",

      reducedMotion:
        "reduce",

      locale:
        "en-US",
    });

  const page =
    await context.newPage();

  try {
    await configureRoutes(
      page
    );

    await page.goto(
      url,
      {
        waitUntil:
          "networkidle",
      }
    );

    await page
      .locator(
        "#api-state.is-online"
      )
      .waitFor({
        state:
          "visible",

        timeout:
          10_000,
      });

    const headline =
      page.locator(
        ".hero h1"
      );

    assert.match(
      await headline.innerText(),
      /Sports reporting/i
    );

    await page.screenshot({
      path:
        path.join(
          OUTPUT_DIR,
          name
        ),

      fullPage:
        true,

      animations:
        "disabled",
    });

    console.log(
      "SNAPSHOT="
      + name
      + "|WIDTH="
      + viewport.width
      + "|HEIGHT="
      + viewport.height
    );
  }
  finally {
    await context.close();
  }
}


async function main() {
  fs.mkdirSync(
    OUTPUT_DIR,
    {
      recursive:
        true,
    }
  );

  const {
    server,
    url,
  } =
    await startServer();

  const browser =
    await chromium.launch({
      headless:
        true,
    });

  try {
    await capture({
      browser,
      url,
      name:
        "desktop.png",

      viewport: {
        width:
          1440,

        height:
          1000,
      },
    });

    await capture({
      browser,
      url,
      name:
        "mobile.png",

      viewport: {
        width:
          390,

        height:
          844,
      },
    });

    console.log(
      "WEB_APP_VISUAL_SNAPSHOTS=PASS"
    );
  }
  finally {
    await browser.close();

    await new Promise(
      (
        resolve
      ) => {
        server.close(
          resolve
        );
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
