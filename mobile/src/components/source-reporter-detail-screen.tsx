import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { Text, View } from 'react-native';

import { getSourceReporterHistory, sourceReporterEventDetails, sourceReporterIdentity, sourceReporterPolicyNotes, sourceReporterRelations, sourceReporterRoute, type SourceReporterHistoryResponse, type SourceReporterKind } from '../lib/source-reporter-history';
import { useProductTheme } from '../theme/product-theme';
import { ProductButton, ProductMetric, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, ProductSurface, formatProductDate } from '../product-ui/ProductPrimitives';
import { productFonts } from '../product-ui/tokens';

function messageFrom(error: unknown) { return error instanceof Error ? error.message : 'Sportabase could not load this provenance profile.'; }
function humanize(value: string) { return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }

export function SourceReporterDetailScreen({ kind, id }: { kind: SourceReporterKind; id: string }) {
  const router = useRouter(); const { colors, scale } = useProductTheme();
  const [data, setData] = useState<SourceReporterHistoryResponse | null>(null); const [loading, setLoading] = useState(true); const [loadingMore, setLoadingMore] = useState(false); const [error, setError] = useState('');
  const loadHistory = useCallback(async () => { setLoading(true); setError(''); try { setData(await getSourceReporterHistory(kind, id, { limit: 50 })); } catch (problem) { setData(null); setError(messageFrom(problem)); } finally { setLoading(false); } }, [id, kind]);
  useFocusEffect(useCallback(() => { void loadHistory(); }, [loadHistory]));
  const identity = useMemo(() => data ? sourceReporterIdentity(kind, data) : null, [data, kind]);
  const relations = useMemo(() => data ? sourceReporterRelations(kind, data) : [], [data, kind]);
  const notes = useMemo(() => data ? sourceReporterPolicyNotes(data.policy) : [], [data]);
  const counts = useMemo(() => data ? Object.entries(data.counts).filter(([, value]) => Number.isFinite(value)) : [], [data]);
  async function loadMore() { const cursor = data?.pagination.next_cursor; if (!data || !cursor || loadingMore) return; setLoadingMore(true); setError(''); try { const next = await getSourceReporterHistory(kind, id, { limit: 50, cursor }); setData((current) => current ? { ...current, events: [...current.events, ...next.events], pagination: next.pagination } : next); } catch (problem) { setError(messageFrom(problem)); } finally { setLoadingMore(false); } }

  return <ProductPage width="content" testID="provenance-page">
    <View style={{ alignItems: 'flex-start' }}><ProductButton label="Back" onPress={() => router.back()} variant="quiet" /></View>
    {loading && !data ? <ProductStatus loading title="Loading persisted provenance profile" /> : null}
    {error && !data ? <ProductStatus title="Profile unavailable" detail={error} tone="error" action={<ProductButton label="Try again" onPress={() => void loadHistory()} />} /> : null}
    {data && identity ? <>
      <ProductPageHeader label={`${kind} · inspectable provenance`} title={identity.title} description={`${identity.subtitle}. This is an empirical record, not a reliability, trust, or credibility score.`} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 24 }}><ProductMetric label="First seen" value={formatProductDate(identity.firstSeenAt)} /><ProductMetric label="Last seen" value={formatProductDate(identity.lastSeenAt)} /></View>
      {error ? <ProductStatus title="Profile action could not be completed" detail={error} tone="error" /> : null}
      {counts.length ? <ProductSection title="Recorded activity" description="Counts describe persisted observations. Quantity is not probability, reliability, or independence."><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 24 }}>{counts.map(([key, value]) => <ProductMetric key={key} label={humanize(key)} value={String(value)} />)}</View></ProductSection> : null}
      <ProductSection title="Interpretation boundaries"><ProductSurface elevated style={{ gap: 12 }}>{notes.length ? notes.map((note, index) => <View key={note} style={{ alignItems: 'flex-start', flexDirection: 'row', gap: 12 }}><Text style={{ color: colors.accent, fontFamily: productFonts.label }}>0{index + 1}</Text><Text style={{ color: colors.textMuted, flex: 1, fontFamily: productFonts.body, fontSize: 15 * scale, lineHeight: 22 * scale }}>{note}</Text></View>) : <Text style={{ color: colors.textMuted, fontFamily: productFonts.body }}>No additional policy notes were supplied.</Text>}</ProductSurface></ProductSection>
      <ProductSection title="Related intelligence" description="Sources and reporters stay inspectable and are never watch targets."><View>{relations.length ? relations.map((relation) => <ProductRow key={`${relation.kind}:${relation.id}`} label={relation.kind} title={relation.title} description={relation.subtitle} actions={<ProductButton label="Open" onPress={() => router.push(sourceReporterRoute(relation.kind, relation.id))} />} />) : <ProductStatus title="No related canonical objects are exposed" />}</View></ProductSection>
      <ProductSection title="Persisted chronology" description="Ordering reflects domain occurrence time; it does not imply truth, reliability, novelty, or corroboration."><View>{data.events.length ? data.events.map((event, index) => { const details = sourceReporterEventDetails(event); return <ProductRow key={event.id ?? `${event.type}-${event.occurred_at}-${index}`} label={humanize(event.type)} title={details[0]?.value || humanize(event.type)} description={details.slice(details[0] ? 1 : 0).map((item) => `${item.label}: ${item.value}`).join(' · ') || undefined} meta={formatProductDate(event.occurred_at)} />; }) : <ProductStatus title="No persisted chronology is available" />}</View></ProductSection>
      {data.pagination.next_cursor ? <View style={{ alignItems: 'flex-start' }}><ProductButton label={loadingMore ? 'Loading…' : 'Load more history'} onPress={() => void loadMore()} disabled={loadingMore} /></View> : null}
    </> : null}
  </ProductPage>;
}
