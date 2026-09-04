import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  deleteWatch,
  listWatches,
  type WatchItem,
} from '../lib/api';
import { intelligenceRoute } from '../lib/intelligence-history';

const COLORS = {
  background: '#050807',
  surface: '#101412',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  accent: '#76f53f',
  danger: '#ff8c8c',
};

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Sportabase could not load your watchlist.';
}

export default function WatchlistsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<WatchItem[]>([]);
  const [count, setCount] = useState(0);
  const [limit, setLimit] = useState(100);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [deletingId, setDeletingId] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async (refresh = false) => {
    refresh ? setIsRefreshing(true) : setIsLoading(true);
    setMessage('');

    try {
      const response = await listWatches();
      setItems(response.items);
      setCount(response.count);
      setLimit(response.limit);
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function remove(item: WatchItem) {
    setDeletingId(item.id);
    setMessage('');

    try {
      await deleteWatch(item.id);
      setItems((current) =>
        current.filter((watch) => watch.id !== item.id),
      );
      setCount((current) => Math.max(0, current - 1));
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setDeletingId('');
    }
  }

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={() => void load(true)}
              tintColor={COLORS.accent}
            />
          }
          contentContainerStyle={styles.content}
        >
          <View style={styles.headingRow}>
            <View style={styles.headingCopy}>
              <Text style={styles.eyebrow}>
                FUTURE CHANGES ONLY
              </Text>
              <Text style={styles.title}>Watchlist</Text>
              <Text style={styles.subtitle}>
                Watches begin at the current discovery
                baseline. Existing historical intelligence
                does not flood your alert inbox.
              </Text>
            </View>

            <View style={styles.counter}>
              <Text style={styles.counterValue}>{count}</Text>
              <Text style={styles.counterLabel}>/ {limit}</Text>
            </View>
          </View>

          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push('/explore')}
              style={({ pressed }) => [
                styles.primaryButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.primaryButtonText}>
                Discover intelligence
              </Text>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              onPress={() => router.push('/alerts')}
              style={({ pressed }) => [
                styles.secondaryButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.secondaryButtonText}>
                Open alerts
              </Text>
            </Pressable>
          </View>

          {message ? (
            <Text style={styles.message}>{message}</Text>
          ) : null}

          {isLoading && items.length === 0 ? (
            <View style={styles.loadingState}>
              <ActivityIndicator color={COLORS.accent} />
              <Text style={styles.loadingText}>
                Loading watches...
              </Text>
            </View>
          ) : null}

          {!isLoading && items.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>
                Nothing watched yet
              </Text>
              <Text style={styles.emptyCopy}>
                Search persisted Sportabase intelligence and
                choose an entity, story, claim or media item
                to watch for future persisted changes.
              </Text>
            </View>
          ) : null}

          <View style={styles.list}>
            {items.map((item) => (
              <View key={item.id} style={styles.card}>
                <View style={styles.cardTop}>
                  <View style={styles.kindBadge}>
                    <Text style={styles.kindText}>
                      {item.target_kind.toUpperCase()}
                    </Text>
                  </View>
                  <Text style={styles.createdText}>
                    {new Date(
                      item.created_at,
                    ).toLocaleDateString()}
                  </Text>
                </View>

                <Text style={styles.cardTitle}>
                  {item.target_label || item.target_id}
                </Text>

                <Text style={styles.cardMeta}>
                  {item.last_reconciled_at
                    ? `Last checked ${new Date(
                        item.last_reconciled_at,
                      ).toLocaleString()}`
                    : 'Not checked for new activity yet'}
                </Text>

                <View style={styles.cardActions}>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() =>
                      router.push(
                        intelligenceRoute(
                          item.target_kind,
                          item.target_id,
                        ),
                      )
                    }
                    style={({ pressed }) => [
                      styles.cardAction,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.cardActionText}>
                      Open intelligence
                    </Text>
                  </Pressable>

                  <Pressable
                    accessibilityRole="button"
                    onPress={() =>
                      router.push({
                        pathname: '/alerts',
                        params: {
                          targetKind: item.target_kind,
                        },
                      })
                    }
                    style={({ pressed }) => [
                      styles.cardAction,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.cardActionText}>
                      View {item.target_kind} alerts
                    </Text>
                  </Pressable>

                  <Pressable
                    accessibilityRole="button"
                    disabled={deletingId === item.id}
                    onPress={() => void remove(item)}
                    style={({ pressed }) => [
                      styles.removeButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.removeText}>
                      {deletingId === item.id
                        ? 'Removing...'
                        : 'Remove'}
                    </Text>
                  </Pressable>
                </View>
              </View>
            ))}
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
  headingRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 18,
    justifyContent: 'space-between',
  },
  headingCopy: {
    flex: 1,
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
  },
  counter: {
    alignItems: 'baseline',
    flexDirection: 'row',
    marginTop: 22,
  },
  counterValue: {
    color: COLORS.text,
    fontSize: 25,
    fontWeight: '800',
  },
  counterLabel: {
    color: COLORS.muted,
    fontSize: 12,
    marginLeft: 4,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 24,
  },
  primaryButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  primaryButtonText: {
    color: '#071006',
    fontSize: 13,
    fontWeight: '800',
  },
  secondaryButton: {
    borderColor: COLORS.border,
    borderRadius: 12,
    borderWidth: 1,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  secondaryButtonText: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '700',
  },
  message: {
    color: COLORS.muted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 14,
  },
  loadingState: {
    alignItems: 'center',
    gap: 10,
    paddingVertical: 44,
  },
  loadingText: {
    color: COLORS.muted,
    fontSize: 13,
  },
  emptyState: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 18,
    borderWidth: 1,
    marginTop: 24,
    padding: 22,
  },
  emptyTitle: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: '700',
  },
  emptyCopy: {
    color: COLORS.muted,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 8,
  },
  list: {
    gap: 12,
    marginTop: 22,
  },
  card: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 18,
    borderWidth: 1,
    padding: 16,
  },
  cardTop: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  kindBadge: {
    backgroundColor: 'rgba(118, 245, 63, 0.10)',
    borderRadius: 999,
    paddingHorizontal: 9,
    paddingVertical: 5,
  },
  kindText: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
  },
  createdText: {
    color: COLORS.muted,
    fontSize: 11,
  },
  cardTitle: {
    color: COLORS.text,
    fontSize: 18,
    fontWeight: '700',
    lineHeight: 24,
    marginTop: 13,
  },
  cardMeta: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 8,
  },
  cardActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 9,
    marginTop: 15,
  },
  cardAction: {
    borderColor: COLORS.border,
    borderRadius: 10,
    borderWidth: 1,
    flex: 1,
    minWidth: 140,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  cardActionText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
  },
  removeButton: {
    borderColor: 'rgba(255, 140, 140, 0.35)',
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  removeText: {
    color: COLORS.danger,
    fontSize: 12,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.7,
  },
});
