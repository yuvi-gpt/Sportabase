import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { Linking, Text, View } from 'react-native';

import { createWatch, listWatches, type WatchTargetKind } from '../lib/api';
import { getIntelligenceHistory, intelligenceEventDetails, intelligenceIdentity, intelligencePolicyNotes, intelligenceRelations, intelligenceRoute, type IntelligenceHistoryResponse } from '../lib/intelligence-history';
import { useProductTheme } from '../theme/product-theme';
import { ProductButton, ProductMetric, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, ProductSurface, formatProductDate } from '../product-ui/ProductPrimitives';
import { productFonts } from '../product-ui/tokens';

function messageFrom(error: unknown) { return error instanceof Error ? error.message : 'Sportabase could not load this intelligence object.'; }
function humanize(value: string) { return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()); }

export function IntelligenceDetailScreen({ kind, id }: { kind: WatchTargetKind; id: string }) {
  const router = useRouter(); const { colors, scale } = useProductTheme();
  const [data, setData] = useState<IntelligenceHistoryResponse | null>(null); const [loading, setLoading] = useState(true); const [loadingMore, setLoadingMore] = useState(false); const [watching, setWatching] = useState(false); const [addingWatch, setAddingWatch] = useState(false); const [message, setMessage] = useState(''); const [error, setError] = useState('');
  const loadWatchState = useCallback(async () => { try { const response = await listWatches(); setWatching(response.items.some((item) => item.target_kind === kind && item.target_id === id)); } catch { /* Public intelligence remains available. */ } }, [id, kind]);
  const loadHistory = useCallback(async () => { setLoading(true); setError(''); try { setData(await getIntelligenceHistory(kind, id, { limit: 50 })); } catch (problem) { setData(null); setError(messageFrom(problem)); } finally { setLoading(false); } }, [id, kind]);
  useFocusEffect(useCallback(() => { void loadHistory(); void loadWatchState(); }, [loadHistory, loadWatchState]));
  const identity = useMemo(() => data ? intelligenceIdentity(kind, data) : null, [data, kind]);
  const relations = useMemo(() => data ? intelligenceRelations(kind, data) : [], [data, kind]);
  const policyNotes = useMemo(() => data ? intelligencePolicyNotes(data.policy) : [], [data]);
  async function addWatch() { if (watching || addingWatch) return; setAddingWatch(true); setMessage(''); setError(''); try { const response = await createWatch(kind, id); setWatching(true); setMessage(response.created ? 'Watch added. Only future persisted changes can generate alerts.' : 'This object is already on your watchlist.'); } catch (problem) { setError(messageFrom(problem)); } finally { setAddingWatch(false); } }
  async function loadMore() { const cursor = data?.pagination.next_cursor; if (!data || !cursor || loadingMore) return; setLoadingMore(true); setError(''); try { const next = await getIntelligenceHistory(kind, id, { limit: 50, cursor }); setData((current) => current ? ({ ...current, events: [...current.events, ...next.events], pagination: next.pagination } as IntelligenceHistoryResponse) : next); } catch (problem) { setError(messageFrom(problem)); } finally { setLoadingMore(false); } }

  return <ProductPage width="content" testID="intelligence-page">
    <View style={{ alignItems: 'flex-start' }}><ProductButton label="Back" onPress={() => router.back()} variant="quiet" /></View>
    {loading && !data ? <ProductStatus loading title="Loading persisted intelligence" /> : null}
    {error && !data ? <ProductStatus title="Intelligence unavailable" detail={error} tone="error" action={<ProductButton label="Try again" onPress={() => void loadHistory()} />} /> : null}
    {data && identity ? <>
      <ProductPageHeader label={`${kind} · canonical intelligence object`} title={identity.title} description={identity.subtitle} aside={<View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}><ProductButton label={addingWatch ? 'Adding…' : watching ? 'Watching' : 'Watch future changes'} onPress={() => void addWatch()} variant={watching ? 'quiet' : 'primary'} disabled={addingWatch || watching} />{identity.canonicalUrl ? <ProductButton label="Open source" onPress={() => void Linking.openURL(identity.canonicalUrl!).catch(() => setError('Could not open the canonical source URL.'))} /> : null}</View>} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 24 }}><ProductMetric label="First seen" value={formatProductDate(identity.firstSeenAt)} /><ProductMetric label="Last seen" value={formatProductDate(identity.lastSeenAt)} /></View>
      {message ? <ProductStatus title={message} tone="success" /> : null}{error ? <ProductStatus title="Action could not be completed" detail={error} tone="error" /> : null}
      <ProductSection title="Interpretation boundaries" description="These constraints travel with the object wherever it appears."><ProductSurface elevated style={{ gap: 12 }}>{policyNotes.length ? policyNotes.map((note, index) => <View key={note} style={{ alignItems: 'flex-start', flexDirection: 'row', gap: 12 }}><Text style={{ color: colors.accent, fontFamily: productFonts.label }}>0{index + 1}</Text><Text style={{ color: colors.textMuted, flex: 1, fontFamily: productFonts.body, fontSize: 15 * scale, lineHeight: 22 * scale }}>{note}</Text></View>) : <Text style={{ color: colors.textMuted, fontFamily: productFonts.body }}>No additional policy notes were supplied.</Text>}</ProductSurface></ProductSection>
      <ProductSection title="Related intelligence" description="Only persisted graph relationships appear here—not temporary search matches."><View>{relations.length ? relations.map((relation) => <ProductRow key={`${relation.kind}:${relation.id}`} label={relation.kind} title={relation.title} description={relation.subtitle} actions={<ProductButton label="Open" onPress={() => router.push(intelligenceRoute(relation.kind, relation.id))} />} />) : <ProductStatus title="No related canonical objects are exposed" />}</View></ProductSection>
      <ProductSection title="Persisted chronology" description="Ordering records when intelligence occurred. It does not imply truth, novelty, probability, or independent corroboration."><View>{data.events.length ? data.events.map((event, index) => { const details = intelligenceEventDetails(event); return <ProductRow key={event.id ?? `${event.type}-${event.occurred_at}-${index}`} label={humanize(event.type)} title={details[0]?.value || humanize(event.type)} description={details.slice(details[0] ? 1 : 0).map((item) => `${item.label}: ${item.value}`).join(' · ') || undefined} meta={formatProductDate(event.occurred_at)} />; }) : <ProductStatus title="No persisted chronology is available" />}</View></ProductSection>
      {data.pagination.next_cursor ? <View style={{ alignItems: 'flex-start' }}><ProductButton label={loadingMore ? 'Loading…' : 'Load more history'} onPress={() => void loadMore()} disabled={loadingMore} /></View> : null}
    </> : null}
  </ProductPage>;
}
