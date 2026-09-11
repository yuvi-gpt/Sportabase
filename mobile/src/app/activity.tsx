import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { Linking, Text, View } from 'react-native';

import { accountRequest } from '../lib/account-api';
import { useAccount } from '../lib/account-context';
import { createRequestGeneration } from '../lib/request-generation';
import { ProductButton, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, ProductTextField } from '../product-ui/ProductPrimitives';
import { ProtectedWebDestination } from '../product-ui/ProtectedWebDestination';

type Item = { id: string; kind: string; title: string; url: string; created_at: number; platform: string; restorable: boolean };
type Cursor = { before: number; cursor: string } | null;

function ActivityScreen() {
  const router = useRouter(); const { preferences } = useAccount();
  const [items, setItems] = useState<Item[]>([]); const [query, setQuery] = useState(''); const [kind, setKind] = useState(''); const [next, setNext] = useState<Cursor>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false); const [loaded, setLoaded] = useState(false);
  const requests = useRef(createRequestGeneration()).current;
  const focusGeneration = useRef(0); const focused = useRef(false);
  const requestId = useRef(0);
  const activeRequest = useRef<{ focus: number; id: number; key: string; promise: Promise<void> } | null>(null);
  const load = useCallback(async (append = false) => {
    const focus = focusGeneration.current;
    const params = new URLSearchParams({ q: query, kind, ...(append && next ? { before: String(next.before), cursor: next.cursor } : {}) });
    const key = `${append ? 'append' : 'replace'}:${params}`;
    if (activeRequest.current?.focus === focus && activeRequest.current.key === key) return activeRequest.current.promise;
    const isCurrent = requests.begin();
    const id = ++requestId.current;
    const promise = (async () => {
      setBusy(true); setError('');
      try {
        const data = await accountRequest<{ items: Item[]; next: Cursor }>(`/account/activity?${params}`);
        if (!isCurrent()) return;
        setItems((old) => append ? [...old, ...data.items] : data.items); setNext(data.next); setLoaded(true);
      } catch (problem) { if (isCurrent()) setError(problem instanceof Error ? problem.message : 'Could not load activity.'); } finally {
        if (isCurrent()) setBusy(false);
        if (activeRequest.current?.id === id) activeRequest.current = null;
      }
    })();
    activeRequest.current = { focus, id, key, promise };
    return promise;
  }, [kind, next, query, requests]);
  const loadRef = useRef(load);
  const previousKind = useRef(kind);
  useEffect(() => { loadRef.current = load; }, [load]);
  useEffect(() => {
    if (previousKind.current === kind) return;
    previousKind.current = kind;
    if (focused.current) void loadRef.current();
  }, [kind]);
  useFocusEffect(useCallback(() => {
    focused.current = true; focusGeneration.current += 1;
    void loadRef.current();
    return () => {
      focused.current = false; focusGeneration.current += 1;
      requests.invalidate(); activeRequest.current = null;
    };
  }, [requests]));
  function date(value: number) { const parsed = new Date(value * 1000); return preferences.date_format === 'iso' ? parsed.toISOString().slice(0, 10) : parsed.toLocaleString(); }

  return <ProductPage width="reading" testID="activity-page">
    <View style={{ alignItems: 'flex-start' }}><ProductButton label="Back to Settings" onPress={() => router.push('/settings')} variant="quiet" /></View>
    <ProductPageHeader label="Your saved analysis history" title="My Activity" description="Search and revisit analyses saved to your Sportabase account. Results are records of prior work, not new canonical relationships." />
    <ProductSection title="Filter activity"><View style={{ gap: 14 }}><ProductTextField nativeID="activity-query" label="Search titles" value={query} onChangeText={setQuery} onSubmitEditing={() => void load()} placeholder="Search saved analysis titles" autoComplete="off" inputMode="search" /><View accessibilityRole="tablist" style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{[['', 'All'], ['article', 'Articles'], ['video', 'Videos']].map(([value, label]) => <ProductButton key={value || 'all'} label={label} onPress={() => setKind(value)} variant={kind === value ? 'primary' : 'secondary'} disabled={busy} />)}</View><View style={{ alignItems: 'flex-start' }}><ProductButton label={busy ? 'Searching…' : 'Search activity'} onPress={() => void load()} variant="primary" disabled={busy} /></View></View></ProductSection>
    {busy && !items.length ? <ProductStatus loading title="Loading activity" /> : null}
    {error ? <ProductStatus title="Activity could not be loaded" detail={error} tone="error" action={<ProductButton label="Retry" onPress={() => void load()} />} /> : null}
    {loaded && !busy && !error && !items.length ? <ProductStatus title="No activity found" detail="Completed analyses appear here when account saving is enabled." action={<ProductButton label="Analyze a URL" onPress={() => router.push('/')} variant="primary" />} /> : null}
    {items.length ? <ProductSection title="Saved analyses"><View>{items.map((item) => {
      const canOpen = /^https?:\/\//.test(item.url);
      const actions = <View style={{ alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {item.restorable ? <ProductButton label="View analysis" onPress={() => router.push({ pathname: '/analysis', params: { activity: item.id } })} variant="primary" /> : <Text accessibilityLabel="Analysis snapshot unavailable" style={{ opacity: 0.7 }}>Snapshot unavailable</Text>}
        {canOpen ? <ProductButton label="Open source" onPress={() => void Linking.openURL(item.url).catch(() => setError('Could not open the saved source URL.'))} /> : null}
      </View>;
      return <ProductRow key={item.id} label={item.kind === 'article' ? 'Article' : 'Video'} title={item.title} meta={`${item.platform === 'mobile' ? 'Mobile' : item.platform} · ${date(item.created_at)}`} actions={actions} />;
    })}</View></ProductSection> : null}
    {next ? <View style={{ alignItems: 'flex-start' }}><ProductButton label={busy ? 'Loading…' : 'Load more'} onPress={() => void load(true)} disabled={busy} /></View> : null}
  </ProductPage>;
}

export default function ActivityRoute() { return <ProtectedWebDestination destination="/activity" title="Activity"><ActivityScreen /></ProtectedWebDestination>; }
