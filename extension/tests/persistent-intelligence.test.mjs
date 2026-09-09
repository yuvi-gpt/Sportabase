import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  filterAlertsForTarget,
  historyRelations,
  mediaItemIdForUrl,
  normalizeCanonicalAnalysisUrl,
} from "../src/content/persistent-intelligence-core.mjs";


test(
  "canonical URL normalization matches Sportabase tracking and query policy",
  () => {
    assert.equal(
      normalizeCanonicalAnalysisUrl(
        "https://Example.com/path//to///story/?utm_source=x&b=2&a=1#section"
      ),
      "https://example.com/path/to/story?a=1&b=2"
    );
  }
);


test(
  "YouTube variants normalize to one canonical watch URL",
  () => {
    const expected =
      "https://youtube.com/watch?v=dQw4w9WgXcQ";

    assert.equal(
      normalizeCanonicalAnalysisUrl(
        "https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share"
      ),
      expected
    );

    assert.equal(
      normalizeCanonicalAnalysisUrl(
        "https://youtu.be/dQw4w9WgXcQ?t=42"
      ),
      expected
    );
  }
);


test(
  "media item IDs match backend SHA-256 identity derivation",
  async () => {
    assert.equal(
      await mediaItemIdForUrl(
        "https://youtu.be/dQw4w9WgXcQ?t=42"
      ),
      "8353913ab175b5d7cba85c1fc3dbe6fbdd7c65d6e27ff667457d26ebf23a8ccb"
    );
  }
);


test(
  "story history exposes only canonical claim and media relations",
  () => {
    const relations = historyRelations(
      "story",
      {
        claims: [
          {
            id: "claim-1",
            canonical_text:
              "Player will join Club A",
            claim_type: "transfer",
          },
        ],
        media: [
          {
            id: "media-1",
            title: "Report title",
            mode: "article",
          },
        ],
        events: [],
      }
    );

    assert.deepEqual(
      relations.map((item) => [
        item.kind,
        item.id,
      ]),
      [
        ["claim", "claim-1"],
        ["media", "media-1"],
      ]
    );
  }
);


test(
  "alert filtering is exact on both canonical kind and target ID",
  () => {
    const alerts = [
      {
        id: "a1",
        target_kind: "story",
        target_id: "story-1",
      },
      {
        id: "a2",
        target_kind: "story",
        target_id: "story-2",
      },
      {
        id: "a3",
        target_kind: "claim",
        target_id: "story-1",
      },
    ];

    assert.deepEqual(
      filterAlertsForTarget(
        alerts,
        {
          kind: "story",
          id: "story-1",
        }
      ).map((item) => item.id),
      ["a1"]
    );
  }
);


test(
  "video results never collapse evidence logic and verdict into a composite",
  () => {
    const source = readFileSync(
      new URL("../src/content/video-mode.js", import.meta.url),
      "utf8"
    );

    assert.doesNotMatch(source, /supportScore|OVERALL SUPPORT/);
    assert.match(source, /evidenceScore/);
    assert.match(source, /logicScore/);
    assert.match(source, /verdictLabel/);
  }
);
