import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'expo-router';
import { Animated, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions } from 'react-native';

import { accountRequest } from '../lib/account-api';
import { getHomepageStorylines, type HomepageStoryline, listWatches } from '../lib/api';
import { useAccount } from '../lib/account-context';
import { runProductAnalysis, type ProductAnalysisPhase, type ProductAnalysisResult as AnalysisResult } from '../lib/product-analysis';
import { useAnalysisResultContext } from '../lib/use-analysis-result-context';
import { AnalysisResultGeometry, type AnalysisResultGeometryVariant } from '../result-ui/AnalysisResultGeometry.web';
import { useProductTheme } from '../theme/product-theme';
import { ProductAnalysisResult } from './ProductAnalysisResult.web';
import { formatProductDate } from './ProductPrimitives';
import { ProductAnalysisLoader } from './ProductAnalysisLoader.web';
import { useProductHomeControls } from './ProductShellContext';
import { getProductHomePalette, type ProductHomePalette } from './ProductHomeTheme';
import { ProductWatermark } from './ProductWatermark';
import { productFonts } from './tokens';

type Phase = 'idle' | ProductAnalysisPhase | 'result';
type SportKey = 'football' | 'f1' | 'tennis' | 'cricket' | 'basketball' | 'nfl';
type ActivityItem = { id: string; kind: string; title: string; url: string; created_at: number; platform: string };
type AccountSummary = { recentActivity: ActivityItem[]; watchCount: number };
type AccountSummaryPhase = 'idle' | 'loading' | 'ready' | 'error';
type StorylinePhase = 'loading' | 'ready' | 'error';

const SPORTS: { label: string; sportKey: SportKey }[] = [
  { label: 'Football', sportKey: 'football' },
  { label: 'Formula 1', sportKey: 'f1' },
  { label: 'Tennis', sportKey: 'tennis' },
  { label: 'Cricket', sportKey: 'cricket' },
  { label: 'Basketball', sportKey: 'basketball' },
  { label: 'NFL', sportKey: 'nfl' },
];

function displayKey(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function accountSummaryCopy(accountReady: boolean, signedIn: boolean, phase: AccountSummaryPhase, summary: AccountSummary | null) {
  if (!accountReady) return 'Checking your account for saved analyses and current watches.';
  if (!signedIn) return 'Sign in to see your saved analyses and current watches. Nothing is inferred while you are signed out.';
  if (phase === 'loading') return 'Loading your saved activity and current watches.';
  if (phase === 'error') return 'Your account summary is temporarily unavailable. Activity and Watches remain available from the navigation.';
  if (!summary) return 'Your account is ready. Saved analyses and watches will appear here when available.';
  const latest = summary.recentActivity[0];
  if (!latest && summary.watchCount === 0) return 'No saved analyses or watches yet. Completed analyses and watchable intelligence will appear here.';
  const watches = `${summary.watchCount} current ${summary.watchCount === 1 ? 'watch' : 'watches'}.`;
  return latest ? `${watches} Latest saved analysis: ${latest.title || 'Untitled analysis'}.` : `${watches} No saved analysis is available in recent activity.`;
}

export function ProductAnalyze() {
  const router = useRouter();
  const { dark, reduceMotion } = useProductTheme();
  const account = useAccount();
  const { width } = useWindowDimensions();
  const mobile = width < 700;
  const palette = getProductHomePalette(dark);
  const styles = useMemo(() => createStyles(palette, dark), [dark, palette]);
  const press = useRef(new Animated.Value(1)).current;
  const [url, setUrl] = useState(() => {
    if (typeof window === 'undefined') return '';
    const pending = window.sessionStorage.getItem('sportabase:pending-analysis-url') ?? '';
    window.sessionStorage.removeItem('sportabase:pending-analysis-url');
    return pending;
  });
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [sportKey, setSportKey] = useState<SportKey>('football');
  const [storylines, setStorylines] = useState<HomepageStoryline[]>([]);
  const [storylinePhase, setStorylinePhase] = useState<StorylinePhase>('loading');
  const [storylineRequest, setStorylineRequest] = useState(0);
  const [accountSummary, setAccountSummary] = useState<AccountSummary | null>(null);
  const [accountSummaryPhase, setAccountSummaryPhase] = useState<AccountSummaryPhase>('idle');
  const accountId = account.state?.account.id ?? '';
  const resultContext = useAnalysisResultContext(url, phase === 'result' && result !== null);

  const reset = useCallback(() => { setUrl(''); setError(''); setResult(null); setPhase('idle'); }, []);
  useProductHomeControls(useMemo(() => ({ onHome: reset, onAnother: reset, showAnother: phase === 'result' }), [phase, reset]));

  useEffect(() => {
    let active = true;
    setStorylinePhase('loading');
    void getHomepageStorylines({ limit: 100 }).then((response) => {
      if (!active) return;
      setStorylines(response.storylines);
      setStorylinePhase('ready');
    }).catch(() => {
      if (!active) return;
      setStorylines([]);
      setStorylinePhase('error');
    });
    return () => { active = false; };
  }, [storylineRequest]);

  useEffect(() => {
    if (!account.ready || !account.signedIn) {
      setAccountSummary(null);
      setAccountSummaryPhase('idle');
      return;
    }
    if (!accountId) {
      setAccountSummary(null);
      setAccountSummaryPhase('error');
      return;
    }
    let active = true;
    setAccountSummaryPhase('loading');
    void Promise.all([
      listWatches(),
      accountRequest<{ items: ActivityItem[]; next: { before: number; cursor: string } | null }>('/account/activity?limit=3'),
    ]).then(([watches, activity]) => {
      if (!active) return;
      setAccountSummary({ recentActivity: activity.items, watchCount: watches.count });
      setAccountSummaryPhase('ready');
    }).catch(() => {
      if (!active) return;
      setAccountSummary(null);
      setAccountSummaryPhase('error');
    });
    return () => { active = false; };
  }, [account.ready, account.signedIn, accountId]);

  const runAnalysis = useCallback(async () => {
    if (phase === 'resolving' || phase === 'analyzing') return;
    setError('');
    setResult(null);
    try {
      if (!account.ready) throw new Error('Sportabase is still checking your account. Try again in a moment.');
      if (!account.signedIn) {
        window.sessionStorage.setItem('sportabase:pending-analysis-url', url.trim());
        await account.signIn(false, '/');
        return;
      }
      setPhase('resolving');
      const analysis = await runProductAnalysis(url, undefined, setPhase);
      const savedActivity = analysis.data.saved_activity;
      if (savedActivity?.restorable) {
        router.replace({ pathname: '/analysis', params: { activity: savedActivity.id } });
        return;
      }
      setResult(analysis);
      setPhase('result');
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : 'Sportabase could not analyze this URL.');
      setPhase('idle');
    }
  }, [account, phase, router, url]);

  const busy = phase === 'resolving' || phase === 'analyzing';
  const disabled = busy || !url.trim();
  const submit = useCallback(() => {
    if (disabled) return;
    Animated.sequence([
      Animated.timing(press, { toValue: 0.98, duration: 100, useNativeDriver: false }),
      Animated.timing(press, { toValue: 1, duration: 90, useNativeDriver: false }),
    ]).start(() => { void runAnalysis(); });
  }, [disabled, press, runAnalysis]);

  const pageGutter = width >= 1200 ? 68 : width >= 700 ? 40 : 20;
  const shellWidth = Math.max(Math.min(width - pageGutter * 2, 1256), 280);

  if (phase === 'result' && result) {
    const geometryVariant: AnalysisResultGeometryVariant = result.kind === 'article'
      ? result.data.merit_score >= 90 ? 'confirmed' : result.data.merit_score >= 80 ? 'confirmed' : result.data.merit_score >= 65 ? 'opinion' : result.data.merit_score >= 50 ? 'plausible' : result.data.merit_score >= 35 ? 'limited' : 'critical'
      : 'plausible';
    return <SafeAreaView style={styles.safe} testID="analyze-page">
      <AnalysisResultGeometry compact={mobile} light={!dark} reduceMotion={reduceMotion} variant={geometryVariant} />
      <ScrollView nativeID="sportabase-page-scroll" contentContainerStyle={styles.scrollContent}>
        <View style={[styles.shell, { width: shellWidth, marginHorizontal: 'auto' }]}>
          <ProductAnalysisResult context={resultContext.context} contextPhase={resultContext.phase} mobile={mobile} onRetryContext={resultContext.retry} result={result} sourceUrl={url} />
        </View>
      </ScrollView>
    </SafeAreaView>;
  }

  if (busy) {
    return <SafeAreaView style={styles.safe} testID="analyze-page">
      <ProductWatermark approvedHome compact light={!dark} />
      <ScrollView nativeID="sportabase-page-scroll" contentContainerStyle={styles.loadingScrollContent}>
        <View style={[styles.shell, { width: shellWidth, marginHorizontal: 'auto' }]}>
          <ProductAnalysisLoader mobile={mobile} phase={phase} url={url} />
        </View>
      </ScrollView>
    </SafeAreaView>;
  }

  const summaryCopy = accountSummaryCopy(account.ready, account.signedIn, accountSummaryPhase, accountSummary);
  const selectedSport = SPORTS.find((item) => item.sportKey === sportKey) ?? SPORTS[0];
  const visibleStorylines = storylines.filter((item) => item.sport_key === selectedSport.sportKey).slice(0, 3);
  const unscopedStorylineCount = storylines.filter((item) => !item.sport_key).length;

  return <SafeAreaView style={styles.safe} testID="analyze-page">
    <ProductWatermark approvedHome compact light={!dark} />
    <ScrollView nativeID="sportabase-page-scroll" contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
      <View style={[styles.shell, { width: shellWidth, marginHorizontal: 'auto' }]}>
        <View style={[styles.hero, mobile && styles.heroMobile]}>
          <Text accessibilityRole="header" aria-level={1} style={[styles.headline, mobile && styles.headlineMobile]}>Know what backs the story.</Text>
          <Text style={[styles.copy, mobile && styles.copyMobile]}>Paste a sports article or YouTube video. See the central claim, the informational Merit of the reporting, and the evidence or reasoning behind it.</Text>
          <Animated.View style={[styles.actionRow, mobile && styles.actionRowMobile, { transform: [{ scale: press }] }]}>
            <TextInput accessibilityLabel="Article or YouTube URL" nativeID="analysis-url" value={url} onChangeText={(value) => { setUrl(value); setError(''); }} onSubmitEditing={submit} placeholder="Paste a sports article or YouTube URL" placeholderTextColor={palette.muted} keyboardType="url" autoCapitalize="none" autoComplete="off" autoCorrect={false} editable={!busy} style={styles.input} />
            <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={submit} testID="analyze-submit" style={({ pressed }) => [styles.buttonShell, mobile && styles.buttonMobile, disabled && styles.disabled, pressed && styles.pressed]}>
              <View style={styles.button}><Text style={styles.buttonText}>{busy ? 'Analyzing…' : 'Analyze'}</Text><Text style={styles.arrow}>→</Text></View>
            </Pressable>
          </Animated.View>
          {error ? <Text accessibilityLiveRegion="assertive" accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
        </View>

        <View style={styles.sectionHeader}><View><Text style={styles.eyebrow}>Discover</Text><Text style={styles.sectionTitle}>Top storylines</Text></View>{!mobile ? <Text style={styles.sectionNote}>Signals across the current sports cycle</Text> : null}</View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.sportSelector}>{SPORTS.map((item) => <Pressable key={item.sportKey} accessibilityRole="button" accessibilityState={{ selected: sportKey === item.sportKey }} onPress={() => setSportKey(item.sportKey)} style={[styles.sportOption, sportKey === item.sportKey && styles.sportOptionActive]}><Text style={[styles.sportText, sportKey === item.sportKey && styles.sportTextActive]}>{item.label}</Text></Pressable>)}</ScrollView>
        {storylinePhase === 'loading' ? <View accessibilityLiveRegion="polite" style={styles.emptyStory}><View style={styles.storyTop}><Text style={styles.storyContext}>Loading persisted storylines</Text><Text style={styles.storyIndex}>…</Text></View><Text style={styles.storyTitle}>Checking the latest canonical Sportabase storylines.</Text><Text style={styles.emptyMeta}>No sample reporting is substituted</Text></View> : null}
        {storylinePhase === 'error' ? <View accessibilityLiveRegion="polite" style={styles.emptyStory}><View style={styles.storyTop}><Text style={styles.storyContext}>Storylines unavailable</Text><Text style={styles.storyIndex}>!</Text></View><Text style={styles.storyTitle}>Top Storylines could not be loaded.</Text><Text style={styles.storyDescription}>The persisted feed is temporarily unavailable. Try again without changing your selected sport.</Text><Pressable accessibilityRole="button" onPress={() => setStorylineRequest((request) => request + 1)} style={({ pressed }) => [styles.retry, pressed && styles.pressed]}><Text style={styles.retryText}>Try again</Text></Pressable></View> : null}
        {storylinePhase === 'ready' && visibleStorylines.length ? <View style={styles.storyGrid}>{visibleStorylines.map((storyline, index) => {
          const headline = storyline.representative_media?.title || storyline.title;
          return <View key={storyline.storyline_id} style={[styles.storyCard, mobile && styles.storyCardMobile]}><View style={styles.storyTop}><Text style={styles.storyContext}>{displayKey(storyline.current_state)}</Text><Text style={styles.storyIndex}>0{index + 1}</Text></View><Text style={styles.storyTitle}>{headline}</Text><Text style={styles.storyDescription}>Latest activity {formatProductDate(storyline.latest_activity_at)}</Text><View style={styles.storyMeta}><Text style={styles.storyMetaItem}>{storyline.report_count} {storyline.report_count === 1 ? 'report' : 'reports'}</Text><Text style={styles.storyMetaItem}>{storyline.distinct_source_count} distinct {storyline.distinct_source_count === 1 ? 'source' : 'sources'}</Text>{storyline.verified_independent_reporting_present ? <Text style={styles.storyMetaItem}>{storyline.verified_independent_report_count} verified independent {storyline.verified_independent_report_count === 1 ? 'report' : 'reports'}</Text> : null}</View></View>;
        })}</View> : null}
        {storylinePhase === 'ready' && !visibleStorylines.length ? <View style={styles.emptyStory}><View style={styles.storyTop}><Text style={styles.storyContext}>No matching storylines</Text><Text style={styles.storyIndex}>—</Text></View><Text style={styles.storyTitle}>No persisted {selectedSport.label} storylines are available in the current page.</Text><Text style={styles.storyDescription}>Only storylines carrying the explicit “{selectedSport.sportKey}” sport key appear in this tab.</Text><Text style={styles.emptyMeta}>No sport is inferred from titles or entities</Text></View> : null}
        {storylinePhase === 'ready' && unscopedStorylineCount ? <Text style={styles.unscopedNote}>{unscopedStorylineCount} persisted {unscopedStorylineCount === 1 ? 'storyline is' : 'storylines are'} not assigned to one unambiguous sport and remain outside the sport tabs.</Text> : null}

        <View style={[styles.across, mobile && styles.acrossMobile]}><View style={styles.acrossHeading}><Text style={styles.eyebrow}>Intelligence</Text><Text style={styles.sectionTitle}>Across Sportabase</Text></View><View style={[styles.acrossGrid, mobile && styles.acrossGridMobile]}><View style={[styles.acrossItem, mobile && styles.acrossItemMobile]}><Text style={styles.acrossLabel}>Live data unavailable</Text><Text style={styles.acrossTitle}>No public cross-sport intelligence feed is available yet.</Text><Text style={styles.acrossState}>Only persisted production intelligence will appear here.</Text></View></View></View>

        <View style={[styles.future, mobile && styles.futureMobile]}><View><Text style={styles.eyebrow}>Your Sportabase</Text><Text style={styles.futureTitle}>A place for the stories you follow.</Text></View><Text style={styles.futureNote}>{summaryCopy}</Text></View>
      </View>
    </ScrollView>
  </SafeAreaView>;
}

const createStyles = (palette: ProductHomePalette, dark: boolean) => StyleSheet.create({
  safe: { backgroundColor: palette.ground, flex: 1 }, scrollContent: { minHeight: '100%', paddingBottom: 72 }, loadingScrollContent: { flexGrow: 1, minHeight: '100%' }, shell: { alignSelf: 'center', maxWidth: 1256, paddingBottom: 54, position: 'relative', zIndex: 1 },
  hero: { maxWidth: 940, paddingTop: 48 }, heroMobile: { paddingTop: 34 }, headline: { color: palette.text, fontFamily: productFonts.display, fontSize: 56, fontWeight: '800', letterSpacing: -1.8, lineHeight: 61, maxWidth: 780 }, headlineMobile: { fontSize: 39, letterSpacing: -1.1, lineHeight: 44, maxWidth: 340 }, copy: { color: palette.secondary, fontFamily: productFonts.body, fontSize: 17, lineHeight: 26, marginTop: 18, maxWidth: 710 }, copyMobile: { fontSize: 16, lineHeight: 24, marginTop: 15, maxWidth: 340 },
  actionRow: { alignItems: 'stretch', flexDirection: 'row', marginTop: 28, maxWidth: 900, width: '100%' }, actionRowMobile: { flexDirection: 'column', gap: 12, marginTop: 24 }, input: { backgroundColor: palette.deep, borderColor: palette.line, borderRadius: 9, borderWidth: 1, color: palette.text, flex: 1, fontFamily: productFonts.body, fontSize: 16, minHeight: 58, paddingHorizontal: 20 }, buttonShell: { backgroundColor: dark ? '#070A09' : '#D8C8B1', borderColor: dark ? '#F4F7F1' : '#18221B', borderRadius: 9, borderWidth: 1, marginLeft: 10, minWidth: 166, overflow: 'hidden' }, buttonMobile: { marginLeft: 0, minWidth: 0, width: '100%' }, button: { alignItems: 'center', flexDirection: 'row', gap: 18, justifyContent: 'center', minHeight: 56, paddingHorizontal: 26 }, buttonText: { color: dark ? '#F4F7F1' : '#18221B', fontFamily: productFonts.emphasis, fontSize: 17, fontWeight: '800' }, arrow: { color: dark ? '#F4F7F1' : '#18221B', fontSize: 21 }, disabled: { opacity: 0.46 }, pressed: { opacity: 0.72 }, error: { color: palette.danger, fontFamily: productFonts.body, fontSize: 14, lineHeight: 20, marginTop: 12 },
  sectionHeader: { alignItems: 'flex-end', borderTopColor: palette.line, borderTopWidth: 1, flexDirection: 'row', gap: 20, justifyContent: 'space-between', marginTop: 72, paddingTop: 25 }, eyebrow: { color: palette.teal, fontFamily: productFonts.label, fontSize: 11, fontWeight: '900', letterSpacing: 1.35, textTransform: 'uppercase' }, sectionTitle: { color: palette.text, fontFamily: productFonts.display, fontSize: 27, fontWeight: '800', letterSpacing: -0.4, lineHeight: 34, marginTop: 5 }, sectionNote: { color: palette.muted, fontFamily: productFonts.body, fontSize: 12 }, sportSelector: { gap: 8, paddingRight: 24, paddingVertical: 22 }, sportOption: { borderBottomColor: 'transparent', borderBottomWidth: 2, justifyContent: 'center', minHeight: 34, paddingHorizontal: 12 }, sportOptionActive: { borderBottomColor: palette.lime }, sportText: { color: palette.muted, fontFamily: productFonts.emphasis, fontSize: 14, fontWeight: '700' }, sportTextActive: { color: palette.text },
  emptyStory: { borderTopColor: palette.line, borderTopWidth: 1, paddingBottom: 10, paddingTop: 18 }, storyGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 18 }, storyCard: { borderTopColor: palette.line, borderTopWidth: 1, flex: 1, minWidth: 280, paddingBottom: 8, paddingTop: 18 }, storyCardMobile: { flexBasis: '100%' }, storyTop: { flexDirection: 'row', gap: 12, justifyContent: 'space-between' }, storyContext: { color: palette.teal, fontFamily: productFonts.label, fontSize: 11, fontWeight: '800', letterSpacing: 1, textTransform: 'uppercase' }, storyIndex: { color: palette.muted, fontFamily: productFonts.label, fontSize: 11, fontWeight: '800', opacity: 0.45 }, storyTitle: { color: palette.text, fontFamily: productFonts.display, fontSize: 21, fontWeight: '800', lineHeight: 27, marginTop: 14, maxWidth: 580 }, storyDescription: { color: palette.secondary, fontFamily: productFonts.body, fontSize: 14, lineHeight: 21, marginTop: 10, maxWidth: 620 }, storyMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 18 }, storyMetaItem: { color: palette.muted, fontFamily: productFonts.body, fontSize: 12 }, emptyMeta: { color: palette.muted, fontFamily: productFonts.body, fontSize: 12, marginTop: 18 }, retry: { alignSelf: 'flex-start', borderColor: palette.line, borderRadius: 7, borderWidth: 1, marginTop: 18, paddingHorizontal: 14, paddingVertical: 9 }, retryText: { color: palette.text, fontFamily: productFonts.emphasis, fontSize: 13, fontWeight: '700' }, unscopedNote: { color: palette.muted, fontFamily: productFonts.body, fontSize: 12, lineHeight: 18, marginTop: 18 },
  across: { borderTopColor: palette.line, borderTopWidth: 1, marginTop: 72, paddingTop: 26 }, acrossMobile: { marginTop: 54 }, acrossHeading: { marginBottom: 24 }, acrossGrid: { flexDirection: 'row' }, acrossGridMobile: { flexDirection: 'column' }, acrossItem: { borderLeftColor: palette.line, borderLeftWidth: 1, flex: 1, minWidth: 0, paddingBottom: 8, paddingHorizontal: 26 }, acrossItemMobile: { borderLeftWidth: 0, borderTopColor: palette.line, borderTopWidth: 1, paddingHorizontal: 0, paddingVertical: 20 }, acrossLabel: { color: palette.muted, fontFamily: productFonts.label, fontSize: 11, fontWeight: '900', letterSpacing: 1, textTransform: 'uppercase' }, acrossTitle: { color: palette.text, fontFamily: productFonts.emphasis, fontSize: 18, fontWeight: '700', lineHeight: 24, marginTop: 7, maxWidth: 520 }, acrossState: { color: palette.secondary, fontFamily: productFonts.body, fontSize: 12, marginTop: 12 },
  future: { alignItems: 'center', borderBottomColor: palette.line, borderBottomWidth: 1, borderTopColor: palette.line, borderTopWidth: 1, flexDirection: 'row', gap: 40, justifyContent: 'space-between', marginTop: 68, paddingVertical: 28 }, futureMobile: { alignItems: 'flex-start', flexDirection: 'column', gap: 14, marginTop: 48 }, futureTitle: { color: palette.text, fontFamily: productFonts.emphasis, fontSize: 18, fontWeight: '700', marginTop: 7 }, futureNote: { color: palette.muted, fontFamily: productFonts.body, fontSize: 13, lineHeight: 20, maxWidth: 460 },
});
