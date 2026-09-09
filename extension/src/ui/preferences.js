export const SPORTABASE_VIEWPORT_GUTTER = 8;

export const DEFAULT_PREFERENCES = {
  sportabaseAppearance: "system",

  sportabaseTextScale: "system",
  sportabaseDensity: "comfortable",
  sportabaseMotionLevel: "system",

  sportabaseHighContrast: false,

  /*
   * New users start comfortable and
   * pinned to the top-right corner.
   */
  sportabasePanelPosition: "top-right",
  sportabaseSizeMode: "comfort",

  /*
   * These values are populated after the
   * user manually drags or resizes.
   */
  sportabaseCustomWidth: null,
  sportabaseCustomHeight: null,
  sportabaseLeft: null,
  sportabaseTop: null,

  sportabaseHorizontalAnchor: "right",
  sportabaseEdgeOffset: SPORTABASE_VIEWPORT_GUTTER,
  sportabaseRememberPosition: true,

  sportabaseDetailLevel: "full",
};

const PALETTES = {
  dark: {
    panelTop: "#101012",
    panelBottom: "#09090b",
    header: "rgba(14, 14, 16, 0.96)",
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
    header: "rgba(255, 255, 255, 0.97)",
    surface: "#ffffff",
    raised: "#eef0f4",
    text: "#15161a",
    muted: "#666a73",
    border: "rgba(15, 23, 42, 0.13)",
    divider: "rgba(15, 23, 42, 0.09)",
    shadow: "rgba(15, 23, 42, 0.20)",
  },
};

const SIZE_PRESETS = {
  compact: {
    width: 430,
    height: 580,
  },

  comfort: {
    width: 520,
    height: 680,
  },

  large: {
    width: 650,
    height: 790,
  },
};

const EDGE_MARGIN = SPORTABASE_VIEWPORT_GUTTER;
const MIN_PANEL_WIDTH = 300;
const MIN_PANEL_HEIGHT = 320;

function getViewportWidth() {
  return Math.max(
    1,
    document.documentElement
      ?.clientWidth ||
      globalThis.innerWidth ||
      1
  );
}

function getViewportHeight() {
  return Math.max(
    1,
    document.documentElement
      ?.clientHeight ||
      globalThis.innerHeight ||
      1
  );
}

function clamp(
  value,
  minimum,
  maximum
) {
  return Math.max(
    minimum,
    Math.min(maximum, value)
  );
}

function finiteNumber(value) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : null;
}

function fitDimension(
  desired,
  available,
  minimum
) {
  if (available <= minimum) {
    return Math.max(
      1,
      available
    );
  }

  return clamp(
    desired,
    minimum,
    available
  );
}

export function resolvePreferences(
  input = {}
) {
  const merged = {
    ...DEFAULT_PREFERENCES,
    ...(input || {}),
  };

  const panelPosition =
    [
      "top-right",
      "top-left",
    ].includes(
      merged.sportabasePanelPosition
    )
      ? merged.sportabasePanelPosition
      : "top-right";

  const sizeMode =
    [
      "compact",
      "comfort",
      "large",
      "custom",
    ].includes(
      merged.sportabaseSizeMode
    )
      ? merged.sportabaseSizeMode
      : "comfort";

  const horizontalAnchor =
    merged.sportabaseHorizontalAnchor ===
    "left"
      ? "left"
      : "right";

  const detailLevel =
    merged.sportabaseDetailLevel ===
    "essential"
      ? "essential"
      : "full";

  return {
    ...merged,

    sportabasePanelPosition:
      panelPosition,

    sportabaseSizeMode:
      sizeMode,

    sportabaseCustomWidth:
      finiteNumber(
        merged.sportabaseCustomWidth
      ),

    sportabaseCustomHeight:
      finiteNumber(
        merged.sportabaseCustomHeight
      ),

    sportabaseLeft:
      finiteNumber(
        merged.sportabaseLeft
      ),

    sportabaseTop:
      finiteNumber(
        merged.sportabaseTop
      ),

    sportabaseHorizontalAnchor:
      horizontalAnchor,

    sportabaseEdgeOffset:
      finiteNumber(
        merged.sportabaseEdgeOffset
      ) ?? EDGE_MARGIN,

    sportabaseRememberPosition:
      merged.sportabaseRememberPosition !==
      false,

    sportabaseDetailLevel:
      detailLevel,
  };
}

export function applyPanelLayout(
  overlay,
  inputPreferences = {}
) {
  if (!overlay) return;

  const preferences =
    resolvePreferences(
      inputPreferences
    );

  const preset =
    SIZE_PRESETS[
      preferences.sportabaseSizeMode
    ] ||
    SIZE_PRESETS.comfort;

  const customSizeAvailable =
    preferences.sportabaseSizeMode ===
      "custom" &&
    preferences.sportabaseCustomWidth !==
      null &&
    preferences.sportabaseCustomHeight !==
      null;

  const availableWidth =
    Math.max(
      1,
      getViewportWidth() -
        EDGE_MARGIN * 2
    );

  const availableHeight =
    Math.max(
      1,
      getViewportHeight() -
        EDGE_MARGIN * 2
    );

  const desiredWidth =
    customSizeAvailable
      ? preferences
          .sportabaseCustomWidth
      : preset.width;

  /*
   * Preset layouts use the complete
   * available viewport height, leaving
   * the same gutter at the top and bottom.
   *
   * Manual edge resizing switches the
   * panel to Custom and preserves the
   * user's chosen height.
   */
  const desiredHeight =
    customSizeAvailable
      ? preferences
          .sportabaseCustomHeight
      : availableHeight;

  const width =
    fitDimension(
      desiredWidth,
      availableWidth,
      MIN_PANEL_WIDTH
    );

  const height =
    fitDimension(
      desiredHeight,
      availableHeight,
      MIN_PANEL_HEIGHT
    );

  const hasSavedPosition =
    preferences
      .sportabaseRememberPosition &&
    preferences.sportabaseLeft !== null &&
    preferences.sportabaseTop !== null;

  let left;
  let top;

  if (hasSavedPosition) {
    const maximumEdgeOffset =
      Math.max(
        EDGE_MARGIN,
        getViewportWidth() -
          width -
          EDGE_MARGIN
      );

    const edgeOffset =
      clamp(
        preferences
          .sportabaseEdgeOffset,
        EDGE_MARGIN,
        maximumEdgeOffset
      );

    left =
      preferences
        .sportabaseHorizontalAnchor ===
      "right"
        ? (
            getViewportWidth() -
            width -
            edgeOffset
          )
        : edgeOffset;

    top =
      clamp(
        preferences.sportabaseTop,
        EDGE_MARGIN,
        Math.max(
          EDGE_MARGIN,
          getViewportHeight() -
            height -
            EDGE_MARGIN
        )
      );
  } else {
    top = EDGE_MARGIN;

    left =
      preferences
        .sportabasePanelPosition ===
      "top-left"
        ? EDGE_MARGIN
        : (
            getViewportWidth() -
            width -
            EDGE_MARGIN
          );
  }

  left =
    clamp(
      left,
      EDGE_MARGIN,
      Math.max(
        EDGE_MARGIN,
        getViewportWidth() -
          width -
          EDGE_MARGIN
      )
    );

  overlay.dataset.sbPosition =
    preferences
      .sportabasePanelPosition;

  overlay.dataset.sbSize =
    preferences
      .sportabaseSizeMode;

  overlay.style.left =
    `${Math.round(left)}px`;

  overlay.style.right =
    "auto";

  overlay.style.top =
    `${Math.round(top)}px`;

  overlay.style.bottom =
    "auto";

  overlay.style.width =
    `${Math.round(width)}px`;

  overlay.style.height =
    `${Math.round(height)}px`;
}

export function applyPreferences(
  overlay,
  inputPreferences = {}
) {
  const preferences =
    resolvePreferences(
      inputPreferences
    );

  if (!overlay) {
    return preferences;
  }

  const systemPrefersLight =
    window.matchMedia?.(
      "(prefers-color-scheme: light)"
    )?.matches || false;

  const appearance =
    preferences.sportabaseAppearance ===
    "system"
      ? (
          systemPrefersLight
            ? "light"
            : "dark"
        )
      : preferences
          .sportabaseAppearance;

  const palette =
    PALETTES[appearance] ||
    PALETTES.dark;

  overlay.dataset.sbText = preferences.sportabaseTextScale;
  overlay.dataset.sbDensity = preferences.sportabaseDensity;
  overlay.dataset.sbMotion = preferences.sportabaseMotionLevel === "system" ? (matchMedia("(prefers-reduced-motion: reduce)").matches ? "reduce" : "full") : preferences.sportabaseMotionLevel;
  overlay.dataset.sbAppearance =
    appearance;

  overlay.dataset.sbDetail =
    preferences
      .sportabaseDetailLevel;

  overlay.classList.toggle(
    "sb-high-contrast",
    Boolean(
      preferences
        .sportabaseHighContrast
    )
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

  const resultPaletteActive =
    overlay.classList.contains(
      "sb-has-analysis-accent"
    );

  if (!resultPaletteActive) {
    overlay.style.setProperty(
      "--sb-accent",
      appearance === "light" ? "#246b16" : "#78f54a"
    );

    overlay.style.setProperty(
      "--sb-accent-bright",
      "#9cff38"
    );
  }

  applyPanelLayout(
    overlay,
    preferences
  );

  overlay.style.colorScheme =
    appearance;

  overlay.dispatchEvent(
    new CustomEvent(
      "sportabase:preferences-changed",
      {
        detail: preferences,
      }
    )
  );

  return preferences;
}

export async function savePreferences(
  payload = {}
) {
  return chrome.runtime.sendMessage({
    type:
      "SPORTABASE_SAVE_OVERLAY_PREFS",

    payload,
  });
}
