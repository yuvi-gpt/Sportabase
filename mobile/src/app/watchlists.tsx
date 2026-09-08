import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { View } from 'react-native';

import { deleteWatch, listWatches, type WatchItem } from '../lib/api';
import { intelligenceRoute } from '../lib/intelligence-history';
import { ProductButton, ProductMetric, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, formatProductDate } from '../product-ui/ProductPrimitives';
import { ProtectedWebDestination } from '../product-ui/ProtectedWebDestination';

function messageFrom(error: unknown) { return error instanceof Error ? error.message : 'Sportabase could not load your watches.'; }

function WatchlistsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<WatchItem[]>([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(100);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState('');
  const [pendingRemoval, setPendingRemoval] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { const response = await listWatches(); setItems(response.items); setCount(response.count); setLimit(response.limit); }
    catch (problem) { setError(messageFrom(problem)); } finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { void load(); }, [load]));

  async function remove(item: WatchItem) {
    setDeletingId(item.id); setError('');
    try { await deleteWatch(item.id); setItems((current) => current.filter((watch) => watch.id !== item.id)); setCount((current) => Math.max(0, current - 1)); setPendingRemoval(''); }
    catch (problem) { setError(messageFrom(problem)); } finally { setDeletingId(''); }
  }

  return <ProductPage width="reading" testID="watches-page">
    <ProductPageHeader label="Future changes only" title="Watches" description="Watches begin at the current discovery baseline. Existing historical intelligence does not flood your alert inbox." aside={<ProductMetric label="Capacity" value={`${count}/${limit}`} detail="Watchable: entity, story, claim, media" />} />
    <View style={{ alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}><ProductButton label="Discover intelligence" onPress={() => router.push('/explore')} variant="primary" /><ProductButton label="Open alerts" onPress={() => router.push('/alerts')} /></View>
    {loading ? <ProductStatus loading title="Loading watches" detail="Checking your current saved intelligence targets." /> : null}
    {error ? <ProductStatus title="Watches could not be loaded" detail={error} tone="error" action={<ProductButton label="Retry" onPress={() => void load()} />} /> : null}
    {!loading && !error && items.length === 0 ? <ProductStatus title="Nothing watched yet" detail="Discover persisted Sportabase intelligence, then watch an entity, story, claim, or media item for future changes." action={<ProductButton label="Go to Discover" onPress={() => router.push('/explore')} variant="primary" />} /> : null}
    {items.length ? <ProductSection title="Current watches" description="Removing a watch stops future alerts; it does not alter persisted intelligence."><View>{items.map((item) => {
      const confirming = pendingRemoval === item.id; const deleting = deletingId === item.id;
      return <ProductRow key={item.id} label={item.target_kind} title={item.target_label || item.target_id} meta={`Added ${formatProductDate(item.created_at)} · ${item.last_reconciled_at ? `checked ${formatProductDate(item.last_reconciled_at)}` : 'not checked yet'}`} actions={confirming ? <><ProductButton label={deleting ? 'Removing…' : 'Confirm remove'} onPress={() => void remove(item)} variant="danger" disabled={deleting} /><ProductButton label="Cancel" onPress={() => setPendingRemoval('')} variant="quiet" disabled={deleting} /></> : <><ProductButton label="Open intelligence" onPress={() => router.push(intelligenceRoute(item.target_kind, item.target_id))} /><ProductButton label="View alerts" onPress={() => router.push({ pathname: '/alerts', params: { targetKind: item.target_kind } })} /><ProductButton label="Remove" onPress={() => setPendingRemoval(item.id)} variant="danger" /></>} />;
    })}</View></ProductSection> : null}
  </ProductPage>;
}

export default function WatchlistsRoute() { return <ProtectedWebDestination destination="/watchlists" title="Watches"><WatchlistsScreen /></ProtectedWebDestination>; }
