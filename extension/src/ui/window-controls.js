import {
  savePreferences,
} from "./preferences.js";

const MIN_WIDTH = 360;
const MIN_HEIGHT = 320;
const EDGE_MARGIN = 8;

function clamp(value, minimum, maximum) {
  return Math.max(
    minimum,
    Math.min(maximum, value)
  );
}

function getViewportLimits() {
  return {
    maxWidth: Math.max(
      MIN_WIDTH,
      Math.min(820, window.innerWidth - EDGE_MARGIN * 2)
    ),
    maxHeight: Math.max(
      MIN_HEIGHT,
      Math.min(900, window.innerHeight - EDGE_MARGIN * 2)
    ),
  };
}

function clampGeometry({
  left,
  top,
  width,
  height,
}) {
  const {
    maxWidth,
    maxHeight,
  } = getViewportLimits();

  const safeWidth = clamp(
    width,
    MIN_WIDTH,
    maxWidth
  );

  const safeHeight = clamp(
    height,
    MIN_HEIGHT,
    maxHeight
  );

  const safeLeft = clamp(
    left,
    EDGE_MARGIN,
    Math.max(
      EDGE_MARGIN,
      window.innerWidth -
        safeWidth -
        EDGE_MARGIN
    )
  );

  const safeTop = clamp(
    top,
    EDGE_MARGIN,
    Math.max(
      EDGE_MARGIN,
      window.innerHeight -
        safeHeight -
        EDGE_MARGIN
    )
  );

  return {
    left: safeLeft,
    top: safeTop,
    width: safeWidth,
    height: safeHeight,
  };
}

function readGeometry(overlay) {
  const rect = overlay.getBoundingClientRect();

  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
  };
}

function applyGeometry(
  overlay,
  geometry
) {
  const safeGeometry =
    clampGeometry(geometry);

  overlay.style.left =
    `${Math.round(safeGeometry.left)}px`;

  overlay.style.top =
    `${Math.round(safeGeometry.top)}px`;

  overlay.style.right = "auto";

  overlay.style.width =
    `${Math.round(safeGeometry.width)}px`;

  overlay.style.height =
    `${Math.round(safeGeometry.height)}px`;

  return safeGeometry;
}

function saveGeometry(
  geometry,
  preferences
) {
  if (
    preferences.sportabaseRememberPosition ===
    false
  ) {
    return;
  }

  savePreferences({
    sportabaseSizeMode: "custom",
    sportabaseCustomWidth:
      Math.round(geometry.width),
    sportabaseCustomHeight:
      Math.round(geometry.height),
    sportabaseLeft:
      Math.round(geometry.left),
    sportabaseTop:
      Math.round(geometry.top),
  }).catch((error) => {
    console.error(
      "[sportabase] Could not save panel geometry:",
      error
    );
  });
}

function restoreGeometry(
  overlay,
  preferences
) {
  if (
    preferences.sportabaseRememberPosition ===
    false
  ) {
    return;
  }

  const current = readGeometry(overlay);

  const width = Number(
    preferences.sportabaseCustomWidth
  );

  const height = Number(
    preferences.sportabaseCustomHeight
  );

  const left = Number(
    preferences.sportabaseLeft
  );

  const top = Number(
    preferences.sportabaseTop
  );

  const hasSavedSize =
    Number.isFinite(width) &&
    Number.isFinite(height);

  const hasSavedPosition =
    Number.isFinite(left) &&
    Number.isFinite(top);

  if (
    !hasSavedSize &&
    !hasSavedPosition
  ) {
    return;
  }

  applyGeometry(overlay, {
    left: hasSavedPosition
      ? left
      : current.left,
    top: hasSavedPosition
      ? top
      : current.top,
    width: hasSavedSize
      ? width
      : current.width,
    height: hasSavedSize
      ? height
      : current.height,
  });
}

export function installWindowControls({
  overlay,
  preferences = {},
} = {}) {
  if (!overlay) return;

  const dragHandles = overlay.querySelectorAll(
    ".sb-header, .sb-settings-header"
  );

  restoreGeometry(
    overlay,
    preferences
  );

  function beginInteraction({
    event,
    direction = null,
  }) {
    if (event.button !== 0) return;

    event.preventDefault();

    const startGeometry =
      readGeometry(overlay);

    const startX = event.clientX;
    const startY = event.clientY;

    overlay.classList.add(
      direction
        ? "sb-is-resizing"
        : "sb-is-dragging"
    );

    document.documentElement.classList.add(
      "sb-window-interaction-active"
    );

    function handlePointerMove(
      moveEvent
    ) {
      const deltaX =
        moveEvent.clientX - startX;

      const deltaY =
        moveEvent.clientY - startY;

      let {
        left,
        top,
        width,
        height,
      } = startGeometry;

      if (!direction) {
        left += deltaX;
        top += deltaY;
      } else {
        if (direction.includes("e")) {
          width += deltaX;
        }

        if (direction.includes("s")) {
          height += deltaY;
        }

        if (direction.includes("w")) {
          width -= deltaX;
          left += deltaX;
        }

        if (direction.includes("n")) {
          height -= deltaY;
          top += deltaY;
        }
      }

      applyGeometry(overlay, {
        left,
        top,
        width,
        height,
      });
    }

    function finishInteraction() {
      document.removeEventListener(
        "pointermove",
        handlePointerMove
      );

      document.removeEventListener(
        "pointerup",
        finishInteraction
      );

      document.removeEventListener(
        "pointercancel",
        finishInteraction
      );

      overlay.classList.remove(
        "sb-is-dragging",
        "sb-is-resizing"
      );

      document.documentElement.classList.remove(
        "sb-window-interaction-active"
      );

      saveGeometry(
        readGeometry(overlay),
        preferences
      );
    }

    document.addEventListener(
      "pointermove",
      handlePointerMove
    );

    document.addEventListener(
      "pointerup",
      finishInteraction
    );

    document.addEventListener(
      "pointercancel",
      finishInteraction
    );
  }

  dragHandles.forEach((dragHandle) => {
    dragHandle.addEventListener(
      "pointerdown",
      (event) => {
        if (
          event.target.closest(
            "button, a, input, select, textarea"
          )
        ) {
          return;
        }

        beginInteraction({
          event,
        });
      }
    );
  });

  [
    "n",
    "s",
    "e",
    "w",
    "ne",
    "nw",
    "se",
    "sw",
  ].forEach((direction) => {
    const handle =
      document.createElement("div");

    handle.className =
      "sb-resize-handle";

    handle.dataset.direction =
      direction;

    handle.setAttribute(
      "aria-hidden",
      "true"
    );

    handle.addEventListener(
      "pointerdown",
      (event) => {
        event.stopPropagation();

        beginInteraction({
          event,
          direction,
        });
      }
    );

    overlay.appendChild(handle);
  });
}
