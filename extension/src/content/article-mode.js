import {
  extractArticlePage,
} from "./article-extractor.js";

import {
  postJson,
  SportabaseApiError,
} from "./api.js";

import {
  createAnalysisLoader,
} from "../ui/loader.js";

import {
  createRequestLifecycle,
} from "./request-lifecycle.js";

import {
  normalizeArticleIntelligence,
} from "./article-intelligence.mjs";

import {
  createAccentTheme,
  getScorePalette,
} from "../ui/accent-theme.js";

const ANALYSIS_STEPS = [
  {
    message: "Identifying the article's central story…",
    progress: 50,
  },
  {
    message: "Separating reporting from filler…",
    progress: 62,
  },
  {
    message: "Evaluating evidence and sourcing…",
    progress: 74,
  },
  {
    message: "Scoring substance and credibility…",
    progress: 86,
  },
  {
    message: "Distilling the final intelligence brief…",
    progress: 93,
  },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const MINIMUM_LOADER_DURATION = 3000;

function wait(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function waitForNextPaint() {
  return new Promise((resolve) => {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(resolve);
    });
  });
}

function clampScore(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(100, Math.round(numericValue))
  );
}

function humanizeLabel(value) {
  const normalized = String(
    value || "Article analysis"
  )
    .trim()
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\s+/g, " ");

  return normalized.replace(
    /\b\w/g,
    (character) => character.toUpperCase()
  );
}

function normalizeStringList(value) {
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (
          item &&
          typeof item === "object"
        ) {
          return String(
            item.text ||
            item.summary ||
            item.point ||
            item.claim ||
            item.label ||
            ""
          ).trim();
        }

        return String(item || "").trim();
      })
      .filter(Boolean);
  }

  if (typeof value === "string") {
    return value
      .split(/\n+|•|\u2022/)
      .map((item) =>
        item
          .replace(/^[-*]\s*/, "")
          .trim()
      )
      .filter(Boolean);
  }

  return [];
}

function getSummaryItems(data) {
  const candidates = [
    data.tldr,
    data.tl_dr,
    data.summary_bullets,
    data.bullets,
    data.key_points,
    data.summary,
  ];

  for (const candidate of candidates) {
    const items =
      normalizeStringList(candidate);

    if (items.length) {
      return items.slice(0, 5);
    }
  }

  return [
    "No summary bullets were returned.",
  ];
}

function getTags(data) {
  const candidates = [
    data.tags,
    data.entities,
    data.topics,
    data.teams,
  ];

  for (const candidate of candidates) {
    const tags =
      normalizeStringList(candidate);

    if (tags.length) {
      return tags.slice(0, 8);
    }
  }

  return [];
}

function getMeritScore(data) {
  return clampScore(
    data.merit_score ??
    data.score ??
    data.overall_score ??
    data.substance_score ??
    0
  );
}

function getReasonItems(data) {
  const candidates = [
    data.localized_reasons,
    data.reasons,
    data.reason,
    data.merit_reasons,
    data.merit_reason,
    data.score_reason,
    data.explanation,
    data.why_it_matters,
  ];

  for (const candidate of candidates) {
    const items =
      normalizeStringList(candidate);

    if (items.length) {
      return items.slice(0, 9);
    }
  }

  return [
    "No scoring explanation was returned.",
  ];
}

function getArticleType(data) {
  const localizedLabel = String(
    data.localized_article_type ||
    data.article_type_label ||
    ""
  ).trim();

  if (localizedLabel) {
    return localizedLabel;
  }

  return humanizeLabel(
    data.article_type ||
    data.content_type ||
    data.category ||
    data.story_type ||
    "Article analysis"
  );
}

const DEFAULT_ARTICLE_UI_LABELS =
  Object.freeze({
    article_intelligence:
      "ARTICLE INTELLIGENCE",
    merit_score:
      "MERIT SCORE",
    summary:
      "TL;DR",
    why_scored:
      "Why it scored this way",
    analyzed_story:
      "Analyzed story",
    article_overview:
      "Article overview",
    analyze_again:
      "Analyze again",
    characters_analyzed:
      "characters analyzed",
    content_blocks:
      "content blocks",
    analyzing:
      "ANALYZING",
    ready:
      "READY",
    limited:
      "LIMITED",
    unavailable:
      "UNAVAILABLE",
    retry_analysis:
      "Retry analysis",
    return_to_overview:
      "Return to article overview",
  });

function getArticleUiLabels(data) {
  const labels = {
    ...DEFAULT_ARTICLE_UI_LABELS,
  };

  const responseLabels =
    data?.ui_labels;

  if (
    !responseLabels ||
    typeof responseLabels !== "object"
  ) {
    return labels;
  }

  for (
    const key
    of Object.keys(labels)
  ) {
    const localizedValue = String(
      responseLabels[key] || ""
    ).trim();

    if (localizedValue) {
      labels[key] = localizedValue;
    }
  }

  return labels;
}


function validateArticleResponse(data) {
  if (
    !data ||
    typeof data !== "object"
  ) {
    throw new SportabaseApiError(
      "Sportabase returned an empty article analysis."
    );
  }

  const status = String(
    data.status || ""
  ).toLowerCase();

  const verdict = String(
    data.verdict || ""
  ).toLowerCase();

  if (
    status === "analysis_failed" ||
    verdict === "analysis_failed"
  ) {
    throw new SportabaseApiError(
      String(
        data.debug?.error ||
        data.error ||
        data.message ||
        "The AI analysis could not be completed."
      )
    );
  }

  return data;
}

function getFriendlyErrorMessage(error) {
  if (
    error instanceof SportabaseApiError
  ) {
    return error.message;
  }

  return (
    String(
      error?.message || error || ""
    ).trim() ||
    "Sportabase could not analyze this article right now."
  );
}

function getAnalyzeButtonMarkup(label) {
  return `
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3v18"></path>
      <path d="m17 8-5-5-5 5"></path>
    </svg>

    <span>${escapeHtml(label)}</span>
  `;
}


function getPageLanguageCode(article) {
  const candidates = [
    document
      .documentElement
      ?.lang,

    document
      .querySelector(
        'meta[property="og:locale"]'
      )
      ?.getAttribute(
        "content"
      ),

    document
      .querySelector(
        'meta[name="language"]'
      )
      ?.getAttribute(
        "content"
      ),

    document
      .querySelector(
        'meta[http-equiv="content-language"]'
      )
      ?.getAttribute(
        "content"
      ),
  ];

  for (
    const candidate
    of candidates
  ) {
    const normalized =
      String(
        candidate || ""
      )
        .trim()
        .toLowerCase()
        .replaceAll(
          "_",
          "-"
        );

    const languageCode =
      normalized
        .split("-")[0];

    if (
      /^[a-z]{2,3}$/.test(
        languageCode
      )
    ) {
      return languageCode
        .toUpperCase();
    }
  }

  /*
   * Script fallback for sites that do not
   * declare an HTML language.
   */
  const sample =
    String(
      article?.text || ""
    ).slice(
      0,
      4000
    );

  const scriptLanguages = [
    [
      /[\u0900-\u097f]/,
      "HI",
    ],
    [
      /[\u0980-\u09ff]/,
      "BN",
    ],
    [
      /[\u3040-\u30ff]/,
      "JA",
    ],
    [
      /[\uac00-\ud7af]/,
      "KO",
    ],
    [
      /[\u4e00-\u9fff]/,
      "ZH",
    ],
    [
      /[\u0600-\u06ff]/,
      "AR",
    ],
    [
      /[\u0400-\u04ff]/,
      "RU",
    ],
    [
      /[\u0370-\u03ff]/,
      "EL",
    ],
    [
      /[\u0590-\u05ff]/,
      "HE",
    ],
    [
      /[\u0e00-\u0e7f]/,
      "TH",
    ],
  ];

  for (
    const [
      pattern,
      languageCode,
    ]
    of scriptLanguages
  ) {
    if (
      pattern.test(sample)
    ) {
      return languageCode;
    }
  }

  return "SB";
}


export function openArticleMode({
  shell,
  config = {},
} = {}) {
  if (!shell?.content) return;

  let analysisRunning = false;
  let loadingTicker = null;

  const analysisRequests =
    createRequestLifecycle();

  const accentTheme =
    createAccentTheme(shell.overlay);


  function stopLoadingTicker() {
    if (!loadingTicker) return;

    window.clearInterval(
      loadingTicker
    );

    loadingTicker = null;
  }

  function cancelActiveAnalysis() {
    stopLoadingTicker();

    analysisRequests.cancel(
      "article mode closed"
    );

    analysisRunning = false;
  }

  shell.onClose?.(
    cancelActiveAnalysis
  );

  function getCurrentArticle() {
    const configuredLimit = Number(
      config.maxAnalyzeChars ||
      config.max_analyze_chars ||
      6000
    );

    return extractArticlePage({
      maxCharacters:
        Number.isFinite(configuredLimit)
          ? configuredLimit
          : 6000,
    });
  }

  function renderLanding() {
    stopLoadingTicker();
    accentTheme.clear();

    analysisRunning = false;

    const article =
      getCurrentArticle();

    const articleDetected =
      article.characterCount >= 300;

    shell.setModeLabel(
      articleDetected
        ? "ARTICLE INTELLIGENCE · READY"
        : "ARTICLE INTELLIGENCE · LIMITED"
    );

    shell.content.innerHTML = `
      <div class="sb-article-layout">
        <section class="sb-article-card">
          <div class="sb-article-card-header">
            <div class="sb-article-ready-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path
                  d="M6 3h9l4 4v14H6z"
                ></path>

                <path d="M14 3v5h5"></path>
                <path d="M9 13h6"></path>
                <path d="M9 17h6"></path>
              </svg>
            </div>

            <div class="sb-article-heading">
              <div class="sb-article-eyebrow">
                ${
                  articleDetected
                    ? "ARTICLE READY"
                    : "LIMITED TEXT"
                }
              </div>

              <h2>
                Evidence-first article intelligence
              </h2>
            </div>

            <div class="sb-article-detected-pill">
              <span></span>

              ${
                articleDetected
                  ? "DETECTED"
                  : "CHECK PAGE"
              }
            </div>
          </div>

          <div class="sb-article-context">
            <div class="sb-article-context-label">
              Current story
            </div>

            <div class="sb-article-title">
              ${escapeHtml(article.title)}
            </div>

            <div class="sb-article-source">
              ${escapeHtml(article.hostname)}
              ·
              ${article.characterCount.toLocaleString()}
              characters
            </div>
          </div>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-analyze
            ${
              articleDetected
                ? ""
                : "disabled"
            }
          >
            ${getAnalyzeButtonMarkup(
              articleDetected
                ? "Analyze article"
                : "Article text unavailable"
            )}
          </button>

          <p class="sb-data-disclosure">
            By analyzing, the page URL, title, and readable
            article text are sent to Sportabase and Google
            Gemini for analysis.
            <a
              href="https://yuvi-gpt.github.io/Sportabase/privacy.html"
              target="_blank"
              rel="noopener noreferrer"
            >
              Privacy policy
            </a>
          </p>

          <div class="sb-article-feature-grid">
            <div>
              <span>01</span>
              Summary
            </div>

            <div>
              <span>02</span>
              Merit
            </div>

            <div>
              <span>03</span>
              Evidence
            </div>
          </div>


        </section>

        <div class="sb-article-status">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path
              d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"
            ></path>

            <path d="m9 12 2 2 4-4"></path>
          </svg>

          <span>
            ${
              articleDetected
                ? "Sportabase found readable article text on this page."
                : "Open the full article page, then refresh and try again."
            }
          </span>
        </div>
      </div>
    `;

    if (articleDetected) {
      shell.content
        .querySelector(
          "[data-sb-article-analyze]"
        )
        ?.addEventListener(
          "click",
          runAnalysis
        );
    }

  }

  function renderError(error) {
    stopLoadingTicker();
    accentTheme.clear();

    analysisRunning = false;

    shell.setModeLabel(
      "ARTICLE INTELLIGENCE · UNAVAILABLE"
    );

    shell.content.innerHTML = `
      <div class="sb-article-state-layout">
        <section class="sb-article-error-card">
          <div class="sb-article-state-icon">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <circle
                cx="12"
                cy="12"
                r="9"
              ></circle>

              <path d="M12 8v5"></path>
              <path d="M12 16h.01"></path>
            </svg>
          </div>

          <div class="sb-article-state-eyebrow">
            ANALYSIS UNAVAILABLE
          </div>

          <h2>
            Sportabase could not finish this readout
          </h2>

          <p>
            ${escapeHtml(
              getFriendlyErrorMessage(error)
            )}
          </p>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-retry
          >
            ${getAnalyzeButtonMarkup(
              "Try again"
            )}
          </button>

          <button
            class="sb-secondary-button"
            type="button"
            data-sb-article-back
          >
            Return to article overview
          </button>
        </section>
      </div>
    `;

    shell.content
      .querySelector(
        "[data-sb-article-retry]"
      )
      ?.addEventListener(
        "click",
        runAnalysis
      );

    shell.content
      .querySelector(
        "[data-sb-article-back]"
      )
      ?.addEventListener(
        "click",
        renderLanding
      );
  }

  function renderResults(
    data,
    article
  ) {
    stopLoadingTicker();
    analysisRunning = false;

    const meritScore =
      getMeritScore(data);

    const scorePalette =
      getScorePalette(meritScore);

    const articleType =
      getArticleType(data);

    const uiLabels =
      getArticleUiLabels(data);

    const summaryItems =
      getSummaryItems(data);

    const tags =
      getTags(data);

    const reasonItems =
      getReasonItems(data);

    const intelligence =
      normalizeArticleIntelligence(
        data.intelligence
      );

    const intelligenceMarkup =
      intelligence
        ? `
          <section
            class="sb-article-intelligence-card ${
              intelligence.status ===
              "available"
                ? "is-available"
                : "is-unavailable"
            }"
          >
            <div class="sb-article-intelligence-head">
              <div>
                <div class="sb-article-section-label">
                  EVIDENCE INTELLIGENCE
                </div>

                <h3>
                  ${escapeHtml(
                    intelligence.label
                  )}
                </h3>
              </div>

              <div
                class="sb-article-intelligence-status"
              >
                ${
                  intelligence.status ===
                  "available"
                    ? "ASSESSED"
                    : "LIMITED"
                }
              </div>
            </div>

            ${
              intelligence.detail
                ? `
                  <p
                    class="sb-article-intelligence-detail"
                  >
                    ${escapeHtml(
                      intelligence.detail
                    )}
                  </p>
                `
                : ""
            }

            ${
              intelligence.status ===
              "available"
                ? `
                  <div
                    class="sb-article-intelligence-grid"
                  >
                    <div>
                      <span>
                        CORROBORATION
                      </span>

                      <strong>
                        ${escapeHtml(
                          intelligence
                            .corroborationLabel
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        INDEPENDENCE
                      </span>

                      <strong>
                        ${escapeHtml(
                          intelligence
                            .independenceLabel
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        SOURCES FOUND
                      </span>

                      <strong>
                        ${
                          intelligence
                            .candidateCount
                        }
                      </strong>
                    </div>

                    <div>
                      <span>
                        PAIRS CHECKED
                      </span>

                      <strong>
                        ${
                          intelligence
                            .verificationPairs
                        }
                      </strong>
                    </div>
                  </div>
                `
                : ""
            }

            <div
              class="sb-article-intelligence-note"
            >
              ${
                intelligence.affectsMeritScore
                  ? "Included in the displayed Merit Score."
                  : "Evidence signal is informational while Sportabase validation remains active; it does not alter the displayed Merit Score."
              }
            </div>
          </section>
        `
        : "";

    const summaryMarkup =
      summaryItems
        .map(
          (item) => `
            <li>
              ${escapeHtml(item)}
            </li>
          `
        )
        .join("");

    const reasonMarkup =
      reasonItems
        .map(
          (item) => `
            <li>
              ${escapeHtml(item)}
            </li>
          `
        )
        .join("");

    const tagsMarkup =
      tags.length
        ? `
            <div class="sb-article-tags">
              ${tags
                .map(
                  (tag) => `
                    <span>
                      ${escapeHtml(tag)}
                    </span>
                  `
                )
                .join("")}
            </div>
          `
        : "";

    accentTheme.apply(scorePalette);

    shell.setModeLabel(
      `${uiLabels.article_intelligence} ? ${articleType}`
    );

    shell.content.innerHTML = `
      <div class="sb-article-results">
        <section class="sb-article-score-card">
          <div class="sb-article-score-top">
            <div>
              <div class="sb-article-result-eyebrow">
                ${escapeHtml(
                  uiLabels.merit_score
                )}
              </div>

              <div class="sb-article-score">
                <strong>
                  ${meritScore}
                </strong>

                <span>/100</span>
              </div>
            </div>

            <div class="sb-article-type-pill">
              ${escapeHtml(articleType)}
            </div>
          </div>

          <div class="sb-article-score-track">
            <div
              style="width:${meritScore}%;"
            ></div>
          </div>

          <div class="sb-article-analysis-meta">
            ${article.characterCount.toLocaleString()}
            ${escapeHtml(
              uiLabels.characters_analyzed
            )} &middot;
            ${article.paragraphCount}
            ${escapeHtml(
              uiLabels.content_blocks
            )}
          </div>
        </section>

        <section class="sb-article-summary-card">
          <div class="sb-article-section-label">
            ${escapeHtml(
              uiLabels.summary
            )}
          </div>

          <ul>
            ${summaryMarkup}
          </ul>
        </section>

        <section class="sb-article-reason-card">
          <div class="sb-article-section-label">
            ${escapeHtml(
              uiLabels.why_scored
            )}
          </div>

          <ul>
            ${reasonMarkup}
          </ul>
        </section>

        ${intelligenceMarkup}

        ${tagsMarkup}

        <section class="sb-article-source-card">
          <div class="sb-article-section-label">
            ${escapeHtml(
              uiLabels.analyzed_story
            )}
          </div>

          <div class="sb-article-source-title">
            ${escapeHtml(article.title)}
          </div>

          <div class="sb-article-source-domain">
            ${escapeHtml(article.hostname)}
          </div>
        </section>

        <div class="sb-article-result-actions">
          <button
            class="sb-secondary-button"
            type="button"
            data-sb-article-overview
          >
            ${escapeHtml(
              uiLabels.article_overview
            )}
          </button>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-reanalyze
          >
            ${getAnalyzeButtonMarkup(
              uiLabels.analyze_again
            )}
          </button>
        </div>
      </div>
    `;

    shell.content
      .querySelector(
        "[data-sb-article-overview]"
      )
      ?.addEventListener(
        "click",
        renderLanding
      );

    shell.content
      .querySelector(
        "[data-sb-article-reanalyze]"
      )
      ?.addEventListener(
        "click",
        runAnalysis
      );
  }

  async function runAnalysis() {
    if (analysisRunning) return;

    analysisRunning = true;
    stopLoadingTicker();

    accentTheme.clear();

    const article =
      getCurrentArticle();

    if (article.characterCount < 300) {
      renderError(
        new SportabaseApiError(
          "Sportabase could not find enough readable article text on this page."
        )
      );

      return;
    }

    const pageLanguageCode =
      getPageLanguageCode(
        article
      );

    const sourceDomain =
      article.hostname ||
      window.location.hostname ||
      "Sportabase";

    shell.setModeLabel(
      `${sourceDomain} \u00B7 ${pageLanguageCode}`
    );

    const loader =
      createAnalysisLoader({
        container:
          shell.content,

        modeLabel:
          sourceDomain,

        message:
          article.title,

        progress:
          18,

        neutral:
          true,

        sourceTitle:
          article.title,

        sourceDomain,

        languageCode:
          pageLanguageCode,
      });

    const loaderStartedAt =
      performance.now();

    const analysisRequest =
      analysisRequests.begin();

    try {
      await waitForNextPaint();

      if (
        !analysisRequest.isCurrent()
      ) {
        return;
      }
      loader.update({
        message:
          "Article text found. Preparing the intelligence pass…",
        progress: 28,
      });

      await wait(320);

      if (
        !analysisRequest.isCurrent()
      ) {
        return;
      }

      let smoothProgress = 28;
      let loadingStepIndex = 0;

      loader.update({
        message:
          ANALYSIS_STEPS[
            loadingStepIndex
          ].message,
        progress: smoothProgress,
      });

      loadingTicker =
        window.setInterval(() => {
          if (smoothProgress >= 92) {
            return;
          }

          const increment =
            smoothProgress < 58
              ? 3
              : smoothProgress < 78
                ? 2
                : 1;

          smoothProgress = Math.min(
            92,
            smoothProgress + increment
          );

          while (
            loadingStepIndex <
              ANALYSIS_STEPS.length - 1 &&
            smoothProgress >=
              ANALYSIS_STEPS[
                loadingStepIndex + 1
              ].progress
          ) {
            loadingStepIndex += 1;
          }

          loader.update({
            message:
              ANALYSIS_STEPS[
                loadingStepIndex
              ].message,
            progress: smoothProgress,
          });
        }, 520);

      const apiBase = String(
        config.api ||
        "https://sportabase-api.onrender.com"
      ).replace(/\/+$/, "");

      const response = await postJson(
        `${apiBase}/analyze`,
        {
          title: article.title,
          url: article.url,
          text: article.text,
          max_bullets: 4,
        },
        {
          timeoutMs: 120000,
          signal:
            analysisRequest.signal,
        }
      );

      if (
        !analysisRequest.isCurrent()
      ) {
        return;
      }

      stopLoadingTicker();

      loader.update({
        message:
          "Finalizing your Sportabase article brief…",
        progress: 95,
      });

      const validatedResponse =
        validateArticleResponse(response);

      const loaderElapsed =
        performance.now() -
        loaderStartedAt;

      const remainingLoaderTime =
        Math.max(
          0,
          MINIMUM_LOADER_DURATION -
            loaderElapsed
        );

      await wait(remainingLoaderTime);

      if (
        !analysisRequest.isCurrent()
      ) {
        return;
      }

      loader.update({
        message:
          "Analysis complete. Opening your intelligence brief…",
        progress: 95,
      });

      await wait(420);

      if (
        !analysisRequest.isCurrent()
      ) {
        return;
      }

      renderResults(
        validatedResponse,
        article
      );
    } catch (error) {
      if (
        error?.cancelled ||
        !analysisRequest.isCurrent()
      ) {
        return;
      }

      console.error(
        "[sportabase] Article analysis failed:",
        error
      );

      renderError(error);
    } finally {
      analysisRequest.finish();

      if (
        !analysisRequests.hasActive()
      ) {
        analysisRunning = false;
      }
    }
  }

  renderLanding();
}
