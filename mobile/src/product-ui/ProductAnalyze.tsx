import { useCallback, useMemo, useState } from 'react';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

import { type ArticleAnalyzeResponse, type VideoAnalyzeResponse } from '../lib/api';
import { useAccount } from '../lib/account-context';
import { runProductAnalysis, type ProductAnalysisResult as AnalysisResult } from '../lib/product-analysis';
import { useProductTheme } from '../theme/product-theme';
import { useProductHomeControls } from './ProductShellContext';
import { ProductButton, ProductMetric, ProductPage, ProductPageHeader, ProductSection, ProductStatus, ProductSurface, ProductTextField } from './ProductPrimitives';
import { productFonts, productPalette } from './tokens';

type Phase = 'idle' | 'resolving' | 'analyzing' | 'result';

function displayKey(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ArticleResult({ data }: { data: ArticleAnalyzeResponse }) {
  const { colors, scale } = useProductTheme();
  const reasons = data.localized_reasons?.length ? data.localized_reasons : data.reasons;
  return <View style={styles.resultStack} testID="article-analysis-result">
    <ProductPageHeader label={data.article_type_label || data.article_type || 'Article analysis'} title={data.title} description="Informational value, not truth probability." aside={<ProductMetric label="Article Merit Score" value={`${data.merit_score}/100`} detail={data.badge} />} />
    <ProductSection title="What the reporting says" description="A concise rendering of the analyzed article—not an independent claim of truth.">
      <ProductSurface style={styles.listSurface}>{data.tldr.map((item, index) => <View key={`${item}-${index}`} style={styles.bulletRow}><Text style={[styles.bulletIndex, { color: colors.accent }]}>0{index + 1}</Text><Text style={[styles.body, { color: colors.text, fontSize: 17 * scale, lineHeight: 25 * scale }]}>{item}</Text></View>)}</ProductSurface>
    </ProductSection>
    {reasons.length ? <ProductSection title="Why it earned this Merit" description="Reporting quality and evidential support determine Article Merit.">
      <View>{reasons.map((reason, index) => <ProductSurface key={`${reason}-${index}`} style={styles.reason}><Text style={[styles.reasonNumber, { color: colors.teal }]}>0{index + 1}</Text><Text style={[styles.body, { color: colors.textMuted, fontSize: 16 * scale, lineHeight: 23 * scale }]}>{reason}</Text></ProductSurface>)}</View>
    </ProductSection> : null}
    {Object.keys(data.score_components ?? {}).length ? <ProductSection title="Score components" description="Inputs to reporting merit—not probabilities or credibility ratings."><View style={styles.metrics}>{Object.entries(data.score_components).map(([key, value]) => <ProductMetric key={key} label={displayKey(key)} value={String(value)} />)}</View></ProductSection> : null}
    {data.intelligence ? <ProductSection title="Signal Resolution" description="Depth scan of linked intelligence supplied by Sportabase."><ProductSurface elevated style={styles.intelligence}><Text style={[styles.signalLabel, { color: colors.accent }]}>{data.intelligence.label}</Text><Text style={[styles.body, { color: colors.text, fontSize: 18 * scale, lineHeight: 25 * scale }]}>{data.intelligence.detail}</Text><Text style={[styles.body, { color: colors.textMuted, fontSize: 15 * scale, lineHeight: 22 * scale }]}>{data.intelligence.signal}</Text><View style={styles.intelligenceMeta}><Text style={[styles.meta, { color: colors.textMuted }]}>Corroboration: {displayKey(data.intelligence.corroboration_status)}</Text><Text style={[styles.meta, { color: colors.textMuted }]}>Independence: {displayKey(data.intelligence.independence_status)}</Text></View></ProductSurface></ProductSection> : null}
  </View>;
}

function VideoResult({ data }: { data: VideoAnalyzeResponse }) {
  const { colors, scale } = useProductTheme();
  return <View style={styles.resultStack} testID="video-analysis-result">
    <ProductPageHeader label={data.localized_content_type || data.content_type || 'Video analysis'} title={data.claim || 'Video analysis'} description="Evidence, logic, and verdict remain separate dimensions." />
    <View style={styles.metrics}><ProductMetric label="Evidence Score" value={`${data.evidence_score}/100`} detail="Support visible in the analyzed transcript." /><ProductMetric label="Logic Score" value={`${data.logic_score}/100`} detail="Internal reasoning quality in the analyzed transcript." /><ProductMetric label="Verdict" value={data.localized_verdict || data.verdict} detail="A separate classification—not a composite credibility score." /></View>
    {data.evidence_used.length ? <ProductSection title="Evidence used"><ProductSurface style={styles.listSurface}>{data.evidence_used.map((item, index) => <View key={`${item}-${index}`} style={styles.bulletRow}><Text style={[styles.bulletIndex, { color: colors.accent }]}>0{index + 1}</Text><Text style={[styles.body, { color: colors.text, fontSize: 16 * scale, lineHeight: 23 * scale }]}>{item}</Text></View>)}</ProductSurface></ProductSection> : null}
    <ProductSection title="Reasoning review"><View style={styles.twoColumn}><ProductSurface style={styles.column}><Text style={[styles.signalLabel, { color: colors.teal }]}>Logic check</Text><Text style={[styles.body, { color: colors.text, fontSize: 16 * scale, lineHeight: 23 * scale }]}>{data.logic_check}</Text></ProductSurface><ProductSurface style={styles.column}><Text style={[styles.signalLabel, { color: colors.teal }]}>Hype check</Text><Text style={[styles.body, { color: colors.text, fontSize: 16 * scale, lineHeight: 23 * scale }]}>{data.hype_check}</Text></ProductSurface></View></ProductSection>
  </View>;
}

export function ProductAnalyze() {
  const { colors, scale } = useProductTheme();
  const account = useAccount();
  const { width } = useWindowDimensions();
  const [url, setUrl] = useState(() => {
    if (typeof window === 'undefined') return '';
    const pending = window.sessionStorage.getItem('sportabase:pending-analysis-url') ?? '';
    window.sessionStorage.removeItem('sportabase:pending-analysis-url');
    return pending;
  });
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const reset = useCallback(() => { setUrl(''); setError(''); setResult(null); setPhase('idle'); }, []);
  useProductHomeControls(useMemo(() => ({ onHome: reset, onAnother: reset, showAnother: phase === 'result' }), [phase, reset]));

  const submit = useCallback(async () => {
    if (phase === 'resolving' || phase === 'analyzing') return;
    setError(''); setResult(null);
    try {
      if (!account.ready) throw new Error('Sportabase is still checking your account. Try again in a moment.');
      if (!account.signedIn) {
        if (typeof window !== 'undefined') window.sessionStorage.setItem('sportabase:pending-analysis-url', url.trim());
        await account.signIn(false, '/');
        return;
      }
      setPhase('resolving');
      const analysis = await runProductAnalysis(url, undefined, () => setPhase('analyzing'));
      setResult(analysis);
      setPhase('result');
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Sportabase could not analyze this URL.');
      setPhase('idle');
    }
  }, [account, phase, url]);

  const busy = phase === 'resolving' || phase === 'analyzing';
  return <ProductPage width="wide" watermark testID="analyze-page">
    {phase !== 'result' || !result ? <View style={[styles.hero, { minHeight: width < 700 ? 510 : 600, paddingTop: width < 700 ? 32 : 76 }]}>
      <View style={styles.heroCopy}><Text style={[styles.heroLabel, { color: colors.teal }]}>SPORTS INTELLIGENCE</Text><Text accessibilityRole="header" style={[styles.heroTitle, { color: colors.text, fontSize: (width < 700 ? 43 : 68) * scale, lineHeight: (width < 700 ? 47 : 70) * scale }]}>Know what backs the story.</Text><Text style={[styles.heroBody, { color: colors.textMuted, fontSize: 18 * scale, lineHeight: 27 * scale }]}>Paste a sports article or YouTube video. Sportabase separates what is claimed, what evidence is present, and how the reporting or reasoning holds up.</Text></View>
      <View style={styles.analyzeForm}><ProductTextField nativeID="analysis-url" label="Article or YouTube URL" value={url} onChangeText={setUrl} onSubmitEditing={() => void submit()} placeholder="https://…" autoCapitalize="none" autoComplete="off" autoCorrect={false} inputMode="url" keyboardType="url" editable={!busy} error={error} /><View style={styles.analyzeAction}><LinearGradient colors={[productPalette.cyan, productPalette.teal, productPalette.lime]} end={{ x: 1, y: 0.5 }} start={{ x: 0, y: 0.5 }} style={StyleSheet.absoluteFill} /><ProductButton label={busy ? 'Analyzing…' : 'Analyze'} onPress={() => void submit()} variant="primary" disabled={busy || !url.trim()} testID="analyze-submit" /></View></View>
      {busy ? <ProductStatus loading title={phase === 'resolving' ? 'Resolving content' : 'Running the depth scan'} detail={phase === 'resolving' ? 'Sportabase is extracting the article or transcript.' : 'Assessing evidence, informational merit, and reasoning without collapsing distinct signals.'} /> : null}
      {!busy && !error ? <View style={styles.promise}><Text style={[styles.heroLabel, { color: colors.accent }]}>CLEAR BOUNDARIES</Text><Text style={[styles.promiseTitle, { color: colors.text }]}>Evidence-first, without invented certainty.</Text><Text style={[styles.body, { color: colors.textMuted, fontSize: 15 * scale, lineHeight: 22 * scale }]}>Article Merit measures reporting quality and evidential support. Video analysis keeps Evidence Score, Logic Score, and Verdict separate.</Text></View> : null}
    </View> : <><ArticleOrVideo result={result} /><View style={styles.finalAction}><ProductButton label="Analyze another" onPress={reset} variant="primary" /></View></>}
  </ProductPage>;
}

function ArticleOrVideo({ result }: { result: AnalysisResult }) { return result.kind === 'article' ? <ArticleResult data={result.data} /> : <VideoResult data={result.data} />; }

const styles = StyleSheet.create({
  hero: { justifyContent: 'center', maxWidth: 930 }, heroCopy: { gap: 16 }, heroLabel: { fontFamily: productFonts.label, fontSize: 13, letterSpacing: 1.6 }, heroTitle: { fontFamily: productFonts.display, letterSpacing: -1.5, maxWidth: 850 }, heroBody: { fontFamily: productFonts.body, maxWidth: 760 },
  analyzeForm: { alignItems: 'flex-end', flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 32, maxWidth: 900 }, analyzeAction: { borderRadius: 8, minWidth: 158, overflow: 'hidden' },
  promise: { borderTopColor: productPalette.line, borderTopWidth: 1, gap: 8, marginTop: 54, maxWidth: 690, paddingTop: 22 }, promiseTitle: { fontFamily: productFonts.display, fontSize: 25 },
  resultStack: { gap: 42 }, listSurface: { gap: 0, paddingVertical: 6 }, bulletRow: { alignItems: 'flex-start', flexDirection: 'row', gap: 16, paddingVertical: 14 }, bulletIndex: { fontFamily: productFonts.label, fontSize: 12, letterSpacing: 1 }, body: { flexShrink: 1, fontFamily: productFonts.body },
  reason: { alignItems: 'flex-start', borderLeftWidth: 0, borderRightWidth: 0, borderTopWidth: 0, flexDirection: 'row', gap: 16 }, reasonNumber: { fontFamily: productFonts.label, fontSize: 12, letterSpacing: 1 }, metrics: { flexDirection: 'row', flexWrap: 'wrap', gap: 24 }, intelligence: { gap: 12 }, signalLabel: { fontFamily: productFonts.label, fontSize: 13, letterSpacing: 1.2, textTransform: 'uppercase' }, intelligenceMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 18 }, meta: { fontFamily: productFonts.body, fontSize: 13 }, twoColumn: { flexDirection: 'row', flexWrap: 'wrap', gap: 16 }, column: { flex: 1, gap: 12, minWidth: 260 }, finalAction: { alignItems: 'flex-start' },
});
