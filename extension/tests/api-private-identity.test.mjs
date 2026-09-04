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
  getSportabaseClientId,
  SportabaseApiError,
} = await import(moduleUrl);


test(
  "storage failure never collapses private identity to anonymous",
  async () => {
    const originalChrome =
      globalThis.chrome;

    globalThis.chrome = {
      storage: {
        local: {
          async get() {
            throw new Error(
              "storage unavailable"
            );
          },
          async set() {
            throw new Error(
              "storage unavailable"
            );
          },
        },
      },
    };

    try {
      const transientId =
        await getSportabaseClientId();

      assert.ok(transientId);
      assert.notEqual(
        transientId,
        "anonymous"
      );

      await assert.rejects(
        getSportabaseClientId({
          requirePersistent: true,
        }),
        (error) => {
          assert.ok(
            error instanceof
              SportabaseApiError
          );
          assert.match(
            error.message,
            /require Chrome extension storage/i
          );
          return true;
        }
      );
    } finally {
      if (
        originalChrome === undefined
      ) {
        delete globalThis.chrome;
      } else {
        globalThis.chrome =
          originalChrome;
      }
    }
  }
);
