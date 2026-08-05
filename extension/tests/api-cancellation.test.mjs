import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";


const source = await readFile(
  new URL(
    "../src/content/api.js",
    import.meta.url
  ),
  "utf8"
);

const moduleUrl = [
  "data:text/javascript;base64,",
  Buffer
    .from(source)
    .toString("base64"),
].join("");

const {
  postJson,
  SportabaseApiError,
} = await import(moduleUrl);


function installBrowserMocks() {
  const originals = {
    window: globalThis.window,
    chrome: globalThis.chrome,
    fetch: globalThis.fetch,
  };

  globalThis.window = {
    setTimeout:
      globalThis.setTimeout.bind(
        globalThis
      ),
    clearTimeout:
      globalThis.clearTimeout.bind(
        globalThis
      ),
  };

  globalThis.chrome = {
    storage: {
      local: {
        async get() {
          return {
            sportabaseClientId:
              "test-client",
          };
        },

        async set() {},
      },
    },
  };

  globalThis.fetch = (
    _url,
    options
  ) => new Promise(
    (_resolve, reject) => {
      options.signal.addEventListener(
        "abort",
        () => {
          const error =
            new Error("aborted");

          error.name = "AbortError";

          reject(error);
        },
        {
          once: true,
        }
      );
    }
  );

  return () => {
    if (
      originals.window === undefined
    ) {
      delete globalThis.window;
    } else {
      globalThis.window =
        originals.window;
    }

    if (
      originals.chrome === undefined
    ) {
      delete globalThis.chrome;
    } else {
      globalThis.chrome =
        originals.chrome;
    }

    globalThis.fetch =
      originals.fetch;
  };
}


test(
  "caller cancellation is marked as silent cancellation",
  async () => {
    const restore =
      installBrowserMocks();

    try {
      const controller =
        new AbortController();

      const request = postJson(
        "https://example.com/analyze",
        {
          text: "test",
        },
        {
          timeoutMs: 1000,
          signal: controller.signal,
        }
      );

      controller.abort();

      await assert.rejects(
        request,
        (error) => {
          assert.ok(
            error instanceof
              SportabaseApiError
          );

          assert.equal(
            error.status,
            499
          );

          assert.equal(
            error.cancelled,
            true
          );

          return true;
        }
      );
    } finally {
      restore();
    }
  }
);


test(
  "internal timeout remains a visible timeout error",
  async () => {
    const restore =
      installBrowserMocks();

    try {
      await assert.rejects(
        postJson(
          "https://example.com/analyze",
          {
            text: "test",
          },
          {
            timeoutMs: 5,
          }
        ),
        (error) => {
          assert.ok(
            error instanceof
              SportabaseApiError
          );

          assert.equal(
            error.status,
            408
          );

          assert.equal(
            error.cancelled,
            false
          );

          return true;
        }
      );
    } finally {
      restore();
    }
  }
);
