export const ARTICLE_INTELLIGENCE_PUBLIC_VERSION =
  "article-intelligence-public-v1";


function clean(value) {
  return String(
    value ?? ""
  )
    .trim()
    .replace(/\s+/g, " ");
}


function count(value) {
  const numeric = Number(value);

  if (!Number.isFinite(numeric)) {
    return 0;
  }

  return Math.max(
    0,
    Math.trunc(numeric)
  );
}


function humanize(value) {
  const normalized = clean(value)
    .replaceAll("_", " ")
    .replaceAll("-", " ");

  if (!normalized) {
    return "Unknown";
  }

  return normalized.replace(
    /\b\w/g,
    (character) =>
      character.toUpperCase()
  );
}


export function normalizeArticleIntelligence(
  value
) {
  if (
    !value ||
    typeof value !== "object"
  ) {
    return null;
  }

  if (
    clean(value.version) !==
    ARTICLE_INTELLIGENCE_PUBLIC_VERSION
  ) {
    return null;
  }

  const status = clean(
    value.status
  ).toLowerCase();

  if (
    status !== "available" &&
    status !== "unavailable"
  ) {
    return null;
  }

  const corroborationStatus =
    clean(
      value.corroboration_status
    ).toLowerCase() ||
    "unknown";

  const independenceStatus =
    clean(
      value.independence_status
    ).toLowerCase() ||
    "unknown";

  return {
    status,

    label:
      clean(value.label) ||
      (
        status === "available"
          ? "Evidence intelligence"
          : "Evidence check unavailable"
      ),

    detail:
      clean(value.detail),

    candidateCount:
      count(value.candidate_count),

    verificationPairs:
      count(value.verification_pairs),

    corroborationStatus,

    corroborationLabel:
      humanize(
        corroborationStatus
      ),

    independenceStatus,

    independenceLabel:
      humanize(
        independenceStatus
      ),

    contested:
      Boolean(value.contested),

    provisional:
      value.provisional !== false,

    affectsMeritScore:
      value.affects_merit_score === true,
  };
}
