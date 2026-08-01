const ARTICLE_SELECTORS = [
  "article",
  "main article",
  "[role='main'] article",
  "main",
  "section article",
  "div[data-testid='Body']",
  "div[data-testid='article-body']",
  ".Story__Body",
  ".story__body",
  ".article-body",
  ".article__body",
  ".RichTextContainer",
  ".Article__Content",
  ".article__content",
  "[data-module='ArticleBody']",
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
  "[aria-hidden='true']",
  "[hidden]",
  "[role='navigation']",
  "[role='banner']",
  "[role='complementary']",
  ".advertisement",
  ".advert",
  ".ads",
  ".ad",
  ".social-share",
  ".share-tools",
  ".newsletter",
  ".related-content",
  ".recommended-content",
  ".comments",
];

function normalizeText(value) {
  return String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/[ \t]+/g, " ")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function extractTextFromElement(element) {
  if (!element) return "";

  const clone = element.cloneNode(true);

  for (const selector of NOISE_SELECTORS) {
    clone
      .querySelectorAll(selector)
      .forEach((node) => node.remove());
  }

  const paragraphs = Array.from(
    clone.querySelectorAll(
      "p, h2, h3, blockquote, li"
    )
  )
    .map((node) =>
      normalizeText(node.innerText || node.textContent)
    )
    .filter((text) => text.length >= 25);

  if (paragraphs.length >= 3) {
    return normalizeText(
      paragraphs.join("\n\n")
    );
  }

  return normalizeText(
    clone.innerText || clone.textContent
  );
}

function scoreCandidate(element, text) {
  if (!text) return -Infinity;

  const paragraphCount =
    element.querySelectorAll("p").length;

  const headingCount =
    element.querySelectorAll("h1, h2, h3").length;

  const linkTextLength = Array.from(
    element.querySelectorAll("a")
  ).reduce(
    (total, link) =>
      total +
      normalizeText(
        link.innerText || link.textContent
      ).length,
    0
  );

  const linkDensity =
    text.length > 0
      ? linkTextLength / text.length
      : 1;

  return (
    text.length +
    paragraphCount * 140 +
    headingCount * 45 -
    linkDensity * 1200
  );
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

    document.querySelector("h1")
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

export function extractArticlePage({
  maxCharacters = 6000,
} = {}) {
  const candidates = [];
  const seenElements = new Set();

  for (const selector of ARTICLE_SELECTORS) {
    const elements =
      document.querySelectorAll(selector);

    for (const element of elements) {
      if (
        !element ||
        seenElements.has(element)
      ) {
        continue;
      }

      seenElements.add(element);

      const text =
        extractTextFromElement(element);

      if (text.length < 200) continue;

      candidates.push({
        selector,
        element,
        text,
        score: scoreCandidate(
          element,
          text
        ),
      });
    }
  }

  if (!candidates.length && document.body) {
    const fallbackText =
      extractTextFromElement(document.body);

    if (fallbackText.length >= 200) {
      candidates.push({
        selector: "body",
        element: document.body,
        text: fallbackText,
        score: scoreCandidate(
          document.body,
          fallbackText
        ),
      });
    }
  }

  candidates.sort(
    (left, right) =>
      right.score - left.score
  );

  const bestCandidate =
    candidates[0] || null;

  const fullText =
    bestCandidate?.text || "";

  const safeLimit = Math.max(
    1000,
    Number(maxCharacters) || 6000
  );

  const text = fullText
    .slice(0, safeLimit)
    .trim();

  return {
    title: getArticleTitle(),
    url: window.location.href,
    hostname: window.location.hostname,
    text,
    fullCharacterCount:
      fullText.length,
    characterCount: text.length,
    paragraphCount:
      text
        ? text.split(/\n{2,}/).length
        : 0,
    selector:
      bestCandidate?.selector || null,
  };
}
