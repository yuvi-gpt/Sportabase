import { useCallback, useMemo, useState } from 'react';
import {
  useFocusEffect,
  useLocalSearchParams,
} from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  listAlerts,
  markAlertRead,
  reconcileAlerts,
  type AlertItem,
  type WatchTargetKind,
} from '../lib/api';

const WATCHABLE = new Set<WatchTargetKind>([
  'entity',
  'story',
  'claim',
  'media',
]);

const COLORS = {
  background: '#050807',
  surface: '#101412',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  accent: '#76f53f',
  accentSoft: 'rgba(118, 245, 63, 0.10)',
};

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Sportabase could not load alerts.';
}

export default function AlertsScreen() {
  const params = useLocalSearchParams<{
    targetKind?: string | string[];
  }>();

  const routeKind = Array.isArray(params.targetKind)
    ? params.targetKind[0]
    : params.targetKind;

  const targetKind = useMemo<WatchTargetKind | ''>(
    () =>
      routeKind && WATCHABLE.has(routeKind as WatchTargetKind)
        ? (routeKind as WatchTargetKind)
        : '',
    [routeKind],
  );

  const [items, setItems] = useState<AlertItem[]>([]);
  const [nextCursor, setNextCursor] = useState<
    string | null
  >(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isChecking, setIsChecking] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [readingId, setReadingId] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(
    async (
      options: {
        append?: boolean;
        cursor?: string;
      } = {},
    ) => {
      options.append
        ? setIsLoadingMore(true)
        : setIsLoading(true);
      setMessage('');

      try {
        const response = await listAlerts({
          unreadOnly,
          targetKind,
          limit: 50,
          cursor: options.cursor,
        });

        setItems((current) =>
          options.append
            ? [...current, ...response.items]
            : response.items,
        );
        setNextCursor(response.pagination.next_cursor);
      } catch (error) {
        setMessage(messageFrom(error));
      } finally {
        setIsLoading(false);
        setIsLoadingMore(false);
      }
    },
    [targetKind, unreadOnly],
  );

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function checkForUpdates() {
    setIsChecking(true);
    setMessage('');

    try {
      const result = await reconcileAlerts();
      await load();
      setMessage(
        result.new_alerts > 0
          ? `${result.new_alerts} new alert${
              result.new_alerts === 1 ? '' : 's'
            } added from persisted intelligence.`
          : `No new alert activity across ${result.watches_checked} watch${
              result.watches_checked === 1 ? '' : 'es'
            } checked.`,
      );
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setIsChecking(false);
    }
  }

  async function markRead(item: AlertItem) {
    if (item.read_at || readingId) {
      return;
    }

    setReadingId(item.id);

    try {
      const updated = await markAlertRead(item.id);
      setItems((current) =>
        current
          .map((candidate) =>
            candidate.id === updated.id
              ? updated
              : candidate,
          )
          .filter(
            (candidate) =>
              !unreadOnly || candidate.read_at === null,
          ),
      );
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setReadingId('');
    }
  }

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          <Text style={styles.eyebrow}>
            IN-APP INTELLIGENCE INBOX
          </Text>
          <Text style={styles.title}>Alerts</Text>
          <Text style={styles.subtitle}>
            Alerts are generated only from newly persisted
            Sportabase intelligence after a watch&apos;s
            baseline. Checking for updates is explicit and
            local; it does not call Gemini or notification
            providers.
          </Text>

          {targetKind ? (
            <View style={styles.filterBadge}>
              <Text style={styles.filterText}>
                FILTER · {targetKind.toUpperCase()}
              </Text>
            </View>
          ) : null}

          <View style={styles.toolbar}>
            <Pressable
              accessibilityRole="button"
              disabled={isChecking}
              onPress={checkForUpdates}
              style={({ pressed }) => [
                styles.checkButton,
                pressed && styles.pressed,
              ]}
            >
              {isChecking ? (
                <ActivityIndicator color="#071006" />
              ) : (
                <Text style={styles.checkButtonText}>
                  Check for updates
                </Text>
              )}
            </Pressable>

            <View style={styles.unreadControl}>
              <Text style={styles.unreadLabel}>
                Unread only
              </Text>
              <Switch
                value={unreadOnly}
                onValueChange={setUnreadOnly}
                trackColor={{
                  false: '#303731',
                  true: '#4c7b35',
                }}
                thumbColor={
                  unreadOnly ? COLORS.accent : '#b7c0b9'
                }
              />
            </View>
          </View>

          {message ? (
            <Text style={styles.message}>{message}</Text>
          ) : null}

          {isLoading && items.length === 0 ? (
            <View style={styles.loadingState}>
              <ActivityIndicator color={COLORS.accent} />
              <Text style={styles.loadingText}>
                Loading alerts...
              </Text>
            </View>
          ) : null}

          {!isLoading && items.length === 0 ? (
            <View style={styles.emptyState}>
              <Text style={styles.emptyTitle}>
                No alerts in this view
              </Text>
              <Text style={styles.emptyCopy}>
                Add watches from Discover, then use “Check
                for updates” after new intelligence has been
                persisted.
              </Text>
            </View>
          ) : null}

          <View style={styles.list}>
            {items.map((item) => {
              const unread = item.read_at === null;

              return (
                <Pressable
                  key={item.id}
                  accessibilityRole="button"
                  onPress={() => void markRead(item)}
                  style={({ pressed }) => [
                    styles.card,
                    unread && styles.cardUnread,
                    pressed && styles.pressed,
                  ]}
                >
                  <View style={styles.cardTop}>
                    <View style={styles.kindBadge}>
                      <Text style={styles.kindText}>
                        {item.target_kind.toUpperCase()}
                      </Text>
                    </View>

                    {unread ? (
                      <View style={styles.unreadBadge}>
                        <View style={styles.unreadDot} />
                        <Text style={styles.unreadBadgeText}>
                          NEW
                        </Text>
                      </View>
                    ) : (
                      <Text style={styles.readText}>READ</Text>
                    )}
                  </View>

                  <Text style={styles.cardTitle}>
                    {item.summary}
                  </Text>

                  <Text style={styles.eventType}>
                    {item.event_type
                      .replace(/_/g, ' ')
                      .toUpperCase()}
                  </Text>

                  <View style={styles.timeGrid}>
                    <View style={styles.timeCell}>
                      <Text style={styles.timeLabel}>
                        OCCURRED
                      </Text>
                      <Text style={styles.timeValue}>
                        {new Date(
                          item.occurred_at,
                        ).toLocaleString()}
                      </Text>
                    </View>
                    <View style={styles.timeCell}>
                      <Text style={styles.timeLabel}>
                        DETECTED
                      </Text>
                      <Text style={styles.timeValue}>
                        {new Date(
                          item.detected_at,
                        ).toLocaleString()}
                      </Text>
                    </View>
                  </View>

                  {item.related_kind && item.related_id ? (
                    <Text style={styles.relatedText}>
                      Related {item.related_kind} ·{' '}
                      {item.related_id}
                    </Text>
                  ) : null}

                  {readingId === item.id ? (
                    <Text style={styles.markingText}>
                      Marking read...
                    </Text>
                  ) : unread ? (
                    <Text style={styles.markingText}>
                      Tap to mark read
                    </Text>
                  ) : null}
                </Pressable>
              );
            })}
          </View>

          {nextCursor ? (
            <Pressable
              accessibilityRole="button"
              disabled={isLoadingMore}
              onPress={() =>
                void load({
                  append: true,
                  cursor: nextCursor,
                })
              }
              style={({ pressed }) => [
                styles.moreButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.moreButtonText}>
                {isLoadingMore
                  ? 'Loading...'
                  : 'Load more alerts'}
              </Text>
            </Pressable>
          ) : null}
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
  },
  filterBadge: {
    alignSelf: 'flex-start',
    backgroundColor: COLORS.accentSoft,
    borderRadius: 999,
    marginTop: 16,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  filterText: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1,
  },
  toolbar: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
    justifyContent: 'space-between',
    marginTop: 24,
  },
  checkButton: {
    alignItems: 'center',
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    minHeight: 44,
    minWidth: 154,
    justifyContent: 'center',
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  checkButtonText: {
    color: '#071006',
    fontSize: 13,
    fontWeight: '800',
  },
  unreadControl: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 9,
  },
  unreadLabel: {
    color: COLORS.muted,
    fontSize: 12,
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
  cardUnread: {
    borderColor: 'rgba(118, 245, 63, 0.35)',
  },
  cardTop: {
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
    letterSpacing: 1,
  },
  unreadBadge: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 5,
  },
  unreadDot: {
    backgroundColor: COLORS.accent,
    borderRadius: 999,
    height: 6,
    width: 6,
  },
  unreadBadgeText: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
  },
  readText: {
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: '700',
  },
  cardTitle: {
    color: COLORS.text,
    fontSize: 17,
    fontWeight: '700',
    lineHeight: 24,
    marginTop: 13,
  },
  eventType: {
    color: '#bdc6bf',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.9,
    marginTop: 8,
  },
  timeGrid: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 15,
  },
  timeCell: {
    flex: 1,
  },
  timeLabel: {
    color: '#69736c',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1,
  },
  timeValue: {
    color: COLORS.muted,
    fontSize: 11,
    lineHeight: 16,
    marginTop: 4,
  },
  relatedText: {
    color: COLORS.muted,
    fontSize: 11,
    marginTop: 12,
  },
  markingText: {
    color: COLORS.accent,
    fontSize: 11,
    fontWeight: '700',
    marginTop: 12,
  },
  moreButton: {
    alignItems: 'center',
    borderColor: COLORS.border,
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 18,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  moreButtonText: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.7,
  },
});
