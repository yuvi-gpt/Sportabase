import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  createWatch,
  listWatches,
  searchIntelligence,
  type IntelligenceSearchResult,
} from '../lib/api';
import { intelligenceRoute } from '../lib/intelligence-history';

const COLORS = {
  background: '#050807',
  surface: '#101412',
  raised: '#171c19',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  accent: '#76f53f',
  accentSoft: 'rgba(118, 245, 63, 0.10)',
  error: '#ff8c8c',
};

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Sportabase could not complete that request.';
}

export default function ExploreScreen() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<
    IntelligenceSearchResult[]
  >([]);
  const [watchedKeys, setWatchedKeys] = useState<
    Set<string>
  >(new Set());
  const [busyKey, setBusyKey] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [message, setMessage] = useState('');

  const loadWatches = useCallback(async () => {
    try {
      const response = await listWatches();
      setWatchedKeys(
        new Set(
          response.items.map(
            (item) =>
              `${item.target_kind}:${item.target_id}`,
          ),
        ),
      );
    } catch {
      // Search remains public and usable even if private
      // watch state cannot be loaded yet.
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void loadWatches();
    }, [loadWatches]),
  );

  async function runSearch() {
    const value = query.trim();

    if (!value) {
      setMessage('Enter a player, team, story, or claim.');
      return;
    }

    setIsSearching(true);
    setMessage('');

    try {
      const response = await searchIntelligence(value);
      setResults(response.results);

      if (response.results.length === 0) {
        setMessage(
          'No persisted intelligence matched that search.',
        );
      }
    } catch (error) {
      setResults([]);
      setMessage(messageFrom(error));
    } finally {
      setIsSearching(false);
    }
  }

  async function watch(result: IntelligenceSearchResult) {
    const key = `${result.kind}:${result.id}`;
    setBusyKey(key);
    setMessage('');

    try {
      const response = await createWatch(
        result.kind,
        result.id,
      );

      setWatchedKeys((current) => {
        const next = new Set(current);
        next.add(key);
        return next;
      });

      setMessage(
        response.created
          ? `Watching ${result.title}. Future persisted changes can now appear in Alerts.`
          : `${result.title} is already on your watchlist.`,
      );
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setBusyKey('');
    }
  }

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          <Text style={styles.eyebrow}>
            PERSISTED INTELLIGENCE
          </Text>
          <Text style={styles.title}>Discover</Text>
          <Text style={styles.subtitle}>
            Search Sportabase&apos;s canonical entities,
            stories, claims and media. A text match helps you
            discover persisted objects; it does not create a
            new verified relationship.
          </Text>

          <View style={styles.searchCard}>
            <TextInput
              value={query}
              onChangeText={(value) => {
                setQuery(value);
                setMessage('');
              }}
              placeholder="Player, club, story, claim..."
              placeholderTextColor="#667169"
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="search"
              onSubmitEditing={runSearch}
              style={styles.input}
            />

            <Pressable
              accessibilityRole="button"
              disabled={isSearching}
              onPress={runSearch}
              style={({ pressed }) => [
                styles.searchButton,
                pressed && styles.pressed,
              ]}
            >
              {isSearching ? (
                <ActivityIndicator color="#071006" />
              ) : (
                <Text style={styles.searchButtonText}>
                  Search
                </Text>
              )}
            </Pressable>
          </View>

          {message ? (
            <Text style={styles.message}>{message}</Text>
          ) : null}

          <View style={styles.results}>
            {results.map((result) => {
              const key = `${result.kind}:${result.id}`;
              const watched = watchedKeys.has(key);
              const busy = busyKey === key;

              return (
                <View key={key} style={styles.resultCard}>
                  <View style={styles.resultTop}>
                    <View style={styles.kindBadge}>
                      <Text style={styles.kindText}>
                        {result.kind.toUpperCase()}
                      </Text>
                    </View>

                    <Text style={styles.matchText}>
                      {result.match_type}
                    </Text>
                  </View>

                  <Text style={styles.resultTitle}>
                    {result.title || 'Untitled intelligence'}
                  </Text>

                  {result.subtitle ? (
                    <Text style={styles.resultSubtitle}>
                      {result.subtitle}
                    </Text>
                  ) : null}

                  <Text style={styles.resultMeta}>
                    Matched {result.matched_field}
                    {result.last_seen_at
                      ? ` · seen ${new Date(
                          result.last_seen_at,
                        ).toLocaleDateString()}`
                      : ''}
                  </Text>

                  <View style={styles.resultActions}>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() =>
                        router.push(
                          intelligenceRoute(
                            result.kind,
                            result.id,
                          ),
                        )
                      }
                      style={({ pressed }) => [
                        styles.detailButton,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text style={styles.detailButtonText}>
                        Open intelligence
                      </Text>
                    </Pressable>

                    <Pressable
                      accessibilityRole="button"
                      disabled={watched || busy}
                      onPress={() => watch(result)}
                      style={({ pressed }) => [
                        styles.watchButton,
                        watched && styles.watchButtonActive,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text
                        style={[
                          styles.watchButtonText,
                          watched &&
                            styles.watchButtonTextActive,
                        ]}
                      >
                        {busy
                          ? 'Adding...'
                          : watched
                            ? 'Watching'
                            : 'Watch future changes'}
                      </Text>
                    </Pressable>
                  </View>
                </View>
              );
            })}
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  safeArea: {
    flex: 1,
  },
  content: {
    alignSelf: 'center',
    maxWidth: 760,
    paddingHorizontal: 20,
    paddingTop: 22,
    paddingBottom: 36,
    width: '100%',
  },
  eyebrow: {
    color: COLORS.accent,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.8,
  },
  title: {
    color: COLORS.text,
    fontSize: 38,
    fontWeight: '800',
    letterSpacing: -1.2,
    marginTop: 8,
  },
  subtitle: {
    color: COLORS.muted,
    fontSize: 15,
    lineHeight: 23,
    marginTop: 10,
    maxWidth: 660,
  },
  searchCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 10,
    marginTop: 24,
    padding: 10,
  },
  input: {
    color: COLORS.text,
    flex: 1,
    fontSize: 15,
    minHeight: 46,
    paddingHorizontal: 10,
  },
  searchButton: {
    alignItems: 'center',
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    justifyContent: 'center',
    minWidth: 92,
    paddingHorizontal: 18,
  },
  searchButtonText: {
    color: '#071006',
    fontSize: 14,
    fontWeight: '800',
  },
  message: {
    color: COLORS.muted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 14,
  },
  results: {
    gap: 12,
    marginTop: 18,
  },
  resultCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 18,
    borderWidth: 1,
    padding: 16,
  },
  resultTop: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  kindBadge: {
    backgroundColor: COLORS.accentSoft,
    borderRadius: 999,
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  kindText: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.1,
  },
  matchText: {
    color: COLORS.muted,
    fontSize: 11,
    textTransform: 'uppercase',
  },
  resultTitle: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: '700',
    lineHeight: 24,
    marginTop: 13,
  },
  resultSubtitle: {
    color: '#bdc6bf',
    fontSize: 13,
    marginTop: 5,
  },
  resultMeta: {
    color: COLORS.muted,
    fontSize: 11,
    lineHeight: 17,
    marginTop: 12,
  },
  resultActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 9,
    marginTop: 15,
  },
  detailButton: {
    alignItems: 'center',
    borderColor: COLORS.border,
    borderRadius: 12,
    borderWidth: 1,
    flex: 1,
    minWidth: 142,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  detailButtonText: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '700',
  },
  watchButton: {
    alignItems: 'center',
    backgroundColor: COLORS.raised,
    borderColor: '#354038',
    borderRadius: 12,
    borderWidth: 1,
    flex: 1,
    minWidth: 156,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  watchButtonActive: {
    backgroundColor: COLORS.accentSoft,
    borderColor: 'rgba(118, 245, 63, 0.28)',
  },
  watchButtonText: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '700',
  },
  watchButtonTextActive: {
    color: COLORS.accent,
  },
  pressed: {
    opacity: 0.72,
  },
});
