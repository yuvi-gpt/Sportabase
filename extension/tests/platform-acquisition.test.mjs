import test
  from "node:test";

import assert
  from "node:assert/strict";

import {
  BROWSER_CAPTURE_VERSION,
  PLATFORM_ACQUISITION_VERSION,
  acquirePageSnapshot,
  detectBrowserPlatform,
}
from "../src/content/platform-acquisition.mjs";


class FakeNode {
  constructor({
    text = "",
    attrs = {},
    children = {},
    all = {},
    src = "",
    currentSrc = "",
    duration = NaN,
  } = {}) {
    this.textContent =
      text;

    this.innerText =
      text;

    this.attrs =
      attrs;

    this.children =
      children;

    this.all =
      all;

    this.src =
      src;

    this.currentSrc =
      currentSrc;

    this.duration =
      duration;
  }


  getAttribute(name) {
    return (
      this.attrs[name] ??
      ""
    );
  }


  querySelector(
    selector
  ) {
    return (
      this.children[
        selector
      ] ??
      null
    );
  }


  querySelectorAll(
    selector
  ) {
    return (
      this.all[
        selector
      ] ??
      []
    );
  }
}


class FakeDocument
extends FakeNode {
  constructor(
    options = {}
  ) {
    super(options);

    this.title =
      options.title ||
      "";

    this.body =
      options.body ||
      null;
  }
}


const OBSERVED =
  "2026-08-16T12:00:00Z";


function meta(content) {
  return new FakeNode({
    attrs: {
      content,
    },
  });
}


function link(
  href,
  text = ""
) {
  return new FakeNode({
    text,

    attrs: {
      href,
    },
  });
}


test(
  "detects supported platforms without trusting lookalike hosts",

  () => {
    const cases = [
      [
        "https://instagram.com/p/ABC",
        "instagram",
      ],

      [
        "https://x.com/a/status/123",
        "x",
      ],

      [
        "https://twitter.com/a/status/123",
        "x",
      ],

      [
        "https://www.tiktok.com/@a/video/1",
        "tiktok",
      ],

      [
        "https://old.reddit.com/r/soccer/comments/a/b",
        "reddit",
      ],

      [
        "https://facebook.com/a/posts/1",
        "facebook",
      ],

      [
        "https://youtu.be/abcDEF12345",
        "youtube",
      ],

      [
        "https://youtube.com/shorts/abcDEF12345",
        "youtube",
      ],

      [
        "https://example.com/story",
        "web",
      ],

      [
        "https://youtube.com.evil.example/watch?v=x",
        "web",
      ],
    ];


    for (
      const [
        url,
        expected,
      ]
      of cases
    ) {
      assert.equal(
        detectBrowserPlatform(
          url
        ),
        expected,
        url
      );
    }
  }
);


test(
  "captures X permalink text actor timestamp and media",

  () => {
    const tweet =
      new FakeNode({
        children: {
          "[data-testid='tweetText']":
            new FakeNode({
              text:
                "Arsenal agree a deal.",
            }),

          "[data-testid='User-Name'] a[href^='/']":
            link(
              "/Reporter",
              "Reporter Name"
            ),

          "[data-testid='User-Name']":
            new FakeNode({
              text:
                "Reporter Name",
            }),

          "time[datetime]":
            new FakeNode({
              attrs: {
                datetime:
                  "2026-08-16T09:00:00Z",
              },
            }),
        },

        all: {
          "[data-testid='tweetPhoto'] img":
            [
              new FakeNode({
                src:
                  "https://pbs.twimg.com/media/a.jpg",
              }),
            ],

          video: [],
        },
      });


    const doc =
      new FakeDocument({
        children: {
          "article[data-testid='tweet']":
            tweet,

          "meta[property='og:title']":
            meta(
              "Reporter on X"
            ),

          "link[rel='canonical']":
            new FakeNode({
              attrs: {
                href:
                  "https://x.com/Reporter/status/123456",
              },
            }),
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://twitter.com/Reporter/status/123456?s=20",

        observedAt:
          OBSERVED,
      });


    assert.equal(
      result.version,
      BROWSER_CAPTURE_VERSION
    );

    assert.equal(
      result.payload.platform,
      "x"
    );

    assert.equal(
      result.payload.body,
      "Arsenal agree a deal."
    );

    assert.equal(
      result.payload.published_at,
      "2026-08-16T09:00:00Z"
    );

    assert.equal(
      result.actor.handle,
      "Reporter"
    );

    assert.equal(
      result.payload
        .media[0]
        .media_kind,
      "image"
    );
  }
);


test(
  "captures Instagram reel caption and video",

  () => {
    const article =
      new FakeNode({
        children: {
          h1:
            new FakeNode({
              text:
                "Training ground update",
            }),
        },

        all: {
          video: [
            new FakeNode({
              currentSrc:
                "https://cdn.example/reel.mp4",

              duration:
                22,
            }),
          ],

          "img[src]":
            [],
        },
      });


    const doc =
      new FakeDocument({
        children: {
          article,
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://instagram.com/reel/ABC123",

        observedAt:
          OBSERVED,
      });


    assert.equal(
      result.payload.surface,
      "reel"
    );

    assert.equal(
      result.payload.caption,
      "Training ground update"
    );

    assert.equal(
      result.payload
        .media[0]
        .duration_seconds,
      22
    );
  }
);


test(
  "captures TikTok caption username and video",

  () => {
    const scope =
      new FakeNode({
        children: {
          "[data-e2e='browse-video-desc']":
            new FakeNode({
              text:
                "Goal clip",
            }),

          "[data-e2e='browse-username']":
            new FakeNode({
              text:
                "@club",
            }),
        },

        all: {
          video: [
            new FakeNode({
              src:
                "https://cdn.example/tiktok.mp4",
            }),
          ],

          "[data-e2e='photo-mode-canvas'] img":
            [],

          "img[src]":
            [],
        },
      });


    const doc =
      new FakeDocument({
        children: {
          "[data-e2e='browse-video-container']":
            scope,
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://www.tiktok.com/@club/video/738123456789",

        observedAt:
          OBSERVED,
      });


    assert.equal(
      result.payload.platform,
      "tiktok"
    );

    assert.equal(
      result.actor.handle,
      "club"
    );

    assert.equal(
      result.payload.caption,
      "Goal clip"
    );
  }
);


test(
  "captures Reddit post title body and author",

  () => {
    const post =
      new FakeNode({
        attrs: {
          author:
            "u/reporter",
        },

        children: {
          "[slot='title']":
            new FakeNode({
              text:
                "Transfer thread",
            }),

          "[slot='text-body']":
            new FakeNode({
              text:
                "Club statement linked here.",
            }),
        },

        all: {
          video: [],
          "img[src]": [],
        },
      });


    const doc =
      new FakeDocument({
        children: {
          "shreddit-post":
            post,
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://reddit.com/r/soccer/comments/abc123/title/",

        observedAt:
          OBSERVED,
      });


    assert.equal(
      result.payload.title,
      "Transfer thread"
    );

    assert.equal(
      result.payload.body,
      "Club statement linked here."
    );

    assert.equal(
      result.actor.handle,
      "u/reporter"
    );
  }
);


test(
  "captures Facebook post message without inventing evidence fields",

  () => {
    const article =
      new FakeNode({
        children: {
          "[data-ad-preview='message']":
            new FakeNode({
              text:
                "Squad update",
            }),
        },

        all: {
          video: [],
          "img[src]": [],
        },
      });


    const doc =
      new FakeDocument({
        children: {
          "[role='article']":
            article,
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://facebook.com/club/posts/123",

        observedAt:
          OBSERVED,
      });


    assert.equal(
      result.payload.body,
      "Squad update"
    );

    assert.equal(
      result.payload
        .metadata
        .browser_acquisition_version,

      PLATFORM_ACQUISITION_VERSION
    );

    assert.equal(
      "merit_score"
      in result.payload,
      false
    );

    assert.equal(
      "authority"
      in result.payload.metadata,
      false
    );
  }
);


test(
  "captures YouTube short as video and reuses transcript enrichment",

  () => {
    const video =
      new FakeNode({
        currentSrc:
          "https://googlevideo.example/videoplayback",

        duration:
          44,
      });


    const doc =
      new FakeDocument({
        children: {
          "h1 yt-formatted-string":
            new FakeNode({
              text:
                "Match reaction",
            }),

          "#description":
            new FakeNode({
              text:
                "Post-match thoughts",
            }),
        },

        all: {
          video: [
            video,
          ],
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://youtube.com/shorts/abcDEF12345",

        observedAt:
          OBSERVED,

        youtubeTranscript: {
          transcript:
            "Existing caption transcript",
        },
      });


    assert.equal(
      result.payload.surface,
      "short"
    );

    assert.equal(
      result.payload
        .container_kind,
      "media"
    );

    assert.equal(
      result.payload.transcript,
      "Existing caption transcript"
    );

    assert.equal(
      result.extraction_method,
      "browser_dom+youtube_transcript"
    );

    assert.equal(
      result.payload
        .media[0]
        .media_kind,
      "video"
    );
  }
);


test(
  "captures YouTube community post separately from video architecture",

  () => {
    const post =
      new FakeNode({
        children: {
          "#content-text":
            new FakeNode({
              text:
                "Community update",
            }),
        },

        all: {
          "img[src]": [
            new FakeNode({
              src:
                "https://yt.example/post.jpg",
            }),
          ],
        },
      });


    const doc =
      new FakeDocument({
        children: {
          "ytd-backstage-post-thread-renderer":
            post,
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://youtube.com/post/UgkxABC_123",

        observedAt:
          OBSERVED,
      });


    assert.equal(
      result.payload.surface,
      "community_post"
    );

    assert.equal(
      result.payload
        .container_kind,
      "post"
    );

    assert.equal(
      result.payload.body,
      "Community update"
    );
  }
);


test(
  "generic web reuses existing article extraction without changing analysis semantics",

  () => {
    const doc =
      new FakeDocument({
        children: {
          "link[rel='canonical']":
            new FakeNode({
              attrs: {
                href:
                  "https://example.com/story",
              },
            }),
        },
      });


    const result =
      acquirePageSnapshot({
        documentRef:
          doc,

        sourceUrl:
          "https://example.com/story?utm_source=x",

        observedAt:
          OBSERVED,

        articleExtraction: {
          title:
            "Article title",

          text:
            "A long extracted article body that came from the existing article extractor.",

          url:
            "https://example.com/story?utm_source=x",

          selector:
            "article",

          candidateCount:
            2,
        },
      });


    assert.equal(
      result.payload.platform,
      "web"
    );

    assert.equal(
      result.payload.surface,
      "article"
    );

    assert.equal(
      result.payload
        .body
        .startsWith(
          "A long extracted"
        ),
      true
    );

    assert.equal(
      result.extraction_method,
      "browser_dom+article_extractor"
    );
  }
);


test(
  "fails closed when URL document timestamp or usable content is missing",

  () => {
    const emptyDoc =
      new FakeDocument();


    assert.throws(
      () =>
        acquirePageSnapshot({
          documentRef:
            emptyDoc,

          sourceUrl:
            "not a url",

          observedAt:
            OBSERVED,
        }),

      /HTTP or HTTPS/
    );


    assert.throws(
      () =>
        acquirePageSnapshot({
          documentRef:
            null,

          sourceUrl:
            "https://example.com",

          observedAt:
            OBSERVED,
        }),

      /document-like/
    );


    assert.throws(
      () =>
        acquirePageSnapshot({
          documentRef:
            emptyDoc,

          sourceUrl:
            "https://example.com",

          observedAt:
            "",
        }),

      /observedAt/
    );


    assert.throws(
      () =>
        acquirePageSnapshot({
          documentRef:
            emptyDoc,

          sourceUrl:
            "https://example.com",

          observedAt:
            OBSERVED,
        }),

      /No usable content/
    );
  }
);
