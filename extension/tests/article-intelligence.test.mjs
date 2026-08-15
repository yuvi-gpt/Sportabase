import test from "node:test";
import assert from "node:assert/strict";

import {
  ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
  normalizeArticleIntelligence,
} from "../src/content/article-intelligence.mjs";


test(
  "normalizes verified corroboration",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status: "available",
        label:
          "Verified independent support",
        detail: "Verified.",
        candidate_count: 4,
        verification_pairs: 2,
        independence_status:
          "established",
        corroboration_status:
          "established",
        provisional: true,
        affects_merit_score: false,
      });

    assert.equal(
      result.status,
      "available"
    );

    assert.equal(
      result.candidateCount,
      4
    );

    assert.equal(
      result.verificationPairs,
      2
    );

    assert.equal(
      result.independenceLabel,
      "Established"
    );
  }
);


test(
  "keeps unknown independence explicit",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status: "available",
        independence_status:
          "unknown",
        corroboration_status:
          "not_established",
      });

    assert.equal(
      result.independenceStatus,
      "unknown"
    );
  }
);


test(
  "supports unavailable state",
  () => {
    const result =
      normalizeArticleIntelligence({
        version:
          ARTICLE_INTELLIGENCE_PUBLIC_VERSION,
        status: "unavailable",
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
  "rejects unknown public version",
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
  "missing intelligence remains hidden",
  () => {
    assert.equal(
      normalizeArticleIntelligence(
        null
      ),
      null
    );
  }
);


test(
  "public intelligence never implies merit effect by default",
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
