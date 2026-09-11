import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { View } from 'react-native';

import { createWatch, listWatches } from '../lib/api';
import { useAccount } from '../lib/account-context';
import { inspectableIntelligenceRoute, isWatchableIntelligenceKind } from '../lib/intelligence-kinds';
import { searchInspectableIntelligence, type IntelligenceSearchResult } from '../lib/intelligence-search';
import { ProductButton, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, ProductTextField, formatProductDate } from '../product-ui/ProductPrimitives';

function messageFrom(error: unknown) { return error instanceof Error ? error.message : 'Sportabase could not complete that request.'; }

export default function ExploreScreen() {
  const router = useRouter();
  const account = useAccount();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<IntelligenceSearchResult[]>([]);
  const [watchedKeys, setWatchedKeys] = useState<Set<string>>(new Set());
  const [busyKey, setBusyKey] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');

  const loadWatches = useCallback(async () => {
    if (!account.signedIn) { setWatchedKeys(new Set()); return; }
    try { const response = await listWatches(); setWatchedKeys(new Set(response.items.map((item) => `${item.target_kind}:${item.target_id}`))); } catch { /* Public search remains usable. */ }
  }, [account.signedIn]);
  useFocusEffect(useCallback(() => { void loadWatches(); }, [loadWatches]));

  const runSearch = useCallback(async () => {
    const value = query.trim();
    if (!value) { setFieldError('Enter a player, team, story, claim, source, or reporter.'); return; }
    setIsSearching(true); setMessage(''); setError(''); setFieldError(''); setSearched(true);
    try { const response = await searchInspectableIntelligence(value); setResults(response.results); }
    catch (problem) { setResults([]); setError(messageFrom(problem)); }
    finally { setIsSearching(false); }
  }, [query]);

  async function watch(result: IntelligenceSearchResult) {
    if (!isWatchableIntelligenceKind(result.kind)) return;
    if (!account.signedIn) {
      try { await account.signIn(false, '/explore'); } catch (problem) { setError(messageFrom(problem)); }
      return;
    }
    const key = `${result.kind}:${result.id}`; setBusyKey(key); setMessage(''); setError('');
    try {
      const response = await createWatch(result.kind, result.id);
      setWatchedKeys((current) => new Set(current).add(key));
      setMessage(response.created ? `Watching ${result.title}. Future persisted changes can now appear in Alerts.` : `${result.title} is already on your watchlist.`);
    } catch (problem) { setError(messageFrom(problem)); } finally { setBusyKey(''); }
  }

  return <ProductPage width="reading" testID="discover-page">
    <ProductPageHeader label="Persisted intelligence" title="Discover" description="Search Sportabase entities, stories, claims, media, sources, and reporters. A text match aids discovery; it does not create a canonical relationship or a reliability judgment." />
    <ProductSection title="Search the intelligence graph">
      <View style={{ gap: 12 }}><ProductTextField nativeID="discover-query" label="Search term" value={query} onChangeText={(value) => { setQuery(value); setError(''); setFieldError(''); }} onSubmitEditing={() => void runSearch()} returnKeyType="search" autoCapitalize="none" autoComplete="off" autoCorrect={false} inputMode="search" placeholder="Player, club, story, source, reporter…" error={fieldError} /><View style={{ alignItems: 'flex-start' }}><ProductButton label={isSearching ? 'Searching…' : 'Search'} onPress={() => void runSearch()} variant="primary" disabled={isSearching} /></View></View>
    </ProductSection>
    {isSearching ? <ProductStatus loading title="Searching persisted intelligence" detail="Looking across inspectable Sportabase objects." /> : null}
    {message ? <ProductStatus title={message} tone="success" /> : null}
    {!isSearching && searched && !error && results.length === 0 ? <ProductStatus title="No persisted intelligence matched" detail="Try a broader sports subject, team, person, source, or reporter. No new relationship is inferred from this search." action={<ProductButton label="Clear search" onPress={() => { setQuery(''); setSearched(false); }} variant="quiet" />} /> : null}
    {error && searched ? <ProductStatus title="Search could not be completed" detail={error} tone="error" action={<ProductButton label="Retry search" onPress={() => void runSearch()} />} /> : null}
    {results.length ? <ProductSection title={`${results.length} ${results.length === 1 ? 'result' : 'results'}`} description="Sources and reporters are provenance profiles only. Watch actions appear only for entities, stories, claims, and media.">
      <View>{results.map((result) => {
        const key = `${result.kind}:${result.id}`; const watchable = isWatchableIntelligenceKind(result.kind); const watched = watchedKeys.has(key); const busy = busyKey === key;
        return <ProductRow key={key} label={`${result.kind} · ${result.match_type}`} title={result.title || 'Untitled intelligence'} description={result.subtitle} meta={`Matched ${result.matched_field}${result.last_seen_at ? ` · seen ${formatProductDate(result.last_seen_at)}` : ''}`} actions={<><ProductButton label="Open intelligence" onPress={() => router.push(inspectableIntelligenceRoute(result.kind, result.id))} />{watchable ? <ProductButton label={busy ? 'Adding…' : watched ? 'Watching' : account.signedIn ? 'Watch changes' : 'Sign in to watch'} onPress={() => void watch(result)} variant={watched ? 'quiet' : 'secondary'} disabled={busy || watched} /> : null}</>} />;
      })}</View>
    </ProductSection> : null}
  </ProductPage>;
}
