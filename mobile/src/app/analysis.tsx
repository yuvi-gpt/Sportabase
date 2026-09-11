import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView, ScrollView, StyleSheet, View, useWindowDimensions } from 'react-native';

import { getSavedAnalysis, type SavedAnalysisResponse } from '../lib/api';
import type { AuthReturnDestination } from '../lib/auth-destinations';
import type { ProductAnalysisResult } from '../lib/product-analysis';
import { useAnalysisResultContext } from '../lib/use-analysis-result-context';
import { AnalysisResultGeometry, type AnalysisResultGeometryVariant } from '../result-ui/AnalysisResultGeometry.web';
import { ProductAnalysisResult as ProductAnalysisResultView } from '../product-ui/ProductAnalysisResult.web';
import { ProductButton, ProductPage, ProductPageHeader, ProductStatus } from '../product-ui/ProductPrimitives';
import { ProtectedWebDestination } from '../product-ui/ProtectedWebDestination';
import { useProductHomeControls } from '../product-ui/ProductShellContext';
import { useProductTheme } from '../theme/product-theme';

const ACTIVITY_ID = /^act_[0-9a-f]{32}$/;

function geometryVariant(result: ProductAnalysisResult): AnalysisResultGeometryVariant {
  if (result.kind === 'video') return 'plausible';
  const score = result.data.merit_score;
  return score >= 80 ? 'confirmed' : score >= 65 ? 'opinion' : score >= 50 ? 'plausible' : score >= 35 ? 'limited' : 'critical';
}

function SavedAnalysisScreen({ activityId }: { activityId: string }) {
  const router = useRouter();
  const { dark, reduceMotion } = useProductTheme();
  const { width } = useWindowDimensions();
  const mobile = width < 700;
  const [saved, setSaved] = useState<SavedAnalysisResponse | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const goHome = useCallback(() => router.push('/'), [router]);
  useProductHomeControls(useMemo(() => ({ onHome: goHome, onAnother: goHome, showAnother: true }), [goHome]));

  useEffect(() => {
    let active = true;
    setSaved(null);
    setError('');
    void getSavedAnalysis(activityId).then((response) => {
      if (active) setSaved(response);
    }).catch((problem) => {
      if (active) setError(problem instanceof Error ? problem.message : 'This saved analysis is unavailable.');
    });
    return () => { active = false; };
  }, [activityId, attempt]);

  const sourceUrl = saved?.source_url ?? '';
  const context = useAnalysisResultContext(sourceUrl, Boolean(saved));

  if (!saved) {
    return <ProductPage width="reading" testID="saved-analysis-page">
      <ProductPageHeader label="Saved analysis" title={error ? 'Analysis unavailable' : 'Loading saved analysis'} description={error ? 'Sportabase could not restore this historical result.' : 'Restoring the exact analysis snapshot from your private Activity.'} />
      <ProductStatus loading={!error} tone={error ? 'error' : 'neutral'} title={error ? 'Saved analysis could not be opened' : 'Loading historical snapshot'} detail={error || 'This does not run a new analysis.'} action={error ? <View style={styles.actions}><ProductButton label="Retry saved analysis" onPress={() => setAttempt((value) => value + 1)} /><ProductButton label="Analyze another" onPress={goHome} variant="primary" /></View> : undefined} />
    </ProductPage>;
  }

  const result: ProductAnalysisResult = saved.kind === 'article'
    ? { kind: 'article', data: saved.analysis }
    : { kind: 'video', data: saved.analysis };
  const pageGutter = width >= 1200 ? 68 : width >= 700 ? 40 : 20;
  const shellWidth = Math.max(Math.min(width - pageGutter * 2, 1256), 280);

  return <SafeAreaView style={styles.safe} testID="saved-analysis-page">
    <AnalysisResultGeometry compact={mobile} light={!dark} reduceMotion={reduceMotion} variant={geometryVariant(result)} />
    <ScrollView nativeID="sportabase-page-scroll" contentContainerStyle={styles.scrollContent}>
      <View style={[styles.shell, { width: shellWidth, marginHorizontal: 'auto' }]}>
        <ProductAnalysisResultView context={context.context} contextPhase={context.phase} mobile={mobile} onRetryContext={context.retry} result={result} sourceUrl={saved.source_url} />
      </View>
    </ScrollView>
  </SafeAreaView>;
}

export default function SavedAnalysisRoute() {
  const params = useLocalSearchParams<{ activity?: string | string[] }>();
  const activityId = typeof params.activity === 'string' ? params.activity : '';
  const valid = ACTIVITY_ID.test(activityId);
  const returnDestination = (valid ? `/analysis?activity=${activityId}` : '/analysis') as AuthReturnDestination;

  return <ProtectedWebDestination destination="/analysis" returnDestination={returnDestination} title="Saved analysis">
    {valid ? <SavedAnalysisScreen activityId={activityId} /> : <ProductPage width="reading" testID="saved-analysis-page">
      <ProductPageHeader label="Saved analysis" title="Analysis unavailable" description="This saved-analysis link is missing a valid Activity reference." />
      <ProductStatus tone="error" title="Saved analysis could not be opened" detail="Open the analysis again from My Activity." />
    </ProductPage>}
  </ProtectedWebDestination>;
}

const styles = StyleSheet.create({
  actions: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  safe: { flex: 1, minHeight: '100%' },
  scrollContent: { minHeight: '100%', paddingBottom: 72 },
  shell: { alignSelf: 'center', maxWidth: 1256, paddingBottom: 54, position: 'relative', zIndex: 1 },
});
