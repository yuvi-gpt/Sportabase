export const DEFAULT_PREFERENCES = {
  sportabaseAppearance: "system",
  sportabaseAccentMode: "dynamic",
  sportabaseAccentColor: "#7c3aed",
  sportabaseGlowLevel: "reduced",
  sportabaseMotionLevel: "full",
  sportabaseHighContrast: false,
  sportabaseTextScale: "medium",
  sportabaseDensity: "comfortable",
  sportabaseSizeMode: "comfort",
  sportabaseRememberPosition: true,
};

const PALETTES = {
  dark: {
    panelTop: "#121214",
    panelBottom: "#0c0c0e",
    header: "rgba(16, 16, 18, 0.92)",
    surface: "#19191c",
    raised: "#222226",
    text: "#f8f8fa",
    muted: "#9d9da5",
    border: "rgba(255, 255, 255, 0.10)",
    divider: "rgba(255, 255, 255, 0.08)",
    shadow: "rgba(0, 0, 0, 0.50)",
  },

  light: {
    panelTop: "#ffffff",
    panelBottom: "#f3f4f7",
    header: "rgba(255, 255, 255, 0.94)",
    surface: "#ffffff",
    raised: "#eef0f4",
    text: "#15161a",
    muted: "#666a73",
    border: "rgba(15, 23, 42, 0.13)",
    divider: "rgba(15, 23, 42, 0.09)",
    shadow: "rgba(15, 23, 42, 0.20)",
  },
};

export function resolvePreferences(input = {}) {
  return {
    ...DEFAULT_PREFERENCES,
    ...(input || {}),
  };
}

export function applyPreferences(
  overlay,
  inputPreferences = {}
) {
  if (!overlay) return resolvePreferences(inputPreferences);

  const preferences = resolvePreferences(inputPreferences);

  const systemPrefersLight =
    window.matchMedia?.(
      "(prefers-color-scheme: light)"
    )?.matches || false;

  const appearance =
    preferences.sportabaseAppearance === "system"
      ? systemPrefersLight
        ? "light"
        : "dark"
      : preferences.sportabaseAppearance;

  const palette =
    PALETTES[appearance] || PALETTES.dark;

  const accent =
    preferences.sportabaseAccentMode === "fixed"
      ? preferences.sportabaseAccentColor || "#7c3aed"
      : "#7c3aed";

  const textScaleMap = {
    small: 0.94,
    medium: 1,
    large: 1.08,
  };

  const densityMap = {
    compact: 0.88,
    comfortable: 1,
    spacious: 1.12,
  };

  const glowMap = {
    off: 0,
    reduced: 0.55,
    full: 1,
  };

  overlay.dataset.sbAppearance = appearance;
  overlay.dataset.sbMotion =
    preferences.sportabaseMotionLevel;
  overlay.dataset.sbGlow =
    preferences.sportabaseGlowLevel;

  overlay.classList.toggle(
    "sb-high-contrast",
    Boolean(preferences.sportabaseHighContrast)
  );

  overlay.style.setProperty(
    "--sb-panel-top",
    palette.panelTop
  );

  overlay.style.setProperty(
    "--sb-panel-bottom",
    palette.panelBottom
  );

  overlay.style.setProperty(
    "--sb-header-background",
    palette.header
  );

  overlay.style.setProperty(
    "--sb-surface",
    palette.surface
  );

  overlay.style.setProperty(
    "--sb-raised",
    palette.raised
  );

  overlay.style.setProperty(
    "--sb-text",
    palette.text
  );

  overlay.style.setProperty(
    "--sb-muted",
    palette.muted
  );

  overlay.style.setProperty(
    "--sb-border",
    palette.border
  );

  overlay.style.setProperty(
    "--sb-divider",
    palette.divider
  );

  overlay.style.setProperty(
    "--sb-shadow",
    palette.shadow
  );

  overlay.style.setProperty(
    "--sb-accent",
    accent
  );

  overlay.style.setProperty(
    "--sb-accent-bright",
    `color-mix(in srgb, ${accent} 72%, white 28%)`
  );

  overlay.style.setProperty(
    "--sb-text-scale",
    String(
      textScaleMap[preferences.sportabaseTextScale] || 1
    )
  );

  overlay.style.setProperty(
    "--sb-density",
    String(
      densityMap[preferences.sportabaseDensity] || 1
    )
  );

  overlay.style.setProperty(
    "--sb-glow-strength",
    String(
      glowMap[preferences.sportabaseGlowLevel] ?? 0.55
    )
  );

  overlay.style.colorScheme = appearance;

  return preferences;
}

export async function savePreferences(payload = {}) {
  return chrome.runtime.sendMessage({
    type: "SPORTABASE_SAVE_OVERLAY_PREFS",
    payload,
  });
}
