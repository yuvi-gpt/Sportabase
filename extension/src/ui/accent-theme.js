export const SPORTABASE_BRAND_PALETTE =
  Object.freeze({
    accent: "#06b6d4",
    bright: "#9cff38",
  });

export function getScorePalette(score) {
  const normalizedScore = Math.max(
    0,
    Math.min(100, Number(score) || 0)
  );

  if (normalizedScore < 35) {
    return {
      accent: "#dc2626",
      bright: "#fb7185",
    };
  }

  if (normalizedScore < 50) {
    return {
      accent: "#ea580c",
      bright: "#facc15",
    };
  }

  if (normalizedScore < 65) {
    return {
      accent: "#2563eb",
      bright: "#22d3ee",
    };
  }

  if (normalizedScore < 80) {
    return {
      accent: "#6d28d9",
      bright: "#d946ef",
    };
  }

  if (normalizedScore < 90) {
    return {
      accent: "#0f766e",
      bright: "#22d3ee",
    };
  }

  return {
    accent: "#16a34a",
    bright: "#bef264",
  };
}

export function createAccentTheme(overlay) {
  const baseAccent =
    SPORTABASE_BRAND_PALETTE.accent;

  const baseAccentBright =
    SPORTABASE_BRAND_PALETTE.bright;

  function apply(palette = {}) {
    const accent =
      palette.accent || baseAccent;

    const bright =
      palette.bright || accent;

    overlay.style.setProperty(
      "--sb-accent",
      accent
    );

    overlay.style.setProperty(
      "--sb-accent-bright",
      bright
    );

    overlay.style.setProperty(
      "--sb-score-color",
      accent
    );

    overlay.style.setProperty(
      "--sb-score-color-bright",
      bright
    );

    overlay.style.setProperty(
      "--sb-analysis-accent",
      accent
    );

    overlay.style.setProperty(
      "--sb-analysis-accent-bright",
      bright
    );

    overlay.classList.add(
      "sb-has-analysis-accent"
    );
  }

  function clear() {
    overlay.style.setProperty(
      "--sb-accent",
      baseAccent
    );

    overlay.style.setProperty(
      "--sb-accent-bright",
      baseAccentBright
    );

    overlay.style.removeProperty(
      "--sb-score-color"
    );

    overlay.style.removeProperty(
      "--sb-score-color-bright"
    );

    overlay.style.removeProperty(
      "--sb-analysis-accent"
    );

    overlay.style.removeProperty(
      "--sb-analysis-accent-bright"
    );

    overlay.classList.remove(
      "sb-has-analysis-accent"
    );
  }

  return {
    apply,
    clear,
  };
}
