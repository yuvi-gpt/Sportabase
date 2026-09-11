import type { AnalysisResultContext, ArticleAnalyzeResponse, VideoAnalyzeResponse } from '../lib/api';
import { normalizeArticleIntelligence } from '../lib/article-intelligence';
import type { ProductAnalysisResult as AnalysisResult } from '../lib/product-analysis';
import { AnalysisResultView } from '../result-ui/AnalysisResultView.web';
import { getAnalysisMeritBand, type AnalysisEvidenceViewModel, type AnalysisResultViewModel } from '../result-ui/analysis-result-model';
import { useProductTheme } from '../theme/product-theme';
import { getProductHomePalette } from './ProductHomeTheme';

export type ProductResultContextPhase = 'loading' | 'ready' | 'empty' | 'error';

function cleanItems(items: string[] | undefined) {
  return Array.isArray(items) ? items.map((item) => item.trim()).filter(Boolean) : [];
}

function displayKey(value: string) {
  return value.trim().replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function sourceHost(value: string) {
  try { return new URL(value).hostname.replace(/^www\./, ''); } catch { return value; }
}

function formatContextTime(value: string) {
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return value;
  return new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' }).format(parsed);
}

function contextEvidence(context: AnalysisResultContext | null, accent: string): AnalysisEvidenceViewModel | null {
  if (!context?.evidence) return null;
  const evidence = context.evidence;
  return {
    accent,
    status: evidence.label || displayKey(evidence.status),
    detail: evidence.detail,
    signal: evidence.signal ? displayKey(evidence.signal) : undefined,
    metrics: [
      { label: 'Corroboration', value: evidence.corroboration_status },
      { label: 'Independence', value: evidence.independence_status },
      { label: 'Sources located', value: String(evidence.distinct_source_count) },
      { label: 'Verification pairs', value: String(evidence.verification_pairs) },
      { label: 'Merit impact', value: evidence.affects_merit_score ? 'Included' : 'Informational only' },
    ],
  };
}

function responseEvidence(data: ArticleAnalyzeResponse, accent: string): AnalysisEvidenceViewModel | null {
  const intelligence = normalizeArticleIntelligence(data.intelligence);
  if (!intelligence) return null;
  return {
    accent,
    status: intelligence.label,
    detail: intelligence.detail,
    signal: data.intelligence?.signal ? displayKey(data.intelligence.signal) : undefined,
    metrics: intelligence.status === 'available' ? [
      { label: 'Corroboration', value: intelligence.corroborationLabel },
      { label: 'Independence', value: intelligence.independenceLabel },
      { label: 'Candidates located', value: String(intelligence.candidateCount) },
      { label: 'Verification pairs', value: String(intelligence.verificationPairs) },
      { label: 'Merit impact', value: intelligence.affectsMeritScore ? 'Included' : 'Informational only' },
    ] : [],
  };
}

function evidenceModel(data: ArticleAnalyzeResponse, context: AnalysisResultContext | null, contextPhase: ProductResultContextPhase, accent: string, muted: string): AnalysisEvidenceViewModel {
  if (contextPhase === 'loading') return { accent, status: 'Checking intelligence…', detail: 'Loading persisted evidence and reporting relationships for this source.', metrics: [] };
  return contextEvidence(context, accent)
    || responseEvidence(data, accent)
    || { accent: muted, status: 'Not available', detail: 'No linked evidence intelligence is available in this analysis response.', metrics: [] };
}

function sourceItems(sourceUrl: string, context: AnalysisResultContext | null, extras: string[] = []) {
  const primary = context?.media?.source_name || context?.media?.source_domain || sourceHost(sourceUrl) || 'Analyzed source';
  return [
    { label: primary, primary: true },
    ...(context?.media?.source_type ? [{ label: displayKey(context.media.source_type) }] : []),
    ...(context?.media?.published_at ? [{ label: formatContextTime(context.media.published_at) }] : []),
    ...extras.filter(Boolean).map((label) => ({ label })),
  ];
}

function railModel(context: AnalysisResultContext | null, contextPhase: ProductResultContextPhase) {
  return {
    railState: contextPhase,
    relatedReports: context?.related_reports.map((item, index) => ({
      id: item.media_item_id || `${index}-${item.source_id || item.canonical_url || item.headline}`,
      source: item.source_name || sourceHost(item.canonical_url || ''),
      headline: item.headline,
      time: formatContextTime(item.observed_at),
      relationship: item.relationship,
      sourceType: displayKey(item.source_type),
      url: item.canonical_url || undefined,
    })) || [],
    evolution: context?.evolution.map((item) => ({ id: item.id, label: item.label, detail: item.detail, occurredAt: item.occurred_at })) || [],
  } as const;
}

function articleModel(data: ArticleAnalyzeResponse, sourceUrl: string, context: AnalysisResultContext | null, contextPhase: ProductResultContextPhase, dark: boolean): AnalysisResultViewModel {
  const palette = getProductHomePalette(dark);
  const score = Math.max(0, Math.min(100, Math.round(data.merit_score)));
  const band = getAnalysisMeritBand(score, !dark);
  const localizedReasons = cleanItems(data.localized_reasons);
  const reasons = localizedReasons.length ? localizedReasons : cleanItems(data.reasons);
  const scoreComponents = Object.entries(data.score_components || {}).map(([label, value]) => `${displayKey(label)}: ${value}`);
  const articleUrl = data.url?.trim() || sourceUrl;
  const extras = [
    data.article_subtype?.trim() ? displayKey(data.article_subtype) : '',
    Number.isFinite(data.type_confidence) ? `Type confidence ${Math.round(Math.max(0, Math.min(1, data.type_confidence)) * 100)}%` : '',
  ];
  return {
    mode: 'article',
    contentType: data.localized_article_type?.trim() || data.article_type_label?.trim() || displayKey(data.article_type || 'Article analysis'),
    claim: data.title,
    sourceItems: sourceItems(articleUrl, context, extras),
    sourceUrl: articleUrl,
    sourceLinkLabel: 'View analyzed source',
    merit: { score, band: band.key, colors: band.colors, disclaimer: 'Informational value, not truth probability.' },
    evidence: evidenceModel(data, context, contextPhase, palette.lime, palette.muted),
    summaryLabel: 'Summary',
    summary: cleanItems(data.tldr),
    ...railModel(context, contextPhase),
    details: [
      { key: 'merit', title: 'Why this Merit', preview: reasons[0] || 'No additional Merit reasons are available.', paragraphs: reasons.length ? reasons : ['No additional Merit reasons are available in this analysis response.'] },
      { key: 'evidence', title: 'Score components', preview: scoreComponents[0] || 'No score component detail is available.', paragraphs: scoreComponents.length ? scoreComponents : ['No score component detail is available in this analysis response.'] },
    ],
  };
}

function videoModel(data: VideoAnalyzeResponse, sourceUrl: string, context: AnalysisResultContext | null, contextPhase: ProductResultContextPhase): AnalysisResultViewModel {
  return {
    mode: 'video',
    contentType: data.localized_content_type?.trim() || data.content_type?.trim() || 'Video analysis',
    claim: data.claim || 'Video analysis',
    sourceItems: sourceItems(sourceUrl, context),
    sourceUrl,
    sourceLinkLabel: 'View analyzed source',
    videoMetrics: [
      { label: 'Evidence score', value: String(data.evidence_score), maximum: '/100', note: 'Support visible in the analyzed transcript.' },
      { label: 'Logic score', value: String(data.logic_score), maximum: '/100', note: 'Internal reasoning quality in the analyzed transcript.' },
      { label: 'Verdict', value: data.localized_verdict?.trim() || data.verdict, note: 'A separate classification, not a composite credibility score.' },
    ],
    summaryLabel: 'Evidence used',
    summary: cleanItems(data.evidence_used),
    ...railModel(context, contextPhase),
    details: [
      { key: 'logic', title: 'Logic check', preview: data.logic_check || 'No logic detail is available.', paragraphs: [data.logic_check || 'No logic detail is available in this analysis response.'] },
      { key: 'hype', title: 'Hype check', preview: data.hype_check || 'No hype detail is available.', paragraphs: [data.hype_check || 'No hype detail is available in this analysis response.'] },
    ],
  };
}

export function ProductAnalysisResult({ context, contextPhase, mobile, onRetryContext, result, sourceUrl }: { context: AnalysisResultContext | null; contextPhase: ProductResultContextPhase; mobile: boolean; onRetryContext: () => void; result: AnalysisResult; sourceUrl: string }) {
  const { dark, reduceMotion } = useProductTheme();
  const palette = getProductHomePalette(dark);
  const model = result.kind === 'article'
    ? articleModel(result.data, sourceUrl, context, contextPhase, dark)
    : videoModel(result.data, sourceUrl, context, contextPhase);
  return <AnalysisResultView
    mobile={mobile}
    model={{ ...model, onRetryContext }}
    palette={palette}
    reduceMotion={reduceMotion}
  />;
}
