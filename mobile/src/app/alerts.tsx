import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { Switch, Text, View } from 'react-native';

import { listAlerts, markAlertRead, reconcileAlerts, type AlertItem, type WatchTargetKind } from '../lib/api';
import { intelligenceRoute } from '../lib/intelligence-history';
import { useProductTheme } from '../theme/product-theme';
import { ProductButton, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, formatProductDate } from '../product-ui/ProductPrimitives';
import { ProtectedWebDestination } from '../product-ui/ProtectedWebDestination';
import { productFonts } from '../product-ui/tokens';

const WATCHABLE = new Set<WatchTargetKind>(['entity', 'story', 'claim', 'media']);
function messageFrom(error: unknown) { return error instanceof Error ? error.message : 'Sportabase could not load alerts.'; }

function AlertsScreen() {
  const router = useRouter(); const { colors, scale } = useProductTheme();
  const params = useLocalSearchParams<{ targetKind?: string | string[] }>();
  const routeKind = Array.isArray(params.targetKind) ? params.targetKind[0] : params.targetKind;
  const targetKind = useMemo<WatchTargetKind | ''>(() => routeKind && WATCHABLE.has(routeKind as WatchTargetKind) ? routeKind as WatchTargetKind : '', [routeKind]);
  const [items, setItems] = useState<AlertItem[]>([]); const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [unreadOnly, setUnreadOnly] = useState(false); const [loading, setLoading] = useState(true); const [checking, setChecking] = useState(false); const [loadingMore, setLoadingMore] = useState(false); const [readingId, setReadingId] = useState('');
  const [message, setMessage] = useState(''); const [error, setError] = useState('');

  const load = useCallback(async (options: { append?: boolean; cursor?: string } = {}) => {
    options.append ? setLoadingMore(true) : setLoading(true); setError('');
    try { const response = await listAlerts({ unreadOnly, targetKind, limit: 50, cursor: options.cursor }); setItems((current) => options.append ? [...current, ...response.items] : response.items); setNextCursor(response.pagination.next_cursor); }
    catch (problem) { setError(messageFrom(problem)); } finally { setLoading(false); setLoadingMore(false); }
  }, [targetKind, unreadOnly]);
  useFocusEffect(useCallback(() => { void load(); }, [load]));

  async function checkForUpdates() {
    setChecking(true); setMessage(''); setError('');
    try { const result = await reconcileAlerts(); await load(); setMessage(result.new_alerts > 0 ? `${result.new_alerts} new alert${result.new_alerts === 1 ? '' : 's'} added from persisted intelligence.` : `No new alert activity across ${result.watches_checked} watch${result.watches_checked === 1 ? '' : 'es'} checked.`); }
    catch (problem) { setError(messageFrom(problem)); } finally { setChecking(false); }
  }
  async function markRead(item: AlertItem) {
    if (item.read_at || readingId) return; setReadingId(item.id);
    try { const updated = await markAlertRead(item.id); setItems((current) => current.map((candidate) => candidate.id === updated.id ? updated : candidate).filter((candidate) => !unreadOnly || candidate.read_at === null)); }
    catch (problem) { setError(messageFrom(problem)); } finally { setReadingId(''); }
  }
  function openAlert(item: AlertItem) { if (!item.read_at) void markRead(item); router.push(intelligenceRoute(item.target_kind, item.target_id)); }

  return <ProductPage width="reading" testID="alerts-page">
    <ProductPageHeader label="In-app intelligence inbox" title="Alerts" description="Alerts are generated only from newly persisted Sportabase intelligence after a watch baseline. Checking is explicit and does not invoke analysis providers." />
    <View style={{ alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 18, justifyContent: 'space-between' }}>
      <ProductButton label={checking ? 'Checking…' : 'Check for updates'} onPress={() => void checkForUpdates()} variant="primary" disabled={checking} />
      <View style={{ alignItems: 'center', flexDirection: 'row', gap: 10, minHeight: 44 }}><Text style={{ color: colors.text, fontFamily: productFonts.emphasis, fontSize: 15 * scale }}>Unread only</Text><Switch accessibilityLabel="Show unread alerts only" value={unreadOnly} onValueChange={setUnreadOnly} trackColor={{ false: colors.surfaceRaised, true: colors.accentSoft }} thumbColor={unreadOnly ? colors.accent : colors.muted} /></View>
    </View>
    {targetKind ? <ProductStatus title={`Filtered to ${targetKind} alerts`} detail="This filter came from the selected watch." /> : null}
    {message ? <ProductStatus title={message} tone="success" /> : null}
    {error ? <ProductStatus title="Alerts could not be updated" detail={error} tone="error" action={<ProductButton label="Retry" onPress={() => void load()} />} /> : null}
    {loading ? <ProductStatus loading title="Loading alerts" /> : null}
    {!loading && !error && items.length === 0 ? <ProductStatus title="No alerts in this view" detail="Add watches from Discover, then check for updates after new intelligence has been persisted." action={<ProductButton label="Open Watches" onPress={() => router.push('/watchlists')} />} /> : null}
    {items.length ? <ProductSection title="Persisted alert history" description="Occurred and detected times remain distinct; chronology is ordering only."><View>{items.map((item) => <ProductRow key={item.id} label={`${item.target_kind} · ${item.read_at ? 'read' : 'new'}`} title={item.summary} description={item.event_type.replace(/_/g, ' ')} meta={`Occurred ${formatProductDate(item.occurred_at)} · Detected ${formatProductDate(item.detected_at)}${item.related_kind && item.related_id ? ` · Related ${item.related_kind}: ${item.related_id}` : ''}`} actions={<ProductButton label={readingId === item.id ? 'Opening…' : 'Open intelligence'} onPress={() => openAlert(item)} disabled={readingId === item.id} />} selected={!item.read_at} />)}</View></ProductSection> : null}
    {nextCursor ? <View style={{ alignItems: 'flex-start' }}><ProductButton label={loadingMore ? 'Loading…' : 'Load more alerts'} onPress={() => void load({ append: true, cursor: nextCursor })} disabled={loadingMore} /></View> : null}
  </ProductPage>;
}

export default function AlertsRoute() { return <ProtectedWebDestination destination="/alerts" title="Alerts"><AlertsScreen /></ProtectedWebDestination>; }
