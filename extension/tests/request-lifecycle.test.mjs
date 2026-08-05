import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const lifecycleSource =
  await readFile(
    new URL(
      "../src/content/request-lifecycle.js",
      import.meta.url
    ),
    "utf8"
  );

const lifecycleModuleUrl = [
  "data:text/javascript;base64,",
  Buffer
    .from(lifecycleSource)
    .toString("base64"),
].join("");

const {
  createRequestLifecycle,
} = await import(
  lifecycleModuleUrl
);


test(
  "begin creates a current request",
  () => {
    const lifecycle =
      createRequestLifecycle();

    const request =
      lifecycle.begin();

    assert.equal(
      request.isCurrent(),
      true
    );

    assert.equal(
      lifecycle.hasActive(),
      true
    );
  }
);


test(
  "new request cancels stale request",
  () => {
    const lifecycle =
      createRequestLifecycle();

    const first =
      lifecycle.begin();

    const second =
      lifecycle.begin();

    assert.equal(
      first.signal.aborted,
      true
    );

    assert.equal(
      first.isCurrent(),
      false
    );

    assert.equal(
      second.isCurrent(),
      true
    );
  }
);


test(
  "cancel aborts the active request",
  () => {
    const lifecycle =
      createRequestLifecycle();

    const request =
      lifecycle.begin();

    lifecycle.cancel(
      "panel closed"
    );

    assert.equal(
      request.signal.aborted,
      true
    );

    assert.equal(
      request.isCurrent(),
      false
    );

    assert.equal(
      lifecycle.hasActive(),
      false
    );
  }
);


test(
  "finish clears completed request",
  () => {
    const lifecycle =
      createRequestLifecycle();

    const request =
      lifecycle.begin();

    request.finish();

    assert.equal(
      lifecycle.hasActive(),
      false
    );
  }
);


test(
  "article mode passes signal and suppresses cancelled errors",
  async () => {
    const source = await readFile(
      new URL(
        "../src/content/article-mode.js",
        import.meta.url
      ),
      "utf8"
    );

    assert.match(
      source,
      /signal:\s*analysisRequest\.signal/
    );

    assert.match(
      source,
      /shell\.onClose\?\.\(/
    );

    assert.match(
      source,
      /error\?\.cancelled/
    );
  }
);

test(
  "video mode passes signal and suppresses cancelled errors",
  async () => {
    const source = await readFile(
      new URL(
        "../src/content/video-mode.js",
        import.meta.url
      ),
      "utf8"
    );

    assert.match(
      source,
      /signal:\s*analysisRequest\.signal/
    );

    assert.match(
      source,
      /shell\.onClose\?\.\(/
    );

    assert.match(
      source,
      /error\?\.cancelled/
    );

    assert.match(
      source,
      /analysisRequest\.isCurrent\(\)/
    );
  }
);

