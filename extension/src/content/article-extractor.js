const PRIMARY_ARTICLE_SELECTORS = [
  "[itemprop='articleBody']",
  "[data-testid='article-body']",
  "[data-testid='Body']",
  "[data-module='ArticleBody']",
  ".article-body",
  ".article__body",
  ".article-content",
  ".article__content",
  ".Article__Content",
  ".entry-content",
  ".post-content",
  ".post__content",
  ".story-body",
  ".story__body",
  ".Story__Body",
  ".RichTextContainer",
];

const STRUCTURAL_ARTICLE_SELECTORS = [
  "article",
  "[role='article']",
  "main article",
  "[role='main'] article",
  "section article",
];

const FALLBACK_ARTICLE_SELECTORS = [
  "main",
  "[role='main']",
];

const NOISE_SELECTORS = [
  "script",
  "style",
  "noscript",
  "svg",
  "canvas",
  "iframe",
  "nav",
  "footer",
  "aside",
  "form",
  "button",
  "input",
  "textarea",
  "select",
  "figure",
  "figcaption",
  "[aria-hidden='true']",
  "[hidden]",
  "[role='navigation']",
  "[role='banner']",
  "[role='complementary']",
  "[role='dialog']",
  ".advertisement",
  ".advert",
  ".ads",
  ".ad",
  ".banner",
  ".social-share",
  ".share-tools",
  ".newsletter",
  ".related-content",
  ".recommended-content",
  ".comments",
  ".sidebar",
  ".widget",
  ".promo",
  ".sponsored",
];

const NOISE_TOKEN_PATTERN =
  /(?:^|[\s_-])(?:ad|ads|advert|advertisement|banner|betting|bookmaker|comments?|cookie|footer|latest|menu|newsletter|odds|promo|recommended|related|share|sidebar|social|sponsor|subscription|trending|widget)(?:$|[\s_-])/i;

const PROMOTIONAL_PATTERNS = [
  /\b(?:advertisement|advertising|sponsored|paid content)\b/i,
  /\b(?:publicidad|contenido patrocinado|patrocinado)\b/i,
  /\b(?:publicidade|conte?do patrocinado)\b/i,
  /\b(?:publicit?|contenu sponsoris?)\b/i,
  /\b(?:werbung|gesponsert)\b/i,
  /\b(?:pubblicit?|contenuto sponsorizzato)\b/i,

  /\b(?:register|sign up|subscribe|join now)\b/i,
  /\b(?:reg[i?]strate|suscr[i?]bete|inicia sesi[o?]n)\b/i,
  /\b(?:cadastre-se|inscreva-se)\b/i,
  /\b(?:inscrivez-vous|abonnez-vous)\b/i,

  /\b(?:bet365|sportsbook|bookmaker|betting odds|casino bonus)\b/i,
  /\b(?:apuestas?|cuotas?|juego seguro|bono de apuesta)\b/i,
  /\b(?:apostas?|cota??es|b?nus de aposta)\b/i,
  /\b(?:paris sportifs|cotes|bonus de pari)\b/i,
  /\b(?:scommesse|quote|bonus scommessa)\b/i,
  /\b(?:sportwetten|quoten|wettbonus)\b/i,
];

const BOILERPLATE_PATTERNS = [
  /\b(?:follow us|share this|read more|recommended for you)\b/i,
  /\b(?:s[i?]guenos|compartir|leer tambi[e?]n|te puede interesar)\b/i,
  /\b(?:siga-nos|compartilhar|leia tamb[e?]m)\b/i,
  /\b(?:suivez-nous|partager|lire aussi)\b/i,
  /\b(?:folgen sie uns|teilen|auch lesen)\b/i,
  /\b(?:seguici|condividi|leggi anche)\b/i,
];

function normalizeText(value) {
  return String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function getNodeText(node) {
  return normalizeText(
    node?.innerText ||
    node?.textContent ||
    ""
  );
}

function getLinkDensity(element, text) {
  if (!element || !text) return 1;

  const linkTextLength = Array.from(
    element.querySelectorAll("a")
  ).reduce(
    (total, link) =>
      total + getNodeText(link).length,
    0
  );

  return Math.min(
    1,
    linkTextLength /
      Math.max(1, text.length)
  );
}

function countMatches(text, pattern) {
  return (
    String(text || "").match(pattern) || []
  ).length;
}

function looksLikeFeedDump(text) {
  const dateHits = countMatches(
    text,
    /\b\d{1,2}\s+[A-Za-z?-?]{3,10}\s+\d{4}\b/gi
  );

  const timeHits = countMatches(
    text,
    /\b\d{1,2}:\d{2}\b/g
  );

  const pipeHits = countMatches(
    text,
    /\|/g
  );

  return (
    dateHits >= 2 ||
    timeHits >= 4 ||
    (
      timeHits >= 2 &&
      pipeHits >= 2
    )
  );
}

function looksPromotional(text) {
  const matches = PROMOTIONAL_PATTERNS
    .filter((pattern) =>
      pattern.test(text)
    )
    .length;

  return (
    matches >= 2 ||
    (
      matches >= 1 &&
      text.length <= 260
    )
  );
}

function looksLikeBoilerplate(text) {
  return (
    text.length <= 240 &&
    BOILERPLATE_PATTERNS.some(
      (pattern) => pattern.test(text)
    )
  );
}

function isUsefulContentBlock(
  node,
  text
) {
  if (!text) return false;

  const tagName =
    String(node.tagName || "")
      .toLowerCase();

  const minimumLength =
    tagName === "h2" ||
    tagName === "h3"
      ? 30
      : 45;

  if (text.length < minimumLength) {
    return false;
  }

  if (looksLikeFeedDump(text)) {
    return false;
  }

  if (looksPromotional(text)) {
    return false;
  }

  if (looksLikeBoilerplate(text)) {
    return false;
  }

  const linkDensity =
    getLinkDensity(node, text);

  if (
    linkDensity >= 0.65 &&
    text.length < 500
  ) {
    return false;
  }

  return true;
}

function cloneAndClean(element) {
  const clone =
    element.cloneNode(true);

  for (
    const selector
    of NOISE_SELECTORS
  ) {
    clone
      .querySelectorAll(selector)
      .forEach((node) =>
        node.remove()
      );
  }

  clone
    .querySelectorAll(
      "[class], [id]"
    )
    .forEach((node) => {
      const signature = [
        node.getAttribute("class"),
        node.getAttribute("id"),
      ]
        .filter(Boolean)
        .join(" ");

      if (
        NOISE_TOKEN_PATTERN.test(
          signature
        )
      ) {
        node.remove();
      }
    });

  return clone;
}

function collectContentBlocks(
  element
) {
  if (!element) return [];

  const clone =
    cloneAndClean(element);

  const blocks = [];
  const seen = new Set();

  const addBlock = (node) => {
    const text =
      getNodeText(node);

    if (
      !isUsefulContentBlock(
        node,
        text
      )
    ) {
      return;
    }

    const duplicateKey =
      text.toLowerCase();

    if (seen.has(duplicateKey)) {
      return;
    }

    seen.add(duplicateKey);
    blocks.push(text);
  };

  clone
    .querySelectorAll(
      "p, h2, h3, blockquote"
    )
    .forEach(addBlock);

  /*
   * Some sites render article text in
   * plain leaf divs instead of paragraphs.
   */
  if (blocks.length < 2) {
    clone
      .querySelectorAll("div")
      .forEach((node) => {
        if (
          node.querySelector(
            "p, div, section, article"
          )
        ) {
          return;
        }

        addBlock(node);
      });
  }

  return blocks;
}

function buildCandidate(
  element,
  selector,
  priorityBonus = 0
) {
  const blocks =
    collectContentBlocks(element);

  const text =
    normalizeText(
      blocks.join("\n\n")
    );

  if (
    text.length < 250 ||
    blocks.length < 2
  ) {
    return null;
  }

  const blockCount =
    blocks.length;

  const averageBlockLength =
    text.length / blockCount;

  const shortBlockCount =
    blocks.filter(
      (block) =>
        block.length < 80
    ).length;

  const longBlockCount =
    blocks.filter(
      (block) =>
        block.length >= 140
    ).length;

  const shortBlockRatio =
    shortBlockCount /
    Math.max(1, blockCount);

  const linkDensity =
    getLinkDensity(
      element,
      text
    );

  const tooManyBlocks =
    blockCount > 90;

  const heavilyFragmented =
    blockCount > 35 &&
    averageBlockLength < 95;

  const mostlyTinyBlocks =
    blockCount > 15 &&
    shortBlockRatio > 0.72;

  const linkHeavy =
    linkDensity > 0.55;

  const suspicious =
    tooManyBlocks ||
    heavilyFragmented ||
    mostlyTinyBlocks ||
    linkHeavy;

  const fragmentationPenalty =
    Math.max(
      0,
      blockCount - 35
    ) * 240;

  const score =
    priorityBonus +
    Math.min(text.length, 14000) +
    blockCount * 115 +
    longBlockCount * 170 +
    Math.min(
      averageBlockLength,
      260
    ) * 4 -
    shortBlockRatio * 2200 -
    linkDensity * 6500 -
    fragmentationPenalty -
    (
      suspicious
        ? 8500
        : 0
    );

  return {
    selector,
    element,
    blocks,
    text,
    score,
    suspicious,
    metrics: {
      blockCount,
      averageBlockLength:
        Math.round(
          averageBlockLength
        ),
      linkDensity:
        Number(
          linkDensity.toFixed(3)
        ),
      shortBlockRatio:
        Number(
          shortBlockRatio.toFixed(3)
        ),
    },
  };
}

function getArticleTitle() {
  const candidates = [
    document
      .querySelector(
        'meta[property="og:title"]'
      )
      ?.getAttribute("content"),

    document
      .querySelector(
        'meta[name="twitter:title"]'
      )
      ?.getAttribute("content"),

    document
      .querySelector("article h1")
      ?.textContent,

    document
      .querySelector("main h1")
      ?.textContent,

    document
      .querySelector("h1")
      ?.textContent,

    document.title,
  ];

  return (
    candidates
      .map(normalizeText)
      .find(Boolean) ||
    "Untitled sports article"
  );
}

function findTitleAnchoredCandidates() {
  const heading =
    document.querySelector(
      [
        "article h1",
        "[role='article'] h1",
        "main h1",
        "[role='main'] h1",
        "h1",
      ].join(", ")
    );

  if (!heading) return [];

  const candidates = [];

  let current =
    heading.parentElement;

  let previousCandidate = null;

  for (
    let depth = 0;
    current &&
    current !== document.body &&
    depth < 9;
    depth += 1
  ) {
    const candidate =
      buildCandidate(
        current,
        "title-anchored",
        Math.max(
          1200,
          4200 - depth * 350
        )
      );

    if (candidate) {
      if (
        previousCandidate &&
        candidate.metrics.blockCount >
          previousCandidate.metrics
            .blockCount * 2.2 &&
        candidate.text.length >
          previousCandidate.text.length *
            2.1
      ) {
        break;
      }

      candidates.push(candidate);
      previousCandidate = candidate;
    }

    if (
      current.matches(
        [
          ...PRIMARY_ARTICLE_SELECTORS,
          ...STRUCTURAL_ARTICLE_SELECTORS,
        ].join(", ")
      )
    ) {
      break;
    }

    current =
      current.parentElement;
  }

  return candidates;
}

function addSelectorCandidates(
  candidates,
  seenElements,
  selectors,
  priorityBonus
) {
  for (
    const selector
    of selectors
  ) {
    const elements =
      document.querySelectorAll(
        selector
      );

    for (
      const element
      of elements
    ) {
      if (
        !element ||
        seenElements.has(element)
      ) {
        continue;
      }

      seenElements.add(element);

      const candidate =
        buildCandidate(
          element,
          selector,
          priorityBonus
        );

      if (candidate) {
        candidates.push(
          candidate
        );
      }
    }
  }
}

function truncateBlocks(
  blocks,
  maximumCharacters
) {
  const selected = [];
  let usedCharacters = 0;

  for (
    const block
    of blocks
  ) {
    const separatorLength =
      selected.length ? 2 : 0;

    const available =
      maximumCharacters -
      usedCharacters -
      separatorLength;

    if (available <= 0) break;

    if (
      block.length <= available
    ) {
      selected.push(block);

      usedCharacters +=
        separatorLength +
        block.length;

      continue;
    }

    /*
     * Only include a partial final block
     * when enough useful room remains.
     */
    if (available >= 140) {
      let partial =
        block.slice(0, available);

      const finalBoundary =
        Math.max(
          partial.lastIndexOf(". "),
          partial.lastIndexOf("! "),
          partial.lastIndexOf("? "),
          partial.lastIndexOf("?"),
          partial.lastIndexOf("?"),
          partial.lastIndexOf("?")
        );

      if (
        finalBoundary >=
        available * 0.55
      ) {
        partial =
          partial.slice(
            0,
            finalBoundary + 1
          );
      } else {
        const lastSpace =
          partial.lastIndexOf(" ");

        if (
          lastSpace >=
          available * 0.7
        ) {
          partial =
            partial.slice(
              0,
              lastSpace
            );
        }
      }

      partial =
        partial.trim();

      if (partial.length >= 100) {
        selected.push(partial);
      }
    }

    break;
  }

  return {
    text: normalizeText(
      selected.join("\n\n")
    ),
    blockCount:
      selected.length,
  };
}

export function extractArticlePage({
  maxCharacters = 6000,
} = {}) {
  const candidates = [];
  const seenElements =
    new Set();

  for (
    const candidate
    of findTitleAnchoredCandidates()
  ) {
    if (
      seenElements.has(
        candidate.element
      )
    ) {
      continue;
    }

    seenElements.add(
      candidate.element
    );

    candidates.push(candidate);
  }

  addSelectorCandidates(
    candidates,
    seenElements,
    PRIMARY_ARTICLE_SELECTORS,
    5200
  );

  addSelectorCandidates(
    candidates,
    seenElements,
    STRUCTURAL_ARTICLE_SELECTORS,
    3000
  );

  /*
   * Broad main containers are considered
   * only after article-specific containers.
   */
  addSelectorCandidates(
    candidates,
    seenElements,
    FALLBACK_ARTICLE_SELECTORS,
    0
  );

  if (
    !candidates.length &&
    document.body
  ) {
    const bodyCandidate =
      buildCandidate(
        document.body,
        "body-fallback",
        -5000
      );

    if (bodyCandidate) {
      candidates.push(
        bodyCandidate
      );
    }
  }

  const cleanCandidates =
    candidates.filter(
      (candidate) =>
        !candidate.suspicious
    );

  const candidatePool =
    cleanCandidates.length
      ? cleanCandidates
      : candidates;

  candidatePool.sort(
    (left, right) =>
      right.score - left.score
  );

  const bestCandidate =
    candidatePool[0] || null;

  const safeLimit =
    Math.max(
      1000,
      Number(maxCharacters) ||
        6000
    );

  const truncated =
    truncateBlocks(
      bestCandidate?.blocks || [],
      safeLimit
    );

  return {
    title: getArticleTitle(),
    url: window.location.href,
    hostname:
      window.location.hostname,

    text: truncated.text,

    fullCharacterCount:
      bestCandidate?.text.length ||
      0,

    characterCount:
      truncated.text.length,

    paragraphCount:
      truncated.blockCount,

    selector:
      bestCandidate?.selector ||
      null,

    extractionMetrics:
      bestCandidate?.metrics ||
      null,

    candidateCount:
      candidates.length,
  };
}
