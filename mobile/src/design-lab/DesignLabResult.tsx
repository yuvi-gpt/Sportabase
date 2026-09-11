import { AnalysisResultView } from '../result-ui/AnalysisResultView.web';
import type { AnalysisResultViewModel } from '../result-ui/analysis-result-model';
import { DesignLabHeader } from './DesignLabHeader';
import { getEvidenceTone, getMeritBand } from './design-lab-theme';
import { useDesignLabTheme } from './DesignLabThemeContext';
import type { DetailKey, MockResult } from './mock-results';

const fixtureUrl = (file: string) => `http://localhost:8082/design-lab-fixtures/${file}`;

function toViewModel(result: MockResult, theme: 'dark' | 'light'): AnalysisResultViewModel {
  const band = getMeritBand(result.merit, theme);
  const tone = getEvidenceTone(result.tone, theme);
  return {
    mode: 'article',
    contentType: result.contentType,
    claim: result.claim,
    sourceItems: [result.source.publisher, result.source.platform, result.source.sport, result.source.subject, result.source.published].map((label, index) => ({ label, primary: index === 0 })),
    sourceUrl: fixtureUrl(result.fixtureFile),
    sourceLinkLabel: result.source.linkLabel,
    merit: { score: result.merit, band: band.key, colors: band.colors, disclaimer: 'Informational value, not truth probability.' },
    evidence: {
      accent: tone.accent,
      status: result.evidenceStatus,
      metrics: [
        { label: 'Corroboration', value: result.corroboration },
        { label: 'Independence', value: result.independence },
        { label: 'Sources located', value: String(result.sources) },
        { label: 'Verification pairs', value: String(result.verificationPairs) },
        { label: 'Merit impact', value: result.meritImpact },
      ],
    },
    summaryLabel: 'Summary',
    summary: [...result.summary],
    railState: 'ready',
    relatedReports: result.related.map((item, index) => ({ id: `${index}-${item.source}-${item.headline}`, source: item.source, headline: item.headline, time: item.time, relationship: item.relationship, sourceType: item.sourceType, url: fixtureUrl(item.fixtureFile) })),
    evolution: result.evolution.map(([label, detail], index) => ({ id: `${index}-${label}`, label, detail })),
    details: (['merit', 'evidence'] as DetailKey[]).map((key) => ({ key, ...result.details[key], paragraphs: [...result.details[key].paragraphs] })),
  };
}

export function DesignLabResult({ result, mobile, onHome, onSettled, showHeader = true }: { result: MockResult; mobile: boolean; onHome: () => void; onSettled?: () => void; showHeader?: boolean }) {
  const { palette, theme } = useDesignLabTheme();
  return <AnalysisResultView
    header={showHeader ? <DesignLabHeader mobile={mobile} onHome={onHome} onAnother={onHome} showAnother /> : undefined}
    mobile={mobile}
    model={toViewModel(result, theme)}
    onSettled={onSettled}
    palette={palette}
  />;
}
