import { useProductTheme, scaleStyles } from '../theme/product-theme';
import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  createWatch,
  listWatches,
  type WatchTargetKind,
} from '../lib/api';
import {
  getIntelligenceHistory,
  intelligenceEventDetails,
  intelligenceIdentity,
  intelligencePolicyNotes,
  intelligenceRelations,
  intelligenceRoute,
  type IntelligenceHistoryResponse,
} from '../lib/intelligence-history';

const COLORS = {
  background: '#050807',
  surface: '#101412',
  raised: '#171c19',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  faint: '#69736c',
  accent: '#76f53f',
  accentSoft: 'rgba(118, 245, 63, 0.10)',
  error: '#ff8c8c',
};

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Sportabase could not load this intelligence object.';
}

function formatDate(value: string) {
  if (!value) {
    return 'Not recorded';
  }

  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString();
}

export function IntelligenceDetailScreen({
  kind,
  id,
}: {
  kind: WatchTargetKind;
  id: string;
}) {
  const { colors: COLORS,scale }=useProductTheme();
  const styles=scaleStyles(makeStyles(COLORS),scale);
  const router = useRouter();
  const [data, setData] =
    useState<IntelligenceHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isWatching, setIsWatching] = useState(false);
  const [isAddingWatch, setIsAddingWatch] = useState(false);
  const [message, setMessage] = useState('');

  const loadWatchState = useCallback(async () => {
    try {
      const response = await listWatches();
      setIsWatching(
        response.items.some(
          (item) =>
            item.target_kind === kind &&
            item.target_id === id,
        ),
      );
    } catch {
      // Public history remains usable if private watch
      // state cannot be loaded on this device.
    }
  }, [id, kind]);

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setMessage('');

    try {
      const response = await getIntelligenceHistory(
        kind,
        id,
        { limit: 50 },
      );
      setData(response);
    } catch (error) {
      setData(null);
      setMessage(messageFrom(error));
    } finally {
      setIsLoading(false);
    }
  }, [id, kind]);

  useFocusEffect(
    useCallback(() => {
      void loadHistory();
      void loadWatchState();
    }, [loadHistory, loadWatchState]),
  );

  const identity = useMemo(
    () => (data ? intelligenceIdentity(kind, data) : null),
    [data, kind],
  );

  const relations = useMemo(
    () => (data ? intelligenceRelations(kind, data) : []),
    [data, kind],
  );

  const policyNotes = useMemo(
    () => (data ? intelligencePolicyNotes(data.policy) : []),
    [data],
  );

  async function addWatch() {
    if (isWatching || isAddingWatch) {
      return;
    }

    setIsAddingWatch(true);
    setMessage('');

    try {
      const response = await createWatch(kind, id);
      setIsWatching(true);
      setMessage(
        response.created
          ? 'Watch added. Only future persisted changes can generate alerts.'
          : 'This object is already on your watchlist.',
      );
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setIsAddingWatch(false);
    }
  }

  async function loadMore() {
    const cursor = data?.pagination.next_cursor;
    if (!data || !cursor || isLoadingMore) {
      return;
    }

    setIsLoadingMore(true);
    setMessage('');

    try {
      const next = await getIntelligenceHistory(kind, id, {
        limit: 50,
        cursor,
      });

      setData((current) =>
        current
          ? ({
              ...current,
              events: [...current.events, ...next.events],
              pagination: next.pagination,
            } as IntelligenceHistoryResponse)
          : next,
      );
    } catch (error) {
      setMessage(messageFrom(error));
    } finally {
      setIsLoadingMore(false);
    }
  }

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          <View style={styles.topRow}>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.back()}
              style={({ pressed }) => [
                styles.backButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.backText}>← Back</Text>
            </Pressable>

            <View style={styles.kindBadge}>
              <Text style={styles.kindText}>
                {kind.toUpperCase()}
              </Text>
            </View>
          </View>

          {isLoading && !data ? (
            <View style={styles.loadingState}>
              <ActivityIndicator color={COLORS.accent} />
              <Text style={styles.loadingText}>
                Loading persisted intelligence...
              </Text>
            </View>
          ) : null}

          {message && !data ? (
            <View style={styles.errorCard}>
              <Text style={styles.errorTitle}>
                Intelligence unavailable
              </Text>
              <Text style={styles.errorCopy}>{message}</Text>
              <Pressable
                accessibilityRole="button"
                onPress={() => void loadHistory()}
                style={({ pressed }) => [
                  styles.retryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.retryText}>Try again</Text>
              </Pressable>
            </View>
          ) : null}

          {data && identity ? (
            <>
              <Text style={styles.eyebrow}>
                CANONICAL INTELLIGENCE OBJECT
              </Text>
              <Text style={styles.title}>{identity.title}</Text>
              <Text style={styles.subtitle}>
                {identity.subtitle}
              </Text>

              <View style={styles.timeGrid}>
                <View style={styles.timeCell}>
                  <Text style={styles.timeLabel}>FIRST SEEN</Text>
                  <Text style={styles.timeValue}>
                    {formatDate(identity.firstSeenAt)}
                  </Text>
                </View>
                <View style={styles.timeCell}>
                  <Text style={styles.timeLabel}>LAST SEEN</Text>
                  <Text style={styles.timeValue}>
                    {formatDate(identity.lastSeenAt)}
                  </Text>
                </View>
              </View>

              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={isWatching || isAddingWatch}
                  onPress={() => void addWatch()}
                  style={({ pressed }) => [
                    styles.primaryButton,
                    isWatching && styles.primaryButtonActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.primaryButtonText,
                      isWatching && styles.primaryButtonTextActive,
                    ]}
                  >
                    {isAddingWatch
                      ? 'Adding watch...'
                      : isWatching
                        ? 'Watching future changes'
                        : 'Watch future changes'}
                  </Text>
                </Pressable>

                <Pressable
                  accessibilityRole="button"
                  onPress={() =>
                    router.push({
                      pathname: '/alerts',
                      params: { targetKind: kind },
                    })
                  }
                  style={({ pressed }) => [
                    styles.secondaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.secondaryButtonText}>
                    Open {kind} alerts
                  </Text>
                </Pressable>

                {identity.canonicalUrl ? (
                  <Pressable
                    accessibilityRole="link"
                    onPress={() =>
                      void Linking.openURL(
                        identity.canonicalUrl as string,
                      )
                    }
                    style={({ pressed }) => [
                      styles.secondaryButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.secondaryButtonText}>
                      Open original media ↗
                    </Text>
                  </Pressable>
                ) : null}
              </View>

              {message ? (
                <Text style={styles.message}>{message}</Text>
              ) : null}

              <View style={styles.policyCard}>
                <Text style={styles.sectionEyebrow}>
                  INTERPRETATION BOUNDARIES
                </Text>
                {policyNotes.map((note) => (
                  <View key={note} style={styles.policyRow}>
                    <View style={styles.policyDot} />
                    <Text style={styles.policyText}>{note}</Text>
                  </View>
                ))}
              </View>

              <View style={styles.sectionHeading}>
                <View>
                  <Text style={styles.sectionEyebrow}>
                    PERSISTED GRAPH
                  </Text>
                  <Text style={styles.sectionTitle}>
                    Related intelligence
                  </Text>
                </View>
                <Text style={styles.sectionCount}>
                  {relations.length}
                </Text>
              </View>

              {relations.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Text style={styles.emptyText}>
                    No related canonical objects are exposed by
                    this history response yet.
                  </Text>
                </View>
              ) : (
                <View style={styles.relatedList}>
                  {relations.map((relation) => (
                    <Pressable
                      key={`${relation.kind}:${relation.id}`}
                      accessibilityRole="button"
                      onPress={() =>
                        router.push(
                          intelligenceRoute(
                            relation.kind,
                            relation.id,
                          ),
                        )
                      }
                      style={({ pressed }) => [
                        styles.relatedCard,
                        pressed && styles.pressed,
                      ]}
                    >
                      <View style={styles.relatedTop}>
                        <Text style={styles.relatedKind}>
                          {relation.kind.toUpperCase()}
                        </Text>
                        <Text style={styles.relatedArrow}>→</Text>
                      </View>
                      <Text style={styles.relatedTitle}>
                        {relation.title}
                      </Text>
                      {relation.subtitle ? (
                        <Text style={styles.relatedSubtitle}>
                          {relation.subtitle}
                        </Text>
                      ) : null}
                    </Pressable>
                  ))}
                </View>
              )}

              <View style={styles.sectionHeading}>
                <View>
                  <Text style={styles.sectionEyebrow}>
                    DOMAIN CHRONOLOGY
                  </Text>
                  <Text style={styles.sectionTitle}>
                    Persisted history
                  </Text>
                </View>
                <Text style={styles.sectionCount}>
                  {data.events.length}
                </Text>
              </View>

              <Text style={styles.timelineNote}>
                Events are ordered by their domain occurrence
                time. Ordering does not imply truth, credibility,
                novelty or independent corroboration.
              </Text>

              {data.events.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Text style={styles.emptyText}>
                    No persisted history events are exposed for
                    this object yet.
                  </Text>
                </View>
              ) : (
                <View style={styles.timeline}>
                  {data.events.map((event, index) => {
                    const details = intelligenceEventDetails(event);
                    const key = `${event.type}:${event.id ?? index}:${event.occurred_at}`;

                    return (
                      <View key={key} style={styles.eventCard}>
                        <View style={styles.eventTop}>
                          <View style={styles.eventIndex}>
                            <Text style={styles.eventIndexText}>
                              {String(index + 1).padStart(2, '0')}
                            </Text>
                          </View>
                          <View style={styles.eventHeading}>
                            <Text style={styles.eventType}>
                              {event.type
                                .replace(/_/g, ' ')
                                .toUpperCase()}
                            </Text>
                            <Text style={styles.eventTime}>
                              {formatDate(event.occurred_at)}
                            </Text>
                          </View>
                        </View>

                        {details.length > 0 ? (
                          <View style={styles.detailGrid}>
                            {details.map((detail) => (
                              <View
                                key={`${key}:${detail.label}`}
                                style={styles.detailRow}
                              >
                                <Text style={styles.detailLabel}>
                                  {detail.label}
                                </Text>
                                <Text style={styles.detailValue}>
                                  {detail.value}
                                </Text>
                              </View>
                            ))}
                          </View>
                        ) : (
                          <Text style={styles.noDetailText}>
                            Persisted relationship/event record.
                          </Text>
                        )}
                      </View>
                    );
                  })}
                </View>
              )}

              {data.pagination.next_cursor ? (
                <Pressable
                  accessibilityRole="button"
                  disabled={isLoadingMore}
                  onPress={() => void loadMore()}
                  style={({ pressed }) => [
                    styles.moreButton,
                    pressed && styles.pressed,
                  ]}
                >
                  {isLoadingMore ? (
                    <ActivityIndicator color={COLORS.text} />
                  ) : (
                    <Text style={styles.moreButtonText}>
                      Load more history
                    </Text>
                  )}
                </Pressable>
              ) : null}
            </>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const makeStyles = (COLORS: Record<string,string>) => StyleSheet.create({
  screen: {
    backgroundColor: COLORS.background,
    flex: 1,
  },
  safeArea: {
    flex: 1,
  },
  content: {
    alignSelf: 'center',
    maxWidth: 820,
    paddingBottom: 42,
    paddingHorizontal: 20,
    paddingTop: 18,
    width: '100%',
  },
  topRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 22,
  },
  backButton: {
    borderColor: COLORS.border,
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 9,
  },
  backText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  kindBadge: {
    backgroundColor: COLORS.accentSoft,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  kindText: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  loadingState: {
    alignItems: 'center',
    gap: 10,
    paddingVertical: 70,
  },
  loadingText: {
    color: COLORS.muted,
    fontSize: 13,
  },
  errorCard: {
    backgroundColor: COLORS.surface,
    borderColor: 'rgba(255, 140, 140, 0.35)',
    borderRadius: 18,
    borderWidth: 1,
    padding: 20,
  },
  errorTitle: {
    color: COLORS.error,
    fontSize: 18,
    fontWeight: '800',
  },
  errorCopy: {
    color: COLORS.muted,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 8,
  },
  retryButton: {
    alignSelf: 'flex-start',
    borderColor: COLORS.border,
    borderRadius: 10,
    borderWidth: 1,
    marginTop: 16,
    paddingHorizontal: 13,
    paddingVertical: 10,
  },
  retryText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  eyebrow: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.6,
  },
  title: {
    color: COLORS.text,
    fontSize: 34,
    fontWeight: '800',
    letterSpacing: -1,
    lineHeight: 42,
    marginTop: 9,
  },
  subtitle: {
    color: COLORS.muted,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 8,
  },
  timeGrid: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  timeCell: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 14,
    borderWidth: 1,
    flex: 1,
    padding: 13,
  },
  timeLabel: {
    color: COLORS.faint,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1,
  },
  timeValue: {
    color: COLORS.text,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 5,
  },
  actions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 9,
    marginTop: 18,
  },
  primaryButton: {
    backgroundColor: COLORS.accent,
    borderRadius: 11,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  primaryButtonActive: {
    backgroundColor: COLORS.accentSoft,
    borderColor: 'rgba(118, 245, 63, 0.30)',
    borderWidth: 1,
  },
  primaryButtonText: {
    color: '#071006',
    fontSize: 12,
    fontWeight: '800',
  },
  primaryButtonTextActive: {
    color: COLORS.accent,
  },
  secondaryButton: {
    borderColor: COLORS.border,
    borderRadius: 11,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 11,
  },
  secondaryButtonText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  message: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 13,
  },
  policyCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 18,
    borderWidth: 1,
    gap: 10,
    marginTop: 24,
    padding: 17,
  },
  sectionEyebrow: {
    color: COLORS.accent,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.4,
  },
  policyRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 9,
  },
  policyDot: {
    backgroundColor: COLORS.accent,
    borderRadius: 999,
    height: 5,
    marginTop: 7,
    width: 5,
  },
  policyText: {
    color: COLORS.muted,
    flex: 1,
    fontSize: 12,
    lineHeight: 19,
  },
  sectionHeading: {
    alignItems: 'flex-end',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 30,
  },
  sectionTitle: {
    color: COLORS.text,
    fontSize: 22,
    fontWeight: '800',
    marginTop: 5,
  },
  sectionCount: {
    color: COLORS.muted,
    fontSize: 12,
    fontWeight: '700',
  },
  relatedList: {
    gap: 9,
    marginTop: 14,
  },
  relatedCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 15,
    borderWidth: 1,
    padding: 14,
  },
  relatedTop: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  relatedKind: {
    color: COLORS.accent,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1,
  },
  relatedArrow: {
    color: COLORS.muted,
    fontSize: 15,
  },
  relatedTitle: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: '700',
    lineHeight: 20,
    marginTop: 8,
  },
  relatedSubtitle: {
    color: COLORS.muted,
    fontSize: 11,
    marginTop: 4,
  },
  timelineNote: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 19,
    marginTop: 10,
  },
  timeline: {
    gap: 10,
    marginTop: 14,
  },
  eventCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 16,
    borderWidth: 1,
    padding: 15,
  },
  eventTop: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 11,
  },
  eventIndex: {
    alignItems: 'center',
    backgroundColor: COLORS.raised,
    borderRadius: 9,
    justifyContent: 'center',
    minHeight: 30,
    minWidth: 36,
  },
  eventIndexText: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '800',
  },
  eventHeading: {
    flex: 1,
  },
  eventType: {
    color: COLORS.text,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  eventTime: {
    color: COLORS.muted,
    fontSize: 11,
    marginTop: 4,
  },
  detailGrid: {
    gap: 9,
    marginTop: 14,
  },
  detailRow: {
    borderTopColor: '#202620',
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: 9,
  },
  detailLabel: {
    color: COLORS.faint,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  detailValue: {
    color: '#c4cdc6',
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
  noDetailText: {
    color: COLORS.muted,
    fontSize: 12,
    marginTop: 12,
  },
  emptyCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 15,
    borderWidth: 1,
    marginTop: 14,
    padding: 16,
  },
  emptyText: {
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 19,
  },
  moreButton: {
    alignItems: 'center',
    borderColor: COLORS.border,
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  moreButtonText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.7,
  },
});
