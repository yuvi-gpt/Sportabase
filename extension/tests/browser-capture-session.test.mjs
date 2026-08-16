import test
  from "node:test";

import assert
  from "node:assert/strict";

import {
  createBrowserCaptureSession,
}
from "../src/content/browser-capture-session.mjs";


const OBSERVED =
  "2026-08-16T12:00:00Z";


function makeAcquireRecorder() {
  const calls = [];

  const implementation =
    (options) => {
      calls.push(options);

      return {
        version:
          "browser-capture-v1",

        source_url:
          options.sourceUrl,

        observed_at:
          options.observedAt,

        extraction_method:
          "browser_dom",

        payload: {
          platform:
            "test",

          surface:
            "post",

          container_kind:
            "post",

          canonical_url:
            options.sourceUrl,

          title:
            "Captured content",

          metadata: {},
        },

        actor: {},
      };
    };

  return {
    calls,
    implementation,
  };
}


function makePostRecorder() {
  const calls = [];

  const implementation =
    async (
      url,
      payload,
      options
    ) => {
      calls.push({
        url,
        payload,
        options,
      });

      return {
        version:
          "browser-ingestion-v1",

        item: {
          item_id:
            "test:item",
        },

        processing_plan: {},
      };
    };

  return {
    calls,
    implementation,
  };
}


test(
  "web session reuses provided article extraction and submits capture",

  async () => {
    const acquire =
      makeAcquireRecorder();

    const post =
      makePostRecorder();

    let extractorCalls = 0;

    const session =
      createBrowserCaptureSession({
        config: {
          api:
            "https://api.example/",
        },

        documentRef: {},

        sourceUrlResolver:
          () =>
            "https://example.com/story",

        now:
          () =>
            OBSERVED,

        acquirePageSnapshotImpl:
          acquire.implementation,

        detectBrowserPlatformImpl:
          () =>
            "web",

        extractArticlePageImpl:
          () => {
            extractorCalls += 1;

            return {
              title:
                "Should not run",
            };
          },

        postJsonImpl:
          post.implementation,
      });


    const article = {
      title:
        "Existing article",

      text:
        "Existing extracted body.",
    };


    const result =
      await session({
        articleExtraction:
          article,
      });


    assert.equal(
      extractorCalls,
      0
    );

    assert.equal(
      acquire.calls.length,
      1
    );

    assert.equal(
      acquire.calls[0]
        .articleExtraction,
      article
    );

    assert.equal(
      post.calls.length,
      1
    );

    assert.equal(
      post.calls[0].url,
      "https://api.example/content/browser-capture"
    );

    assert.equal(
      post.calls[0]
        .payload
        .capture,
      result.capture
    );
  }
);


test(
  "web session invokes existing article extractor when enrichment was not provided",

  async () => {
    const acquire =
      makeAcquireRecorder();

    const post =
      makePostRecorder();

    let extractorCalls = 0;

    const session =
      createBrowserCaptureSession({
        documentRef: {},

        sourceUrlResolver:
          () =>
            "https://example.com/story",

        now:
          () =>
            OBSERVED,

        detectBrowserPlatformImpl:
          () =>
            "web",

        extractArticlePageImpl:
          () => {
            extractorCalls += 1;

            return {
              title:
                "Extracted article",

              text:
                "Extracted body.",
            };
          },

        acquirePageSnapshotImpl:
          acquire.implementation,

        postJsonImpl:
          post.implementation,
      });


    const result =
      await session();


    assert.equal(
      extractorCalls,
      1
    );

    assert.equal(
      acquire.calls[0]
        .articleExtraction
        .title,
      "Extracted article"
    );

    assert.equal(
      result.capture
        .payload
        .metadata
        .article_extractor_capture
        .status,
      "available"
    );
  }
);


test(
  "youtube session reuses provided transcript without extracting twice",

  async () => {
    const acquire =
      makeAcquireRecorder();

    const post =
      makePostRecorder();

    let transcriptCalls = 0;

    const session =
      createBrowserCaptureSession({
        documentRef: {},

        sourceUrlResolver:
          () =>
            "https://youtube.com/watch?v=abcDEF12345",

        now:
          () =>
            OBSERVED,

        detectBrowserPlatformImpl:
          () =>
            "youtube",

        extractYouTubeTranscriptImpl:
          async () => {
            transcriptCalls += 1;

            return {
              transcript:
                "Should not run",
            };
          },

        acquirePageSnapshotImpl:
          acquire.implementation,

        postJsonImpl:
          post.implementation,
      });


    const transcript = {
      transcript:
        "Existing transcript",

      extractionConfidence:
        0.94,

      segmentCount:
        12,

      characterCount:
        420,

      extractionWarnings:
        [],
    };


    const result =
      await session({
        youtubeTranscript:
          transcript,
      });


    assert.equal(
      transcriptCalls,
      0
    );

    assert.equal(
      acquire.calls[0]
        .youtubeTranscript,
      transcript
    );

    assert.equal(
      result.capture
        .payload
        .metadata
        .youtube_transcript_capture
        .status,
      "provided"
    );

    assert.equal(
      result.capture
        .payload
        .metadata
        .youtube_transcript_capture
        .extraction_confidence,
      0.94
    );
  }
);


test(
  "youtube session can obtain transcript through existing extractor",

  async () => {
    const acquire =
      makeAcquireRecorder();

    const post =
      makePostRecorder();

    let transcriptCalls = 0;

    const session =
      createBrowserCaptureSession({
        documentRef: {},

        sourceUrlResolver:
          () =>
            "https://youtube.com/shorts/abcDEF12345",

        now:
          () =>
            OBSERVED,

        detectBrowserPlatformImpl:
          () =>
            "youtube",

        extractYouTubeTranscriptImpl:
          async () => {
            transcriptCalls += 1;

            return {
              transcript:
                "Fresh transcript",

              segmentCount:
                3,
            };
          },

        acquirePageSnapshotImpl:
          acquire.implementation,

        postJsonImpl:
          post.implementation,
      });


    const result =
      await session();


    assert.equal(
      transcriptCalls,
      1
    );

    assert.equal(
      acquire.calls[0]
        .youtubeTranscript
        .transcript,
      "Fresh transcript"
    );

    assert.equal(
      result.capture
        .payload
        .metadata
        .youtube_transcript_capture
        .status,
      "available"
    );
  }
);


test(
  "transcript extraction failure does not block structural YouTube capture",

  async () => {
    const acquire =
      makeAcquireRecorder();

    const post =
      makePostRecorder();

    const session =
      createBrowserCaptureSession({
        documentRef: {},

        sourceUrlResolver:
          () =>
            "https://youtube.com/watch?v=abcDEF12345",

        now:
          () =>
            OBSERVED,

        detectBrowserPlatformImpl:
          () =>
            "youtube",

        extractYouTubeTranscriptImpl:
          async () => {
            throw new Error(
              "Transcript unavailable"
            );
          },

        acquirePageSnapshotImpl:
          acquire.implementation,

        postJsonImpl:
          post.implementation,
      });


    const result =
      await session();


    assert.equal(
      acquire.calls.length,
      1
    );

    assert.equal(
      acquire.calls[0]
        .youtubeTranscript,
      null
    );

    assert.equal(
      result.capture
        .payload
        .metadata
        .youtube_transcript_capture
        .status,
      "unavailable"
    );

    assert.equal(
      post.calls.length,
      1
    );
  }
);


test(
  "social capture bypasses legacy article and YouTube extractors and forwards cancellation signal",

  async () => {
    const acquire =
      makeAcquireRecorder();

    const post =
      makePostRecorder();

    let articleCalls = 0;
    let transcriptCalls = 0;

    const controller =
      new AbortController();

    const session =
      createBrowserCaptureSession({
        documentRef: {},

        sourceUrlResolver:
          () =>
            "https://x.com/reporter/status/123456",

        now:
          () =>
            OBSERVED,

        detectBrowserPlatformImpl:
          () =>
            "x",

        extractArticlePageImpl:
          () => {
            articleCalls += 1;
            return {};
          },

        extractYouTubeTranscriptImpl:
          async () => {
            transcriptCalls += 1;
            return {};
          },

        acquirePageSnapshotImpl:
          acquire.implementation,

        postJsonImpl:
          post.implementation,
      });


    await session({
      signal:
        controller.signal,
    });


    assert.equal(
      articleCalls,
      0
    );

    assert.equal(
      transcriptCalls,
      0
    );

    assert.equal(
      post.calls[0]
        .options
        .signal,
      controller.signal
    );
  }
);
