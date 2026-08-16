export const BROWSER_CAPTURE_VERSION =
  "browser-capture-v1";

export const PLATFORM_ACQUISITION_VERSION =
  "platform-acquisition-v1";


const PLATFORM_HOSTS =
  Object.freeze({
    instagram: [
      "instagram.com",
    ],

    x: [
      "x.com",
      "twitter.com",
    ],

    tiktok: [
      "tiktok.com",
    ],

    reddit: [
      "reddit.com",
      "redd.it",
    ],

    facebook: [
      "facebook.com",
      "fb.watch",
    ],

    youtube: [
      "youtube.com",
      "youtu.be",
      "youtube-nocookie.com",
    ],
  });


function cleanText(value) {
  return String(
    value ?? ""
  )
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}


function truncateText(
  value,
  limit
) {
  const text =
    cleanText(value);

  const safeLimit =
    Math.max(
      500,
      Number(limit) ||
        12000
    );

  if (
    text.length <=
    safeLimit
  ) {
    return text;
  }

  return text
    .slice(
      0,
      safeLimit
    )
    .trim();
}


function hostMatches(
  hostname,
  expected
) {
  return (
    hostname === expected ||
    hostname.endsWith(
      `.${expected}`
    )
  );
}


function parseHttpUrl(
  value,
  base = undefined
) {
  try {
    const parsed =
      new URL(
        String(
          value || ""
        ),
        base
      );

    if (
      ![
        "http:",
        "https:",
      ].includes(
        parsed.protocol
      )
    ) {
      return null;
    }

    return parsed;
  } catch (_) {
    return null;
  }
}


function absoluteUrl(
  value,
  baseUrl
) {
  const parsed =
    parseHttpUrl(
      value,
      baseUrl
    );

  return parsed
    ? parsed.href
    : "";
}


function queryFirst(
  root,
  selectors
) {
  if (
    !root ||
    typeof root.querySelector !==
      "function"
  ) {
    return null;
  }

  for (
    const selector
    of selectors
  ) {
    try {
      const node =
        root.querySelector(
          selector
        );

      if (node) {
        return node;
      }
    } catch (_) {}
  }

  return null;
}


function queryAll(
  root,
  selectors
) {
  if (
    !root ||
    typeof root.querySelectorAll !==
      "function"
  ) {
    return [];
  }

  const nodes = [];
  const seen =
    new Set();

  for (
    const selector
    of selectors
  ) {
    try {
      const selected =
        Array.from(
          root.querySelectorAll(
            selector
          ) || []
        );

      for (
        const node
        of selected
      ) {
        if (
          !node ||
          seen.has(node)
        ) {
          continue;
        }

        seen.add(node);

        nodes.push({
          node,
          selector,
        });
      }
    } catch (_) {}
  }

  return nodes;
}


function nodeText(node) {
  return cleanText(
    node?.innerText ||
    node?.textContent ||
    ""
  );
}


function firstText(
  root,
  selectors
) {
  for (
    const selector
    of selectors
  ) {
    const node =
      queryFirst(
        root,
        [
          selector,
        ]
      );

    const text =
      nodeText(node);

    if (text) {
      return text;
    }
  }

  return "";
}


function firstAttr(
  root,
  selectors,
  attribute
) {
  for (
    const selector
    of selectors
  ) {
    const node =
      queryFirst(
        root,
        [
          selector,
        ]
      );

    const value =
      cleanText(
        node
          ?.getAttribute
          ?.(attribute) ||
        ""
      );

    if (value) {
      return value;
    }
  }

  return "";
}


function firstMeta(
  documentRef,
  selectors
) {
  return firstAttr(
    documentRef,
    selectors,
    "content"
  );
}


function canonicalUrl(
  documentRef,
  sourceUrl
) {
  const raw =
    firstAttr(
      documentRef,
      [
        "link[rel='canonical']",
        'link[rel="canonical"]',
      ],
      "href"
    ) ||
    firstMeta(
      documentRef,
      [
        "meta[property='og:url']",
        'meta[property="og:url"]',
      ]
    );

  return (
    absoluteUrl(
      raw,
      sourceUrl
    ) ||
    sourceUrl
  );
}


function titleFromDocument(
  documentRef
) {
  return (
    firstMeta(
      documentRef,
      [
        "meta[property='og:title']",
        'meta[property="og:title"]',

        "meta[name='twitter:title']",
        'meta[name="twitter:title"]',
      ]
    ) ||

    firstText(
      documentRef,
      [
        "h1",
      ]
    ) ||

    cleanText(
      documentRef?.title ||
      ""
    )
  );
}


function descriptionFromDocument(
  documentRef
) {
  return firstMeta(
    documentRef,
    [
      "meta[property='og:description']",
      'meta[property="og:description"]',

      "meta[name='twitter:description']",
      'meta[name="twitter:description"]',

      "meta[name='description']",
      'meta[name="description"]',
    ]
  );
}


function publishedFromDocument(
  documentRef,
  scope = documentRef
) {
  return (
    firstAttr(
      scope,
      [
        "time[datetime]",
      ],
      "datetime"
    ) ||

    firstMeta(
      documentRef,
      [
        "meta[property='article:published_time']",
        'meta[property="article:published_time"]',

        "meta[name='date']",
        'meta[name="date"]',
      ]
    )
  );
}


function actorFromLink(
  linkValue,
  sourceUrl,
  displayName = ""
) {
  const profileUrl =
    absoluteUrl(
      linkValue,
      sourceUrl
    );

  let handle = "";

  if (profileUrl) {
    const parsed =
      parseHttpUrl(
        profileUrl
      );

    const parts =
      parsed
        ?.pathname
        .split("/")
        .filter(Boolean) ||
      [];

    if (parts.length) {
      handle =
        parts[0]
          .replace(
            /^@/,
            ""
          );
    }
  }

  return {
    platform_actor_id: "",
    handle,
    display_name:
      cleanText(
        displayName
      ),
    profile_url:
      profileUrl,
    canonical_entity_id: "",
    metadata: {},
  };
}


function actorFromHandle(
  handle,
  displayName = ""
) {
  return {
    platform_actor_id: "",

    handle:
      cleanText(handle)
        .replace(
          /^@/,
          ""
        ),

    display_name:
      cleanText(
        displayName
      ),

    profile_url: "",
    canonical_entity_id: "",
    metadata: {},
  };
}


function hasActor(actor) {
  return Boolean(
    actor &&
    (
      actor.platform_actor_id ||
      actor.handle ||
      actor.display_name ||
      actor.profile_url
    )
  );
}


function mediaUrlForNode(
  node,
  sourceUrl
) {
  const raw =
    node?.currentSrc ||
    node?.src ||
    node
      ?.getAttribute
      ?.( "src" ) ||
    node
      ?.getAttribute
      ?.( "href" ) ||
    "";

  return absoluteUrl(
    raw,
    sourceUrl
  );
}


function collectMedia(
  documentRef,
  scope,
  sourceUrl,
  descriptors = []
) {
  const media = [];
  const seen =
    new Set();

  const add = (
    kind,
    url,
    node = null,
    selector = "metadata"
  ) => {
    const normalizedUrl =
      absoluteUrl(
        url,
        sourceUrl
      );

    if (!normalizedUrl) {
      return;
    }

    const identity =
      `${kind}|${normalizedUrl}`;

    if (
      seen.has(
        identity
      )
    ) {
      return;
    }

    seen.add(
      identity
    );

    const item = {
      component_id:
        `${kind}:${media.length}`,

      media_kind:
        kind,

      media_url:
        normalizedUrl,

      metadata: {
        capture_selector:
          selector,
      },
    };

    if (
      kind === "video"
    ) {
      const duration =
        Number(
          node?.duration
        );

      if (
        Number.isFinite(
          duration
        ) &&
        duration >= 0
      ) {
        item.duration_seconds =
          duration;
      }
    }

    media.push(
      item
    );
  };


  for (
    const descriptor
    of descriptors
  ) {
    for (
      const {
        node,
        selector,
      }
      of queryAll(
        scope,
        descriptor.selectors ||
          []
      )
    ) {
      add(
        descriptor.kind,
        mediaUrlForNode(
          node,
          sourceUrl
        ),
        node,
        selector
      );
    }
  }


  const ogVideo =
    firstMeta(
      documentRef,
      [
        "meta[property='og:video']",
        'meta[property="og:video"]',

        "meta[property='og:video:url']",
        'meta[property="og:video:url"]',
      ]
    );


  const ogImage =
    firstMeta(
      documentRef,
      [
        "meta[property='og:image']",
        'meta[property="og:image"]',
      ]
    );


  if (ogVideo) {
    add(
      "video",
      ogVideo,
      null,
      "og:video"
    );
  }

  if (ogImage) {
    add(
      "image",
      ogImage,
      null,
      "og:image"
    );
  }

  return media;
}


function basePayload({
  platform,
  surface,
  containerKind,
  canonical,
  title,
  publishedAt,
  metadata = {},
}) {
  const payload = {
    platform,
    surface,

    container_kind:
      containerKind,

    canonical_url:
      canonical,

    metadata: {
      browser_acquisition_version:
        PLATFORM_ACQUISITION_VERSION,

      adapter:
        platform,

      ...metadata,
    },
  };


  if (title) {
    payload.title =
      title;
  }

  if (publishedAt) {
    payload.published_at =
      publishedAt;
  }

  return payload;
}


function surfaceForUrl(
  platform,
  sourceUrl
) {
  const parsed =
    parseHttpUrl(
      sourceUrl
    );

  const parts =
    parsed
      ?.pathname
      .split("/")
      .filter(Boolean)
      .map(
        (part) =>
          part.toLowerCase()
      ) ||
    [];


  if (
    platform ===
    "instagram"
  ) {
    if (
      parts[0] ===
      "stories"
    ) {
      return "story";
    }

    if (
      [
        "reel",
        "reels",
      ].includes(
        parts[0]
      )
    ) {
      return "reel";
    }

    if (
      parts[0] === "tv"
    ) {
      return "video";
    }

    return "post";
  }


  if (
    platform ===
    "youtube"
  ) {
    if (
      parts[0] ===
      "shorts"
    ) {
      return "short";
    }

    if (
      parts[0] ===
      "post"
    ) {
      return "community_post";
    }

    return "video";
  }


  if (
    platform ===
    "reddit"
  ) {
    return (
      parts.includes(
        "comments"
      ) &&
      parts.length >= 6
    )
      ? "comment"
      : "post";
  }


  if (
    platform ===
    "facebook"
  ) {
    if (
      parts[0] ===
      "reel"
    ) {
      return "reel";
    }

    if (
      parts[0] ===
      "watch"
    ) {
      return "video";
    }

    return "post";
  }


  if (
    platform ===
    "tiktok"
  ) {
    return parts.includes(
      "photo"
    )
      ? "photo"
      : "video";
  }


  if (
    platform === "x"
  ) {
    return "post";
  }


  return "article";
}


export function detectBrowserPlatform(
  url
) {
  const parsed =
    parseHttpUrl(
      url
    );

  if (!parsed) {
    return "web";
  }

  const hostname =
    parsed.hostname
      .toLowerCase()
      .replace(
        /^www\./,
        ""
      );


  for (
    const [
      platform,
      hosts,
    ]
    of Object.entries(
      PLATFORM_HOSTS
    )
  ) {
    if (
      hosts.some(
        (host) =>
          hostMatches(
            hostname,
            host
          )
      )
    ) {
      return platform;
    }
  }

  return "web";
}


function acquireX(
  documentRef,
  sourceUrl,
  limit
) {
  const scope =
    queryFirst(
      documentRef,
      [
        "article[data-testid='tweet']",
        "article",
      ]
    ) ||
    documentRef;


  const body =
    truncateText(
      firstText(
        scope,
        [
          "[data-testid='tweetText']",
        ]
      ) ||
      descriptionFromDocument(
        documentRef
      ),
      limit
    );


  const actorLink =
    firstAttr(
      scope,
      [
        "[data-testid='User-Name'] a[href^='/']",
      ],
      "href"
    );


  const actorName =
    firstText(
      scope,
      [
        "[data-testid='User-Name']",
      ]
    );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "image",
          selectors: [
            "[data-testid='tweetPhoto'] img",
          ],
        },

        {
          kind: "video",
          selectors: [
            "video",
          ],
        },
      ]
    );


  const payload =
    basePayload({
      platform: "x",
      surface: "post",
      containerKind:
        "post",

      canonical:
        canonicalUrl(
          documentRef,
          sourceUrl
        ),

      title:
        titleFromDocument(
          documentRef
        ),

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),
    });


  if (body) {
    payload.body =
      body;
  }

  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,

    actor:
      actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      ),
  };
}


function acquireInstagram(
  documentRef,
  sourceUrl,
  limit
) {
  const scope =
    queryFirst(
      documentRef,
      [
        "article",
      ]
    ) ||
    documentRef;


  const surface =
    surfaceForUrl(
      "instagram",
      sourceUrl
    );


  const caption =
    truncateText(
      firstText(
        scope,
        [
          "h1",
          "[data-testid='post-comment-root']",
        ]
      ) ||
      descriptionFromDocument(
        documentRef
      ),
      limit
    );


  const actorLink =
    firstAttr(
      scope,
      [
        "header a[href^='/']",
        "a[href^='/']",
      ],
      "href"
    );


  const actorName =
    firstText(
      scope,
      [
        "header a[href^='/']",
      ]
    );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video",
          ],
        },

        {
          kind: "image",
          selectors: [
            "img[src]",
          ],
        },
      ]
    );


  const payload =
    basePayload({
      platform:
        "instagram",

      surface,

      containerKind:
        surface === "story"
          ? "story"
          : "post",

      canonical:
        canonicalUrl(
          documentRef,
          sourceUrl
        ),

      title:
        titleFromDocument(
          documentRef
        ),

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),
    });


  if (caption) {
    payload.caption =
      caption;
  }

  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,

    actor:
      actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      ),
  };
}


function acquireTikTok(
  documentRef,
  sourceUrl,
  limit
) {
  const scope =
    queryFirst(
      documentRef,
      [
        "[data-e2e='browse-video-container']",
        "main",
      ]
    ) ||
    documentRef;


  const caption =
    truncateText(
      firstText(
        scope,
        [
          "[data-e2e='browse-video-desc']",
        ]
      ) ||
      descriptionFromDocument(
        documentRef
      ),
      limit
    );


  const username =
    firstText(
      scope,
      [
        "[data-e2e='browse-username']",
        "[data-e2e='video-author-uniqueid']",
      ]
    );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video",
          ],
        },

        {
          kind: "image",
          selectors: [
            "[data-e2e='photo-mode-canvas'] img",
            "img[src]",
          ],
        },
      ]
    );


  const payload =
    basePayload({
      platform:
        "tiktok",

      surface:
        surfaceForUrl(
          "tiktok",
          sourceUrl
        ),

      containerKind:
        "post",

      canonical:
        canonicalUrl(
          documentRef,
          sourceUrl
        ),

      title:
        titleFromDocument(
          documentRef
        ),

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),
    });


  if (caption) {
    payload.caption =
      caption;
  }

  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,

    actor:
      actorFromHandle(
        username
      ),
  };
}


function acquireReddit(
  documentRef,
  sourceUrl,
  limit
) {
  const scope =
    queryFirst(
      documentRef,
      [
        "shreddit-post",
        "article",
      ]
    ) ||
    documentRef;


  const title =
    firstText(
      scope,
      [
        "[slot='title']",
        "h1",
      ]
    ) ||
    titleFromDocument(
      documentRef
    );


  const body =
    truncateText(
      firstText(
        scope,
        [
          "[slot='text-body']",
          "[data-post-click-location='text-body']",
          "div[slot='text-body']",
        ]
      ) ||
      descriptionFromDocument(
        documentRef
      ),
      limit
    );


  const author =
    cleanText(
      scope
        ?.getAttribute
        ?.("author") ||

      firstText(
        scope,
        [
          "[data-testid='post_author_link']",
        ]
      )
    );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video",
          ],
        },

        {
          kind: "image",
          selectors: [
            "img[src]",
          ],
        },
      ]
    );


  const surface =
    surfaceForUrl(
      "reddit",
      sourceUrl
    );


  const payload =
    basePayload({
      platform:
        "reddit",

      surface,

      containerKind:
        surface ===
        "comment"
          ? "comment"
          : "post",

      canonical:
        canonicalUrl(
          documentRef,
          sourceUrl
        ),

      title,

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),
    });


  if (body) {
    payload.body =
      body;
  }

  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,

    actor:
      actorFromHandle(
        author
      ),
  };
}


function acquireFacebook(
  documentRef,
  sourceUrl,
  limit
) {
  const scope =
    queryFirst(
      documentRef,
      [
        "[role='article']",
      ]
    ) ||
    documentRef;


  const body =
    truncateText(
      firstText(
        scope,
        [
          "[data-ad-preview='message']",
          "[data-testid='post_message']",
        ]
      ) ||
      descriptionFromDocument(
        documentRef
      ),
      limit
    );


  const actorLink =
    firstAttr(
      scope,
      [
        "h2 a[href]",
        "h3 a[href]",
      ],
      "href"
    );


  const actorName =
    firstText(
      scope,
      [
        "h2 a[href]",
        "h3 a[href]",
      ]
    );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video",
          ],
        },

        {
          kind: "image",
          selectors: [
            "img[src]",
          ],
        },
      ]
    );


  const surface =
    surfaceForUrl(
      "facebook",
      sourceUrl
    );


  const payload =
    basePayload({
      platform:
        "facebook",

      surface,

      containerKind:
        "post",

      canonical:
        canonicalUrl(
          documentRef,
          sourceUrl
        ),

      title:
        titleFromDocument(
          documentRef
        ),

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),
    });


  if (body) {
    payload.body =
      body;
  }

  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,

    actor:
      actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      ),
  };
}


function acquireYouTube(
  documentRef,
  sourceUrl,
  limit,
  youtubeTranscript
) {
  const surface =
    surfaceForUrl(
      "youtube",
      sourceUrl
    );


  const isCommunity =
    surface ===
    "community_post";


  const scope =
    isCommunity
      ? (
          queryFirst(
            documentRef,
            [
              "ytd-backstage-post-thread-renderer",
              "ytd-post-renderer",
            ]
          ) ||
          documentRef
        )
      : documentRef;


  const title =
    isCommunity
      ? titleFromDocument(
          documentRef
        )
      : (
          firstText(
            documentRef,
            [
              "h1 yt-formatted-string",
              "h1",
            ]
          ) ||
          titleFromDocument(
            documentRef
          )
        );


  const description =
    truncateText(
      isCommunity
        ? firstText(
            scope,
            [
              "#content-text",
              "yt-formatted-string#content-text",
            ]
          )
        : (
            firstText(
              documentRef,
              [
                "#description-inline-expander yt-attributed-string",
                "#description",
              ]
            ) ||

            descriptionFromDocument(
              documentRef
            )
          ),
      limit
    );


  const actorLink =
    isCommunity
      ? firstAttr(
          scope,
          [
            "#author-text[href]",
            "a#author-text",
          ],
          "href"
        )
      : firstAttr(
          documentRef,
          [
            "#channel-name a[href]",
            "ytd-channel-name a[href]",
          ],
          "href"
        );


  const actorName =
    isCommunity
      ? firstText(
          scope,
          [
            "#author-text",
            "a#author-text",
          ]
        )
      : firstText(
          documentRef,
          [
            "#channel-name",
            "ytd-channel-name",
          ]
        );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,

      isCommunity
        ? [
            {
              kind: "image",
              selectors: [
                "img[src]",
              ],
            },
          ]
        : [
            {
              kind: "video",
              selectors: [
                "video",
              ],
            },
          ]
    );


  const payload =
    basePayload({
      platform:
        "youtube",

      surface,

      containerKind:
        isCommunity
          ? "post"
          : "media",

      canonical:
        canonicalUrl(
          documentRef,
          sourceUrl
        ),

      title,

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),
    });


  if (description) {
    if (isCommunity) {
      payload.body =
        description;
    } else {
      payload.description =
        description;
    }
  }


  const transcript =
    cleanText(
      youtubeTranscript
        ?.transcript ||
      ""
    );


  if (transcript) {
    payload.transcript =
      truncateText(
        transcript,

        Math.max(
          limit,
          20000
        )
      );
  }


  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,

    actor:
      actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      ),
  };
}


function acquireWeb(
  documentRef,
  sourceUrl,
  limit,
  articleExtraction
) {
  const article =
    articleExtraction &&
    typeof articleExtraction ===
      "object"
      ? articleExtraction
      : null;


  const scope =
    queryFirst(
      documentRef,
      [
        "article",
        "main",
        "[role='main']",
      ]
    ) ||

    documentRef?.body ||
    documentRef;


  const title =
    cleanText(
      article?.title ||
      titleFromDocument(
        documentRef
      )
    );


  const body =
    truncateText(
      article?.text ||
      nodeText(scope) ||
      descriptionFromDocument(
        documentRef
      ),
      limit
    );


  const media =
    collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video",
          ],
        },

        {
          kind: "image",
          selectors: [
            "article img[src]",
            "main img[src]",
          ],
        },
      ]
    );


  const articleUrl =
    cleanText(
      article?.url ||
      sourceUrl
    ) ||
    sourceUrl;


  const payload =
    basePayload({
      platform:
        "web",

      surface:
        "article",

      containerKind:
        "article",

      canonical:
        canonicalUrl(
          documentRef,
          articleUrl
        ),

      title,

      publishedAt:
        publishedFromDocument(
          documentRef,
          scope
        ),

      metadata:
        article
          ? {
              legacy_article_extractor:
                true,

              article_selector:
                cleanText(
                  article.selector ||
                  ""
                ),

              article_candidate_count:
                Number(
                  article.candidateCount ||
                  0
                ),
            }
          : {},
    });


  if (body) {
    payload.body =
      body;
  }

  if (media.length) {
    payload.media =
      media;
  }


  return {
    payload,
    actor: {},
  };
}


export function acquirePageSnapshot({
  documentRef =
    globalThis.document,

  sourceUrl =
    globalThis.location
      ?.href ||
    "",

  observedAt =
    new Date()
      .toISOString(),

  maxTextCharacters =
    12000,

  articleExtraction =
    null,

  youtubeTranscript =
    null,
} = {}) {
  const parsed =
    parseHttpUrl(
      sourceUrl
    );


  if (!parsed) {
    throw new Error(
      "Browser acquisition requires an HTTP or HTTPS page URL."
    );
  }


  if (
    !documentRef ||
    typeof documentRef.querySelector !==
      "function"
  ) {
    throw new Error(
      "Browser acquisition requires a document-like object."
    );
  }


  const timestamp =
    cleanText(
      observedAt
    );


  if (!timestamp) {
    throw new Error(
      "Browser acquisition requires observedAt."
    );
  }


  const platform =
    detectBrowserPlatform(
      sourceUrl
    );


  const adapter = {
    instagram:
      () =>
        acquireInstagram(
          documentRef,
          sourceUrl,
          maxTextCharacters
        ),

    x:
      () =>
        acquireX(
          documentRef,
          sourceUrl,
          maxTextCharacters
        ),

    tiktok:
      () =>
        acquireTikTok(
          documentRef,
          sourceUrl,
          maxTextCharacters
        ),

    reddit:
      () =>
        acquireReddit(
          documentRef,
          sourceUrl,
          maxTextCharacters
        ),

    facebook:
      () =>
        acquireFacebook(
          documentRef,
          sourceUrl,
          maxTextCharacters
        ),

    youtube:
      () =>
        acquireYouTube(
          documentRef,
          sourceUrl,
          maxTextCharacters,
          youtubeTranscript
        ),

    web:
      () =>
        acquireWeb(
          documentRef,
          sourceUrl,
          maxTextCharacters,
          articleExtraction
        ),
  }[
    platform
  ];


  const {
    payload,
    actor,
  } =
    adapter();


  const hasText =
    [
      "title",
      "body",
      "caption",
      "description",
      "transcript",
    ].some(
      (key) =>
        cleanText(
          payload[key] ||
          ""
        )
    );


  const hasMedia =
    Array.isArray(
      payload.media
    ) &&
    payload.media.length >
      0;


  if (
    !hasText &&
    !hasMedia
  ) {
    throw new Error(
      "No usable content was captured from the current page."
    );
  }


  let extractionMethod =
    "browser_dom";


  if (
    platform === "web" &&
    articleExtraction
  ) {
    extractionMethod =
      "browser_dom+article_extractor";
  }


  if (
    platform ===
      "youtube" &&
    cleanText(
      youtubeTranscript
        ?.transcript ||
      ""
    )
  ) {
    extractionMethod =
      "browser_dom+youtube_transcript";
  }


  return {
    version:
      BROWSER_CAPTURE_VERSION,

    source_url:
      sourceUrl,

    observed_at:
      timestamp,

    extraction_method:
      extractionMethod,

    payload,

    actor:
      hasActor(actor)
        ? actor
        : {},
  };
}
