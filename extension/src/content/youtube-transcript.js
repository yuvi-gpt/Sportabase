const TRANSCRIPT_SELECTORS = [
  'transcript-segment-view-model span[role="text"]',
  'ytd-transcript-segment-renderer .segment-text',
  'ytd-transcript-segment-renderer yt-formatted-string',
];

export function normalizeTranscriptSegments(
  rawSegments
) {
  const normalizedSegments = [];
  const seenAdjacent = [];

  let rawSegmentCount = 0;
  let emptySegmentCount = 0;
  let duplicateSegmentCount = 0;

  for (const rawSegment of rawSegments || []) {
    rawSegmentCount += 1;

    const text = String(
      rawSegment?.text ??
      rawSegment ??
      ""
    )
      .replace(/\u00a0/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (!text) {
      emptySegmentCount += 1;
      continue;
    }

    const duplicateKey = text
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, " ")
      .trim();

    const previousKey =
      seenAdjacent[
        seenAdjacent.length - 1
      ];

    if (
      duplicateKey &&
      duplicateKey === previousKey
    ) {
      duplicateSegmentCount += 1;
      continue;
    }

    seenAdjacent.push(duplicateKey);

    normalizedSegments.push({
      text,
      timestamp: String(
        rawSegment?.timestamp || ""
      ).trim(),
    });
  }

  const transcript = normalizedSegments
    .map((segment) => segment.text)
    .join("\n")
    .trim();

  const characterCount =
    transcript.length;

  const segmentCount =
    normalizedSegments.length;

  const duplicateRatio =
    rawSegmentCount > 0
      ? duplicateSegmentCount /
        rawSegmentCount
      : 0;

  const averageSegmentLength =
    segmentCount > 0
      ? characterCount / segmentCount
      : 0;

  const warnings = [];

  if (segmentCount < 3) {
    warnings.push(
      "very_few_segments"
    );
  }

  if (characterCount < 120) {
    warnings.push(
      "very_short_transcript"
    );
  }

  if (duplicateRatio >= 0.25) {
    warnings.push(
      "high_duplicate_ratio"
    );
  }

  if (
    segmentCount >= 5 &&
    averageSegmentLength < 8
  ) {
    warnings.push(
      "fragmented_captions"
    );
  }

  let extractionConfidence = 1.0;

  extractionConfidence -= Math.min(
    0.35,
    duplicateRatio
  );

  if (segmentCount < 3) {
    extractionConfidence -= 0.35;
  } else if (segmentCount < 8) {
    extractionConfidence -= 0.12;
  }

  if (characterCount < 120) {
    extractionConfidence -= 0.30;
  } else if (characterCount < 400) {
    extractionConfidence -= 0.10;
  }

  if (
    averageSegmentLength > 0 &&
    averageSegmentLength < 8
  ) {
    extractionConfidence -= 0.15;
  }

  extractionConfidence = Math.max(
    0,
    Math.min(
      1,
      Number(
        extractionConfidence.toFixed(2)
      )
    )
  );

  return {
    transcript,
    segments: normalizedSegments,
    rawSegmentCount,
    segmentCount,
    characterCount,
    emptySegmentCount,
    duplicateSegmentCount,
    duplicateRatio: Number(
      duplicateRatio.toFixed(3)
    ),
    averageSegmentLength: Number(
      averageSegmentLength.toFixed(1)
    ),
    extractionConfidence,
    warnings,
  };
}


function getTranscriptTimestamp(
  element
) {
  const container = element.closest(
    [
      "transcript-segment-view-model",
      "ytd-transcript-segment-renderer",
    ].join(", ")
  );

  return (
    container
      ?.querySelector(
        [
          ".segment-timestamp",
          "[class*='timestamp']",
          "[aria-label*='minute' i]",
          "[aria-label*='second' i]",
        ].join(", ")
      )
      ?.textContent
      ?.replace(/\s+/g, " ")
      .trim() ||
    ""
  );
}


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

  const rawSegments = transcriptElements.map(
    (element) => {
      return {
        text: element.textContent || "",
        timestamp:
          getTranscriptTimestamp(element),
      };
    }
  );

  const normalized =
    normalizeTranscriptSegments(
      rawSegments
    );

  if (!normalized.transcript) {
    throw new Error(
      "The transcript panel opened, but no transcript text was found."
    );
  }

  return {
    transcript: normalized.transcript,
    segmentCount:
      normalized.segmentCount,
    characterCount:
      normalized.characterCount,
    extractionConfidence:
      normalized.extractionConfidence,
    extractionWarnings:
      normalized.warnings,
    duplicateSegmentCount:
      normalized.duplicateSegmentCount,
    duplicateRatio:
      normalized.duplicateRatio,
    averageSegmentLength:
      normalized.averageSegmentLength,
    timestampsAvailable:
      normalized.segments.some(
        (segment) =>
          Boolean(segment.timestamp)
      ),
  };
}
