export type AnalysisResultMode = 'article' | 'video';
export type AnalysisResultRailState = 'loading' | 'ready' | 'empty' | 'error';

export type AnalysisResultPalette = {
  ground: string;
  text: string;
  secondary: string;
  muted: string;
  teal: string;
  line: string;
};

export type AnalysisSourceItem = {
  label: string;
  primary?: boolean;
};

export type AnalysisEvidenceMetric = {
  label: string;
  value: string;
};

export type AnalysisEvidenceViewModel = {
  accent: string;
  status: string;
  detail?: string;
  metrics: AnalysisEvidenceMetric[];
  signal?: string;
};

export type AnalysisMeritViewModel = {
  score: number;
  band: string;
  colors: readonly [string, string];
  disclaimer: string;
};

export type AnalysisVideoMetric = {
  label: 'Evidence score' | 'Logic score' | 'Verdict';
  value: string;
  maximum?: string;
  note: string;
};

export type AnalysisRelatedReport = {
  id: string;
  source: string;
  headline: string;
  time: string;
  relationship: string;
  sourceType: string;
  url?: string;
};

export type AnalysisEvolutionItem = {
  id: string;
  label: string;
  detail: string;
  occurredAt?: string;
};

export type AnalysisDetailSection = {
  key: string;
  title: string;
  preview: string;
  paragraphs: string[];
};

export type AnalysisResultViewModel = {
  mode: AnalysisResultMode;
  contentType: string;
  claim: string;
  sourceItems: AnalysisSourceItem[];
  sourceUrl?: string;
  sourceLinkLabel?: string;
  merit?: AnalysisMeritViewModel;
  evidence?: AnalysisEvidenceViewModel;
  videoMetrics?: AnalysisVideoMetric[];
  summaryLabel: string;
  summary: string[];
  railState: AnalysisResultRailState;
  relatedReports: AnalysisRelatedReport[];
  evolution: AnalysisEvolutionItem[];
  details: AnalysisDetailSection[];
  onRetryContext?: () => void;
};

const darkMeritBands = [
  { key: 'critical', min: 0, colors: ['#D96B78', '#B94B50'] as const },
  { key: 'weak', min: 35, colors: ['#C87942', '#D2A84A'] as const },
  { key: 'developing', min: 50, colors: ['#557CC4', '#8995D0'] as const },
  { key: 'substantial', min: 65, colors: ['#8060B8', '#BC6FC1'] as const },
  { key: 'strong', min: 80, colors: ['#3C8E83', '#68A6AE'] as const },
  { key: 'high', min: 90, colors: ['#278E61', '#4DBB72'] as const },
] as const;

const lightMeritBands = [
  { key: 'critical', min: 0, colors: ['#BE123C', '#B91C1C'] as const },
  { key: 'weak', min: 35, colors: ['#C2410C', '#A16207'] as const },
  { key: 'developing', min: 50, colors: ['#1D4ED8', '#4338CA'] as const },
  { key: 'substantial', min: 65, colors: ['#6D28D9', '#A21CAF'] as const },
  { key: 'strong', min: 80, colors: ['#0F766E', '#0369A1'] as const },
  { key: 'high', min: 90, colors: ['#047857', '#008A46'] as const },
] as const;

export function getAnalysisMeritBand(score: number, light: boolean) {
  const bands = light ? lightMeritBands : darkMeritBands;
  return [...bands].reverse().find((band) => score >= band.min) ?? bands[0];
}
