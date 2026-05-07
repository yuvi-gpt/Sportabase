const API = "http://127.0.0.1:8000";
// const API = "https://sportabase-api.onrender.com"; // switch back after Render deploy

async function injectAndRun(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: async (API) => {
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
          @keyframes sportabase-ripple {
            0% {
              transform: translateX(18px) translateY(-8px) scale(1);
              opacity: 0.72;
              filter: blur(0px);
            }
            50% {
              transform: translateX(-10px) translateY(12px) scale(1.08);
              opacity: 0.92;
              filter: blur(1px);
            }
            100% {
              transform: translateX(18px) translateY(-8px) scale(1);
              opacity: 0.72;
              filter: blur(0px);
            }
          }

          @keyframes sportabase-sheen {
            0% {
              transform: translateX(-80%) rotate(8deg);
              opacity: 0;
            }
            35% {
              opacity: 0.18;
            }
            70% {
              opacity: 0.08;
            }
            100% {
              transform: translateX(115%) rotate(8deg);
              opacity: 0;
            }
          }

          @keyframes sportabase-float {
            0%, 100% {
              transform: translateY(0px);
            }
            50% {
              transform: translateY(-4px);
            }
          }

          #sportabase-overlay * {
            box-sizing: border-box;
          }

          #sportabase-overlay {
            animation: sportabase-float 4.5s ease-in-out infinite;
          }

          #sportabase-overlay .sportabase-ripple {
            animation: sportabase-ripple 6s ease-in-out infinite;
          }

          #sportabase-overlay .sportabase-sheen {
            animation: sportabase-sheen 5.8s ease-in-out infinite;
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

        const bullets = (data.summary || data.tldr || [])
          .map((b) => `<li class="sportabase-bullet">${escapeHtml(b)}</li>`)
          .join("");

        const reasons = (data.reasons || [])
          .map((r) => `<li class="sportabase-reason">${escapeHtml(r)}</li>`)
          .join("");

        const overlay = document.createElement("div");
        overlay.id = "sportabase-overlay";

        overlay.style.position = "fixed";
        overlay.style.top = "18px";
        overlay.style.right = "18px";
        overlay.style.width = "430px";
        overlay.style.maxHeight = "78vh";
        overlay.style.overflow = "hidden";
        overlay.style.zIndex = "2147483647";
        overlay.style.borderRadius = "22px";
        overlay.style.border = `1px solid ${theme.border}`;
        overlay.style.boxShadow = `0 24px 70px rgba(0,0,0,0.58), 0 0 42px ${theme.softGlow}`;
        overlay.style.fontFamily =
          "Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif";
        overlay.style.color = "#fff";
        overlay.style.background = `
          radial-gradient(circle at 88% 28%, ${theme.glow} 0%, transparent 34%),
          radial-gradient(circle at 105% 85%, ${theme.softGlow} 0%, transparent 38%),
          linear-gradient(270deg, ${theme.softGlow} 0%, rgba(10,10,12,0.98) 48%, rgba(5,5,6,0.99) 100%)
        `;

        overlay.innerHTML = `
          <div class="sportabase-ripple"
            style="
              position:absolute;
              inset:-80px -90px -80px 38%;
              background:
                radial-gradient(circle at 50% 35%, ${theme.glow} 0%, transparent 28%),
                radial-gradient(circle at 70% 70%, ${theme.softGlow} 0%, transparent 36%);
              pointer-events:none;
            ">
          </div>

          <div class="sportabase-sheen"
            style="
              position:absolute;
              top:-60px;
              bottom:-60px;
              width:120px;
              left:0;
              background:linear-gradient(90deg, transparent, rgba(255,255,255,0.24), transparent);
              pointer-events:none;
            ">
          </div>

          <div
            style="
              position:relative;
              z-index:2;
              padding:16px;
              background:
                linear-gradient(90deg, rgba(0,0,0,0.72) 0%, rgba(0,0,0,0.46) 52%, rgba(0,0,0,0.18) 100%);
              backdrop-filter: blur(11px);
              max-height:78vh;
              overflow:auto;
            "
          >
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
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
                    margin-top:6px;
                    font-size:12px;
                    color:rgba(255,255,255,0.72);
                  "
                >
                  AI sports credibility read
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

        const btn = document.getElementById("sportabase-close");
        if (btn) btn.onclick = () => overlay.remove();
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
    args: [API],
  });
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;
  await injectAndRun(tab.id);
});