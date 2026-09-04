import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";

const source = await readFile(
  new URL(
    "../src/content/reporting-profiles.js",
    import.meta.url
  ),
  "utf8"
);

test(
  "reporting profiles stay public read-only and score-free",
  () => {
    assert.match(
      source,
      /\/intelligence\/\$\{segment\}\/\$\{encodeURIComponent\(id\)\}\/history/
    );
    assert.doesNotMatch(source, /\/watchlists/);
    assert.doesNotMatch(source, /x-sportabase-client-id/i);
    assert.doesNotMatch(source, /reliability_score/i);
    assert.match(source, /NO RELIABILITY SCORE/);
  }
);

test(
  "reporting profiles preserve dependency and independence boundaries",
  () => {
    assert.match(source, /dependency relationship does not mean the reporting is false/i);
    assert.match(source, /Missing verified independence evidence is not evidence of dependence/i);
    assert.match(source, /Multiple sources do not automatically represent independent corroboration/i);
  }
);
