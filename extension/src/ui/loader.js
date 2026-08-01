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
  message = "Preparing the analysis…",
  progress = 12,
} = {}) {
  if (!container) {
    return {
      update() {},
      destroy() {},
    };
  }

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
            <div class="sb-loader-orbit"></div>

            <div class="sb-loader-core">
              SB
            </div>
          </div>

          <div class="sb-loader-brand-copy">
            <div class="sb-loader-title">
              Sportabase
            </div>

            <div class="sb-loader-mode">
              ${escapeHtml(modeLabel)}
            </div>
          </div>

          <div class="sb-loader-live-pill">
            <span></span>
            LIVE
          </div>
        </div>

        <div class="sb-loader-message-area">
          <div
            class="sb-loader-message"
            data-sb-loader-message
          >
            ${escapeHtml(message)}
          </div>

          <div class="sb-loader-progress-row">
            <div class="sb-loader-analyzing">
              <span></span>
              ANALYZING
            </div>

            <div
              class="sb-loader-stage-count"
              data-sb-loader-stage-count
            >
              Stage 1 of 3
            </div>
          </div>

          <div
            class="sb-loader-track"
            role="progressbar"
            aria-label="Sportabase analysis progress"
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
            <div
              class="sb-loader-stage"
              data-sb-loader-stage="0"
            >
              <span></span>
              Read
            </div>

            <div
              class="sb-loader-stage"
              data-sb-loader-stage="1"
            >
              <span></span>
              Evaluate
            </div>

            <div
              class="sb-loader-stage"
              data-sb-loader-stage="2"
            >
              <span></span>
              Distill
            </div>
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

  const stageElements = Array.from(
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
      Number.isFinite(numericProgress)
        ? Math.max(
            5,
            Math.min(
              95,
              Math.round(numericProgress)
            )
          )
        : 12;

    if (
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
      getStageIndex(safeProgress);

    if (stageCountElement) {
      stageCountElement.textContent =
        `Stage ${activeStage + 1} of 3`;
    }

    stageElements.forEach(
      (stageElement, index) => {
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
