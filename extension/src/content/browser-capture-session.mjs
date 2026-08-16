import {
  acquirePageSnapshot,
  detectBrowserPlatform,
} from "./platform-acquisition.mjs";


export const BROWSER_CAPTURE_SESSION_VERSION =
  "browser-capture-session-v1";


function cleanText(value) {
  return String(
    value ?? ""
  ).trim();
}


function youtubeTranscriptEligible(
  sourceUrl
) {
  try {
    const parsed =
      new URL(
        String(
          sourceUrl || ""
        )
      );

    const path =
      parsed.pathname
        .toLowerCase();

    return (
      path === "/watch" ||
      path.startsWith(
        "/shorts/"
      )
    );
  } catch (_) {
    return false;
  }
}


function transcriptMetadata(
  transcriptResult
) {
  if (
    !transcriptResult ||
    typeof transcriptResult !==
      "object"
  ) {
    return {};
  }

  const metadata = {};

  const confidence =
    Number(
      transcriptResult
        .extractionConfidence
    );

  if (
    Number.isFinite(
      confidence
    )
  ) {
    metadata.extraction_confidence =
      confidence;
  }

  const segmentCount =
    Number(
      transcriptResult
        .segmentCount
    );

  if (
    Number.isFinite(
      segmentCount
    )
  ) {
    metadata.segment_count =
      segmentCount;
  }

  const characterCount =
    Number(
      transcriptResult
        .characterCount
    );

  if (
    Number.isFinite(
      characterCount
    )
  ) {
    metadata.character_count =
      characterCount;
  }

  if (
    Array.isArray(
      transcriptResult
        .extractionWarnings
    )
  ) {
    metadata.extraction_warnings =
      transcriptResult
        .extractionWarnings
        .map(
          (value) =>
            cleanText(value)
        )
        .filter(Boolean);
  }

  return metadata;
}


export function createBrowserCaptureSession({
  config = {},

  documentRef =
    globalThis.document,

  sourceUrlResolver =
    () =>
      globalThis.location
        ?.href ||
      "",

  now =
    () =>
      new Date()
        .toISOString(),

  acquirePageSnapshotImpl =
    acquirePageSnapshot,

  detectBrowserPlatformImpl =
    detectBrowserPlatform,

  extractArticlePageImpl =
    null,

  extractYouTubeTranscriptImpl =
    null,

  postJsonImpl =
    null,
} = {}) {
  return async function captureCurrentPage({
    articleExtraction =
      null,

    youtubeTranscript =
      null,

    signal =
      null,
  } = {}) {
    const sourceUrl =
      cleanText(
        sourceUrlResolver()
      );

    if (!sourceUrl) {
      throw new Error(
        "Current page URL is unavailable."
      );
    }

    const platform =
      detectBrowserPlatformImpl(
        sourceUrl
      );

    let articleResult =
      articleExtraction;

    let transcriptResult =
      youtubeTranscript;

    let articleExtractorStatus =
      articleResult
        ? "provided"
        : "not_required";

    let transcriptStatus =
      transcriptResult &&
      cleanText(
        transcriptResult
          .transcript
      )
        ? "provided"
        : "not_required";


    if (
      platform === "web" &&
      !articleResult
    ) {
      try {
        const configuredLimit =
          Number(
            config.maxAnalyzeChars ||
            config.maxArticleChars ||
            config.max_analyze_chars ||
            12000
          );

        articleResult =
          extractArticlePageImpl({
            maxCharacters:
              Number.isFinite(
                configuredLimit
              )
                ? configuredLimit
                : 12000,
          });

        articleExtractorStatus =
          "available";
      } catch (_) {
        articleResult =
          null;

        articleExtractorStatus =
          "unavailable";
      }
    }


    if (
      platform === "youtube" &&
      youtubeTranscriptEligible(
        sourceUrl
      ) &&
      !(
        transcriptResult &&
        cleanText(
          transcriptResult
            .transcript
        )
      )
    ) {
      try {
        transcriptResult =
          await (
            extractYouTubeTranscriptImpl()
          );

        transcriptStatus =
          cleanText(
            transcriptResult
              ?.transcript
          )
            ? "available"
            : "unavailable";
      } catch (_) {
        transcriptResult =
          null;

        transcriptStatus =
          "unavailable";
      }
    }


    const capture =
      acquirePageSnapshotImpl({
        documentRef,

        sourceUrl,

        observedAt:
          now(),

        maxTextCharacters:
          Number(
            config.maxCaptureChars ||
            config.maxAnalyzeChars ||
            config.maxArticleChars ||
            12000
          ) ||
          12000,

        articleExtraction:
          articleResult,

        youtubeTranscript:
          transcriptResult,
      });


    if (
      !capture.payload.metadata ||
      typeof capture.payload.metadata !==
        "object"
    ) {
      capture.payload.metadata = {};
    }


    capture.payload.metadata[
      "browser_capture_session_version"
    ] =
      BROWSER_CAPTURE_SESSION_VERSION;


    if (
      platform === "web"
    ) {
      capture.payload.metadata[
        "article_extractor_capture"
      ] = {
        status:
          articleExtractorStatus,
      };
    }


    if (
      platform === "youtube" &&
      youtubeTranscriptEligible(
        sourceUrl
      )
    ) {
      capture.payload.metadata[
        "youtube_transcript_capture"
      ] = {
        status:
          transcriptStatus,

        ...transcriptMetadata(
          transcriptResult
        ),
      };
    }


    const apiBase =
      String(
        config.api ||
        "https://sportabase-api.onrender.com"
      ).replace(
        /\/+$/,
        ""
      );


    const timeoutMs =
      Math.max(
        1000,
        Number(
          config.captureTimeoutMs ||
          20000
        ) ||
        20000
      );


    if (
      typeof postJsonImpl !==
      "function"
    ) {
      throw new Error(
        "Browser capture transport is unavailable."
      );
    }


    const response =
      await postJsonImpl(
        `${apiBase}/content/browser-capture`,

        {
          capture,
        },

        {
          timeoutMs,
          signal,
        }
      );


    return {
      capture,
      response,
    };
  };
}
