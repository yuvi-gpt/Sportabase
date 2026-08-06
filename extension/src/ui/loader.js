import {
  getSportabaseLogoMarkup,
} from "./logo.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getStageIndex(progress) {
  if (progress < 42) return 0;
  if (progress < 76) return 1;

  return 2;
}

export function createAnalysisLoader({
  container,
  modeLabel = "VIDEO INTELLIGENCE",
  message = "Preparing the analysis\u2026",
  progress = 12,

  neutral = false,
  sourceTitle = "",
  sourceDomain = "",
  languageCode = "",
} = {}) {
  if (!container) {
    return {
      update() {},
      destroy() {},
    };
  }

  const neutralMode =
    Boolean(neutral);

  const safeTitle =
    String(
      sourceTitle ||
      message ||
      ""
    ).trim();

  const safeDomain =
    String(
      sourceDomain ||
      modeLabel ||
      ""
    ).trim();

  const safeLanguageCode =
    String(
      languageCode ||
      "SB"
    )
      .trim()
      .slice(0, 5)
      .toUpperCase();

  const visibleModeLabel =
    neutralMode && safeDomain
      ? safeDomain
      : modeLabel;

  const visibleMessage =
    neutralMode && safeTitle
      ? safeTitle
      : message;

  const liveLabel =
    neutralMode
      ? safeLanguageCode
      : "LIVE";

  const analyzingLabel =
    neutralMode
      ? safeDomain
      : "ANALYZING";

  const firstStageCount =
    neutralMode
      ? `${Math.round(progress)}%`
      : "Stage 1 of 3";

  const stageLabels =
    neutralMode
      ? ["1", "2", "3"]
      : [
          "Read",
          "Evaluate",
          "Distill",
        ];

  const progressAriaLabel =
    neutralMode && safeTitle
      ? safeTitle
      : "Sportabase analysis progress";

  container.innerHTML = `
    <div class="sb-analysis-loader">
      <div
        class="sb-loader-ambient"
        aria-hidden="true"
      ></div>

      <section
        class="sb-loader-card"
        role="status"
        aria-live="polite"
      >
        <div class="sb-loader-brand-row">
          <div
            class="sb-loader-symbol"
            aria-hidden="true"
          >
            <div
              class="
                sb-loader-orbit
                sb-loader-orbit-outer
              "
            ></div>

            <div
              class="
                sb-loader-orbit
                sb-loader-orbit-inner
              "
            ></div>

            <div
              class="sb-loader-scan-wave"
            ></div>

            <span
              class="
                sb-loader-signal
                sb-loader-signal-a
              "
            ></span>

            <span
              class="
                sb-loader-signal
                sb-loader-signal-b
              "
            ></span>

            ${getSportabaseLogoMarkup({
              className:
                "sb-loader-logo",
            })}
          </div>

          <div class="sb-loader-brand-copy">
            <div class="sb-loader-title">
              Sportabase
            </div>

            <div class="sb-loader-mode">
              ${escapeHtml(
                visibleModeLabel
              )}
            </div>
          </div>

          <div class="sb-loader-live-pill">
            <span></span>

            ${escapeHtml(
              liveLabel
            )}
          </div>
        </div>

        <div class="sb-loader-message-area">
          <div
            class="sb-loader-message"
            data-sb-loader-message
          >
            ${escapeHtml(
              visibleMessage
            )}
          </div>

          <div class="sb-loader-progress-row">
            <div class="sb-loader-analyzing">
              <span></span>

              ${escapeHtml(
                analyzingLabel
              )}
            </div>

            <div
              class="sb-loader-stage-count"
              data-sb-loader-stage-count
            >
              ${escapeHtml(
                firstStageCount
              )}
            </div>
          </div>

          <div
            class="sb-loader-track"
            role="progressbar"
            aria-label="${escapeHtml(
              progressAriaLabel
            )}"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow="${progress}"
            data-sb-loader-track
          >
            <div
              class="sb-loader-bar"
              data-sb-loader-bar
              style="width:${progress}%;"
            ></div>
          </div>

          <div class="sb-loader-stages">
            ${stageLabels
              .map(
                (
                  stageLabel,
                  index
                ) => `
                  <div
                    class="sb-loader-stage"
                    data-sb-loader-stage="${index}"
                  >
                    <span></span>

                    ${escapeHtml(
                      stageLabel
                    )}
                  </div>
                `
              )
              .join("")}
          </div>
        </div>
      </section>
    </div>
  `;

  const messageElement =
    container.querySelector(
      "[data-sb-loader-message]"
    );

  const barElement =
    container.querySelector(
      "[data-sb-loader-bar]"
    );

  const trackElement =
    container.querySelector(
      "[data-sb-loader-track]"
    );

  const stageCountElement =
    container.querySelector(
      "[data-sb-loader-stage-count]"
    );

  const stageElements =
    Array.from(
      container.querySelectorAll(
        "[data-sb-loader-stage]"
      )
    );

  function update({
    message: nextMessage,
    progress: nextProgress,
  } = {}) {
    const numericProgress =
      Number(nextProgress);

    const safeProgress =
      Number.isFinite(
        numericProgress
      )
        ? Math.max(
            5,
            Math.min(
              95,
              Math.round(
                numericProgress
              )
            )
          )
        : 12;

    /*
     * Article Mode keeps the original
     * source-language headline visible
     * throughout the loading experience.
     */
    if (
      !neutralMode &&
      nextMessage !== undefined &&
      messageElement
    ) {
      messageElement.textContent =
        String(nextMessage);
    }

    if (barElement) {
      barElement.style.width =
        `${safeProgress}%`;
    }

    if (trackElement) {
      trackElement.setAttribute(
        "aria-valuenow",
        String(safeProgress)
      );
    }

    const activeStage =
      getStageIndex(
        safeProgress
      );

    if (stageCountElement) {
      stageCountElement.textContent =
        neutralMode
          ? `${safeProgress}%`
          : (
              `Stage ${
                activeStage + 1
              } of 3`
            );
    }

    stageElements.forEach(
      (
        stageElement,
        index
      ) => {
        stageElement.classList.remove(
          "sb-loader-stage-active",
          "sb-loader-stage-complete"
        );

        if (index < activeStage) {
          stageElement.classList.add(
            "sb-loader-stage-complete"
          );
        }

        if (index === activeStage) {
          stageElement.classList.add(
            "sb-loader-stage-active"
          );
        }
      }
    );
  }

  update({
    message,
    progress,
  });

  return {
    update,

    destroy() {
      container.innerHTML = "";
    },
  };
}
