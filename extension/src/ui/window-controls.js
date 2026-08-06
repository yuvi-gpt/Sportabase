import {
  applyPanelLayout,
  resolvePreferences,
  savePreferences,
} from "./preferences.js";

const EDGE_MARGIN = 8;
const MIN_WIDTH = 300;
const MIN_HEIGHT = 320;

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

function readGeometry(overlay) {
  const rect =
    overlay.getBoundingClientRect();

  return {
    left: rect.left,
    top: rect.top,
    width: rect.width,
    height: rect.height,
  };
}

function clampGeometry({
  left,
  top,
  width,
  height,
}) {
  const maximumWidth =
    Math.max(
      1,
      window.innerWidth -
        EDGE_MARGIN * 2
    );

  const maximumHeight =
    Math.max(
      1,
      window.innerHeight -
        EDGE_MARGIN * 2
    );

  const safeWidth =
    clamp(
      width,
      Math.min(
        MIN_WIDTH,
        maximumWidth
      ),
      maximumWidth
    );

  const safeHeight =
    clamp(
      height,
      Math.min(
        MIN_HEIGHT,
        maximumHeight
      ),
      maximumHeight
    );

  const safeLeft =
    clamp(
      left,
      EDGE_MARGIN,
      Math.max(
        EDGE_MARGIN,
        window.innerWidth -
          safeWidth -
          EDGE_MARGIN
      )
    );

  const safeTop =
    clamp(
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

function applyGeometry(
  overlay,
  geometry
) {
  const safeGeometry =
    clampGeometry(
      geometry
    );

  overlay.style.left =
    `${Math.round(
      safeGeometry.left
    )}px`;

  overlay.style.right =
    "auto";

  overlay.style.top =
    `${Math.round(
      safeGeometry.top
    )}px`;

  overlay.style.width =
    `${Math.round(
      safeGeometry.width
    )}px`;

  overlay.style.height =
    `${Math.round(
      safeGeometry.height
    )}px`;

  return safeGeometry;
}

export function installWindowControls({
  overlay,
  preferences = {},
} = {}) {
  if (!overlay) return;

  let currentPreferences =
    resolvePreferences(
      preferences
    );

  applyPanelLayout(
    overlay,
    currentPreferences
  );

  const dragHandles =
    overlay.querySelectorAll(
      ".sb-header, .sb-settings-header"
    );

  function saveManualGeometry(
    geometry,
    resized
  ) {
    const anchor =
      (
        geometry.left +
          geometry.width / 2
      ) >=
      window.innerWidth / 2
        ? "right"
        : "left";

    const edgeOffset =
      anchor === "right"
        ? (
            window.innerWidth -
            geometry.left -
            geometry.width
          )
        : geometry.left;

    const payload = {
      sportabasePanelPosition:
        anchor === "right"
          ? "top-right"
          : "top-left",

      sportabaseLeft:
        Math.round(
          geometry.left
        ),

      sportabaseTop:
        Math.round(
          geometry.top
        ),

      sportabaseHorizontalAnchor:
        anchor,

      sportabaseEdgeOffset:
        Math.max(
          EDGE_MARGIN,
          Math.round(
            edgeOffset
          )
        ),

      sportabaseRememberPosition:
        true,
    };

    if (resized) {
      payload.sportabaseSizeMode =
        "custom";

      payload.sportabaseCustomWidth =
        Math.round(
          geometry.width
        );

      payload.sportabaseCustomHeight =
        Math.round(
          geometry.height
        );
    }

    currentPreferences =
      resolvePreferences({
        ...currentPreferences,
        ...payload,
      });

    overlay.dispatchEvent(
      new CustomEvent(
        "sportabase:geometry-changed",
        {
          detail: payload,
        }
      )
    );

    applyPanelLayout(
      overlay,
      currentPreferences
    );

    savePreferences(
      payload
    ).catch((error) => {
      console.error(
        "[sportabase] Could not save panel geometry:",
        error
      );
    });
  }

  function beginInteraction({
    event,
    direction = null,
  }) {
    if (event.button !== 0) {
      return;
    }

    event.preventDefault();

    const startGeometry =
      readGeometry(
        overlay
      );

    const startX =
      event.clientX;

    const startY =
      event.clientY;

    overlay.classList.add(
      direction
        ? "sb-is-resizing"
        : "sb-is-dragging"
    );

    document.documentElement
      .classList.add(
        "sb-window-interaction-active"
      );

    function handlePointerMove(
      moveEvent
    ) {
      const deltaX =
        moveEvent.clientX -
        startX;

      const deltaY =
        moveEvent.clientY -
        startY;

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
        if (
          direction.includes("e")
        ) {
          width += deltaX;
        }

        if (
          direction.includes("s")
        ) {
          height += deltaY;
        }

        if (
          direction.includes("w")
        ) {
          width -= deltaX;
          left += deltaX;
        }

        if (
          direction.includes("n")
        ) {
          height -= deltaY;
          top += deltaY;
        }
      }

      applyGeometry(
        overlay,
        {
          left,
          top,
          width,
          height,
        }
      );
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

      document.documentElement
        .classList.remove(
          "sb-window-interaction-active"
        );

      saveManualGeometry(
        readGeometry(
          overlay
        ),
        Boolean(direction)
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

  dragHandles.forEach(
    (dragHandle) => {
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
    }
  );

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
      document.createElement(
        "div"
      );

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

    overlay.appendChild(
      handle
    );
  });

  function handlePreferencesChanged(
    event
  ) {
    currentPreferences =
      resolvePreferences({
        ...currentPreferences,
        ...(event.detail || {}),
      });

    applyPanelLayout(
      overlay,
      currentPreferences
    );
  }

  function keepInsideViewport() {
    if (!overlay.isConnected) {
      window.removeEventListener(
        "resize",
        keepInsideViewport
      );

      return;
    }

    applyPanelLayout(
      overlay,
      currentPreferences
    );
  }

  overlay.addEventListener(
    "sportabase:preferences-changed",
    handlePreferencesChanged
  );

  window.addEventListener(
    "resize",
    keepInsideViewport
  );

  overlay.addEventListener(
    "sportabase:before-close",
    () => {
      overlay.removeEventListener(
        "sportabase:preferences-changed",
        handlePreferencesChanged
      );

      window.removeEventListener(
        "resize",
        keepInsideViewport
      );
    },
    {
      once: true,
    }
  );
}
