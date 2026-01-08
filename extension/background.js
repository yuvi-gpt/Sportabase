

async function injectAndRun(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: async () => {
      // debugging helper (shows in the PAGE console)
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
            ".RichTextContainer"
            ];


        let root = null;

        for (const sel of candidates) {
          const el = document.querySelector(sel);
          if (el && (el.innerText || "").trim().length > 400) {
            root = el;
            break;
          }
        }

        // fallback: biggest text block on the page (helps ESPN)
        if (!root) {
            const blocks = Array.from(document.querySelectorAll("article, main, section, div"))
                .map((el) => {
                    const ps = el.querySelectorAll("p");
                    let pTextLen = 0;
                    ps.forEach(p => { pTextLen += ((p.innerText || "").trim().length); });
                    return { el, pCount: ps.length, pTextLen };
                })
                .filter(x => x.pCount >= 3 && x.pTextLen >= 600)
                .sort((a, b) => b.pTextLen - a.pTextLen);

            if (blocks.length) root = blocks[0].el;
            }

        if (!root) root = document.body;

        const junkSelectors = [
          "nav", "header", "footer", "aside",
          "[role='navigation']",
          ".nav", ".navbar", ".menu",
          ".subscribe", ".paywall", ".modal", ".popup",
          ".cookie", ".cookies", "#cookie", "#cookies",
          ".comments", "#comments",
          "script", "style", "noscript"
        ];

        const clone = root.cloneNode(true);
        junkSelectors.forEach((sel) => {
          clone.querySelectorAll(sel).forEach((el) => el.remove());
        });

        // prefer paragraph text if possible
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

      function showOverlay(data) {
        const existing = document.getElementById("sportabase-overlay");
        if (existing) existing.remove();

        const overlay = document.createElement("div");
        overlay.id = "sportabase-overlay";
        overlay.style.position = "fixed";
        overlay.style.top = "16px";
        overlay.style.right = "16px";
        overlay.style.width = "360px";
        overlay.style.maxHeight = "70vh";
        overlay.style.overflow = "auto";
        overlay.style.zIndex = "2147483647";
        overlay.style.background = "#111";
        overlay.style.color = "#fff";
        overlay.style.padding = "14px";
        overlay.style.borderRadius = "12px";
        overlay.style.boxShadow = "0 10px 30px rgba(0,0,0,0.35)";
        overlay.style.fontFamily = "system-ui, -apple-system, Segoe UI, Roboto, Arial";
        overlay.style.fontSize = "13px";
        overlay.style.lineHeight = "1.35";

        const bullets = (data.tldr || [])
          .map((b) => `<li style="margin:6px 0">${b}</li>`)
          .join("");

        const reasons = (data.reasons || []).map(r => `<li style="margin:6px 0;opacity:.9">${r}</li>`).join("");


        overlay.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
                <div>
                <div style="font-weight:700;font-size:14px;">Sportabase</div>
                <div style="opacity:.85;margin-top:2px;">
                    Merit: <b>${data.merit_score}/100</b> · ${data.badge}
                </div>
                </div>
                <button id="sportabase-close"
                style="background:#333;color:#fff;border:0;border-radius:10px;padding:8px 10px;cursor:pointer;">
                Close
                </button>
            </div>

            <div style="margin-top:10px;font-weight:700;">TL;DR</div>
            <ul style="margin:8px 0 0 18px;padding:0;">${bullets}</ul>

            ${reasons ? `
                <div style="margin-top:10px;font-weight:700;">Why</div>
                <ul style="margin:8px 0 0 18px;padding:0;">${reasons}</ul>
            ` : ``}
            `;


        document.body.appendChild(overlay);

        const btn = document.getElementById("sportabase-close");
        if (btn) btn.onclick = () => overlay.remove();
      }

      // ----- run -----
      const text = getReadableText();
      log("extracted text length:", text.length);

      const payload = {
        title: document.title || "Untitled",
        url: location.href,
        text,
        max_bullets: 3
      };

      if (!payload.text || payload.text.length < 200) {
        alert("Couldn’t extract enough article text on this page.");
        return;
      }

      try {
        const resp = await fetch("http://127.0.0.1:8000/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        log("backend status:", resp.status);

        if (!resp.ok) {
          const t = await resp.text();
          alert("Sportabase backend error: " + t);
          return;
        }

        const data = await resp.json();
        log("response:", data);

        try {
          showOverlay(data);
        } catch (e) {
          // fallback so you never get "nothing happens"
          alert("Overlay failed, but summary worked:\n\n" + JSON.stringify(data, null, 2));
          log("overlay error:", e);
        }
      } catch (e) {
        alert("Failed to reach Sportabase backend at 127.0.0.1:8000.\n\n" + e);
        log("fetch error:", e);
      }
    }
  });
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;
  await injectAndRun(tab.id);
});
