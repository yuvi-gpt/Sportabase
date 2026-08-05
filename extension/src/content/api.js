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

async function getSportabaseClientId() {
  const storageKey = "sportabaseClientId";

  try {
    const stored =
      await chrome.storage.local.get(storageKey);

    const existing = String(
      stored?.[storageKey] || ""
    ).trim();

    if (existing) {
      return existing;
    }

    const clientId =
      typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : [
            Date.now().toString(36),
            Math.random().toString(36).slice(2),
          ].join("-");

    await chrome.storage.local.set({
      [storageKey]: clientId,
    });

    return clientId;
  } catch (error) {
    console.warn(
      "[sportabase] Client ID unavailable:",
      error
    );

    return "anonymous";
  }
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
