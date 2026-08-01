const TRANSCRIPT_SELECTORS = [
  'transcript-segment-view-model span[role="text"]',
  'ytd-transcript-segment-renderer .segment-text',
  'ytd-transcript-segment-renderer yt-formatted-string',
];

function wait(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function getTranscriptElements() {
  for (const selector of TRANSCRIPT_SELECTORS) {
    const elements = Array.from(
      document.querySelectorAll(selector)
    ).filter((element) => {
      return element.textContent?.trim();
    });

    if (elements.length) {
      return elements;
    }
  }

  return [];
}

function findTranscriptButton() {
  const directButton = document.querySelector(
    [
      "ytd-video-description-transcript-section-renderer button",
      'button[aria-label*="transcript" i]',
      'button[title*="transcript" i]',
    ].join(", ")
  );

  if (directButton) {
    return directButton;
  }

  return Array.from(
    document.querySelectorAll(
      [
        "button",
        "tp-yt-paper-button",
        "ytd-button-renderer button",
        "yt-button-shape button",
      ].join(", ")
    )
  ).find((element) => {
    const searchableText = [
      element.textContent,
      element.getAttribute("aria-label"),
      element.getAttribute("title"),
    ]
      .filter(Boolean)
      .join(" ")
      .trim()
      .toLowerCase();

    return (
      searchableText.includes("show transcript") ||
      searchableText === "transcript"
    );
  });
}

async function expandVideoDescription() {
  const metadata = document.querySelector(
    "ytd-watch-metadata"
  );

  const expandButton = metadata?.querySelector(
    [
      "#expand",
      "tp-yt-paper-button#expand",
      "ytd-text-inline-expander #expand",
    ].join(", ")
  );

  if (!expandButton) return;

  expandButton.click();
  await wait(400);
}

export async function extractYouTubeTranscript({
  timeoutMs = 8000,
} = {}) {
  let transcriptElements =
    getTranscriptElements();

  if (!transcriptElements.length) {
    let transcriptButton =
      findTranscriptButton();

    if (!transcriptButton) {
      await expandVideoDescription();

      transcriptButton =
        findTranscriptButton();
    }

    if (!transcriptButton) {
      throw new Error(
        "No transcript button was found. Captions may be unavailable for this video."
      );
    }

    transcriptButton.click();

    const startedAt = Date.now();

    while (
      Date.now() - startedAt < timeoutMs
    ) {
      transcriptElements =
        getTranscriptElements();

      if (transcriptElements.length) {
        break;
      }

      await wait(250);
    }
  }

  const segments = transcriptElements
    .map((element) => {
      return element.textContent
        ?.replace(/\s+/g, " ")
        .trim();
    })
    .filter(Boolean);

  const transcript = segments.join(" ").trim();

  if (!transcript) {
    throw new Error(
      "The transcript panel opened, but no transcript text was found."
    );
  }

  return {
    transcript,
    segmentCount: segments.length,
    characterCount: transcript.length,
  };
}
