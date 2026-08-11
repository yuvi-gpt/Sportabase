import type {
  ArticleAnalyzeResponse,
} from './api';

const FIXTURE_SCORES = new Set([
  20,
  42,
  59,
  72,
  84,
  94,
]);

const FIXTURE_BADGES: Record<number, string> = {
  20: 'Very Low Signal',
  42: 'Limited Signal',
  59: 'Developing',
  72: 'Substantial Signal',
  84: 'Strong Evidence',
  94: 'High Credibility',
};

const FIXTURE_PATH =
  /^\/Sportabase\/test-fixtures\/score-(20|42|59|72|84|94)\.html$/;

export function getArticleGradientFixture({
  url,
  title,
  text,
}: {
  url: string;
  title: string;
  text: string;
}): ArticleAnalyzeResponse | null {
  let parsed: URL;

  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  if (
    parsed.protocol !== 'https:' ||
    parsed.hostname !== 'yuvi-gpt.github.io'
  ) {
    return null;
  }

  const pathMatch =
    parsed.pathname.match(FIXTURE_PATH);

  if (!pathMatch) {
    return null;
  }

  const score = Number(pathMatch[1]);

  if (!FIXTURE_SCORES.has(score)) {
    return null;
  }

  const expectedMarker =
    `SPORTABASE_TEST_SCORE=${score}`;

  if (!text.includes(expectedMarker)) {
    return null;
  }

  const badge =
    FIXTURE_BADGES[score] ||
    'Test Result';

  return {
    url,
    title,

    tldr: [
      'This is a static Sportabase gradient test result.',
      'The article was resolved normally, but AI analysis was intentionally bypassed.',
      `This fixture forces a merit score of ${score} so the native score theme can be inspected.`,
    ],

    merit_score: score,
    badge,

    article_type: 'transfer_rumor',
    article_type_label: 'Transfer Rumor',
    article_subtype: 'general',

    type_confidence: 0.98,

    type_signals: [
      'sportabase_gradient_fixture',
    ],

    reasons: [
      `Test fixture selected the ${score}/100 merit-score band.`,
      'No Gemini analysis was performed for this result.',
    ],

    score_components: {},
    score_calculation: {
      fixture: true,
      forced_score: score,
    },

    language: {
      code: 'en',
    },

    localized_article_type:
      'Transfer Rumor',

    localized_reasons: [
      `Test fixture selected the ${score}/100 merit-score band.`,
      'No Gemini analysis was performed for this result.',
    ],

    ui_labels: {},

    debug: {
      fixture: true,
      gemini_called: false,
      fixture_score: score,
    },
  };
}
