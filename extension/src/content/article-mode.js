export function openArticleMode({
  shell,
} = {}) {
  if (!shell?.content) return;

  shell.setModeLabel(
    "ARTICLE INTELLIGENCE"
  );

  shell.content.innerHTML = `
    <section class="sb-welcome-card">
      <div class="sb-card-eyebrow">
        ARTICLE MODE
      </div>

      <h2 class="sb-card-title">
        Article migration is next
      </h2>

      <p class="sb-card-description">
        The modular article extractor and analysis
        screen will be connected after Video Mode.
      </p>
    </section>
  `;
}
