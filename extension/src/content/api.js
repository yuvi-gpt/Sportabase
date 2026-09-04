export class SportabaseApiError extends Error {
  constructor(
    message,
    {
      status = 0,
      details = "",
      cancelled = false,
    } = {}
  ) {
    super(message);

    this.name = "SportabaseApiError";
    this.status = status;
    this.details = details;
    this.cancelled = Boolean(cancelled);
  }
}

const CLIENT_ID_STORAGE_KEY =
  "sportabaseClientId";

let clientIdentityPromise = null;

function createRandomClientId() {
  if (
    typeof crypto?.randomUUID ===
    "function"
  ) {
    return crypto.randomUUID();
  }

  if (
    typeof crypto?.getRandomValues ===
    "function"
  ) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);

    bytes[6] =
      (bytes[6] & 0x0f) | 0x40;
    bytes[8] =
      (bytes[8] & 0x3f) | 0x80;

    const hex = Array.from(
      bytes,
      (value) =>
        value
          .toString(16)
          .padStart(2, "0")
    );

    return [
      hex.slice(0, 4).join(""),
      hex.slice(4, 6).join(""),
      hex.slice(6, 8).join(""),
      hex.slice(8, 10).join(""),
      hex.slice(10, 16).join(""),
    ].join("-");
  }

  throw new SportabaseApiError(
    "Sportabase could not create a private installation identity."
  );
}

async function loadClientIdentity() {
  const generatedId =
    createRandomClientId();

  try {
    const stored =
      await chrome.storage.local.get(
        CLIENT_ID_STORAGE_KEY
      );

    const existing = String(
      stored?.[
        CLIENT_ID_STORAGE_KEY
      ] || ""
    ).trim();

    if (existing) {
      return {
        id: existing,
        persisted: true,
      };
    }

    await chrome.storage.local.set({
      [CLIENT_ID_STORAGE_KEY]:
        generatedId,
    });

    return {
      id: generatedId,
      persisted: true,
    };
  } catch (error) {
    console.warn(
      "[sportabase] Persistent client identity unavailable:",
      error
    );

    return {
      id: generatedId,
      persisted: false,
    };
  }
}

export async function getSportabaseClientId({
  requirePersistent = false,
} = {}) {
  if (!clientIdentityPromise) {
    clientIdentityPromise =
      loadClientIdentity().catch(
        (error) => {
          clientIdentityPromise = null;
          throw error;
        }
      );
  }

  const identity =
    await clientIdentityPromise;

  if (
    requirePersistent &&
    !identity.persisted
  ) {
    throw new SportabaseApiError(
      "Watchlists and alerts require Chrome extension storage. Persistent storage is unavailable in this browser session."
    );
  }

  return identity.id;
}


export async function postJson(
  url,
  payload,
  {
    timeoutMs = 120000,
    signal = null,
  } = {}
) {
  const controller =
    new AbortController();

  const callerSignal =
    signal &&
    typeof signal.addEventListener ===
      "function"
      ? signal
      : null;

  let timedOut = false;

  const abortFromCaller = () => {
    controller.abort(
      callerSignal?.reason
    );
  };

  if (callerSignal?.aborted) {
    abortFromCaller();
  } else {
    callerSignal?.addEventListener(
      "abort",
      abortFromCaller,
      {
        once: true,
      }
    );
  }

  const timeoutId = window.setTimeout(
    () => {
      timedOut = true;
      controller.abort();
    },
    timeoutMs
  );

  try {
    const clientId =
      await getSportabaseClientId();

    if (controller.signal.aborted) {
      const abortError =
        new Error("Request aborted.");

      abortError.name = "AbortError";

      throw abortError;
    }

    const response = await fetch(url, {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
        "X-Sportabase-Client-ID":
          clientId,
      },

      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const responseText =
      await response.text();

    let data = null;

    try {
      data = responseText
        ? JSON.parse(responseText)
        : null;
    } catch (_) {
      data = null;
    }

    if (!response.ok) {
      const details = String(
        data?.detail ||
        data?.message ||
        responseText ||
        ""
      );

      if (response.status === 429) {
        throw new SportabaseApiError(
          "The AI analysis quota is temporarily exhausted. Try again after it resets.",
          {
            status: response.status,
            details,
          }
        );
      }

      if (response.status === 503) {
        throw new SportabaseApiError(
          "The AI analysis service is temporarily busy. Try again in a moment.",
          {
            status: response.status,
            details,
          }
        );
      }

      throw new SportabaseApiError(
        details ||
        `Sportabase returned HTTP ${response.status}.`,
        {
          status: response.status,
          details,
        }
      );
    }

    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      if (timedOut) {
        throw new SportabaseApiError(
          "The analysis took too long and was stopped. Try again once.",
          {
            status: 408,
          }
        );
      }

      throw new SportabaseApiError(
        "The analysis was cancelled.",
        {
          status: 499,
          details: "cancelled",
          cancelled: true,
        }
      );
    }

    if (
      error instanceof
      SportabaseApiError
    ) {
      throw error;
    }

    throw new SportabaseApiError(
      "Sportabase could not reach the analysis service.",
      {
        details: String(
          error?.message ||
          error ||
          ""
        ),
      }
    );
  } finally {
    window.clearTimeout(timeoutId);

    callerSignal?.removeEventListener(
      "abort",
      abortFromCaller
    );
  }
}
