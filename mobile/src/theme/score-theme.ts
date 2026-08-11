export type ScoreTheme = {
  min: number;
  max: number;
  name: string;
  start: string;
  end: string;
};

export const SCORE_THEMES: readonly ScoreTheme[] = [
  {
    min: 0,
    max: 34,
    name: 'critical',
    start: '#fb7185',
    end: '#dc2626',
  },
  {
    min: 35,
    max: 49,
    name: 'weak',
    start: '#ea580c',
    end: '#facc15',
  },
  {
    min: 50,
    max: 64,
    name: 'developing',
    start: '#2563eb',
    end: '#818cf8',
  },
  {
    min: 65,
    max: 79,
    name: 'substantial',
    start: '#6d28d9',
    end: '#d946ef',
  },
  {
    min: 80,
    max: 89,
    name: 'strong',
    start: '#0f766e',
    end: '#22d3ee',
  },
  {
    min: 90,
    max: 100,
    name: 'high',
    start: '#16a34a',
    end: '#bef264',
  },
] as const;

export function clampScore(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(100, Math.round(value)),
  );
}

export function getScoreTheme(
  value: number,
): ScoreTheme {
  const score = clampScore(value);

  return (
    SCORE_THEMES.find(
      (theme) =>
        score >= theme.min &&
        score <= theme.max,
    ) ?? SCORE_THEMES[0]
  );
}
