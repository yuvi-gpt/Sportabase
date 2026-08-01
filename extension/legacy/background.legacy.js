const API = "http://127.0.0.1:8000";
// const API = "https://sportabase-api.onrender.com"; // switch back after Render deploy

// Performance controls
const MAX_ARTICLE_CHARS = 6000;
const CACHE_TTL_MS = 1000 * 60 * 60 * 6; // 6 hours
const FETCH_TIMEOUT_MS = 22000; // 22 seconds

async function injectAndRun(tabId) {
  const prefs = await chrome.storage.local.get({
    // Appearance
    sportabaseAppearance: "system",
    sportabaseAccentMode: "dynamic",
    sportabaseAccentColor: "#1ed760",
    sportabaseGlowLevel: "reduced",
    sportabaseMotionLevel: "full",
    sportabaseHighContrast: false,

    // Typography and spacing
    sportabaseTextScale: "medium",
    sportabaseDensity: "comfortable",

    // Panel
    sportabaseSizeMode: "comfort",
    sportabaseCustomWidth: null,
    sportabaseCustomHeight: null,
    sportabaseLeft: null,
    sportabaseTop: null,
    sportabaseRememberPosition: true,

    // Content behaviour
    sportabaseDetailLevel: "full",
    sportabaseAutoTranscript: true,
    sportabaseRememberSections: true,
    sportabaseKeepOpenOnNavigation: false,
  });

  await chrome.scripting.executeScript({
    target: { tabId },
    func: async (API, prefs, config) => {
      const log = (...args) => console.log("[sportabase]", ...args);
      const MAX_ARTICLE_CHARS = config?.MAX_ARTICLE_CHARS ?? 6000;
      const CACHE_TTL_MS = config?.CACHE_TTL_MS ?? 1000 * 60 * 60 * 6;
      const FETCH_TIMEOUT_MS = config?.FETCH_TIMEOUT_MS ?? 22000;

      function getReadableText() {
        const candidates = [
          "article",
          "main article",
          "main",
          "section article",
          "div[data-testid='Body']",
          "div[data-testid='article-body']",
          ".Story__Body",
          ".story__body",
          ".article-body",
          ".RichTextContainer",
          ".Article__Content",
          ".article__content",
          "[data-module='ArticleBody']",
        ];

        let root = null;

        for (const sel of candidates) {
          const el = document.querySelector(sel);
          if (el && (el.innerText || "").trim().length > 400) {
            root = el;
            break;
          }
        }

        if (!root) {
          const blocks = Array.from(
            document.querySelectorAll("article, main, section, div")
          )
            .map((el) => {
              const ps = el.querySelectorAll("p");
              let pTextLen = 0;
              ps.forEach((p) => {
                pTextLen += (p.innerText || "").trim().length;
              });
              return { el, pCount: ps.length, pTextLen };
            })
            .filter((x) => x.pCount >= 3 && x.pTextLen >= 600)
            .sort((a, b) => b.pTextLen - a.pTextLen);

          if (blocks.length) root = blocks[0].el;
        }

        if (!root) root = document.body;

        const junkSelectors = [
          "nav",
          "header",
          "footer",
          "aside",
          "[role='navigation']",
          ".nav",
          ".navbar",
          ".menu",
          ".subscribe",
          ".subscription",
          ".paywall",
          ".modal",
          ".popup",
          ".cookie",
          ".cookies",
          "#cookie",
          "#cookies",
          ".comments",
          "#comments",
          ".ad",
          ".ads",
          ".advertisement",
          "[class*='advert']",
          "[id*='advert']",
          "script",
          "style",
          "noscript",
          "svg",
        ];

        const clone = root.cloneNode(true);

        junkSelectors.forEach((sel) => {
          clone.querySelectorAll(sel).forEach((el) => el.remove());
        });

        const ps = Array.from(clone.querySelectorAll("p"))
          .map((p) => (p.innerText || "").trim())
          .filter((t) => t.length > 40);

        let text = "";
        if (ps.length >= 3) {
          text = ps.join(" ");
        } else {
          text = clone.innerText || "";
        }

        return text.replace(/\s+/g, " ").trim();
      }

      function escapeHtml(value) {
        return String(value ?? "")
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      const ARTICLE_LABEL_MAP = {
        match_report: "Match Report",
        live_commentary: "Live Commentary",
        official_announcement: "Official Announcement",
        transfer_official: "Official Transfer",
        transfer_report: "Transfer Report",
        transfer_rumor: "Transfer Rumor",
        injury_confirmed: "Confirmed Injury Update",
        injury_rumor: "Injury Rumor / Fitness Doubt",
        lineup_confirmed: "Confirmed Lineup",
        lineup_predicted: "Predicted Lineup",
        squad_news: "Squad News",
        manager_interview: "Manager Interview",
        player_interview: "Player Interview",
        agent_interview: "Agent Interview",
        press_conference: "Press Conference",
        discipline_legal: "Discipline / Legal",
        managerial_news: "Managerial News",
        contract_news: "Contract News",
        fixture_schedule: "Fixture / Schedule / Draw",
        tactical_analysis: "Tactical Analysis",
        stats_data_report: "Stats / Data Report",
        opinion_analysis: "Opinion / Column",
        ownership_finance: "Ownership / Finance",
        generic_news: "Generic Sports News",

        aggregate_result: "Aggregate Result",
        knockout_result: "Knockout Result",
        final_score: "Final Score",
        live_updates: "Live Updates",
        primary_source_statement: "Primary Source Statement",
        confirmed_transfer: "Confirmed Transfer",
        advanced_transfer_report: "Advanced Transfer Report",
        reported_interest: "Reported Interest",
        unconfirmed_transfer_claim: "Unconfirmed Transfer Claim",
        confirmed_absence: "Confirmed Absence",
        return_to_training: "Return to Training",
        medical_update: "Medical Update",
        fitness_doubt: "Fitness Doubt",
        confirmed_lineup: "Confirmed Lineup",
        predicted_lineup: "Predicted Lineup",
        availability_update: "Availability Update",
        manager_quotes: "Manager Quotes",
        player_quotes: "Player Quotes",
        agent_quotes: "Agent Quotes",
        manager_media_comments: "Manager Media Comments",
        investigation: "Investigation",
        suspension_ban: "Suspension / Ban",
        legal_case: "Legal Case",
        disciplinary_case: "Disciplinary Case",
        manager_sacking: "Manager Sacking",
        manager_appointment: "Manager Appointment",
        manager_pressure: "Manager Pressure",
        contract_extension: "Contract Extension",
        release_clause: "Release Clause",
        contract_talks: "Contract Talks",
        tournament_draw: "Tournament Draw",
        fixture_change: "Fixture Change",
        schedule_update: "Schedule Update",
        tactical_breakdown: "Tactical Breakdown",
        data_report: "Data Report",
        player_ratings: "Player Ratings",
        ranking: "Ranking",
        opinion_or_column: "Opinion / Column",
        ownership_update: "Ownership Update",
        financial_report: "Financial Report",
        business_update: "Business Update",
        general: "General",
      };

      function escapeRegExp(value) {
        return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      }

      function humanizeArticleLabel(value) {
        const raw = String(value || "").trim();

        if (ARTICLE_LABEL_MAP[raw]) return ARTICLE_LABEL_MAP[raw];

        return raw
          .replaceAll("_", " ")
          .replaceAll("-", " ")
          .replace(/\s+/g, " ")
          .trim()
          .replace(/\b\w/g, (c) => c.toUpperCase());
      }

      function cleanReasonText(value) {
        let text = String(value || "");

        for (const [key, label] of Object.entries(ARTICLE_LABEL_MAP)) {
          const pattern = new RegExp(`\\b${escapeRegExp(key)}\\b`, "g");
          text = text.replace(pattern, label);
        }

        return text
          .replaceAll("Article Type:", "Article type:")
          .replaceAll("Event/Type Fit:", "Event/type fit:");
      }

      function saveOverlayPrefs(payload) {
        try {
          chrome.runtime.sendMessage({
            type: "SPORTABASE_SAVE_OVERLAY_PREFS",
            payload,
          });
        } catch (e) {
          console.warn("[sportabase] could not save overlay prefs", e);
        }
      }

      function clampNum(value, min, max) {
        const n = Number(value);
        if (!Number.isFinite(n)) return min;
        return Math.max(min, Math.min(max, n));
      }

      function installSportabaseGradientIntensityControls(overlay) {
        const scrollBox = overlay.querySelector(".sportabase-content-scroll");

        function updateGradientIntensity() {
          const rect = overlay.getBoundingClientRect();

          const scrollMax = scrollBox
            ? Math.max(1, scrollBox.scrollHeight - scrollBox.clientHeight)
            : 1;

          const scrollRatio = scrollBox
            ? clampNum(scrollBox.scrollTop / scrollMax, 0, 1)
            : 0;

          const widthRatio = clampNum((rect.width - 360) / (760 - 360), 0, 1);
          const heightRatio = clampNum(
            (rect.height - 430) / (Math.floor(window.innerHeight * 0.85) - 430),
            0,
            1
          );

          const sizeRatio = (widthRatio + heightRatio) / 2;

          // Calm when compact/top. Stronger when expanded or scrolled deeper.
          const strength = clampNum(
            0.3 + scrollRatio * 0.18 + sizeRatio * 0.22,
            0.3,
            0.7
          );

          overlay.style.setProperty(
            "--sb-field-opacity",
            String(0.08 + strength * 0.14)
          );

          overlay.style.setProperty(
            "--sb-ripple-opacity",
            "0"
          );

          overlay.style.setProperty(
            "--sb-depth-opacity",
            String(0.03 + strength * 0.08)
          );

          overlay.style.setProperty(
            "--sb-saturate",
            `${Math.round(104 + strength * 18)}%`
          );


          overlay.style.setProperty(
            "--sb-blur",
            `${Math.round(24 + strength * 8)}px`
          );
        }
        updateGradientIntensity();

        if (scrollBox) {
          scrollBox.addEventListener("scroll", updateGradientIntensity, { passive: true });
        }

        const observer = new ResizeObserver(updateGradientIntensity);
        observer.observe(overlay);

        return () => {
          observer.disconnect();
          if (scrollBox) {
            scrollBox.removeEventListener("scroll", updateGradientIntensity);
          }
        };
      }

      function installSportabaseWindowControls(overlay, SIZE_PRESETS) {
        const MIN_W = 320;
        const MIN_H = 260;
        const MAX_W = Math.min(820, window.innerWidth - 16);
        const MAX_H = Math.floor(window.innerHeight * 0.9);

        function clampRect(left, top, width, height) {
          width = Math.max(MIN_W, Math.min(MAX_W, width));
          height = Math.max(MIN_H, Math.min(MAX_H, height));

          left = Math.max(8, Math.min(window.innerWidth - width - 8, left));
          top = Math.max(8, Math.min(window.innerHeight - height - 8, top));

          return { left, top, width, height };
        }

        function applyRect(rect) {
          overlay.style.left = `${Math.round(rect.left)}px`;
          overlay.style.top = `${Math.round(rect.top)}px`;
          overlay.style.right = "auto";
          overlay.style.width = `${Math.round(rect.width)}px`;
          overlay.style.height = `${Math.round(rect.height)}px`;
        }

        function getRect() {
          const r = overlay.getBoundingClientRect();
          return {
            left: r.left,
            top: r.top,
            width: r.width,
            height: r.height,
          };
        }

        function saveRect(mode = "custom") {
          const r = overlay.getBoundingClientRect();

          saveOverlayPrefs({
            sportabaseSizeMode: mode,
            sportabaseCustomWidth: Math.round(r.width),
            sportabaseCustomHeight: Math.round(r.height),
            sportabaseLeft: Math.round(r.left),
            sportabaseTop: Math.round(r.top),
          });
        }

        const dragHandle = overlay.querySelector("#sportabase-drag-handle");

        if (dragHandle) {
          dragHandle.style.cursor = "move";

          dragHandle.addEventListener("pointerdown", (e) => {
            if (e.target.closest("button, a")) return;

            e.preventDefault();

            const start = getRect();
            const startX = e.clientX;
            const startY = e.clientY;

            document.body.style.userSelect = "none";
            document.body.style.cursor = "move";

            function onMove(moveEvent) {
              const dx = moveEvent.clientX - startX;
              const dy = moveEvent.clientY - startY;

              const next = clampRect(
                start.left + dx,
                start.top + dy,
                start.width,
                start.height
              );

              applyRect(next);
            }

            function onUp() {
              document.removeEventListener("pointermove", onMove);
              document.removeEventListener("pointerup", onUp);

              document.body.style.userSelect = "";
              document.body.style.cursor = "";

              saveRect("custom");
            }

            document.addEventListener("pointermove", onMove);
            document.addEventListener("pointerup", onUp);
          });
        }

        ["n", "s", "e", "w", "ne", "nw", "se", "sw"].forEach((dir) => {
          const handle = document.createElement("div");
          handle.className = "sportabase-resize-handle";
          handle.dataset.dir = dir;
          overlay.appendChild(handle);

          handle.addEventListener("pointerdown", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const start = getRect();
            const startX = e.clientX;
            const startY = e.clientY;

            document.body.style.userSelect = "none";
            document.body.style.cursor = window.getComputedStyle(handle).cursor;

            function onMove(moveEvent) {
              const dx = moveEvent.clientX - startX;
              const dy = moveEvent.clientY - startY;

              let left = start.left;
              let top = start.top;
              let width = start.width;
              let height = start.height;

              if (dir.includes("e")) width = start.width + dx;
              if (dir.includes("s")) height = start.height + dy;

              if (dir.includes("w")) {
                width = start.width - dx;
                left = start.left + dx;
              }

              if (dir.includes("n")) {
                height = start.height - dy;
                top = start.top + dy;
              }

              if (width < MIN_W) {
                if (dir.includes("w")) left = start.left + start.width - MIN_W;
                width = MIN_W;
              }

              if (height < MIN_H) {
                if (dir.includes("n")) top = start.top + start.height - MIN_H;
                height = MIN_H;
              }

              if (width > MAX_W) {
                if (dir.includes("w")) left = start.left + start.width - MAX_W;
                width = MAX_W;
              }

              if (height > MAX_H) {
                if (dir.includes("n")) top = start.top + start.height - MAX_H;
                height = MAX_H;
              }

              const next = clampRect(left, top, width, height);
              applyRect(next);
            }

            function onUp() {
              document.removeEventListener("pointermove", onMove);
              document.removeEventListener("pointerup", onUp);

              document.body.style.userSelect = "";
              document.body.style.cursor = "";

              saveRect("custom");
            }

            document.addEventListener("pointermove", onMove);
            document.addEventListener("pointerup", onUp);
          });
        });

        overlay.querySelectorAll(".sportabase-size-btn").forEach((button) => {
          button.addEventListener("click", () => {
            const mode = button.getAttribute("data-size-mode");

            if (mode === "reset") {
              const preset = SIZE_PRESETS.compact;

              overlay.style.left = "";
              overlay.style.top = "18px";
              overlay.style.right = "18px";
              overlay.style.width = `${preset.width}px`;
              overlay.style.height = `${preset.height}px`;

              saveOverlayPrefs({
                sportabaseSizeMode: "compact",
                sportabaseCustomWidth: null,
                sportabaseCustomHeight: null,
                sportabaseLeft: null,
                sportabaseTop: null,
              });

              return;
            }

            const preset = SIZE_PRESETS[mode] || SIZE_PRESETS.compact;
            const current = getRect();

            const next = clampRect(
              current.left,
              current.top,
              preset.width,
              preset.height
            );

            applyRect(next);
            saveRect(mode);
          });
        });

        return () => {
          document.body.style.userSelect = "";
          document.body.style.cursor = "";
        };
      }

      function getTheme(score, badge) {
        const normalizedBadge = String(badge || "").toLowerCase();

        if (score < 20 || normalizedBadge.includes("unverified")) {
          return {
            label: "Unverified Rumor",
            shortLabel: "Rumor",
            color: "#dc2626",
            glow: "rgba(220, 38, 38, 0.62)",
            softGlow: "rgba(220, 38, 38, 0.26)",
            border: "rgba(220, 38, 38, 0.64)",
            textAccent: "#fecaca",
            description: "Very weak sourcing or heavy rumor signals.",
          };
        }

        if (score < 35 || normalizedBadge.includes("speculative")) {
          return {
            label: "Speculative",
            shortLabel: "Speculative",
            color: "#f97316",
            glow: "rgba(249, 115, 22, 0.58)",
            softGlow: "rgba(249, 115, 22, 0.24)",
            border: "rgba(249, 115, 22, 0.60)",
            textAccent: "#fed7aa",
            description: "Possible, but not backed strongly enough.",
          };
        }

        if (score < 50 || normalizedBadge.includes("low evidence")) {
          return {
            label: "Low Evidence",
            shortLabel: "Low Evidence",
            color: "#facc15",
            glow: "rgba(250, 204, 21, 0.42)",
            softGlow: "rgba(250, 204, 21, 0.20)",
            border: "rgba(250, 204, 21, 0.54)",
            textAccent: "#fef3c7",
            description: "Some signal, but evidence is still thin.",
          };
        }

        if (score < 65 || normalizedBadge.includes("developing")) {
          return {
            label: "Developing",
            shortLabel: "Developing",
            color: "#2563eb",
            glow: "rgba(37, 99, 235, 0.62)",
            softGlow: "rgba(37, 99, 235, 0.25)",
            border: "rgba(96, 165, 250, 0.54)",
            textAccent: "#bfdbfe",
            description: "Credible direction, still missing stronger proof.",
          };
        }

        if (score < 80 || normalizedBadge.includes("substantial")) {
          return {
            label: "Substantial Signal",
            shortLabel: "Substantial",
            color: "#a855f7",
            glow: "rgba(168, 85, 247, 0.60)",
            softGlow: "rgba(168, 85, 247, 0.24)",
            border: "rgba(168, 85, 247, 0.58)",
            textAccent: "#e9d5ff",
            description: "Good evidence signals, but not fully locked.",
          };
        }

        if (score < 90 || normalizedBadge.includes("strong evidence")) {
          return {
            label: "Strong Evidence",
            shortLabel: "Strong",
            color: "#14b8a6",
            glow: "rgba(20, 184, 166, 0.64)",
            softGlow: "rgba(20, 184, 166, 0.25)",
            border: "rgba(20, 184, 166, 0.58)",
            textAccent: "#ccfbf1",
            description: "Strong sourcing and detail, just below elite confidence.",
          };
        }

        return {
          label: "High Credibility",
          shortLabel: "High Cred",
          color: "#16a34a",
          glow: "rgba(22, 163, 74, 0.62)",
          softGlow: "rgba(22, 163, 74, 0.25)",
          border: "rgba(22, 163, 74, 0.65)",
          textAccent: "#dcfce7",
          description: "Rare tier: strong official/evidence signals.",
        };
      }

      function ensureSportabaseStyles() {
        const existing = document.getElementById(
          "sportabase-dynamic-styles"
        );

        if (existing) existing.remove();

        const style = document.createElement("style");
        style.id = "sportabase-dynamic-styles";

        style.textContent = `
          #sportabase-overlay,
          #sportabase-overlay * {
            box-sizing: border-box;
          }

          #sportabase-overlay {
            isolation: isolate;
            -webkit-font-smoothing: antialiased;
          }

          #sportabase-overlay .sportabase-gradient-field,
          #sportabase-overlay .sportabase-gradient-ripple,
          #sportabase-overlay .sportabase-gradient-depth {
            position: absolute;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            border-radius: inherit;
          }

          #sportabase-overlay .sportabase-gradient-field {
            background:
              radial-gradient(
                circle at 100% 0%,
                var(--sb-soft-glow, transparent),
                transparent 44%
              );
            opacity: var(--sb-field-opacity, 0.22);
          }

          #sportabase-overlay .sportabase-gradient-ripple {
            display: none;
          }

          #sportabase-overlay .sportabase-gradient-depth {
            background:
              linear-gradient(
                135deg,
                transparent 40%,
                var(--sb-soft-glow, transparent) 100%
              );
            opacity: var(--sb-depth-opacity, 0.12);
          }

          #sportabase-overlay::-webkit-scrollbar,
            #sportabase-overlay *::-webkit-scrollbar {
              width: 6px;
              height: 6px;
            }

            #sportabase-overlay::-webkit-scrollbar-thumb,
            #sportabase-overlay *::-webkit-scrollbar-thumb {
              background: var(
                --sb-ui-border,
                rgba(255, 255, 255, 0.18)
              );
              border: 1px solid transparent;
              background-clip: padding-box;
              border-radius: 999px;
            }

            #sportabase-overlay .sportabase-content-scroll {
              scrollbar-gutter: stable;
              overscroll-behavior: contain;
            }

            #sportabase-overlay #sportabase-drag-handle {
              position: sticky;
              top: 0;
              z-index: 20;
              min-height: 76px;
              margin:
                calc(-18px * var(--sb-density, 1))
                calc(-18px * var(--sb-density, 1))
                20px;
              padding:
                17px
                calc(20px * var(--sb-density, 1));
              align-items: center !important;
              background: var(--sb-ui-panel);
              border-bottom: 1px solid var(--sb-ui-divider);
              box-shadow: 0 10px 28px rgba(0, 0, 0, 0.14);
              backdrop-filter: blur(18px) saturate(135%);
            }

            #sportabase-overlay #sportabase-drag-handle::after {
              content: "";
              position: absolute;
              left: calc(20px * var(--sb-density, 1));
              right: calc(20px * var(--sb-density, 1));
              bottom: -1px;
              height: 2px;
              border-radius: 999px;
              background: var(--sb-color, var(--sb-ui-accent));
              opacity: 0.7;
            }

            #sportabase-overlay *::-webkit-scrollbar-track {
              background: transparent;
            }

            #sportabase-overlay .sportabase-resize-handle {
            position: absolute;
            z-index: 3;
            background: transparent;
            pointer-events: auto;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="n"] {
            top: 0;
            left: 18px;
            right: 18px;
            height: 14px;
            cursor: ns-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="s"] {
            bottom: 0;
            left: 18px;
            right: 18px;
            height: 14px;
            cursor: ns-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="e"] {
            top: 18px;
            right: 0;
            bottom: 18px;
            width: 14px;
            cursor: ew-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="w"] {
            top: 18px;
            left: 0;
            bottom: 18px;
            width: 14px;
            cursor: ew-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="ne"],
          #sportabase-overlay
            .sportabase-resize-handle[data-dir="nw"],
          #sportabase-overlay
            .sportabase-resize-handle[data-dir="se"],
          #sportabase-overlay
            .sportabase-resize-handle[data-dir="sw"] {
            width: 24px;
            height: 24px;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="ne"] {
            top: 0;
            right: 0;
            cursor: nesw-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="nw"] {
            top: 0;
            left: 0;
            cursor: nwse-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="se"] {
            right: 0;
            bottom: 0;
            cursor: nwse-resize;
          }

          #sportabase-overlay
            .sportabase-resize-handle[data-dir="sw"] {
            left: 0;
            bottom: 0;
            cursor: nesw-resize;
          }
         `;

        (document.head || document.documentElement).appendChild(style);
      }

      function getSportabaseUiDefaults() {
        return {
          sportabaseAppearance: "system",
          sportabaseAccentMode: "dynamic",
          sportabaseAccentColor: "#1ed760",
          sportabaseGlowLevel: "reduced",
          sportabaseMotionLevel: "full",
          sportabaseHighContrast: false,
          sportabaseTextScale: "medium",
          sportabaseDensity: "comfortable",
          sportabaseSizeMode: "comfort",
          sportabaseCustomWidth: null,
          sportabaseCustomHeight: null,
          sportabaseLeft: null,
          sportabaseTop: null,
          sportabaseRememberPosition: true,
          sportabaseDetailLevel: "full",
          sportabaseAutoTranscript: true,
          sportabaseRememberSections: true,
          sportabaseKeepOpenOnNavigation: false,
        };
      }

      function applySportabaseUiPreferences(overlay) {
        if (!overlay) return;

        const appearance =
          prefs?.sportabaseAppearance || "system";

        const prefersLight =
          window.matchMedia?.(
            "(prefers-color-scheme: light)"
          )?.matches || false;

        const resolvedAppearance =
          appearance === "system"
            ? prefersLight
              ? "light"
              : "dark"
            : appearance;

        const textScaleMap = {
          small: 0.94,
          medium: 1,
          large: 1.08,
        };

        const densityMap = {
          compact: 0.84,
          comfortable: 1,
          spacious: 1.14,
        };

        const glowMap = {
          off: 0,
          reduced: 0.52,
          full: 1,
        };

        const textScale =
          textScaleMap[prefs?.sportabaseTextScale] || 1;

        const density =
          densityMap[prefs?.sportabaseDensity] || 1;

        const glowStrength =
          glowMap[prefs?.sportabaseGlowLevel] ?? 0.52;

        const fixedAccent =
          prefs?.sportabaseAccentColor || "#1ed760";

        const palette =
          resolvedAppearance === "light"
            ? {
                panel:
                  "linear-gradient(180deg, #ffffff 0%, #f4f5f7 100%)",
                surface: "rgba(255,255,255,0.92)",
                raised: "rgba(242,244,247,0.96)",
                text: "#101114",
                muted: "#62666d",
                border: "rgba(15,23,42,0.13)",
                divider: "rgba(15,23,42,0.10)",
                shadow: "rgba(15,23,42,0.16)",
              }
            : {
                panel:
                  "linear-gradient(180deg, #121212 0%, #0b0b0c 100%)",
                surface: "rgba(27,27,29,0.94)",
                raised: "rgba(38,38,41,0.94)",
                text: "#f7f7f8",
                muted: "#a2a2a8",
                border: "rgba(255,255,255,0.11)",
                divider: "rgba(255,255,255,0.08)",
                shadow: "rgba(0,0,0,0.42)",
              };

        overlay.dataset.sbAppearance =
          resolvedAppearance;

        overlay.dataset.sbAccentMode =
          prefs?.sportabaseAccentMode || "dynamic";

        overlay.dataset.sbMotionLevel =
          prefs?.sportabaseMotionLevel || "full";

        overlay.dataset.sbDensity =
          prefs?.sportabaseDensity || "comfortable";

        overlay.style.setProperty(
          "--sb-ui-panel",
          palette.panel
        );

        overlay.style.setProperty(
          "--sb-ui-surface",
          palette.surface
        );

        overlay.style.setProperty(
          "--sb-ui-raised",
          palette.raised
        );

        overlay.style.setProperty(
          "--sb-ui-text",
          palette.text
        );

        overlay.style.setProperty(
          "--sb-ui-muted",
          palette.muted
        );

        overlay.style.setProperty(
          "--sb-ui-border",
          palette.border
        );

        overlay.style.setProperty(
          "--sb-ui-divider",
          palette.divider
        );

        overlay.style.setProperty(
          "--sb-ui-shadow",
          palette.shadow
        );

        overlay.style.setProperty(
          "--sb-ui-accent",
          fixedAccent
        );

        overlay.style.setProperty(
          "--sb-text-scale",
          String(textScale)
        );

        overlay.style.setProperty(
          "--sb-density",
          String(density)
        );

        overlay.style.setProperty(
          "--sb-glow-strength",
          String(glowStrength)
        );

        overlay.style.fontFamily = [
          '"Circular Std"',
          '"Circular Spotify Tx T"',
          '"Avenir Next"',
          '"Segoe UI Variable Display"',
          '"Segoe UI"',
          "Inter",
          "system-ui",
          "sans-serif",
        ].join(", ");

        overlay.style.fontSize =
          `${Math.round(14 * textScale)}px`;

        overlay.style.background = palette.panel;
        overlay.style.color = palette.text;

        overlay.style.border = prefs?.sportabaseHighContrast
          ? `2px solid ${palette.text}`
          : `1px solid ${palette.border}`;

        overlay.style.boxShadow =
          `0 18px 48px ${palette.shadow}`;

        const motionLevel =
          prefs?.sportabaseMotionLevel || "full";

        if (motionLevel === "none") {
          overlay.style.animation = "none";

          overlay
            .querySelectorAll(
              ".sportabase-gradient-field, " +
              ".sportabase-gradient-ripple, " +
              ".sportabase-gradient-depth"
            )
            .forEach((element) => {
              element.style.animation = "none";
            });
        } else if (motionLevel === "reduced") {
          overlay.style.animationDuration = "12s";
        }

        const gradientOpacity =
          prefs?.sportabaseGlowLevel === "off"
            ? "0"
            : prefs?.sportabaseGlowLevel === "full"
              ? "1"
              : "0.42";

        overlay
          .querySelectorAll(
            ".sportabase-gradient-field, " +
            ".sportabase-gradient-ripple, " +
            ".sportabase-gradient-depth"
          )
          .forEach((element) => {
            element.style.opacity = gradientOpacity;
          });
      }

      function installSportabaseSettingsDrawer(
        overlay,
        SIZE_PRESETS
      ) {
        const previousDrawer = overlay.querySelector(
          "#sportabase-settings-layer"
        );

        if (previousDrawer) {
          previousDrawer.remove();
        }

        const defaults = getSportabaseUiDefaults();

        const layer = document.createElement("div");
        layer.id = "sportabase-settings-layer";

        layer.style.cssText = `
          position:absolute;
          inset:0;
          z-index:2147483646;
          display:none;
          place-items:center;
          padding:12px;
          overflow:hidden;
          border-radius:inherit;
        `;

        layer.innerHTML = `
        <style>
          #sportabase-settings-layer
            > section
            > div
            > section:not(:last-child) {
            padding:13px;
            border:1px solid var(--sb-ui-border);
            border-radius:14px;
            background:var(--sb-ui-surface);
          }

          #sportabase-settings-layer
            .sportabase-setting-row,
          #sportabase-settings-layer
            .sportabase-toggle-row {
            min-height:42px;
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:16px;
            margin-top:8px;
            padding:9px 10px;
            border:1px solid transparent;
            border-radius:11px;
            background:var(--sb-ui-raised);
            color:var(--sb-ui-text);
            font-size:12px;
            font-weight:650;
            line-height:1.35;
            transition:
              border-color 150ms ease,
              background 150ms ease,
              transform 150ms ease;
          }

          #sportabase-settings-layer
            .sportabase-setting-row:hover,
          #sportabase-settings-layer
            .sportabase-toggle-row:hover {
            border-color:var(--sb-ui-border);
            background:var(--sb-ui-surface);
          }

          #sportabase-settings-layer
            .sportabase-setting-row:focus-within,
          #sportabase-settings-layer
            .sportabase-toggle-row:focus-within {
            border-color:var(--sb-color);
          }

          #sportabase-settings-layer
            .sportabase-setting-row
            > span,
          #sportabase-settings-layer
            .sportabase-toggle-row
            > span {
            min-width:0;
            color:var(--sb-ui-text);
          }

          #sportabase-settings-layer select {
            min-width:136px;
            max-width:54%;
            height:32px;
            padding:0 9px;
            border:1px solid var(--sb-ui-border);
            border-radius:9px;
            outline:none;
            background:var(--sb-ui-panel);
            color:var(--sb-ui-text);
            font:inherit;
            font-size:11.5px;
            font-weight:650;
            cursor:pointer;
            transition:
              border-color 150ms ease,
              background 150ms ease;
          }

          #sportabase-settings-layer select:hover,
          #sportabase-settings-layer select:focus {
            border-color:var(--sb-color);
            background:var(--sb-ui-surface);
          }

          #sportabase-settings-layer
            input[type="checkbox"] {
            appearance:none;
            width:36px;
            height:20px;
            flex:0 0 auto;
            margin:0;
            border:1px solid var(--sb-ui-border);
            border-radius:999px;
            background:
              radial-gradient(
                circle at 10px 50%,
                #ffffff 0 6px,
                transparent 6.5px
              ),
              var(--sb-ui-border);
            cursor:pointer;
            transition:
              background 170ms ease,
              border-color 170ms ease,
              box-shadow 170ms ease;
          }

          #sportabase-settings-layer
            input[type="checkbox"]:checked {
            border-color:var(--sb-color);
            background:
              radial-gradient(
                circle at 25px 50%,
                #ffffff 0 6px,
                transparent 6.5px
              ),
              var(--sb-color);
            box-shadow:0 0 12px var(--sb-soft-glow);
          }

          #sportabase-settings-layer
            input[type="checkbox"]:focus-visible {
            outline:2px solid var(--sb-color);
            outline-offset:2px;
          }

          #sportabase-settings-layer
            input[type="color"] {
            width:38px !important;
            height:28px !important;
            padding:2px !important;
            border:1px solid var(--sb-ui-border) !important;
            border-radius:9px;
            background:var(--sb-ui-panel) !important;
            cursor:pointer;
          }

          #sportabase-settings-layer
            input[type="color"]::-webkit-color-swatch-wrapper {
            padding:0;
          }

          #sportabase-settings-layer
            input[type="color"]::-webkit-color-swatch {
            border:0;
            border-radius:6px;
          }

          #sportabase-settings-close:hover {
            transform:translateY(-1px);
            border-color:var(--sb-color) !important;
            background:var(--sb-ui-surface) !important;
          }

          #sportabase-settings-close:active {
            transform:scale(0.94);
          }
        </style>
          <button
            id="sportabase-settings-backdrop"
            aria-label="Close settings"
            style="
              position:absolute;
              inset:0;
              z-index:0;
              width:100%;
              height:100%;
              border:0;
              background:rgba(0,0,0,0.40);
              backdrop-filter:blur(4px);
              cursor:default;
            "
          ></button>

          <section
            style="
              position:relative;
              z-index:1;
              width:min(430px, 100%);
              height:min(620px, 100%);
              overflow-y:auto;
              padding:
                0 calc(18px * var(--sb-density, 1));
              background:var(--sb-ui-panel);
              color:var(--sb-ui-text);
              border:1px solid var(--sb-ui-border);
              border-radius:18px;
              box-shadow:0 18px 48px var(--sb-ui-shadow);
              scrollbar-gutter:stable;
              overscroll-behavior:contain;
            "
          >
            <header
              style="
                position:sticky;
                top:0;
                z-index:3;
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:14px;
                margin:
                  0 calc(-18px * var(--sb-density, 1));
                padding:
                  14px calc(18px * var(--sb-density, 1));
                background:var(--sb-ui-panel);
                border-bottom:1px solid var(--sb-ui-divider);
              "
            >
              <div
                style="
                  display:flex;
                  align-items:center;
                  gap:10px;
                  min-width:0;
                "
              >
                ${getSportabaseLogoMarkup({
                  size: 32,
                  accent: "var(--sb-color)",
                  glow: "var(--sb-soft-glow)",
                  fontSize: 11,
                  radius: 10,
                })}

                <div style="min-width:0;">
                  <div
                    style="
                      color:var(--sb-ui-text);
                      font-size:16px;
                      font-weight:800;
                      line-height:1.15;
                      letter-spacing:-0.3px;
                    "
                  >
                    Settings
                  </div>

                  <div
                    style="
                      margin-top:3px;
                      color:var(--sb-ui-muted);
                      font-size:11px;
                      font-weight:600;
                      line-height:1.3;
                    "
                  >
                    Sportabase preferences
                  </div>
                </div>
              </div>

              <button
                id="sportabase-settings-close"
                aria-label="Close settings"
                title="Close settings"
                style="
                  width:32px;
                  height:32px;
                  flex:0 0 auto;
                  display:grid;
                  place-items:center;
                  padding:0;
                  border-radius:10px;
                  border:1px solid var(--sb-ui-border);
                  background:var(--sb-ui-raised);
                  color:var(--sb-ui-text);
                  cursor:pointer;
                  transition:
                    transform 160ms ease,
                    border-color 160ms ease,
                    background 160ms ease;
                "
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  aria-hidden="true"
                >
                  <path d="M6 6l12 12"></path>
                  <path d="M18 6L6 18"></path>
                </svg>
              </button>
            </header>
            <div
              style="
                display:grid;
                gap:14px;
                padding:16px 0 18px;
              "
            >
              <section>
                <div
                  style="
                    margin-bottom:10px;
                    color:var(--sb-ui-muted);
                    font-size:11px;
                    font-weight:760;
                    letter-spacing:0.75px;
                    text-transform:uppercase;
                  "
                >
                  Appearance
                </div>

                <label class="sportabase-setting-row">
                  <span>Theme</span>

                  <select
                    data-sb-setting="sportabaseAppearance"
                  >
                    <option value="system">System</option>
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                </label>

                <label class="sportabase-setting-row">
                  <span>Accent</span>

                  <select
                    data-sb-setting="sportabaseAccentMode"
                  >
                    <option value="dynamic">
                      Dynamic score
                    </option>
                    <option value="fixed">
                      Fixed color
                    </option>
                  </select>
                </label>

                <label class="sportabase-setting-row">
                  <span>Accent color</span>

                  <input
                    type="color"
                    data-sb-setting="sportabaseAccentColor"
                    value="#1ed760"
                    style="
                      width:44px;
                      height:30px;
                      border:0;
                      padding:0;
                      background:transparent;
                      cursor:pointer;
                    "
                  />
                </label>

                <label class="sportabase-setting-row">
                  <span>Glow</span>

                  <select
                    data-sb-setting="sportabaseGlowLevel"
                  >
                    <option value="off">Off</option>
                    <option value="reduced">Reduced</option>
                    <option value="full">Full</option>
                  </select>
                </label>

                <label class="sportabase-setting-row">
                  <span>Motion</span>

                  <select
                    data-sb-setting="sportabaseMotionLevel"
                  >
                    <option value="full">Full</option>
                    <option value="reduced">Reduced</option>
                    <option value="none">None</option>
                  </select>
                </label>

                <label class="sportabase-toggle-row">
                  <span>High contrast</span>

                  <input
                    type="checkbox"
                    data-sb-setting="sportabaseHighContrast"
                  />
                </label>
              </section>

              <section>
                <div
                  style="
                    margin-bottom:10px;
                    color:var(--sb-ui-muted);
                    font-size:11px;
                    font-weight:760;
                    letter-spacing:0.75px;
                    text-transform:uppercase;
                  "
                >
                  Layout
                </div>

                <label class="sportabase-setting-row">
                  <span>Panel size</span>

                  <select
                    id="sportabase-settings-size"
                  >
                    <option value="compact">Compact</option>
                    <option value="comfort">
                      Comfortable
                    </option>
                    <option value="wide">Wide</option>
                    <option value="debug">Extra wide</option>
                  </select>
                </label>

                <label class="sportabase-setting-row">
                  <span>Text size</span>

                  <select
                    data-sb-setting="sportabaseTextScale"
                  >
                    <option value="small">Small</option>
                    <option value="medium">Medium</option>
                    <option value="large">Large</option>
                  </select>
                </label>

                <label class="sportabase-setting-row">
                  <span>Content density</span>

                  <select
                    data-sb-setting="sportabaseDensity"
                  >
                    <option value="compact">Compact</option>
                    <option value="comfortable">
                      Comfortable
                    </option>
                    <option value="spacious">Spacious</option>
                  </select>
                </label>

                <label class="sportabase-toggle-row">
                  <span>Remember size and position</span>

                  <input
                    type="checkbox"
                    data-sb-setting="sportabaseRememberPosition"
                  />
                </label>
              </section>

              <section>
                <div
                  style="
                    margin-bottom:10px;
                    color:var(--sb-ui-muted);
                    font-size:11px;
                    font-weight:760;
                    letter-spacing:0.75px;
                    text-transform:uppercase;
                  "
                >
                  Behaviour
                </div>

                <label class="sportabase-toggle-row">
                  <span>Automatically find transcripts</span>

                  <input
                    type="checkbox"
                    data-sb-setting="sportabaseAutoTranscript"
                  />
                </label>

                <label class="sportabase-setting-row">
                  <span>Default detail</span>

                  <select
                    data-sb-setting="sportabaseDetailLevel"
                  >
                    <option value="compact">
                      Compact
                    </option>
                    <option value="full">
                      Full
                    </option>
                  </select>
                </label>

                <label class="sportabase-toggle-row">
                  <span>Remember collapsed sections</span>

                  <input
                    type="checkbox"
                    data-sb-setting="sportabaseRememberSections"
                  />
                </label>
              </section>

              <section
                style="
                  position:sticky;
                  bottom:0;
                  z-index:3;
                  margin:
                    0 calc(-18px * var(--sb-density, 1)) -18px;
                  padding:
                    14px calc(18px * var(--sb-density, 1));
                  background:var(--sb-ui-panel);
                  border-top:
                    1px solid var(--sb-ui-divider);
                "
              >
                <button
                  id="sportabase-settings-reset"
                  style="
                    width:100%;
                    padding:11px 13px;
                    border-radius:999px;
                    border:
                      1px solid var(--sb-ui-border);
                    background:var(--sb-ui-raised);
                    color:var(--sb-ui-text);
                    font-weight:720;
                    cursor:pointer;
                  "
                >
                  Restore defaults
                </button>

                <div
                  style="
                    margin-top:12px;
                    color:var(--sb-ui-muted);
                    font-size:11px;
                    text-align:center;
                  "
                >
                  Sportabase local beta
                </div>
              </section>
            </div>
          </section>
        `;

        overlay.appendChild(layer);

        layer
          .querySelectorAll(".sportabase-setting-row")
          .forEach((row) => {
            row.style.cssText = `
              display:flex;
              align-items:center;
              justify-content:space-between;
              gap:14px;
              min-height:42px;
              border-bottom:
                1px solid var(--sb-ui-divider);
              font-size:13px;
            `;
          });

        layer
          .querySelectorAll(".sportabase-toggle-row")
          .forEach((row) => {
            row.style.cssText = `
              display:flex;
              align-items:center;
              justify-content:space-between;
              gap:14px;
              min-height:42px;
              border-bottom:
                1px solid var(--sb-ui-divider);
              font-size:13px;
            `;
          });

        layer
          .querySelectorAll("select")
          .forEach((select) => {
            select.style.cssText = `
              max-width:150px;
              padding:7px 9px;
              border-radius:10px;
              border:
                1px solid var(--sb-ui-border);
              background:var(--sb-ui-raised);
              color:var(--sb-ui-text);
              font:inherit;
              cursor:pointer;
            `;
          });

        function syncControls() {
          layer
            .querySelectorAll("[data-sb-setting]")
            .forEach((control) => {
              const key = control.dataset.sbSetting;
              const value = prefs[key];

              if (control.type === "checkbox") {
                control.checked = Boolean(value);
              } else {
                control.value =
                  value ?? defaults[key] ?? "";
              }
            });

          const sizeControl = layer.querySelector(
            "#sportabase-settings-size"
          );

          if (sizeControl) {
            sizeControl.value =
              prefs.sportabaseSizeMode === "custom"
                ? "comfort"
                : prefs.sportabaseSizeMode || "comfort";
          }
        }

        function updatePreference(key, value) {
          prefs[key] = value;

          saveOverlayPrefs({
            [key]: value,
          });

          applySportabaseUiPreferences(overlay);
        }

        let settingsTransitionToken = 0;

        function openSettings() {
          syncControls();

          settingsTransitionToken += 1;
          const transitionToken = settingsTransitionToken;

          const panel = layer.querySelector(":scope > section");
          const backdrop = layer.querySelector(
            "#sportabase-settings-backdrop"
          );

          const prefersReducedMotion =
            window.matchMedia?.(
              "(prefers-reduced-motion: reduce)"
            )?.matches || false;

          const motionLevel =
            prefs?.sportabaseMotionLevel || "full";

          layer.style.display = "grid";
          layer.style.pointerEvents = "auto";

          if (
            prefersReducedMotion ||
            motionLevel === "none"
          ) {
            return;
          }

          backdrop?.animate(
            [
              {
                opacity: 0,
              },
              {
                opacity: 1,
              },
            ],
            {
              duration:
                motionLevel === "reduced" ? 120 : 190,
              easing: "ease-out",
              fill: "both",
            }
          );

          const panelAnimation = panel?.animate(
            [
              {
                opacity: 0,
                transform: "translateY(10px) scale(0.975)",
              },
              {
                opacity: 1,
                transform: "translateY(0) scale(1)",
              },
            ],
            {
              duration:
                motionLevel === "reduced" ? 150 : 240,
              easing: "cubic-bezier(.2,.8,.2,1)",
              fill: "both",
            }
          );

          panelAnimation?.finished
            .catch(() => {})
            .then(() => {
              if (transitionToken !== settingsTransitionToken) {
                return;
              }

              panel?.getAnimations().forEach((animation) => {
                animation.cancel();
              });
            });
        }

        function closeSettings() {
          if (layer.style.display === "none") return;

          settingsTransitionToken += 1;
          const transitionToken = settingsTransitionToken;

          const panel = layer.querySelector(":scope > section");
          const backdrop = layer.querySelector(
            "#sportabase-settings-backdrop"
          );

          const prefersReducedMotion =
            window.matchMedia?.(
              "(prefers-reduced-motion: reduce)"
            )?.matches || false;

          const motionLevel =
            prefs?.sportabaseMotionLevel || "full";

          if (
            prefersReducedMotion ||
            motionLevel === "none"
          ) {
            layer.style.display = "none";
            return;
          }

          layer.style.pointerEvents = "none";

          const backdropAnimation = backdrop?.animate(
            [
              {
                opacity: 1,
              },
              {
                opacity: 0,
              },
            ],
            {
              duration:
                motionLevel === "reduced" ? 90 : 150,
              easing: "ease-in",
              fill: "forwards",
            }
          );

          const panelAnimation = panel?.animate(
            [
              {
                opacity: 1,
                transform: "translateY(0) scale(1)",
              },
              {
                opacity: 0,
                transform: "translateY(8px) scale(0.98)",
              },
            ],
            {
              duration:
                motionLevel === "reduced" ? 110 : 180,
              easing: "cubic-bezier(.4,0,1,1)",
              fill: "forwards",
            }
          );

          Promise.allSettled(
            [backdropAnimation, panelAnimation]
              .filter(Boolean)
              .map((animation) => animation.finished)
          ).then(() => {
            if (transitionToken !== settingsTransitionToken) {
              return;
            }

            layer.style.display = "none";
            layer.style.pointerEvents = "auto";
          });
        }

        overlay
          .querySelectorAll(".sportabase-settings-button")
          .forEach((button) => {
            button.addEventListener(
              "click",
              openSettings
            );
          });

        layer
          .querySelector(
            "#sportabase-settings-close"
          )
          ?.addEventListener(
            "click",
            closeSettings
          );

        layer
          .querySelector(
            "#sportabase-settings-backdrop"
          )
          ?.addEventListener(
            "click",
            closeSettings
          );

        layer
          .querySelectorAll("[data-sb-setting]")
          .forEach((control) => {
            const eventName =
              control.type === "color"
                ? "input"
                : "change";

            control.addEventListener(
              eventName,
              () => {
                const key = control.dataset.sbSetting;

                const value =
                  control.type === "checkbox"
                    ? control.checked
                    : control.value;

                updatePreference(key, value);
              }
            );
          });

        layer
          .querySelector(
            "#sportabase-settings-size"
          )
          ?.addEventListener(
            "change",
            (event) => {
              const mode = event.target.value;

              const preset =
                SIZE_PRESETS[mode] ||
                SIZE_PRESETS.comfort;

              const width = Math.min(
                preset.width,
                window.innerWidth - 16
              );

              const height = Math.min(
                preset.height,
                window.innerHeight - 16
              );

              const currentRect =
                overlay.getBoundingClientRect();

              const left = Math.max(
                8,
                Math.min(
                  currentRect.left,
                  window.innerWidth - width - 8
                )
              );

              const top = Math.max(
                8,
                Math.min(
                  currentRect.top,
                  window.innerHeight - height - 8
                )
              );

              overlay.style.left = `${Math.round(left)}px`;
              overlay.style.top = `${Math.round(top)}px`;
              overlay.style.right = "auto";
              overlay.style.width = `${Math.round(width)}px`;
              overlay.style.height = `${Math.round(height)}px`;

              prefs.sportabaseSizeMode = mode;
              prefs.sportabaseCustomWidth = null;
              prefs.sportabaseCustomHeight = null;

              const positionPrefs =
                prefs.sportabaseRememberPosition === false
                  ? {}
                  : {
                      sportabaseLeft: Math.round(left),
                      sportabaseTop: Math.round(top),
                    };

              Object.assign(prefs, positionPrefs);

              saveOverlayPrefs({
                sportabaseSizeMode: mode,
                sportabaseCustomWidth: null,
                sportabaseCustomHeight: null,
                ...positionPrefs,
              });
            }
          );

        layer
          .querySelector(
            "#sportabase-settings-reset"
          )
          ?.addEventListener(
            "click",
            () => {
              Object.assign(prefs, defaults);

              saveOverlayPrefs(defaults);

              const preset =
                SIZE_PRESETS.comfort;

              overlay.style.left = "";
              overlay.style.top = "18px";
              overlay.style.right = "18px";
              overlay.style.width =
                `${preset.width}px`;
              overlay.style.height =
                `${Math.min(
                  preset.height,
                  Math.floor(window.innerHeight * 0.9)
                )}px`;

              applySportabaseUiPreferences(overlay);
              syncControls();
            }
          );

        applySportabaseUiPreferences(overlay);
        syncControls();

        return {
          open: openSettings,
          close: closeSettings,
        };
      }

      function getSportabaseLogoMarkup({
        size = 34,
        accent = "var(--sb-color)",
        glow = "var(--sb-soft-glow)",
        textColor = "#ffffff",
        fontSize = 13,
        radius = 10,
        className = "",
      } = {}) {
        return `
          <div
            class="${className}"
            style="
              width:${size}px;
              height:${size}px;
              flex:0 0 auto;
              display:grid;
              place-items:center;
              border-radius:${radius}px;
              background:linear-gradient(
                135deg,
                ${accent} 0%,
                color-mix(in srgb, ${accent} 72%, #ffffff 28%) 100%
              );
              color:${textColor};
              font-size:${fontSize}px;
              font-weight:900;
              line-height:1;
              letter-spacing:-0.9px;
              box-shadow:
                0 0 0 1px var(--sb-ui-border),
                0 8px 20px ${glow};
              position:relative;
              overflow:hidden;
            "
            aria-hidden="true"
          >
            <div
              style="
                position:absolute;
                inset:0;
                background:
                  radial-gradient(
                    circle at 28% 24%,
                    rgba(255,255,255,0.28),
                    transparent 46%
                  );
                pointer-events:none;
              "
            ></div>

            <span
              style="
                position:relative;
                z-index:1;
                font-family:Inter, system-ui, sans-serif;
              "
            >
              SB
            </span>
          </div>
        `;
      }

      function playSportabaseStartupAnimation(overlay) {
        if (!overlay) return;

        const prefersReducedMotion =
          window.matchMedia?.(
            "(prefers-reduced-motion: reduce)"
          )?.matches || false;

        const motionLevel =
          prefs?.sportabaseMotionLevel || "full";

        if (
          prefersReducedMotion ||
          motionLevel === "reduced"
        ) {
          return;
        }

        overlay.animate(
          [
            {
              opacity: 0,
              filter: "blur(7px)",
            },
            {
              opacity: 1,
              filter: "blur(0px)",
            },
          ],
          {
            duration: 320,
            easing: "cubic-bezier(.2,.8,.2,1)",
            fill: "both",
          }
        );

        const brandMark = overlay.querySelector(
          ".sportabase-brand-mark"
        );

        if (!brandMark) return;

        brandMark.animate(
          [
            {
              opacity: 0,
              transform: "scale(0.72) rotate(-14deg)",
            },
            {
              opacity: 1,
              transform: "scale(1.08) rotate(3deg)",
              offset: 0.72,
            },
            {
              opacity: 1,
              transform: "scale(1) rotate(0deg)",
            },
          ],
          {
            duration: 520,
            delay: 80,
            easing: "cubic-bezier(.2,.9,.25,1)",
            fill: "both",
          }
        );
      }

      function installSportabaseButtonDynamics(overlay) {
        if (!overlay) return;

        const buttons = overlay.querySelectorAll(
          ".sportabase-settings-button, " +
            "#sportabase-close, " +
            "#sportabase-video-close"
        );

        buttons.forEach((button) => {
          button.addEventListener("mouseenter", () => {
            button.style.transform = "translateY(-1px)";
            button.style.borderColor = "var(--sb-color)";
            button.style.background = "var(--sb-ui-surface)";
          });

          button.addEventListener("mouseleave", () => {
            button.style.transform = "translateY(0)";
            button.style.borderColor = "var(--sb-ui-border)";
            button.style.background = "var(--sb-ui-raised)";
          });

          button.addEventListener("pointerdown", () => {
            button.style.transform = "scale(0.94)";
          });

          button.addEventListener("pointerup", () => {
            button.style.transform = "translateY(-1px)";
          });

          button.addEventListener("blur", () => {
            button.style.transform = "translateY(0)";
            button.style.borderColor = "var(--sb-ui-border)";
            button.style.background = "var(--sb-ui-raised)";
          });
        });
      }

      function installSportabaseContentReveal(overlay) {
        if (!overlay) return;

        const prefersReducedMotion =
          window.matchMedia?.(
            "(prefers-reduced-motion: reduce)"
          )?.matches || false;

        const motionLevel =
          prefs?.sportabaseMotionLevel || "full";

        if (
          prefersReducedMotion ||
          motionLevel === "none"
        ) {
          return;
        }

        function revealElements(root) {
          if (!root) return;

          const elements = Array.from(
            root.querySelectorAll(
              ":scope > section, " +
                ":scope > div > section"
            )
          ).filter(
            (element) =>
              !element.dataset.sportabaseRevealed
          );

          elements.forEach((element, index) => {
            element.dataset.sportabaseRevealed = "true";

            element.animate(
              [
                {
                  opacity: 0,
                  transform: "translateY(9px)",
                },
                {
                  opacity: 1,
                  transform: "translateY(0)",
                },
              ],
              {
                duration:
                  motionLevel === "reduced" ? 180 : 320,
                delay:
                  motionLevel === "reduced"
                    ? 0
                    : Math.min(index * 55, 275),
                easing: "cubic-bezier(.2,.8,.2,1)",
                fill: "both",
              }
            );
          });
        }

        const articleContent = overlay.querySelector(
          ".sportabase-content-scroll"
        );

        if (articleContent) {
          revealElements(articleContent);
        }

        const videoStatus = overlay.querySelector(
          "#sportabase-video-status"
        );

        if (videoStatus) {
          revealElements(videoStatus);

          const observer = new MutationObserver(() => {
            revealElements(videoStatus);
          });

          observer.observe(videoStatus, {
            childList: true,
            subtree: false,
          });

          overlay.addEventListener(
            "sportabase-cleanup",
            () => observer.disconnect(),
            { once: true }
          );
        }
      }

      function closeSportabaseOverlay(
        overlay,
        cleanupCallbacks = []
      ) {
        if (!overlay) return;

        cleanupCallbacks.forEach((cleanup) => {
          try {
            if (typeof cleanup === "function") {
              cleanup();
            }
          } catch (_) {
            // Ignore cleanup failures during closing.
          }
        });

        overlay.dispatchEvent(
          new CustomEvent("sportabase-cleanup")
        );

        const prefersReducedMotion =
          window.matchMedia?.(
            "(prefers-reduced-motion: reduce)"
          )?.matches || false;

        const motionLevel =
          prefs?.sportabaseMotionLevel || "full";

        if (
          prefersReducedMotion ||
          motionLevel === "none"
        ) {
          overlay.remove();
          return;
        }

        overlay.style.pointerEvents = "none";

        const animation = overlay.animate(
          [
            {
              opacity: 1,
              transform: "translateY(0) scale(1)",
              filter: "blur(0px)",
            },
            {
              opacity: 0,
              transform: "translateY(-7px) scale(0.975)",
              filter: "blur(4px)",
            },
          ],
          {
            duration:
              motionLevel === "reduced" ? 120 : 190,
            easing: "cubic-bezier(.4,0,1,1)",
            fill: "forwards",
          }
        );

        animation.finished
          .catch(() => {})
          .finally(() => {
            overlay.remove();
          });
      }

      function showOverlay(data) {
        ensureSportabaseStyles();

        const existing = document.getElementById("sportabase-overlay");
        if (existing) existing.remove();

        const score = Number.isFinite(Number(data.merit_score))
          ? Number(data.merit_score)
          : 0;

        const safeScore = Math.max(0, Math.min(100, score));
        const theme = getTheme(safeScore, data.badge);

        const title = escapeHtml(data.title || document.title || "Untitled");
        const badge = escapeHtml(data.badge || theme.label);
        const description = escapeHtml(theme.description);

        const articleTypeLabel = escapeHtml(
          humanizeArticleLabel(
            data.article_type_label || data.article_type || "generic_news"
          )
        );

        const articleSubtype = escapeHtml(
          humanizeArticleLabel(data.article_subtype || "general")
        );

        const typeConfidence = Number.isFinite(Number(data.type_confidence))
          ? Math.round(Number(data.type_confidence) * 100)
          : 0;

        const SIZE_PRESETS = {
          compact: {
            label: "Compact",
            width: 440,
            height: 560,
          },
          comfort: {
            label: "Standard",
            width: 520,
            height: 680,
          },
          wide: {
            label: "Wide",
            width: 640,
            height: 760,
          },
          debug: {
            label: "Presentation",
            width: 760,
            height: 820,
          },
        };

        const savedMode = prefs?.sportabaseSizeMode || "compact";
        const selectedPreset = SIZE_PRESETS[savedMode] || SIZE_PRESETS.compact;

        const startWidth = clampNum(
          prefs?.sportabaseCustomWidth || selectedPreset.width,
          320,
          760
        );

        const startHeight = clampNum(
          prefs?.sportabaseCustomHeight || selectedPreset.height,
          260,
          Math.floor(window.innerHeight * 0.85)
        );

        const bullets = (data.summary || data.tldr || [])
          .map((b) => `<li class="sportabase-bullet">${escapeHtml(b)}</li>`)
          .join("");

        const reasons = (data.reasons || [])
          .map(
            (r) =>
              `<li class="sportabase-reason">${escapeHtml(
                cleanReasonText(r)
              )}</li>`
          )
          .join("");

        const overlay = document.createElement("div");
        overlay.id = "sportabase-overlay";

        overlay.style.setProperty("--sb-color", theme.color);
        overlay.style.setProperty("--sb-glow", theme.glow);
        overlay.style.setProperty("--sb-soft-glow", theme.softGlow);
        overlay.style.setProperty("--sb-border", theme.border);

        overlay.style.position = "fixed";
        overlay.style.top = "18px";
        overlay.style.right = "18px";

        if (
          Number.isFinite(Number(prefs?.sportabaseLeft)) &&
          Number.isFinite(Number(prefs?.sportabaseTop))
        ) {
          const safeLeft = clampNum(
            prefs.sportabaseLeft,
            8,
            Math.max(8, window.innerWidth - startWidth - 8)
          );
          const safeTop = clampNum(
            prefs.sportabaseTop,
            8,
            Math.max(8, window.innerHeight - startHeight - 8)
          );

          overlay.style.left = `${safeLeft}px`;
          overlay.style.top = `${safeTop}px`;
          overlay.style.right = "auto";
        }

        overlay.style.width = `${startWidth}px`;
        overlay.style.height = `${startHeight}px`;
        overlay.style.minWidth = "320px";
        overlay.style.minHeight = "260px";
        overlay.style.maxWidth = "calc(100vw - 16px)";
        overlay.style.maxHeight = "90vh";
        overlay.style.overflow = "hidden";
        overlay.style.resize = "none";
        overlay.style.zIndex = "2147483647";
        overlay.style.borderRadius = "22px";
        overlay.style.border = `1px solid ${theme.border}`;
        overlay.style.boxShadow = `0 18px 48px rgba(0,0,0,0.42), 0 0 24px ${theme.softGlow}`;
        overlay.style.fontFamily =
          "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
        overlay.style.color = "#fff";
        overlay.style.background = `
          linear-gradient(
            105deg,
            rgba(2, 4, 10, 0.98) 0%,
            rgba(3, 6, 14, 0.96) 38%,
            rgba(6, 10, 22, 0.92) 62%,
            rgba(8, 13, 28, 0.96) 100%
          )
        `;

        overlay.innerHTML = `
          <div class="sportabase-gradient-field"></div>
          <div class="sportabase-gradient-ripple"></div>
          <div class="sportabase-gradient-depth"></div>

          <div
            class="sportabase-content-scroll"
            style="
              position:relative;
              z-index:2;
              padding:calc(18px * var(--sb-density, 1));
              background:transparent;
              height:100%;
              max-height:100%;
              overflow:auto;
              color:var(--sb-ui-text);
            "
          >
            <div
              id="sportabase-drag-handle"
              style="
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:14px;
                padding:4px 2px 16px;
                border-bottom:1px solid var(--sb-ui-border);
              "
            >
              <div
                style="
                  display:flex;
                  align-items:center;
                  gap:11px;
                  min-width:0;
                "
              >
                ${getSportabaseLogoMarkup({
                    size: 34,
                    accent: theme.color,
                    glow: theme.softGlow,
                    fontSize: 12,
                    radius: 10,
                    className: "sportabase-brand-mark",
                  })}

                <div style="min-width:0;">
                  <div
                    style="
                      color:var(--sb-ui-text);
                      font-size:16px;
                      font-weight:800;
                      line-height:1.15;
                      letter-spacing:-0.35px;
                    "
                  >
                    Sportabase
                  </div>

                  <div
                    style="
                      margin-top:4px;
                      color:var(--sb-ui-muted);
                      font-size:11px;
                      font-weight:600;
                      line-height:1.3;
                      letter-spacing:0.15px;
                      white-space:nowrap;
                      overflow:hidden;
                      text-overflow:ellipsis;
                    "
                  >
                    ARTICLE INTELLIGENCE · ${articleTypeLabel} · ${typeConfidence}%
                  </div>
                </div>
              </div>

              <div
                style="
                  display:flex;
                  align-items:center;
                  gap:7px;
                  flex:0 0 auto;
                "
              >
                <button
                  class="sportabase-settings-button"
                  aria-label="Open settings"
                  title="Settings"
                  style="
                    width:32px;
                    height:32px;
                    display:grid;
                    place-items:center;
                    padding:0;
                    border-radius:10px;
                    border:1px solid var(--sb-ui-border);
                    background:var(--sb-ui-raised);
                    color:var(--sb-ui-text);
                    cursor:pointer;
                    transition:
                      transform 160ms ease,
                      border-color 160ms ease,
                      background 160ms ease;
                  "
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="3"></circle>
                    <path
                      d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.12 2.12-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.55v.09h-3v-.09a1.7 1.7 0 0 0-1.03-1.55 1.7 1.7 0 0 0-1.88.34l-.06.06-2.12-2.12.06-.06A1.7 1.7 0 0 0 7.02 15a1.7 1.7 0 0 0-1.55-1.03H5.4v-3h.07A1.7 1.7 0 0 0 7.02 9.94a1.7 1.7 0 0 0-.34-1.88L6.62 8l2.12-2.12.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 11.71 4.7v-.08h3v.08a1.7 1.7 0 0 0 1.03 1.58 1.7 1.7 0 0 0 1.88-.34l.06-.06L19.8 8l-.06.06a1.7 1.7 0 0 0-.34 1.88 1.7 1.7 0 0 0 1.55 1.03h.08v3h-.08A1.7 1.7 0 0 0 19.4 15Z"
                    ></path>
                  </svg>
                </button>

                <button
                  id="sportabase-close"
                  aria-label="Close Sportabase"
                  title="Close"
                  style="
                    width:32px;
                    height:32px;
                    display:grid;
                    place-items:center;
                    padding:0;
                    border-radius:10px;
                    border:1px solid var(--sb-ui-border);
                    background:var(--sb-ui-raised);
                    color:var(--sb-ui-text);
                    cursor:pointer;
                    transition:
                      transform 160ms ease,
                      border-color 160ms ease,
                      background 160ms ease;
                  "
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    aria-hidden="true"
                  >
                    <path d="M6 6l12 12"></path>
                    <path d="M18 6L6 18"></path>
                  </svg>
                </button>
              </div>
            </div>

            <section
              style="
                margin-top:4px;
                padding:16px;
                border-radius:16px;
                background:var(--sb-ui-surface);
                border:1px solid var(--sb-ui-border);
                box-shadow:0 10px 30px var(--sb-ui-shadow);
              "
            >
              <div
                style="
                  display:flex;
                  align-items:flex-start;
                  justify-content:space-between;
                  gap:18px;
                "
              >
                <div>
                  <div
                    style="
                      font-size:12px;
                      font-weight:650;
                      color:var(--sb-ui-muted);
                      letter-spacing:-0.05px;
                    "
                  >
                    Merit score
                  </div>

                  <div
                    style="
                      display:flex;
                      align-items:baseline;
                      gap:4px;
                      margin-top:5px;
                      color:var(--sb-ui-text);
                    "
                  >
                    <span
                      style="
                        font-size:34px;
                        font-weight:800;
                        line-height:1;
                        letter-spacing:-1.2px;
                      "
                    >
                      ${safeScore}
                    </span>

                    <span
                      style="
                        font-size:13px;
                        font-weight:600;
                        color:var(--sb-ui-muted);
                      "
                    >
                      /100
                    </span>
                  </div>
                </div>

                <div
                  style="
                    max-width:180px;
                    padding:7px 10px;
                    border-radius:10px;
                    background:var(--sb-ui-raised);
                    border:1px solid ${theme.border};
                    color:var(--sb-ui-text);
                    font-size:11.5px;
                    font-weight:700;
                    line-height:1.3;
                    text-align:center;
                  "
                >
                  ${badge}
                </div>
              </div>

              <div
                style="
                  margin-top:11px;
                  max-width:460px;
                  color:var(--sb-ui-muted);
                  font-size:12px;
                  line-height:1.45;
                "
              >
                ${description}
              </div>

              <div
                style="
                  margin-top:14px;
                  height:5px;
                  overflow:hidden;
                  border-radius:999px;
                  background:var(--sb-ui-raised);
                "
              >
                <div
                  style="
                    width:${safeScore}%;
                    height:100%;
                    border-radius:999px;
                    background:${theme.color};
                  "
                ></div>
              </div>
            </section>

              <div
                style="
                  margin-top:9px;
                  font-size:11.5px;
                  color:rgba(255,255,255,0.68);
                "
              >
                ${description}
              </div>

              <div
                style="
                  margin-top:12px;
                  height:8px;
                  border-radius:999px;
                  background:rgba(255,255,255,0.10);
                  overflow:hidden;
                  border:1px solid rgba(255,255,255,0.08);
                "
              >
                <div
                  style="
                    width:${safeScore}%;
                    height:100%;
                    border-radius:999px;
                    background:linear-gradient(90deg, ${theme.color}, rgba(255,255,255,0.72));
                    box-shadow:0 0 16px ${theme.glow};
                  "
                ></div>
              </div>

              <div
                style="
                  display:grid;
                  grid-template-columns: repeat(7, 1fr);
                  gap:4px;
                  margin-top:10px;
                "
              >
                <span title="Unverified Rumor" style="height:4px;border-radius:999px;background:#dc2626;opacity:${safeScore < 20 ? 1 : 0.28};"></span>
                <span title="Speculative" style="height:4px;border-radius:999px;background:#f97316;opacity:${safeScore >= 20 && safeScore < 35 ? 1 : 0.28};"></span>
                <span title="Low Evidence" style="height:4px;border-radius:999px;background:#facc15;opacity:${safeScore >= 35 && safeScore < 50 ? 1 : 0.28};"></span>
                <span title="Developing" style="height:4px;border-radius:999px;background:#2563eb;opacity:${safeScore >= 50 && safeScore < 65 ? 1 : 0.28};"></span>
                <span title="Substantial Signal" style="height:4px;border-radius:999px;background:#a855f7;opacity:${safeScore >= 65 && safeScore < 80 ? 1 : 0.28};"></span>
                <span title="Strong Evidence" style="height:4px;border-radius:999px;background:#14b8a6;opacity:${safeScore >= 80 && safeScore < 90 ? 1 : 0.28};"></span>
                <span title="High Credibility" style="height:4px;border-radius:999px;background:#16a34a;opacity:${safeScore >= 90 ? 1 : 0.28};"></span>
              </div>
            </div>

            <section
              style="
                margin-top:20px;
                padding:0 2px;
              "
            >
              <div
                style="
                  max-width:620px;
                  color:var(--sb-ui-text);
            <section
              style="
                margin-top:20px;
                padding:0 2px;
              "
            >
              <div
                style="
                  max-width:620px;
                  color:var(--sb-ui-text);
                  font-size:18px;
                  font-weight:800;
                  line-height:1.3;
                  letter-spacing:-0.4px;
                  overflow-wrap:anywhere;
                "
              >
                ${title}
              </div>
            </section>

            <div style="margin-top:14px;">
              <div
                style="
                  font-size:12px;
                  font-weight:850;
                  text-transform:uppercase;
                  letter-spacing:0.8px;
                  color:${theme.textAccent};
                "
              >
                TL;DR
              </div>

              ${
                bullets
                  ? `<ul
                      style="
                        margin:9px 0 0 18px;
                        padding:0;
                        color:rgba(255,255,255,0.91);
                        font-size:13px;
                        line-height:1.42;
                      "
                    >
                      ${bullets}
                    </ul>`
                  : `<div style="margin-top:8px;color:rgba(255,255,255,0.72);">
                      No summary returned.
                    </div>`
              }
            </div>

            ${
              reasons
                ? `
                  <div style="margin-top:14px;">
                    <div
                      style="
                        font-size:12px;
                        font-weight:850;
                        text-transform:uppercase;
                        letter-spacing:0.8px;
                        color:${theme.textAccent};
                      "
                    >
                      Why this score?
                    </div>

                    <ul
                      style="
                        margin:9px 0 0 18px;
                        padding:0;
                        color:rgba(255,255,255,0.82);
                        font-size:12.3px;
                        line-height:1.38;
                      "
                    >
                      ${reasons}
                    </ul>
                  </div>
                `
                : ``
            }

            ${
              data.url
                ? `
                  <div style="margin-top:15px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.10);">
                    <a href="${escapeHtml(data.url)}" target="_blank"
                      style="
                        color:${theme.textAccent};
                        text-decoration:none;
                        font-size:12.5px;
                        font-weight:800;
                      ">
                      Read original →
                    </a>
                  </div>
                `
                : ``
            }
          </div>
        `;

        document.body.appendChild(overlay);

        playSportabaseStartupAnimation(overlay);
        installSportabaseButtonDynamics(overlay);
        installSportabaseContentReveal(overlay);

        const articleContentScroll = overlay.querySelector(
          ".sportabase-content-scroll"
        );

        const originalArticleLink = overlay.querySelector(
          '.sportabase-content-scroll a[target="_blank"]'
        );

        if (originalArticleLink) {
          const articleActionBar =
            document.createElement("div");

          articleActionBar.id =
            "sportabase-article-action-bar";

          articleActionBar.style.cssText = `
            position:absolute;
            left:0;
            right:0;
            bottom:0;
            z-index:25;
            display:flex;
            align-items:center;
            justify-content:flex-end;
            min-height:68px;
            padding:12px 18px;
            background:var(--sb-ui-panel);
            border-top:1px solid var(--sb-ui-divider);
            box-shadow:0 -14px 32px rgba(0,0,0,0.16);
            backdrop-filter:blur(18px) saturate(135%);
          `;

          Object.assign(
            originalArticleLink.style,
            {
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              minWidth: "140px",
              padding: "10px 16px",
              borderRadius: "10px",
              background: "var(--sb-ui-raised)",
              color: "var(--sb-ui-text)",
              border: "1px solid var(--sb-ui-border)",
              boxShadow: "none",
              fontSize: "12.5px",
              fontWeight: "750",
              textDecoration: "none",
            }
          );

          articleActionBar.appendChild(
            originalArticleLink
          );

          overlay.appendChild(articleActionBar);

          if (articleContentScroll) {
            articleContentScroll.style.paddingBottom =
              "88px";
          }
        }

        applySportabaseUiPreferences(overlay);

        installSportabaseSettingsDrawer(
          overlay,
          SIZE_PRESETS
        );

        const cleanupGradientIntensity = installSportabaseGradientIntensityControls(overlay);

        const cleanupWindowControls = installSportabaseWindowControls(
          overlay,
          SIZE_PRESETS
        );

        const btn = document.getElementById("sportabase-close");

        if (btn) {
          btn.onclick = () => {
            closeSportabaseOverlay(overlay, [
              cleanupGradientIntensity,
              cleanupWindowControls,
            ]);
          };
        }
      }

      function showVideoOverlay() {
        ensureSportabaseStyles();

        const existing = document.getElementById("sportabase-overlay");
        if (existing) existing.remove();

        const SIZE_PRESETS = {
          compact: {
            label: "Compact",
            width: 440,
            height: 560,
          },
          comfort: {
            label: "Standard",
            width: 520,
            height: 680,
          },
          wide: {
            label: "Wide",
            width: 640,
            height: 760,
          },
          debug: {
            label: "Presentation",
            width: 760,
            height: 820,
          },
        };

        const savedMode = prefs?.sportabaseSizeMode || "comfort";
        const selectedPreset =
          SIZE_PRESETS[savedMode] || SIZE_PRESETS.comfort;

        const startWidth = clampNum(
          prefs?.sportabaseCustomWidth || selectedPreset.width,
          320,
          760
        );

        const startHeight = clampNum(
          prefs?.sportabaseCustomHeight || selectedPreset.height,
          260,
          Math.floor(window.innerHeight * 0.85)
        );

        const initialScore = 55;
        let currentTheme = getTheme(initialScore, "developing");

        const overlay = document.createElement("div");
        overlay.id = "sportabase-overlay";

        function humanizeVideoLabel(value) {
          return String(value || "unknown")
            .replace(/_/g, " ")
            .replace(
              /\b\w/g,
              (character) => character.toUpperCase()
            );
        }

        function applyVideoTheme(score, badge = "") {
          const safeScore = Math.max(
            0,
            Math.min(100, Number(score) || 0)
          );

          currentTheme = getTheme(safeScore, badge);

          overlay.style.setProperty(
            "--sb-color",
            currentTheme.color
          );
          overlay.style.setProperty(
            "--sb-glow",
            currentTheme.glow
          );
          overlay.style.setProperty(
            "--sb-soft-glow",
            currentTheme.softGlow
          );
          overlay.style.setProperty(
            "--sb-border",
            currentTheme.border
          );

          overlay.style.border =
            `1px solid ${currentTheme.border}`;

          overlay.style.boxShadow =
            `0 18px 48px rgba(0,0,0,0.42), ` +
            `0 0 24px ${currentTheme.softGlow}`;

          const analyzeButton = overlay.querySelector(
            "#sportabase-video-analyze"
          );

          const accentColor =
            prefs?.sportabaseAccentMode === "fixed"
              ? prefs?.sportabaseAccentColor || "#1ed760"
              : currentTheme.color;

          if (analyzeButton) {
            analyzeButton.style.background = accentColor;
            analyzeButton.style.color = "#0b0b0c";
            analyzeButton.style.border =
              "1px solid rgba(255,255,255,0.08)";
            analyzeButton.style.boxShadow =
              `0 8px 24px ${currentTheme.softGlow}`;
          }
        }

        overlay.style.position = "fixed";
        overlay.style.top = "18px";
        overlay.style.right = "18px";

        if (
          Number.isFinite(Number(prefs?.sportabaseLeft)) &&
          Number.isFinite(Number(prefs?.sportabaseTop))
        ) {
          const safeLeft = clampNum(
            prefs.sportabaseLeft,
            8,
            Math.max(8, window.innerWidth - startWidth - 8)
          );

          const safeTop = clampNum(
            prefs.sportabaseTop,
            8,
            Math.max(8, window.innerHeight - startHeight - 8)
          );

          overlay.style.left = `${safeLeft}px`;
          overlay.style.top = `${safeTop}px`;
          overlay.style.right = "auto";
        }

        overlay.style.width = `${startWidth}px`;
        overlay.style.height = `${startHeight}px`;
        overlay.style.minWidth = "320px";
        overlay.style.minHeight = "260px";
        overlay.style.maxWidth = "calc(100vw - 16px)";
        overlay.style.maxHeight = "90vh";
        overlay.style.overflow = "hidden";
        overlay.style.resize = "none";
        overlay.style.zIndex = "2147483647";
        overlay.style.borderRadius = "22px";

        overlay.style.fontFamily =
          "Inter, system-ui, -apple-system, " +
          "Segoe UI, Roboto, Arial, sans-serif";

        overlay.style.color = "#fff";

        overlay.style.background = `
          linear-gradient(
            105deg,
            rgba(2, 4, 10, 0.98) 0%,
            rgba(3, 6, 14, 0.96) 38%,
            rgba(6, 10, 22, 0.92) 62%,
            rgba(8, 13, 28, 0.96) 100%
          )
        `;

        const videoTitle =
          document
            .querySelector("h1 yt-formatted-string")
            ?.innerText?.trim() ||
          document.title.replace(" - YouTube", "") ||
          "YouTube video";

        overlay.innerHTML = `
          <div class="sportabase-gradient-field"></div>
          <div class="sportabase-gradient-ripple"></div>
          <div class="sportabase-gradient-depth"></div>

          <div
            class="sportabase-content-scroll"
            style="
              position:relative;
              z-index:2;
              width:100%;
              height:100%;
              overflow-y:auto;
              overflow-x:hidden;
              padding:calc(18px * var(--sb-density, 1));
              background:transparent;
              color:var(--sb-ui-text);
            "
          >
            <div
              id="sportabase-drag-handle"
              style="
                display:flex;
                align-items:center;
                justify-content:space-between;
                gap:14px;
                padding:2px 2px 14px;
                border-bottom:1px solid var(--sb-ui-border);
              "
            >
              <div
                style="
                  display:flex;
                  align-items:center;
                  gap:13px;
                  min-width:0;
                "
>
                ${getSportabaseLogoMarkup({
                  size: 42,
                  accent: "var(--sb-color)",
                  glow: "var(--sb-soft-glow)",
                  fontSize: 12,
                  radius: 14,
                  className: "sportabase-brand-mark",
                })}

                <div style="min-width:0;">
                  <div
                    style="
                      color:var(--sb-ui-text);
                      font-size:18px;
                      font-weight:820;
                      line-height:1.05;
                      letter-spacing:-0.4px;
                    "
                  >
                    Sportabase
                  </div>

                  <div
                    id="sportabase-video-mode-label"
                    style="
                      margin-top:3px;
                      color:var(--sb-ui-muted);
                      font-size:10.5px;
                      font-weight:700;
                      line-height:1.25;
                      letter-spacing:0.18px;
                      white-space:nowrap;
                      overflow:hidden;
                      text-overflow:ellipsis;
                    "
                  >
                    VIDEO INTELLIGENCE · YOUTUBE
                  </div>
                </div>
              </div>

              <div
                style="
                  display:flex;
                  align-items:center;
                  gap:7px;
                  flex:0 0 auto;
                "
              >
                <button
                  class="sportabase-settings-button"
                  aria-label="Open settings"
                  title="Settings"
                  style="
                    width:32px;
                    height:32px;
                    display:grid;
                    place-items:center;
                    padding:0;
                    border-radius:10px;
                    border:1px solid var(--sb-ui-border);
                    background:var(--sb-ui-raised);
                    color:var(--sb-ui-text);
                    cursor:pointer;
                    transition:
                      transform 160ms ease,
                      border-color 160ms ease,
                      background 160ms ease;
                  "
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    aria-hidden="true"
                  >
                    <path d="M4 7h10"></path>
                    <path d="M18 7h2"></path>
                    <circle cx="16" cy="7" r="2"></circle>

                    <path d="M4 17h2"></path>
                    <path d="M10 17h10"></path>
                    <circle cx="8" cy="17" r="2"></circle>
                  </svg>
                </button>

                <button
                  id="sportabase-video-close"
                  aria-label="Close Sportabase"
                  title="Close"
                  style="
                    width:32px;
                    height:32px;
                    display:grid;
                    place-items:center;
                    padding:0;
                    border-radius:10px;
                    border:1px solid var(--sb-ui-border);
                    background:var(--sb-ui-raised);
                    color:var(--sb-ui-text);
                    cursor:pointer;
                    transition:
                      transform 160ms ease,
                      border-color 160ms ease,
                      background 160ms ease;
                  "
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    aria-hidden="true"
                  >
                    <path d="M6 6l12 12"></path>
                    <path d="M18 6L6 18"></path>
                  </svg>
                </button>
              </div>
            </div>

            <div
              id="sportabase-video-landing-shell"
              style="
                min-height:100%;
                display:flex;
                flex-direction:column;
                justify-content:center;
                gap:12px;
                padding-bottom:18px;
              "
            >

            <section
              style="
                margin-top:16px;
                overflow:hidden;
                border:1px solid var(--sb-ui-border);
                border-radius:18px;
                background:var(--sb-ui-surface);
                box-shadow:0 10px 26px var(--sb-ui-shadow);
              "
            >
              <div
                style="
                  padding:16px;
                  background:
                    linear-gradient(
                      145deg,
                      color-mix(
                        in srgb,
                        var(--sb-color) 9%,
                        transparent
                      ),
                      transparent 58%
                    );
                "
              >
                <div
                  style="
                    display:flex;
                    align-items:center;
                    justify-content:space-between;
                    gap:12px;
                  "
                >
                  <div
                    style="
                      display:flex;
                      align-items:center;
                      gap:9px;
                      min-width:0;
                    "
                  >
                    <div
                      style="
                        width:34px;
                        height:34px;
                        flex:0 0 auto;
                        display:grid;
                        place-items:center;
                        border-radius:10px;
                        background:var(--sb-ui-raised);
                        border:1px solid var(--sb-ui-border);
                        color:var(--sb-color);
                      "
                    >
                      <svg
                        width="17"
                        height="17"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.8"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        aria-hidden="true"
                      >
                        <rect
                          x="3"
                          y="5"
                          width="18"
                          height="14"
                          rx="3"
                        ></rect>
                        <path d="m10 9 5 3-5 3V9Z"></path>
                      </svg>
                    </div>

                    <div style="min-width:0;">
                      <div
                        style="
                          color:var(--sb-ui-text);
                          font-size:13px;
                          font-weight:800;
                          line-height:1.2;
                          letter-spacing:-0.15px;
                        "
                      >
                        Video ready
                      </div>

                      <div
                        style="
                          margin-top:3px;
                          color:var(--sb-ui-muted);
                          font-size:10.5px;
                          font-weight:650;
                          line-height:1.25;
                        "
                      >
                        Transcript-based intelligence
                      </div>
                    </div>
                  </div>

                  <div
                    style="
                      display:flex;
                      align-items:center;
                      gap:6px;
                      flex:0 0 auto;
                      padding:5px 8px;
                      border-radius:999px;
                      background:var(--sb-ui-raised);
                      border:1px solid var(--sb-ui-border);
                      color:var(--sb-ui-muted);
                      font-size:9.5px;
                      font-weight:750;
                      letter-spacing:0.55px;
                    "
                  >
                    <span
                      style="
                        width:6px;
                        height:6px;
                        border-radius:50%;
                        background:var(--sb-color);
                        box-shadow:0 0 8px var(--sb-soft-glow);
                      "
                    ></span>
                    DETECTED
                  </div>
                </div>

                <div
                  style="
                    margin-top:15px;
                    padding-top:14px;
                    border-top:1px solid var(--sb-ui-divider);
                  "
                >
                  <div
                    style="
                      color:var(--sb-ui-muted);
                      font-size:10px;
                      font-weight:750;
                      letter-spacing:0.7px;
                      text-transform:uppercase;
                    "
                  >
                    Current video
                  </div>

                  <div
                    style="
                      margin-top:6px;
                      color:var(--sb-ui-text);
                      font-size:14px;
                      font-weight:800;
                      line-height:1.42;
                      letter-spacing:-0.2px;
                      display:-webkit-box;
                      -webkit-box-orient:vertical;
                      -webkit-line-clamp:2;
                      overflow:hidden;
                    "
                  >
                    ${escapeHtml(videoTitle)}
                  </div>
                </div>

                <button
                  id="sportabase-video-analyze"
                  style="
                    width:100%;
                    min-height:42px;
                    display:flex;
                    align-items:center;
                    justify-content:center;
                    gap:8px;
                    margin-top:16px;
                    padding:10px 14px;
                    border:1px solid
                      color-mix(
                        in srgb,
                        var(--sb-color) 72%,
                        white 28%
                      );
                    border-radius:12px;
                    background:var(--sb-color);
                    color:#ffffff;
                    font-size:12.5px;
                    font-weight:850;
                    letter-spacing:-0.1px;
                    cursor:pointer;
                    box-shadow:0 8px 20px var(--sb-soft-glow);
                    transition:
                      transform 160ms ease,
                      filter 160ms ease,
                      box-shadow 160ms ease;
                  "
                >
                  <svg
                    width="15"
                    height="15"
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

                  Analyze video
                </button>

                <div
                  style="
                    display:grid;
                    grid-template-columns:repeat(3, minmax(0, 1fr));
                    gap:7px;
                    margin-top:13px;
                  "
                >
                  <div
                    style="
                      padding:8px 6px;
                      border:1px solid var(--sb-ui-border);
                      border-radius:10px;
                      background:var(--sb-ui-raised);
                      color:var(--sb-ui-muted);
                      font-size:9.5px;
                      font-weight:700;
                      text-align:center;
                    "
                  >
                    Transcript
                  </div>

                  <div
                    style="
                      padding:8px 6px;
                      border:1px solid var(--sb-ui-border);
                      border-radius:10px;
                      background:var(--sb-ui-raised);
                      color:var(--sb-ui-muted);
                      font-size:9.5px;
                      font-weight:700;
                      text-align:center;
                    "
                  >
                    Evidence
                  </div>

                  <div
                    style="
                      padding:8px 6px;
                      border:1px solid var(--sb-ui-border);
                      border-radius:10px;
                      background:var(--sb-ui-raised);
                      color:var(--sb-ui-muted);
                      font-size:9.5px;
                      font-weight:700;
                      text-align:center;
                    "
                  >
                    Logic
                  </div>
                </div>
              </div>
            </section>

            <div
              id="sportabase-video-status"
              style="
                display:flex;
                align-items:flex-start;
                gap:9px;
                margin-top:11px;
                padding:10px 11px;
                border:1px solid var(--sb-ui-border);
                border-radius:12px;
                background:var(--sb-ui-raised);
                color:var(--sb-ui-muted);
                font-size:10.5px;
                font-weight:600;
                line-height:1.45;
              "
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--sb-color)"
                stroke-width="1.9"
                stroke-linecap="round"
                stroke-linejoin="round"
                style="flex:0 0 auto;margin-top:1px;"
                aria-hidden="true"
              >
                <path
                  d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"
                ></path>
                <path d="m9 12 2 2 4-4"></path>
              </svg>

              <span>
                Sportabase will find the transcript automatically.
                No manual transcript setup is required.
              </span>
            </div>
          </div>
        </div>
        `;

        document.body.appendChild(overlay);
        playSportabaseStartupAnimation(overlay);
        installSportabaseButtonDynamics(overlay);
        installSportabaseContentReveal(overlay);

        applyVideoTheme(initialScore, "developing");
        applySportabaseUiPreferences(overlay);

        installSportabaseSettingsDrawer(
          overlay,
          SIZE_PRESETS
        );

        const cleanupGradientIntensity =
          installSportabaseGradientIntensityControls(overlay);

        const cleanupWindowControls =
          installSportabaseWindowControls(
            overlay,
            SIZE_PRESETS
          );

        const closeButton = overlay.querySelector(
          "#sportabase-video-close"
        );

        const analyzeButton = overlay.querySelector(
          "#sportabase-video-analyze"
        );

        if (analyzeButton) {
          analyzeButton.addEventListener("mouseenter", () => {
            if (analyzeButton.disabled) return;

            analyzeButton.style.transform = "translateY(-1px)";
            analyzeButton.style.filter = "brightness(1.06)";
            analyzeButton.style.boxShadow =
              "0 11px 25px var(--sb-soft-glow)";
          });

          analyzeButton.addEventListener("mouseleave", () => {
            if (analyzeButton.disabled) return;

            analyzeButton.style.transform = "translateY(0)";
            analyzeButton.style.filter = "none";
            analyzeButton.style.boxShadow =
              "0 8px 20px var(--sb-soft-glow)";
          });

          analyzeButton.addEventListener("pointerdown", () => {
            if (analyzeButton.disabled) return;

            analyzeButton.style.transform = "scale(0.985)";
          });

          analyzeButton.addEventListener("pointerup", () => {
            if (analyzeButton.disabled) return;

            analyzeButton.style.transform = "translateY(-1px)";
          });
        }

        const status = overlay.querySelector(
          "#sportabase-video-status"
        );

        const modeLabel = overlay.querySelector(
          "#sportabase-video-mode-label"
        );

        const contentScroll = overlay.querySelector(
          ".sportabase-content-scroll"
        );

        const actionBar = document.createElement("div");
        actionBar.id = "sportabase-video-action-bar";

        actionBar.style.cssText = `
          position:absolute;
          left:0;
          right:0;
          bottom:0;
          z-index:25;
          display:flex;
          align-items:center;
          justify-content:flex-end;
          min-height:68px;
          padding:12px 18px;
          background:var(--sb-ui-panel);
          border-top:1px solid var(--sb-ui-divider);
          box-shadow:0 -14px 32px rgba(0,0,0,0.16);
          backdrop-filter:blur(18px) saturate(135%);
        `;

        if (analyzeButton) {
          Object.assign(
            analyzeButton.style,
            {
              width: "auto",
              minWidth: "150px",
              marginTop: "0",
              padding: "10px 16px",
              borderRadius: "10px",
              fontSize: "12.5px",
              fontWeight: "750",
            }
          );

          actionBar.appendChild(analyzeButton);
        }

        if (contentScroll) {
          contentScroll.style.paddingBottom = "88px";
        }

        overlay.appendChild(actionBar);

        closeButton.onclick = () => {
          closeSportabaseOverlay(overlay, [
            cleanupGradientIntensity,
            cleanupWindowControls,
          ]);
        };

        const wait = (milliseconds) =>
          new Promise(
            (resolve) => setTimeout(resolve, milliseconds)
          );

        const transcriptSelector =
          'transcript-segment-view-model span[role="text"]';

        function findTranscriptButton() {
          const directButton = document.querySelector(
            "ytd-video-description-transcript-section-renderer " +
            "button, " +
            'button[aria-label*="transcript" i], ' +
            'button[title*="transcript" i]'
          );

          if (directButton) return directButton;

          return Array.from(
            document.querySelectorAll(
              "button, " +
              "tp-yt-paper-button, " +
              "ytd-button-renderer button, " +
              "yt-button-shape button"
            )
          ).find((element) => {
            const searchableText = [
              element.innerText,
              element.getAttribute("aria-label"),
              element.getAttribute("title"),
            ]
              .filter(Boolean)
              .join(" ")
              .trim()
              .toLowerCase();

            return (
              searchableText.includes("show transcript") ||
              searchableText === "transcript"
            );
          });
        }

        async function ensureTranscriptVisible() {
          if (document.querySelector(transcriptSelector)) {
            return true;
          }

          let transcriptButton = findTranscriptButton();

          if (!transcriptButton) {
            const metadata =
              document.querySelector("ytd-watch-metadata");

            const expandButton = metadata?.querySelector(
              "#expand, " +
              "tp-yt-paper-button#expand, " +
              "ytd-text-inline-expander #expand"
            );

            if (expandButton) {
              expandButton.click();
              await wait(350);
              transcriptButton = findTranscriptButton();
            }
          }

          if (!transcriptButton) {
            return false;
          }

          transcriptButton.click();

          const startedAt = Date.now();

          while (
            !document.querySelector(transcriptSelector) &&
            Date.now() - startedAt < 7000
          ) {
            await wait(250);
          }

          return Boolean(
            document.querySelector(transcriptSelector)
          );
        }

        analyzeButton.onclick = async () => {
          if (analyzeButton.disabled) return;

          analyzeButton.disabled = true;
          analyzeButton.style.opacity = "0.72";
          analyzeButton.style.cursor = "wait";
          analyzeButton.textContent = "Finding transcript...";

          status.innerHTML = buildSportabaseLoadingMarkup(
            "Opening and reading the YouTube transcript...",
            18,
            "VIDEO INTELLIGENCE"
          );

          updateLoadingOverlay(
            "Opening and reading the YouTube transcript...",
            18
          );

          let videoLoadingTicker = null;

          try {
            const transcriptReady =
              await ensureTranscriptVisible();

            if (!transcriptReady) {
              throw new Error(
                "No transcript is available for this video. " +
                "The creator may have disabled captions."
              );
            }

            const transcriptParts = Array.from(
              document.querySelectorAll(transcriptSelector)
            )
              .map(
                (element) => element.innerText.trim()
              )
              .filter(Boolean);

            const transcript = transcriptParts.join(" ");

            if (!transcript) {
              throw new Error(
                "The transcript panel opened, but no " +
                "transcript text was found."
              );
            }

            analyzeButton.textContent = "Analyzing video...";

            const videoLoadingSteps = [
              {
                message: "Identifying the video's central claim...",
                progress: 62,
              },
              {
                message: "Tracing the supporting evidence...",
                progress: 72,
              },
              {
                message: "Testing the argument for gaps...",
                progress: 82,
              },
              {
                message: "Separating substance from presentation...",
                progress: 90,
              },
              {
                message: "Finalizing your video readout...",
                progress: 94,
              },
            ];

            let videoLoadingStepIndex = 0;

            videoLoadingTicker = setInterval(() => {
              const step =
                videoLoadingSteps[videoLoadingStepIndex];

              if (!step) return;

              updateLoadingOverlay(
                step.message,
                step.progress
              );

              if (
                videoLoadingStepIndex <
                videoLoadingSteps.length - 1
              ) {
                videoLoadingStepIndex += 1;
              }
            }, 1900);

            const response = await fetchJsonWithTimeout(
              `${API}/analyze/video`,
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({
                  title: videoTitle,
                  transcript,
                  url: window.location.href,
                }),
              },
              120000
            );

            if (!response.ok) {
              let errorDetail = "";

              try {
                const errorData = await response.json();

                errorDetail = String(
                  errorData?.detail ||
                  errorData?.message ||
                  ""
                );
              } catch (_) {
                errorDetail = "";
              }

              if (response.status === 429) {
                throw new Error(
                  "Gemini quota has been exhausted. " +
                  "Try again after the quota resets."
                );
              }

              if (response.status === 503) {
                throw new Error(
                  "Gemini is temporarily overloaded. " +
                  "Try again later."
                );
              }

              throw new Error(
                errorDetail ||
                `Video analysis failed with HTTP ` +
                `${response.status}.`
              );
            }

            const data = await response.json();

            if (
              data.verdict === "analysis_failed" ||
              String(data.claim || "")
                .toLowerCase()
                .includes("analysis failed")
            ) {
              const backendError =
                data.debug?.error ||
                data.evidence_used?.[0] ||
                "AI analysis failed.";

              throw new Error(String(backendError));
            }

            console.log(
              "[sportabase] Video analysis result:",
              data
            );

            const evidenceScore = Math.max(
              0,
              Math.min(
                100,
                Number(data.evidence_score) || 0
              )
            );

            const logicScore = Math.max(
              0,
              Math.min(
                100,
                Number(data.logic_score) || 0
              )
            );

            const supportScore = Math.round(
              (evidenceScore + logicScore) / 2
            );

            applyVideoTheme(
              supportScore,
              data.verdict
            );

            const rawContentType = String(
              data.content_type || ""
            )
              .trim()
              .toLowerCase();

            const contentTypeLabel =
              rawContentType &&
              rawContentType !== "unknown"
                ? humanizeVideoLabel(rawContentType)
                : "Video analysis";

            const verdictLabel =
              humanizeVideoLabel(data.verdict);

            if (modeLabel) {
              modeLabel.style.color =
                "var(--sb-ui-muted)";

              modeLabel.textContent =
                contentTypeLabel;
            }

            const evidenceItems =
              Array.isArray(data.evidence_used) &&
              data.evidence_used.length
                ? data.evidence_used
                    .map(
                      (item) => `
                        <li style="margin-top:6px;">
                          ${escapeHtml(String(item))}
                        </li>
                      `
                    )
                    .join("")
                : `
                    <li style="margin-top:6px;">
                      No evidence details returned.
                    </li>
                  `;

            status.innerHTML = `
              <section
                style="
                  style="
                    position:relative;
                    overflow:hidden;
                    padding:16px;
                    border-radius:18px;
                    background:
                      linear-gradient(
                        145deg,
                        color-mix(
                          in srgb,
                          var(--sb-color) 10%,
                          var(--sb-ui-surface)
                        ),
                        var(--sb-ui-surface) 58%
                      );
                    border:1px solid
                      color-mix(
                        in srgb,
                        var(--sb-color) 28%,
                        var(--sb-ui-border)
                      );
                    box-shadow:
                      0 10px 26px var(--sb-ui-shadow),
                      inset 0 1px 0 rgba(255,255,255,0.04);
                  "
              >
                <div
                  style="
                    display:flex;
                    align-items:center;
                    justify-content:space-between;
                    gap:14px;
                  "
                >
                  <div>
                    <div
                      style="
                        color:var(--sb-ui-muted);
                        font-size:10.5px;
                        font-weight:750;
                        line-height:1.2;
                        letter-spacing:0.7px;
                        text-transform:uppercase;
                      "
                    >
                      Overall support
                    </div>

                    <div
                      style="
                        display:flex;
                        align-items:baseline;
                        gap:4px;
                        margin-top:4px;
                        color:var(--sb-ui-text);
                      "
                    >
                      <span
                        style="
                          color:var(--sb-ui-text);
                          font-size:36px;
                          font-weight:900;
                          line-height:0.95;
                          letter-spacing:-1.8px;
                          text-shadow:0 5px 18px var(--sb-soft-glow);
                        "
                      >
                        ${supportScore}
                      </span>

                      <span
                        style="
                          font-size:13px;
                          font-weight:600;
                          color:var(--sb-ui-muted);
                        "
                      >
                        /100
                      </span>
                    </div>
                  </div>

                  <div
                    style="
                      max-width:175px;
                      padding:7px 10px;
                      border-radius:999px;
                      background:
                        color-mix(
                          in srgb,
                          var(--sb-color) 10%,
                          var(--sb-ui-raised)
                        );
                      border:1px solid
                        color-mix(
                          in srgb,
                          var(--sb-color) 38%,
                          var(--sb-ui-border)
                        );
                      color:var(--sb-ui-text);
                      font-size:10.5px;
                      font-weight:750;
                      line-height:1.3;
                      letter-spacing:0.15px;
                      text-align:center;
                    "
                  >
                    ${escapeHtml(verdictLabel)}
                  </div>
                </div>

                <div
                  style="
                    margin-top:12px;
                    height:5px;
                    border-radius:999px;
                    background:var(--sb-ui-raised);
                    overflow:hidden;
                  "
                >
                  <div
                    style="
                      width:${supportScore}%;
                      height:100%;
                      border-radius:999px;
                      background:${currentTheme.color};
                    "
                  ></div>
                </div>
              </section>

              <section
                style="
                  margin-top:17px;
                  padding:0 2px;
                "
              >
                <div
                  style="
                    font-size:14px;
                    font-weight:750;
                    letter-spacing:-0.2px;
                    color:var(--sb-ui-text);
                  "
                >
                  Main claim
                </div>

                <div
                  style="
                    margin-top:7px;
                    color:var(--sb-ui-text);
                    font-size:13px;
                    line-height:1.55;
                  "
                >
                  ${escapeHtml(
                    String(
                      data.claim ||
                      "No clear claim returned."
                    )
                  )}
                </div>
              </section>

              <div
                style="
                  display:grid;
                  grid-template-columns:
                    repeat(2, minmax(0, 1fr));
                  gap:8px;
                  margin-top:16px;
                "
              >
                <div
                  style="
                    display:flex;
                    align-items:baseline;
                    justify-content:space-between;
                    gap:8px;
                    padding:10px 11px;
                    border-radius:12px;
                    background:var(--sb-ui-raised);
                    border:1px solid var(--sb-ui-border);
                  "
                >
                  <span
                    style="
                      font-size:11.5px;
                      font-weight:600;
                      color:var(--sb-ui-muted);
                    "
                  >
                    Evidence
                  </span>

                  <span
                    style="
                      color:var(--sb-ui-text);
                      white-space:nowrap;
                    "
                  >
                    <strong
                      style="
                        font-size:18px;
                        font-weight:800;
                      "
                    >
                      ${evidenceScore}
                    </strong>

                    <span
                      style="
                        font-size:11px;
                        color:var(--sb-ui-muted);
                      "
                    >
                      /100
                    </span>
                  </span>
                </div>

                <div
                  style="
                    display:flex;
                    align-items:baseline;
                    justify-content:space-between;
                    gap:8px;
                    padding:10px 11px;
                    border-radius:12px;
                    background:var(--sb-ui-raised);
                    border:1px solid var(--sb-ui-border);
                  "
                >
                  <span
                    style="
                      font-size:11.5px;
                      font-weight:600;
                      color:var(--sb-ui-muted);
                    "
                  >
                    Logic
                  </span>

                  <span
                    style="
                      color:var(--sb-ui-text);
                      white-space:nowrap;
                    "
                  >
                    <strong
                      style="
                        font-size:18px;
                        font-weight:800;
                      "
                    >
                      ${logicScore}
                    </strong>

                    <span
                      style="
                        font-size:11px;
                        color:var(--sb-ui-muted);
                      "
                    >
                      /100
                    </span>
                  </span>
                </div>
              </div>

              style="
                margin-top:14px;
                padding:13px;
                border:1px solid var(--sb-ui-border);
                border-radius:14px;
                background:var(--sb-ui-raised);
              "
              >
                <div
                  style="
                    font-size:13px;
                    font-weight:700;
                    letter-spacing:-0.1px;
                    color:var(--sb-ui-text);
                  "
                >
                  Evidence used
                </div>

                <ul
                  style="
                    margin:9px 0 0 17px;
                    padding:0;
                    color:var(--sb-ui-muted);
                    font-size:12px;
                    line-height:1.55;
                  "
                >
                  ${evidenceItems}
                </ul>
              </section>

              <section
                style="
                  margin-top:10px;
                  padding:13px;
                  border:1px solid var(--sb-ui-border);
                  border-radius:14px;
                  background:var(--sb-ui-raised);
                "
              >
                <div
                  style="
                    font-size:13px;
                    font-weight:700;
                    letter-spacing:-0.1px;
                    color:var(--sb-ui-text);
                  "
                >
                  Logic check
                </div>

                <div
                  style="
                    margin-top:8px;
                    color:var(--sb-ui-muted);
                    font-size:12px;
                    line-height:1.55;
                  "
                >
                  ${escapeHtml(
                    String(
                      data.logic_check ||
                      "No logic assessment returned."
                    )
                  )}
                </div>
              </section>

              <section
                style="
                  margin-top:10px;
                  padding:13px;
                  border:1px solid var(--sb-ui-border);
                  border-radius:14px;
                  background:
                    linear-gradient(
                      145deg,
                      color-mix(
                        in srgb,
                        var(--sb-color) 6%,
                        var(--sb-ui-raised)
                      ),
                      var(--sb-ui-raised)
                    );
                "
              >
                <div
                  style="
                    font-size:13px;
                    font-weight:700;
                    letter-spacing:-0.1px;
                    color:var(--sb-ui-text);
                  "
                >
                  Hype check
                </div>

                <div
                  style="
                    margin-top:8px;
                    color:var(--sb-ui-muted);
                    font-size:12px;
                    line-height:1.55;
                  "
                >
                  ${escapeHtml(
                    String(
                      data.hype_check ||
                      "No hype assessment returned."
                    )
                  )}
                </div>
              </section>
            `;

            analyzeButton.innerHTML = `
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M20 6v5h-5"></path>
                <path d="M4 18v-5h5"></path>
                <path d="M18.5 9a7 7 0 0 0-11.7-2.6L4 9"></path>
                <path d="M5.5 15a7 7 0 0 0 11.7 2.6L20 15"></path>
              </svg>

              Reanalyze video
            `;

            Object.assign(
              analyzeButton.style,
              {
                width: "auto",
                minWidth: "0",
                minHeight: "34px",
                marginTop: "10px",
                padding: "8px 11px",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "7px",
                borderRadius: "10px",
                background:
                  "color-mix(in srgb, var(--sb-color) 8%, var(--sb-ui-raised))",
                color: "var(--sb-ui-text)",
                border:
                  "1px solid color-mix(in srgb, var(--sb-color) 34%, var(--sb-ui-border))",
                boxShadow: "none",
                fontSize: "11.5px",
                fontWeight: "750",
                letterSpacing: "-0.05px",
                cursor: "pointer",
              }
            );
          } catch (error) {
            console.error(
              "[sportabase] Video analysis failed:",
              error
            );

            applyVideoTheme(10, "unverified");

            const rawError = String(error?.message || error);

            let friendlyError =
              "Sportabase could not analyze this video right now. Please try again.";

            if (
              rawError.includes("503") ||
              rawError.toLowerCase().includes("high demand") ||
              rawError.toLowerCase().includes("unavailable")
            ) {
              friendlyError =
                "The AI analysis service is temporarily busy. Please try again in a moment.";
            }

            status.innerHTML = `
              <div
                style="
                  padding:14px;
                  border-radius:14px;
                  background:var(--sb-ui-surface);
                  border:1px solid rgba(239,68,68,0.48);
                  border-left:4px solid #ef4444;
                  color:var(--sb-ui-text);
                  box-shadow:0 12px 28px var(--sb-ui-shadow);
                "
              >
                <div
                  style="
                    font-weight:800;
                    color:#ef4444;
                    letter-spacing:-0.1px;
                  "
                >
                  Video analysis unavailable
                </div>

                <div
                  style="
                    margin-top:7px;
                    line-height:1.5;
                    color:var(--sb-ui-muted);
                    overflow-wrap:anywhere;
                  "
                >
                  ${escapeHtml(friendlyError)}
                </div>
              </div>
            `;

            analyzeButton.textContent = "Try Again";
          } finally {
            if (videoLoadingTicker) {
              clearInterval(videoLoadingTicker);
              videoLoadingTicker = null;
            }

            analyzeButton.disabled = false;
            analyzeButton.style.opacity = "1";
            analyzeButton.style.cursor = "pointer";
          }
        };
      }

      function cacheKeyForUrl(url) {
        return `sportabase_scan_cache_ai_local_v1:${url}`;
      }

      function buildSportabaseLoadingMarkup(
        message = "Reading this story...",
        progress = 15,
        modeLabel = "ARTICLE INTELLIGENCE"
      ) {
        const numericProgress = Number(progress);

        const safeProgress = Number.isFinite(numericProgress)
          ? Math.max(5, Math.min(95, Math.round(numericProgress)))
          : 15;

        return `
          <div
            class="sportabase-loader-content"
            style="
              position:relative;
              overflow:hidden;
              padding:18px;
              border-radius:18px;
              background:var(--sb-ui-surface);
              color:var(--sb-ui-text);
            "
          >
            <div
              aria-hidden="true"
              style="
                position:absolute;
                inset:-80px auto auto -70px;
                width:180px;
                height:180px;
                border-radius:50%;
                background:var(--sb-color);
                opacity:0.08;
                filter:blur(38px);
                pointer-events:none;
              "
            ></div>

            <div
              style="
                position:relative;
                display:flex;
                align-items:center;
                gap:13px;
              "
            >
              <div
                class="sportabase-loader-mark"
                aria-hidden="true"
                style="
                  position:relative;
                  width:46px;
                  height:46px;
                  flex:0 0 auto;
                  display:grid;
                  place-items:center;
                "
              >
                <div
                  class="sportabase-loader-orbit"
                  style="
                    position:absolute;
                    inset:0;
                    border-radius:14px;
                    border:1px solid var(--sb-ui-border);
                    border-top-color:var(--sb-color);
                    border-right-color:var(--sb-color);
                  "
                ></div>

                ${getSportabaseLogoMarkup({
                  size: 34,
                  accent: "var(--sb-color)",
                  glow: "var(--sb-soft-glow)",
                  fontSize: 11,
                  radius: 10,
                  className: "sportabase-loader-core",
                })}

              <div style="min-width:0;">
                <div
                  style="
                    color:var(--sb-ui-text);
                    font-size:16px;
                    font-weight:800;
                    line-height:1.15;
                    letter-spacing:-0.35px;
                  "
                >
                  Sportabase
                </div>

                <div
                  style="
                    margin-top:4px;
                    color:var(--sb-ui-muted);
                    font-size:10.5px;
                    font-weight:700;
                    line-height:1.3;
                    letter-spacing:0.7px;
                  "
                >
                  ${escapeHtml(modeLabel)}
                </div>
              </div>
            </div>

            <div
              style="
                position:relative;
                margin-top:18px;
                padding-top:15px;
                border-top:1px solid var(--sb-ui-border);
              "
            >
              <div
                id="sportabase-loading-message"
                aria-live="polite"
                style="
                  color:var(--sb-ui-text);
                  font-size:13px;
                  font-weight:650;
                  line-height:1.45;
                  overflow-wrap:anywhere;
                "
              >
                ${escapeHtml(message)}
              </div>

              <div
                style="
                  display:flex;
                  align-items:center;
                  justify-content:space-between;
                  gap:12px;
                  margin-top:12px;
                "
              >
                <div
                  style="
                    display:flex;
                    align-items:center;
                    gap:6px;
                    color:var(--sb-ui-muted);
                    font-size:10.5px;
                    font-weight:700;
                    letter-spacing:0.55px;
                  "
                >
                  <span class="sportabase-loader-dot"></span>
                  ANALYZING
                </div>

                <div
                  id="sportabase-loading-progress"
                  style="
                    color:var(--sb-ui-muted);
                    font-size:11px;
                    font-weight:750;
                    font-variant-numeric:tabular-nums;
                  "
                >
                  Stage 1 of 3
                </div>
              </div>

              <div
                id="sportabase-loading-track"
                role="progressbar"
                aria-label="Sportabase analysis progress"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow="${safeProgress}"
                style="
                  margin-top:8px;
                  height:7px;
                  overflow:hidden;
                  border-radius:999px;
                  background:var(--sb-ui-raised);
                  border:1px solid var(--sb-ui-border);
                "
              >
                <div
                  id="sportabase-loading-bar"
                  style="
                    width:${safeProgress}%;
                    height:100%;
                    border-radius:999px;
                    background:
                      linear-gradient(
                        90deg,
                        var(--sb-color),
                        rgba(255,255,255,0.94),
                        var(--sb-color)
                      );
                    background-size:220% 100%;
                    animation:
                      sportabase-loading-shimmer 1.8s linear infinite;
                    transition:width 500ms ease;
                  "
                ></div>
              </div>

              <div
                class="sportabase-loading-stages"
                style="
                  display:grid;
                  grid-template-columns:repeat(3, minmax(0, 1fr));
                  gap:7px;
                  margin-top:13px;
                "
              >
                <div
                  id="sportabase-loading-stage-read"
                  class="sportabase-loading-stage"
                >
                  <span class="sportabase-loading-stage-dot"></span>
                  Read
                </div>

                <div
                  id="sportabase-loading-stage-evaluate"
                  class="sportabase-loading-stage"
                >
                  <span class="sportabase-loading-stage-dot"></span>
                  Evaluate
                </div>

                <div
                  id="sportabase-loading-stage-distill"
                  class="sportabase-loading-stage"
                >
                  <span class="sportabase-loading-stage-dot"></span>
                  Distill
                </div>
              </div>
            </div>

            <style>
              @keyframes sportabase-loader-enter {
                from {
                  opacity:0;
                  transform:translateY(-8px) scale(0.975);
                }

                to {
                  opacity:1;
                  transform:translateY(0) scale(1);
                }
              }

              @keyframes sportabase-loader-orbit {
                from {
                  transform:rotate(0deg);
                }

                to {
                  transform:rotate(360deg);
                }
              }

              @keyframes sportabase-loader-core {
                0%, 100% {
                  transform:scale(1);
                }

                50% {
                  transform:scale(0.93);
                }
              }

              @keyframes sportabase-loader-dot {
                0%, 100% {
                  opacity:0.35;
                  transform:scale(0.78);
                }

                50% {
                  opacity:1;
                  transform:scale(1);
                }
              }

              @keyframes sportabase-loading-shimmer {
                from {
                  background-position:220% 50%;
                }

                to {
                  background-position:-20% 50%;
                }
              }

              #sportabase-loading-overlay {
                animation:
                  sportabase-loader-enter 260ms cubic-bezier(.2,.8,.2,1)
                  both;
              }

              .sportabase-loader-orbit {
                animation:
                  sportabase-loader-orbit 1.7s linear infinite;
              }

              .sportabase-loader-core {
                animation:
                  sportabase-loader-core 1.7s ease-in-out infinite;
              }

              .sportabase-loader-dot {
                width:6px;
                height:6px;
                display:inline-block;
                border-radius:50%;
                background:var(--sb-color);
                box-shadow:0 0 9px var(--sb-soft-glow);
                animation:
                  sportabase-loader-dot 1.25s ease-in-out infinite;
              }

              .sportabase-loading-stage {
                min-height:30px;
                display:flex;
                align-items:center;
                justify-content:center;
                gap:6px;
                padding:6px 8px;
                border:1px solid var(--sb-ui-border);
                border-radius:9px;
                background:var(--sb-ui-raised);
                color:var(--sb-ui-muted);
                font-size:9.5px;
                font-weight:700;
                letter-spacing:0.2px;
                transition:
                  color 220ms ease,
                  border-color 220ms ease,
                  background 220ms ease,
                  transform 220ms ease;
              }

              .sportabase-loading-stage-dot {
                width:5px;
                height:5px;
                flex:0 0 auto;
                border-radius:50%;
                background:var(--sb-ui-border);
                transition:
                  background 220ms ease,
                  box-shadow 220ms ease,
                  transform 220ms ease;
              }

              .sportabase-loading-stage.is-active {
                color:var(--sb-ui-text);
                border-color:var(--sb-color);
                background:
                  color-mix(
                    in srgb,
                    var(--sb-color) 9%,
                    var(--sb-ui-raised)
                  );
                transform:translateY(-1px);
              }

              .sportabase-loading-stage.is-active
                .sportabase-loading-stage-dot {
                background:var(--sb-color);
                box-shadow:0 0 10px var(--sb-soft-glow);
                animation:
                  sportabase-loader-dot 1.15s ease-in-out infinite;
              }

              .sportabase-loading-stage.is-complete {
                color:var(--sb-ui-text);
                border-color:
                  color-mix(
                    in srgb,
                    var(--sb-color) 35%,
                    var(--sb-ui-border)
                  );
              }

              .sportabase-loading-stage.is-complete
                .sportabase-loading-stage-dot {
                background:var(--sb-color);
                box-shadow:0 0 7px var(--sb-soft-glow);
              }

              @media (prefers-reduced-motion: reduce) {
                #sportabase-loading-overlay,
                .sportabase-loader-orbit,
                .sportabase-loader-core,
                .sportabase-loader-dot,
                #sportabase-loading-bar {
                  animation:none !important;
                }
              }
            </style>
          </div>
        `;
      }

      function showLoadingOverlay(
        message = "Reading this story...",
        progress = 15
      ) {
        const existingResult =
          document.getElementById("sportabase-overlay");

        if (existingResult) existingResult.remove();

        const existingLoading =
          document.getElementById("sportabase-loading-overlay");

        if (existingLoading) existingLoading.remove();

        const overlay = document.createElement("div");
        overlay.id = "sportabase-loading-overlay";
        overlay.setAttribute("role", "status");
        overlay.setAttribute("aria-live", "polite");

        overlay.style.setProperty(
          "--sb-color",
          prefs?.sportabaseAccentMode === "custom"
            ? prefs?.sportabaseAccentColor || "#2563eb"
            : "#2563eb"
        );

        overlay.style.setProperty(
          "--sb-soft-glow",
          "rgba(37, 99, 235, 0.24)"
        );

        overlay.style.position = "fixed";
        overlay.style.top = "18px";
        overlay.style.right = "18px";
        overlay.style.width = "360px";
        overlay.style.maxWidth = "calc(100vw - 36px)";
        overlay.style.zIndex = "2147483647";
        overlay.style.borderRadius = "20px";
        overlay.style.padding = "0";
        overlay.style.overflow = "hidden";
        overlay.style.background = "var(--sb-ui-surface)";
        overlay.style.border = "1px solid var(--sb-ui-border)";
        overlay.style.boxShadow =
          "0 24px 65px var(--sb-ui-shadow)";
        overlay.style.fontFamily =
          "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";

        overlay.innerHTML = buildSportabaseLoadingMarkup(
          message,
          progress,
          "ARTICLE INTELLIGENCE"
        );

        document.body.appendChild(overlay);
        applySportabaseUiPreferences(overlay);
        updateLoadingOverlay(message, progress);

      }

      function updateLoadingOverlay(message, progress = null) {
        const messageEl = document.getElementById(
          "sportabase-loading-message"
        );

        if (messageEl && message !== null) {
          messageEl.textContent = String(message);
        }

        if (progress === null) return;

        const numericProgress = Number(progress);

        if (!Number.isFinite(numericProgress)) return;

        const safeProgress = Math.max(
          5,
          Math.min(95, Math.round(numericProgress))
        );

        const barEl = document.getElementById(
          "sportabase-loading-bar"
        );

        if (barEl) {
          barEl.style.width = `${safeProgress}%`;
        }

        const progressEl = document.getElementById(
          "sportabase-loading-progress"
        );

        if (progressEl) {
          const stageNumber =
            safeProgress < 48
              ? 1
              : safeProgress < 78
                ? 2
                : 3;

          progressEl.textContent =
            `Stage ${stageNumber} of 3`;
        }

        const trackEl = document.getElementById(
          "sportabase-loading-track"
        );

        const readStage = document.getElementById(
          "sportabase-loading-stage-read"
        );

        const evaluateStage = document.getElementById(
          "sportabase-loading-stage-evaluate"
        );

        const distillStage = document.getElementById(
          "sportabase-loading-stage-distill"
        );

        const stages = [
          readStage,
          evaluateStage,
          distillStage,
        ].filter(Boolean);

        stages.forEach((stage) => {
          stage.classList.remove(
            "is-active",
            "is-complete"
          );
        });

        if (safeProgress < 48) {
          readStage?.classList.add("is-active");
        } else {
          readStage?.classList.add("is-complete");

          if (safeProgress < 78) {
            evaluateStage?.classList.add("is-active");
          } else {
            evaluateStage?.classList.add("is-complete");
            distillStage?.classList.add("is-active");
          }
        }
      }

      function removeLoadingOverlay() {
        const overlay = document.getElementById("sportabase-loading-overlay");
        if (overlay) overlay.remove();
      }

      function startLoadingTicker() {
        const steps = [
          {
            message: "Extracting the main story...",
            progress: 32,
          },
          {
            message: "Separating reporting from filler...",
            progress: 44,
          },
          {
            message: "Evaluating claims and evidence...",
            progress: 58,
          },
          {
            message: "Checking context and certainty...",
            progress: 70,
          },
          {
            message: "Distilling the key takeaways...",
            progress: 84,
          },
          {
            message: "Finalizing your Sportabase readout...",
            progress: 93,
          },
        ];

        let index = 0;

        updateLoadingOverlay(
          steps[index].message,
          steps[index].progress
        );

        return setInterval(() => {
          if (index < steps.length - 1) {
            index += 1;
          }

          const step = steps[index];

          updateLoadingOverlay(
            step.message,
            step.progress
          );
        }, 1900);
      }

      async function setCachedScan(url, data) {
        try {
          if (!chrome?.storage?.local) return;

          const key = cacheKeyForUrl(url);

          await chrome.storage.local.set({
            [key]: {
              savedAt: Date.now(),
              data,
            },
          });
        } catch (e) {
          log("cache write failed:", e);
        }
      }

      async function fetchJsonWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        try {
          const response = await fetch(url, {
            ...options,
            signal: controller.signal,
          });

          return response;
        } finally {
          clearTimeout(timeoutId);
        }
      }

      const isYouTubeVideoPage =
        window.location.href.includes("youtube.com/watch") ||
        document.querySelector("ytd-watch-flexy") !== null;

      const startedAt = performance.now();

      if (isYouTubeVideoPage) {
        showVideoOverlay();
        return;
      }

      showLoadingOverlay("Reading the page...", 15);

      const rawText = getReadableText();
      log("extracted text length:", rawText.length);

      updateLoadingOverlay("Finding the actual story...", 25);

      const trimmedText = rawText.slice(0, MAX_ARTICLE_CHARS);
      log("text sent to backend:", trimmedText.length);

      const payload = {
        title: document.title || "Untitled",
        url: location.href,
        text: trimmedText,
        max_bullets: 3,
      };

      if (!payload.text || payload.text.length < 200) {
        removeLoadingOverlay();
        alert("Couldn’t extract enough article text on this page.");
        return;
      }

      let loadingTicker = null;

      try {
        updateLoadingOverlay("Sending article to Sportabase...");

        const cached = await getCachedScan(payload.url);

        if (cached) {
          log("cache hit");

          removeLoadingOverlay();

          showOverlay({
            ...cached,
            reasons: [
              "Loaded instantly from local cache.",
              ...(Array.isArray(cached.reasons) ? cached.reasons : []),
            ],
          });

          return;
        }

        updateLoadingOverlay("Sending article to Sportabase...");
        loadingTicker = startLoadingTicker();

        const resp = await fetchJsonWithTimeout(`${API}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        clearInterval(loadingTicker);
        loadingTicker = null;

        log("backend status:", resp.status);

        if (!resp.ok) {
          const t = await resp.text();
          removeLoadingOverlay();
          alert("Sportabase backend error:\n\n" + t);
          return;
        }

        updateLoadingOverlay("Building your readout...");

        const data = await resp.json();

        const totalMs = Math.round(performance.now() - startedAt);
        log("response:", data);
        log("Rule article type:", data?.debug?.rule_article_type);
        log("AI shadow article type:", data?.debug?.ai_article_type_shadow);
        log("total client time ms:", totalMs);

        await setCachedScan(payload.url, data);

        try {
          removeLoadingOverlay();
          showOverlay(data);
        } catch (e) {
          removeLoadingOverlay();

          alert(
            "Overlay failed, but summary worked:\n\n" +
              JSON.stringify(data, null, 2)
          );

          log("overlay error:", e);
        }
      } catch (e) {
        if (loadingTicker) {
          clearInterval(loadingTicker);
          loadingTicker = null;
        }
        removeLoadingOverlay();

        if (e?.name === "AbortError") {
          alert(
            `Sportabase took longer than ${Math.round(FETCH_TIMEOUT_MS / 1000)} seconds.\n\n` +
              "Try again once. If the second try is faster, the backend was probably waking up."
          );
        } else {
          alert(`Failed to reach Sportabase backend at ${API}.\n\n${e}`);
        }

        log("fetch error:", e);
      }
    },
    args: [
      API,
      prefs,
      {
        MAX_ARTICLE_CHARS,
        CACHE_TTL_MS,
        FETCH_TIMEOUT_MS,
      },
    ],
  });
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;

  try {
    await injectAndRun(tab.id);
  } catch (error) {
    const message = String(error?.message || error || "");

    // This can happen if the page reloads/navigates while the extension is injecting.
    // It is not a real Sportabase analysis failure.
    if (
      message.includes("Frame with ID 0 was removed") ||
      message.includes("Extension context invalidated") ||
      message.includes("Cannot access contents of url")
    ) {
      console.warn("[sportabase] injection skipped:", message);
      return;
    }

    console.error("[sportabase] injection failed:", error);
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "SPORTABASE_SAVE_OVERLAY_PREFS") return;

  chrome.storage.local.set(message.payload || {});
});
