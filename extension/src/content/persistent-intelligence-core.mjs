const TRACKING_QUERY_PARAMETERS = new Set([
  "dclid",
  "fbclid",
  "gclid",
  "gbraid",
  "igshid",
  "mc_cid",
  "mc_eid",
  "msclkid",
  "ref_src",
  "s_cid",
  "vero_conv",
  "vero_id",
  "wbraid",
]);

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
  "youtu.be",
  "www.youtu.be",
  "youtube-nocookie.com",
  "www.youtube-nocookie.com",
]);

export const WATCHABLE_KINDS = Object.freeze([
  "entity",
  "story",
  "claim",
  "media",
]);

const HISTORY_PATH_SEGMENTS = Object.freeze({
  entity: "entities",
  story: "stories",
  claim: "claims",
  media: "media",
});

const POLICY_COPY = Object.freeze({
  verified_relationships_only:
    "Entity relationships shown here come from verified persisted relationships.",
  chronology_is_not_truth:
    "Chronology records when intelligence occurred; it is not a truth or credibility score.",
  relationships_are_persisted:
    "Story relationships shown here are persisted graph relationships, not temporary text matches.",
  evidence_quantity_is_not_probability:
    "More evidence records do not automatically mean a claim is more likely to be true.",
  dependencies_remain_distinct:
    "Repeated or dependent reporting remains distinct from independent corroboration.",
  article_merit_is_reporting_quality_not_truth:
    "Article Merit measures reporting and informational quality, not truth probability.",
  video_scores_are_not_combined:
    "Video Evidence Score, Logic Score and Verdict remain separate; there is no composite credibility score.",
  versions_are_not_assumed_comparable:
    "Analysis versions are not assumed to be directly comparable across time.",
});

const EVENT_DETAIL_FIELDS = Object.freeze([
  ["claim_text", "Claim"],
  ["canonical_name", "Entity"],
  ["participant_role", "Participant role"],
  ["verification_status", "Verification status"],
  ["relationship_type", "Relationship"],
  ["link_basis", "Link basis"],
  ["claim_summary", "Observation"],
  ["trigger_type", "Revision trigger"],
  ["field", "Field"],
  ["kind", "Transition"],
  ["mode", "Mode"],
  ["badge", "Article badge"],
  ["article_type", "Article type"],
  ["merit_score", "Merit · reporting quality"],
  ["evidence_score", "Video evidence score"],
  ["logic_score", "Video logic score"],
  ["verdict", "Video verdict"],
  ["analysis_version", "Analysis version"],
  ["scoring_version", "Scoring version"],
]);

function clean(value) {
  return String(value ?? "").trim();
}

function text(value) {
  return typeof value === "string"
    ? value.trim()
    : "";
}

function isTrackingQueryParameter(name) {
  const normalized = clean(name).toLowerCase();
  return (
    normalized.startsWith("utm_") ||
    TRACKING_QUERY_PARAMETERS.has(normalized)
  );
}

function youtubeVideoId(url) {
  const hostname = clean(
    url.hostname
  ).toLowerCase();

  const pathParts = url.pathname
    .split("/")
    .filter(Boolean);

  let candidate = "";

  if (
    hostname === "youtu.be" ||
    hostname === "www.youtu.be"
  ) {
    candidate = pathParts[0] || "";
  } else if (YOUTUBE_HOSTS.has(hostname)) {
    const first =
      clean(pathParts[0]).toLowerCase();

    if (
      ["embed", "live", "shorts", "v"].includes(first) &&
      pathParts.length >= 2
    ) {
      candidate = pathParts[1];
    } else if (
      !pathParts.length ||
      first === "watch"
    ) {
      candidate = clean(
        url.searchParams.get("v")
      );
    }
  }

  candidate = candidate.replace(
    /[^A-Za-z0-9_-]/g,
    ""
  );

  return /^[A-Za-z0-9_-]{6,20}$/.test(candidate)
    ? candidate
    : "";
}

export function normalizeCanonicalAnalysisUrl(value) {
  let rawUrl = clean(value);

  if (!rawUrl) {
    return "";
  }

  rawUrl = rawUrl.split("#", 1)[0].trim();

  try {
    if (/^\/\//.test(rawUrl)) {
      rawUrl = `https:${rawUrl}`;
    } else if (
      !/^[A-Za-z][A-Za-z0-9+.-]*:/.test(rawUrl) &&
      /^[A-Za-z0-9.-]+\//.test(rawUrl)
    ) {
      rawUrl = `https://${rawUrl}`;
    }

    const parsed = new URL(rawUrl);
    const scheme = parsed.protocol
      .replace(/:$/, "")
      .toLowerCase();
    const hostname = parsed.hostname
      .trim()
      .toLowerCase();

    if (!scheme || !hostname) {
      return rawUrl;
    }

    const videoId = youtubeVideoId(parsed);
    if (videoId) {
      return `https://youtube.com/watch?v=${videoId}`;
    }

    let authority = hostname;
    if (parsed.port) {
      authority = `${authority}:${parsed.port}`;
    }

    let path = parsed.pathname || "/";
    path = path.replace(/\/{2,}/g, "/");
    if (path !== "/") {
      path = path.replace(/\/+$/, "");
    }

    const retained = [];
    for (const [key, queryValue] of parsed.searchParams.entries()) {
      if (isTrackingQueryParameter(key)) {
        continue;
      }
      retained.push([key, queryValue]);
    }

    retained.sort((left, right) => {
      const leftKey = left[0].toLowerCase();
      const rightKey = right[0].toLowerCase();

      if (leftKey < rightKey) return -1;
      if (leftKey > rightKey) return 1;
      if (left[1] < right[1]) return -1;
      if (left[1] > right[1]) return 1;
      return 0;
    });

    const query = new URLSearchParams();
    for (const [key, queryValue] of retained) {
      query.append(key, queryValue);
    }

    const encoded = query.toString();
    return `${scheme}://${authority}${path}${
      encoded ? `?${encoded}` : ""
    }`;
  } catch {
    return rawUrl;
  }
}

export async function mediaItemIdForUrl(value) {
  const canonicalUrl =
    normalizeCanonicalAnalysisUrl(value);

  if (!canonicalUrl) {
    throw new Error("Media item URL is required.");
  }

  const payload = new TextEncoder().encode(
    `media|${canonicalUrl}`
  );

  const digest = await crypto.subtle.digest(
    "SHA-256",
    payload
  );

  return Array.from(
    new Uint8Array(digest),
    (byte) =>
      byte
        .toString(16)
        .padStart(2, "0")
  ).join("");
}

export function isWatchableKind(value) {
  return WATCHABLE_KINDS.includes(
    clean(value)
  );
}

export function historyPathFor(
  kind,
  id,
  {
    limit = 30,
    cursor = "",
  } = {}
) {
  if (!isWatchableKind(kind)) {
    throw new Error(
      "Unsupported Sportabase intelligence kind."
    );
  }

  const targetId = clean(id);
  if (!targetId) {
    throw new Error(
      "Sportabase intelligence ID is required."
    );
  }

  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (cursor) {
    params.set("cursor", cursor);
  }

  return (
    `/intelligence/${HISTORY_PATH_SEGMENTS[kind]}/` +
    `${encodeURIComponent(targetId)}/history?${params.toString()}`
  );
}

export function historyIdentity(kind, response) {
  if (kind === "entity") {
    const entity = response?.entity || {};
    return {
      kind,
      id: clean(entity.id),
      title:
        clean(entity.canonical_name) ||
        "Persisted entity",
      subtitle: [
        clean(entity.entity_type),
        clean(entity.sport_key),
      ].filter(Boolean).join(" · "),
      firstSeenAt: clean(entity.first_seen_at),
      lastSeenAt: clean(entity.last_seen_at),
      canonicalUrl: "",
    };
  }

  if (kind === "story") {
    const story = response?.story || {};
    return {
      kind,
      id: clean(story.id),
      title:
        clean(story.canonical_title) ||
        "Persisted story",
      subtitle:
        clean(story.status) ||
        "Persisted story",
      firstSeenAt: clean(story.first_seen_at),
      lastSeenAt: clean(story.last_seen_at),
      canonicalUrl: "",
    };
  }

  if (kind === "claim") {
    const claim = response?.claim || {};
    return {
      kind,
      id: clean(claim.id),
      title:
        clean(claim.canonical_text) ||
        "Persisted claim",
      subtitle: [
        clean(claim.claim_type),
        clean(claim.subject_key),
      ].filter(Boolean).join(" · "),
      firstSeenAt: clean(claim.first_seen_at),
      lastSeenAt: clean(claim.last_seen_at),
      canonicalUrl: "",
    };
  }

  const media = response?.media || {};
  return {
    kind: "media",
    id: clean(media.id),
    title:
      clean(media.title) ||
      "Persisted media",
    subtitle:
      clean(media.mode) ||
      "Persisted media",
    firstSeenAt: clean(media.first_seen_at),
    lastSeenAt: clean(media.last_seen_at),
    canonicalUrl: clean(media.canonical_url),
  };
}

export function historyRelations(kind, response) {
  const relations = [];

  const add = (relation) => {
    if (
      !relation?.id ||
      !isWatchableKind(relation.kind)
    ) {
      return;
    }

    if (
      relations.some(
        (item) =>
          item.kind === relation.kind &&
          item.id === relation.id
      )
    ) {
      return;
    }

    relations.push(relation);
  };

  if (kind === "media") {
    for (const event of response?.events || []) {
      const storyId = text(event?.story_id);
      if (storyId) {
        add({
          kind: "story",
          id: storyId,
          title: `Story ${storyId}`,
          subtitle: "Persisted media relationship",
        });
      }
    }
  }

  if (kind === "story") {
    for (const claim of response?.claims || []) {
      add({
        kind: "claim",
        id: clean(claim?.id),
        title:
          clean(claim?.canonical_text) ||
          `Claim ${clean(claim?.id)}`,
        subtitle: clean(claim?.claim_type),
      });
    }

    for (const media of response?.media || []) {
      add({
        kind: "media",
        id: clean(media?.id),
        title:
          clean(media?.title) ||
          `Media ${clean(media?.id)}`,
        subtitle: clean(media?.mode),
      });
    }
  }

  if (kind === "claim") {
    for (const story of response?.stories || []) {
      add({
        kind: "story",
        id: clean(story?.id),
        title:
          clean(story?.canonical_title) ||
          `Story ${clean(story?.id)}`,
        subtitle: clean(story?.status),
      });
    }

    for (
      const participant of
      response?.verified_participants || []
    ) {
      const entityId = clean(
        participant?.entity_id
      );
      add({
        kind: "entity",
        id: entityId,
        title:
          clean(participant?.canonical_name) ||
          `Entity ${entityId}`,
        subtitle: clean(participant?.entity_type),
      });
    }
  }

  if (kind === "entity") {
    for (const story of response?.stories || []) {
      add({
        kind: "story",
        id: clean(story?.id),
        title:
          clean(story?.canonical_title) ||
          `Story ${clean(story?.id)}`,
        subtitle: clean(story?.status),
      });
    }

    for (const media of response?.media || []) {
      add({
        kind: "media",
        id: clean(media?.id),
        title:
          clean(media?.title) ||
          `Media ${clean(media?.id)}`,
        subtitle: clean(media?.mode),
      });
    }

    for (const event of response?.events || []) {
      const claimId = text(event?.claim_id);
      if (claimId) {
        add({
          kind: "claim",
          id: claimId,
          title:
            text(event?.claim_text) ||
            `Claim ${claimId}`,
          subtitle: "Verified claim participation",
        });
      }
    }
  }

  return relations;
}

export function historyPolicyNotes(policy) {
  return Object.entries(
    policy && typeof policy === "object"
      ? policy
      : {}
  )
    .filter(([, enabled]) => Boolean(enabled))
    .map(([key]) =>
      POLICY_COPY[key] ||
      key.replace(/_/g, " ")
    );
}

export function historyEventDetails(event) {
  const details = [];

  for (const [field, label] of EVENT_DETAIL_FIELDS) {
    const value = event?.[field];

    if (
      typeof value === "string" ||
      typeof value === "number"
    ) {
      const rendered = clean(value);
      if (rendered) {
        details.push({ label, value: rendered });
      }
    }
  }

  if (Array.isArray(event?.reasons)) {
    const reasons = event.reasons
      .filter((value) =>
        typeof value === "string" &&
        value.trim()
      )
      .map((value) => value.trim())
      .join(" · ");

    if (reasons) {
      details.push({
        label: "Reasons",
        value: reasons,
      });
    }
  }

  return details;
}

export function filterAlertsForTarget(
  alerts,
  target
) {
  return (Array.isArray(alerts) ? alerts : [])
    .filter(
      (item) =>
        clean(item?.target_kind) ===
          clean(target?.kind) &&
        clean(item?.target_id) ===
          clean(target?.id)
    );
}
