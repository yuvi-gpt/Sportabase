import test from "node:test";
import assert from "node:assert/strict";

import {
  ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
  normalizeArticleIntelligence,
} from "../article-intelligence.mjs";


test(
  "web normalizes verified corroboration",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status: "available",
        label:
          "Verified independent support",
        detail:
          "Independent support verified.",
        candidate_count: 5,
        verification_pairs: 3,
        corroboration_status:
          "established",
        independence_status:
          "established",
        contested: false,
        provisional: true,
        affects_merit_score: false,
      });

    assert.equal(
      result.status,
      "available"
    );

    assert.equal(
      result.candidateCount,
      5
    );

    assert.equal(
      result.independenceLabel,
      "Established"
    );

    assert.equal(
      result.affectsMeritScore,
      false
    );
  }
);


test(
  "web preserves unknown independence",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status: "available",
        corroboration_status:
          "not_established",
        independence_status:
          "unknown",
      });

    assert.equal(
      result.independenceStatus,
      "unknown"
    );

    assert.equal(
      result.independenceLabel,
      "Unknown"
    );
  }
);


test(
  "web supports unavailable evidence state",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status:
          "unavailable",
        label:
          "Evidence check unavailable",
        detail:
          "Temporarily unavailable.",
      });

    assert.equal(
      result.status,
      "unavailable"
    );
  }
);


test(
  "web rejects unknown contract version",
  () => {
    assert.equal(
      normalizeArticleIntelligence({
        version: "wrong",
        status: "available",
      }),
      null
    );
  }
);


test(
  "web hides missing intelligence",
  () => {
    assert.equal(
      normalizeArticleIntelligence(
        undefined
      ),
      null
    );
  }
);


test(
  "web does not infer Merit effect",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status: "available",
      });

    assert.equal(
      result.affectsMeritScore,
      false
    );
  }
);
