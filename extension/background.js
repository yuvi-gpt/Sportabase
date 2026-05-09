const API = "http://127.0.0.1:8000";
// const API = "https://sportabase-api.onrender.com"; // switch back after Render deploy

async function injectAndRun(tabId) {
  const prefs = await chrome.storage.local.get({
    sportabaseSizeMode: "compact",
    sportabaseCustomWidth: null,
    sportabaseCustomHeight: null,
    sportabaseLeft: null,
    sportabaseTop: null,
  });

  await chrome.scripting.executeScript({
    target: { tabId },
    func: async (API, prefs) => {
      const log = (...args) => console.log("[sportabase]", ...args);

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
            glow: "rgba(220, 38, 38, 0.68)",
            softGlow: "rgba(220, 38, 38, 0.25)",
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
            glow: "rgba(249, 115, 22, 0.62)",
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
            glow: "rgba(250, 204, 21, 0.58)",
            softGlow: "rgba(250, 204, 21, 0.22)",
            border: "rgba(250, 204, 21, 0.58)",
            textAccent: "#fef3c7",
            description: "Some signal, but evidence is still thin.",
          };
        }

        if (score < 65 || normalizedBadge.includes("developing")) {
          return {
            label: "Developing",
            shortLabel: "Developing",
            color: "#2563eb",
            glow: "rgba(37, 99, 235, 0.60)",
            softGlow: "rgba(37, 99, 235, 0.24)",
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
            softGlow: "rgba(168, 85, 247, 0.23)",
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
            glow: "rgba(20, 184, 166, 0.60)",
            softGlow: "rgba(20, 184, 166, 0.23)",
            border: "rgba(20, 184, 166, 0.58)",
            textAccent: "#ccfbf1",
            description: "Strong sourcing and detail, just below elite confidence.",
          };
        }

        return {
          label: "High Credibility",
          shortLabel: "High Cred",
          color: "#16a34a",
          glow: "rgba(22, 163, 74, 0.66)",
          softGlow: "rgba(22, 163, 74, 0.26)",
          border: "rgba(22, 163, 74, 0.65)",
          textAccent: "#dcfce7",
          description: "Rare tier: strong official/evidence signals.",
        };
      }

      function ensureSportabaseStyles() {
        const existing = document.getElementById("sportabase-dynamic-styles");
        if (existing) existing.remove();

        const style = document.createElement("style");
        style.id = "sportabase-dynamic-styles";
        style.textContent = `
          @keyframes sportabase-aurora-drift {
            0% {
              transform: translate3d(0px, 0px, 0) scale(1);
              opacity: 0.55;
            }
            50% {
              transform: translate3d(-18px, 14px, 0) scale(1.08);
              opacity: 0.82;
            }
            100% {
              transform: translate3d(16px, -10px, 0) scale(0.98);
              opacity: 0.6;
            }
          }

          @keyframes sportabase-orb-float {
            0%, 100% {
              transform: translateY(0px) translateX(0px) scale(1);
              opacity: 0.42;
            }
            50% {
              transform: translateY(-10px) translateX(8px) scale(1.06);
              opacity: 0.66;
            }
          }

          @keyframes sportabase-panel-float {
            0%, 100% {
              transform: translateY(0px);
            }
            50% {
              transform: translateY(-3px);
            }
          }

          #sportabase-overlay * {
            box-sizing: border-box;
          }

          #sportabase-overlay {
            animation: sportabase-panel-float 5.5s ease-in-out infinite;
          }

          #sportabase-overlay .sportabase-aurora {
            animation: sportabase-aurora-drift 13s ease-in-out infinite alternate;
            mix-blend-mode: screen;
          }

          #sportabase-overlay .sportabase-orb {
            animation: sportabase-orb-float 9s ease-in-out infinite;
          }

          #sportabase-overlay::-webkit-scrollbar,
          #sportabase-overlay *::-webkit-scrollbar {
            width: 8px;
          }

          #sportabase-overlay::-webkit-scrollbar-thumb,
          #sportabase-overlay *::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.18);
            border-radius: 999px;
          }

          #sportabase-overlay .sportabase-size-btn {
            background: rgba(255,255,255,0.09);
            color: rgba(255,255,255,0.86);
            border: 1px solid rgba(255,255,255,0.13);
            border-radius: 999px;
            padding: 4px 7px;
            font-size: 10.5px;
            font-weight: 800;
            cursor: pointer;
            line-height: 1;
          }

          #sportabase-overlay .sportabase-size-btn:hover {
            background: rgba(255,255,255,0.16);
          }

          #sportabase-overlay .sportabase-resize-handle {
            position: absolute;
            z-index: 2147483647;
            background: transparent;
            pointer-events: auto;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="n"] {
            top: 0;
            left: 18px;
            right: 18px;
            height: 14px;
            cursor: ns-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="s"] {
            bottom: 0;
            left: 18px;
            right: 18px;
            height: 14px;
            cursor: ns-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="e"] {
            top: 18px;
            right: 0;
            bottom: 18px;
            width: 14px;
            cursor: ew-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="w"] {
            top: 18px;
            left: 0;
            bottom: 18px;
            width: 14px;
            cursor: ew-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="ne"] {
            top: 0;
            right: 0;
            width: 22px;
            height: 22px;
            cursor: nesw-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="nw"] {
            top: 0;
            left: 0;
            width: 22px;
            height: 22px;
            cursor: nwse-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="se"] {
            bottom: 0;
            right: 0;
            width: 24px;
            height: 24px;
            cursor: nwse-resize;
          }

          #sportabase-overlay .sportabase-resize-handle[data-dir="sw"] {
            bottom: 0;
            left: 0;
            width: 24px;
            height: 24px;
            cursor: nesw-resize;
          }
        `;

        document.head.appendChild(style);
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
          compact: { label: "S", width: 360, height: 430 },
          comfort: { label: "M", width: 430, height: 560 },
          wide: { label: "L", width: 520, height: 620 },
          debug: { label: "XL", width: 610, height: 720 },
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
        overlay.style.boxShadow = `0 24px 70px rgba(0,0,0,0.58), 0 0 42px ${theme.softGlow}`;
        overlay.style.fontFamily =
          "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
        overlay.style.color = "#fff";
        overlay.style.background = `
          linear-gradient(135deg, rgba(4,6,12,0.98) 0%, rgba(6,9,18,0.97) 42%, rgba(8,12,24,0.96) 100%)
        `;

        overlay.innerHTML = `
          <div class="sportabase-aurora"
            style="
              position:absolute;
              top:-40px;
              right:-20px;
              width:62%;
              height:52%;
              background:
                radial-gradient(circle at 18% 32%, ${theme.softGlow} 0%, transparent 34%),
                radial-gradient(circle at 62% 24%, ${theme.glow} 0%, transparent 28%),
                radial-gradient(circle at 78% 72%, ${theme.softGlow} 0%, transparent 40%);
              filter: blur(34px);
              opacity:0.72;
              pointer-events:none;
            ">
          </div>

          <div class="sportabase-orb"
            style="
              position:absolute;
              top:10px;
              right:26px;
              width:150px;
              height:150px;
              border-radius:50%;
              background:radial-gradient(circle, ${theme.softGlow} 0%, transparent 68%);
              filter: blur(20px);
              opacity:0.46;
              pointer-events:none;
            ">
          </div>

          <div class="sportabase-orb"
            style="
              position:absolute;
              bottom:36px;
              right:50px;
              width:220px;
              height:220px;
              border-radius:50%;
              background:radial-gradient(circle, ${theme.softGlow} 0%, transparent 72%);
              filter: blur(28px);
              opacity:0.22;
              pointer-events:none;
              animation-delay:-4s;
            ">
          </div>

          <div
            style="
              position:relative;
              z-index:2;
              padding:16px;
              background:
                linear-gradient(90deg, rgba(2,4,8,0.84) 0%, rgba(4,6,12,0.70) 50%, rgba(6,10,18,0.34) 100%);
              backdrop-filter: blur(14px) saturate(120%);
              height:100%;
              max-height:100%;
              overflow:auto;
            "
          >
            <div id="sportabase-drag-handle" style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
              <div>
                <div
                  style="
                    font-weight:850;
                    font-size:15px;
                    letter-spacing:0.2px;
                    display:flex;
                    align-items:center;
                    gap:8px;
                  "
                >
                  <span
                    style="
                      width:9px;
                      height:9px;
                      border-radius:50%;
                      background:${theme.color};
                      box-shadow:0 0 16px ${theme.glow};
                      display:inline-block;
                    ">
                  </span>
                  Sportabase Scan
                </div>

                <div
                  style="
                    margin-top:8px;
                    display:inline-flex;
                    align-items:center;
                    gap:6px;
                    padding:5px 8px;
                    border-radius:999px;
                    background:rgba(0,0,0,0.30);
                    border:1px solid rgba(255,255,255,0.12);
                    color:${theme.textAccent};
                    font-size:11.5px;
                    font-weight:750;
                  "
                >
                  ${articleTypeLabel} · ${articleSubtype} · ${typeConfidence}%
                </div>

                <div
                  style="
                    margin-top:8px;
                    display:flex;
                    align-items:center;
                    gap:5px;
                    flex-wrap:wrap;
                  "
                >
                  <button class="sportabase-size-btn" data-size-mode="compact">S</button>
                  <button class="sportabase-size-btn" data-size-mode="comfort">M</button>
                  <button class="sportabase-size-btn" data-size-mode="wide">L</button>
                  <button class="sportabase-size-btn" data-size-mode="debug">XL</button>
                  <button class="sportabase-size-btn" data-size-mode="reset">Reset</button>
                </div>
              </div>

              <button id="sportabase-close"
                style="
                  background:rgba(255,255,255,0.10);
                  color:#fff;
                  border:1px solid rgba(255,255,255,0.14);
                  border-radius:999px;
                  padding:7px 10px;
                  cursor:pointer;
                  font-size:12px;
                  height:max-content;
                ">
                Close
              </button>
            </div>

            <div
              style="
                margin-top:14px;
                padding:13px;
                border-radius:17px;
                background:rgba(0,0,0,0.36);
                border:1px solid rgba(255,255,255,0.10);
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
                <div>
                  <div style="font-size:12px;color:rgba(255,255,255,0.68);">
                    Merit Score
                  </div>
                  <div style="font-size:32px;font-weight:900;line-height:1;margin-top:4px;">
                    ${safeScore}<span style="font-size:15px;color:rgba(255,255,255,0.58);">/100</span>
                  </div>
                </div>

                <div
                  style="
                    color:${theme.textAccent};
                    border:1px solid ${theme.border};
                    background:rgba(0,0,0,0.28);
                    box-shadow:0 0 18px ${theme.softGlow};
                    padding:8px 10px;
                    border-radius:999px;
                    font-size:12px;
                    font-weight:800;
                    white-space:nowrap;
                  "
                >
                  ${badge}
                </div>
              </div>

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

            <div style="margin-top:14px;">
              <div
                style="
                  font-size:13px;
                  font-weight:850;
                  color:rgba(255,255,255,0.94);
                  line-height:1.35;
                "
              >
                ${title}
              </div>
            </div>

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
                      Signals
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
                      Open source →
                    </a>
                  </div>
                `
                : ``
            }
          </div>
        `;

        document.body.appendChild(overlay);

        const cleanupWindowControls = installSportabaseWindowControls(
          overlay,
          SIZE_PRESETS
        );

        const btn = document.getElementById("sportabase-close");
        if (btn) {
          btn.onclick = () => {
            cleanupWindowControls();
            overlay.remove();
          };
        }
      }

      const text = getReadableText();
      log("extracted text length:", text.length);

      const payload = {
        title: document.title || "Untitled",
        url: location.href,
        text,
        max_bullets: 3,
      };

      if (!payload.text || payload.text.length < 200) {
        alert("Couldn’t extract enough article text on this page.");
        return;
      }

      try {
        const resp = await fetch(`${API}/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        log("backend status:", resp.status);

        if (!resp.ok) {
          const t = await resp.text();
          alert("Sportabase backend error:\n\n" + t);
          return;
        }

        const data = await resp.json();
        log("response:", data);

        try {
          showOverlay(data);
        } catch (e) {
          alert(
            "Overlay failed, but summary worked:\n\n" +
              JSON.stringify(data, null, 2)
          );
          log("overlay error:", e);
        }
      } catch (e) {
        alert(`Failed to reach Sportabase backend at ${API}.\n\n${e}`);
        log("fetch error:", e);
      }
    },
    args: [API, prefs],
  });
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;
  await injectAndRun(tab.id);
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== "SPORTABASE_SAVE_OVERLAY_PREFS") return;

  chrome.storage.local.set(message.payload || {});
});