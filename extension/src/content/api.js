export class SportabaseApiError extends Error {
  constructor(
    message,
    {
      status = 0,
      details = "",
    } = {}
  ) {
    super(message);

    this.name = "SportabaseApiError";
    this.status = status;
    this.details = details;
  }
}

export async function postJson(
  url,
  payload,
  {
    timeoutMs = 120000,
  } = {}
) {
  const controller = new AbortController();

  const timeoutId = window.setTimeout(
    () => controller.abort(),
    timeoutMs
  );

  try {
    const response = await fetch(url, {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    const responseText = await response.text();

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
      throw new SportabaseApiError(
        "The analysis took too long and was stopped. Try again once.",
        {
          status: 408,
        }
      );
    }

    if (
      error instanceof SportabaseApiError
    ) {
      throw error;
    }

    throw new SportabaseApiError(
      "Sportabase could not reach the analysis service.",
      {
        details: String(
          error?.message || error || ""
        ),
      }
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
}
