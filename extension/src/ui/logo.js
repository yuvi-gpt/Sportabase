export function getSportabaseLogoMarkup({
  className = "",
} = {}) {
  const logoUrl =
    chrome.runtime.getURL(
      "assets/sportabase-logo.png"
    );

  const extraClass =
    String(className || "").trim();

  return `
    <div
      class="
        sb-logo
        sb-logo-image
        ${extraClass}
      "
      style="
        --sb-logo-art:
          url('${logoUrl}')
      "
      aria-hidden="true"
    >
      <span class="sb-logo-glow"></span>
      <span class="sb-logo-mark"></span>
    </div>
  `;
}
