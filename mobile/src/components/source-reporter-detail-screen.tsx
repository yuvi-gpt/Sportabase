import { useProductTheme, scaleStyles } from '../theme/product-theme';
import { useCallback, useMemo, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  getSourceReporterHistory,
  sourceReporterEventDetails,
  sourceReporterIdentity,
  sourceReporterPolicyNotes,
  sourceReporterRelations,
  sourceReporterRoute,
  type SourceReporterHistoryResponse,
  type SourceReporterKind,
} from '../lib/source-reporter-history';

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
    : 'Sportabase could not load this profile.';
}

function formatDate(value: string) {
  if (!value) return 'Not recorded';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString();
}

function humanize(value: string) {
  return value.replace(/_/g, ' ').toUpperCase();
}

export function SourceReporterDetailScreen({
  kind,
  id,
}: {
  kind: SourceReporterKind;
  id: string;
}) {
  const { colors: COLORS,scale }=useProductTheme();
  const styles=scaleStyles(makeStyles(COLORS),scale);
  const router = useRouter();
  const [data, setData] =
    useState<SourceReporterHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [message, setMessage] = useState('');

  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setMessage('');
    try {
      setData(
        await getSourceReporterHistory(kind, id, { limit: 50 }),
      );
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
    }, [loadHistory]),
  );

  const identity = useMemo(
    () => (data ? sourceReporterIdentity(kind, data) : null),
    [data, kind],
  );
  const relations = useMemo(
    () => (data ? sourceReporterRelations(kind, data) : []),
    [data, kind],
  );
  const policyNotes = useMemo(
    () => (data ? sourceReporterPolicyNotes(data.policy) : []),
    [data],
  );
  const countEntries = useMemo(
    () =>
      data
        ? Object.entries(data.counts).filter(([, value]) =>
            Number.isFinite(value),
          )
        : [],
    [data],
  );

  async function loadMore() {
    const cursor = data?.pagination.next_cursor;
    if (!data || !cursor || isLoadingMore) return;

    setIsLoadingMore(true);
    setMessage('');
    try {
      const next = await getSourceReporterHistory(kind, id, {
        limit: 50,
        cursor,
      });
      setData((current) =>
        current
          ? {
              ...current,
              events: [...current.events, ...next.events],
              pagination: next.pagination,
            }
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
              style={styles.backButton}
            >
              <Text style={styles.backText}>← Back</Text>
            </Pressable>
            <View style={styles.kindBadge}>
              <Text style={styles.kindText}>{kind.toUpperCase()}</Text>
            </View>
          </View>

          {isLoading && !data ? (
            <View style={styles.loadingState}>
              <ActivityIndicator color={COLORS.accent} />
              <Text style={styles.muted}>Loading persisted profile...</Text>
            </View>
          ) : null}

          {message && !data ? (
            <View style={styles.errorCard}>
              <Text style={styles.errorTitle}>Profile unavailable</Text>
              <Text style={styles.muted}>{message}</Text>
              <Pressable onPress={() => void loadHistory()} style={styles.secondaryButton}>
                <Text style={styles.secondaryText}>Try again</Text>
              </Pressable>
            </View>
          ) : null}

          {data && identity ? (
            <>
              <Text style={styles.eyebrow}>PERSISTED REPORTING PROFILE</Text>
              <Text style={styles.title}>{identity.title}</Text>
              <Text style={styles.subtitle}>{identity.subtitle}</Text>

              <View style={styles.timeGrid}>
                <View style={styles.timeCell}>
                  <Text style={styles.label}>FIRST SEEN</Text>
                  <Text style={styles.value}>{formatDate(identity.firstSeenAt)}</Text>
                </View>
                <View style={styles.timeCell}>
                  <Text style={styles.label}>LAST SEEN</Text>
                  <Text style={styles.value}>{formatDate(identity.lastSeenAt)}</Text>
                </View>
              </View>

              <View style={styles.boundaryCard}>
                <Text style={styles.sectionEyebrow}>WHAT THIS PROFILE IS</Text>
                <Text style={styles.boundaryCopy}>
                  An empirical record of persisted Sportabase observations and relationships. It is not a reliability, trust or credibility score.
                </Text>
              </View>

              <View style={styles.sectionHeading}>
                <Text style={styles.sectionTitle}>Recorded activity</Text>
              </View>
              <View style={styles.countGrid}>
                {countEntries.map(([key, value]) => (
                  <View key={key} style={styles.countCard}>
                    <Text style={styles.countValue}>{value}</Text>
                    <Text style={styles.countLabel}>{humanize(key)}</Text>
                  </View>
                ))}
              </View>

              <View style={styles.boundaryCard}>
                <Text style={styles.sectionEyebrow}>INTERPRETATION BOUNDARIES</Text>
                {policyNotes.map((note) => (
                  <View key={note} style={styles.policyRow}>
                    <View style={styles.dot} />
                    <Text style={styles.policyText}>{note}</Text>
                  </View>
                ))}
              </View>

              <View style={styles.sectionHeading}>
                <Text style={styles.sectionTitle}>Related intelligence</Text>
                <Text style={styles.sectionCount}>{relations.length}</Text>
              </View>
              <View style={styles.list}>
                {relations.length ? relations.map((relation) => (
                  <Pressable
                    key={`${relation.kind}:${relation.id}`}
                    onPress={() =>
                      router.push(sourceReporterRoute(relation.kind, relation.id))
                    }
                    style={styles.relationCard}
                  >
                    <View style={styles.relationTop}>
                      <Text style={styles.relationKind}>{relation.kind.toUpperCase()}</Text>
                      <Text style={styles.arrow}>→</Text>
                    </View>
                    <Text style={styles.relationTitle}>{relation.title}</Text>
                    {relation.subtitle ? (
                      <Text style={styles.muted}>{relation.subtitle}</Text>
                    ) : null}
                  </Pressable>
                )) : (
                  <Text style={styles.muted}>No related canonical objects are exposed yet.</Text>
                )}
              </View>

              <View style={styles.sectionHeading}>
                <Text style={styles.sectionTitle}>Persisted chronology</Text>
                <Text style={styles.sectionCount}>{data.events.length}</Text>
              </View>
              <Text style={styles.timelineNote}>
                Ordering reflects domain occurrence time. It does not imply truth, reliability, novelty or independent corroboration.
              </Text>
              <View style={styles.list}>
                {data.events.map((event, index) => {
                  const details = sourceReporterEventDetails(event);
                  return (
                    <View
                      key={`${event.type}:${event.id ?? index}:${event.occurred_at}`}
                      style={styles.eventCard}
                    >
                      <View style={styles.eventTop}>
                        <Text style={styles.eventType}>{humanize(event.type)}</Text>
                        <Text style={styles.eventTime}>{formatDate(event.occurred_at)}</Text>
                      </View>
                      {details.map((detail) => (
                        <View key={detail.label} style={styles.detailRow}>
                          <Text style={styles.detailLabel}>{detail.label}</Text>
                          <Text style={styles.detailValue}>{detail.value}</Text>
                        </View>
                      ))}
                    </View>
                  );
                })}
              </View>

              {data.pagination.next_cursor ? (
                <Pressable
                  disabled={isLoadingMore}
                  onPress={() => void loadMore()}
                  style={styles.moreButton}
                >
                  {isLoadingMore ? (
                    <ActivityIndicator color={COLORS.text} />
                  ) : (
                    <Text style={styles.secondaryText}>Load more history</Text>
                  )}
                </Pressable>
              ) : null}

              {message ? <Text style={styles.message}>{message}</Text> : null}
            </>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const makeStyles = (COLORS: Record<string,string>) => StyleSheet.create({
  screen: { backgroundColor: COLORS.background, flex: 1 },
  safeArea: { flex: 1 },
  content: {
    alignSelf: 'center',
    maxWidth: 820,
    paddingBottom: 44,
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
  backText: { color: COLORS.text, fontSize: 12, fontWeight: '700' },
  kindBadge: {
    backgroundColor: COLORS.accentSoft,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  kindText: { color: COLORS.accent, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  loadingState: { alignItems: 'center', gap: 10, paddingVertical: 70 },
  eyebrow: { color: COLORS.accent, fontSize: 10, fontWeight: '800', letterSpacing: 1.6 },
  title: { color: COLORS.text, fontSize: 34, fontWeight: '800', lineHeight: 42, marginTop: 9 },
  subtitle: { color: COLORS.muted, fontSize: 14, lineHeight: 21, marginTop: 8 },
  muted: { color: COLORS.muted, fontSize: 13, lineHeight: 19 },
  timeGrid: { flexDirection: 'row', gap: 12, marginTop: 20 },
  timeCell: { backgroundColor: COLORS.surface, borderColor: COLORS.border, borderRadius: 14, borderWidth: 1, flex: 1, padding: 14 },
  label: { color: COLORS.muted, fontSize: 9, fontWeight: '800', letterSpacing: 1 },
  value: { color: COLORS.text, fontSize: 12, fontWeight: '700', marginTop: 6 },
  boundaryCard: { backgroundColor: COLORS.surface, borderColor: COLORS.border, borderRadius: 18, borderWidth: 1, marginTop: 20, padding: 16 },
  boundaryCopy: { color: COLORS.text, fontSize: 13, lineHeight: 20, marginTop: 8 },
  sectionEyebrow: { color: COLORS.accent, fontSize: 9, fontWeight: '800', letterSpacing: 1.3 },
  sectionHeading: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between', marginTop: 28, marginBottom: 12 },
  sectionTitle: { color: COLORS.text, fontSize: 19, fontWeight: '800' },
  sectionCount: { color: COLORS.accent, fontSize: 16, fontWeight: '800' },
  countGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  countCard: { backgroundColor: COLORS.raised, borderColor: COLORS.border, borderRadius: 14, borderWidth: 1, minWidth: 138, padding: 13 },
  countValue: { color: COLORS.text, fontSize: 22, fontWeight: '800' },
  countLabel: { color: COLORS.muted, fontSize: 9, fontWeight: '700', lineHeight: 14, marginTop: 5 },
  policyRow: { alignItems: 'flex-start', flexDirection: 'row', gap: 9, marginTop: 10 },
  dot: { backgroundColor: COLORS.accent, borderRadius: 4, height: 6, marginTop: 6, width: 6 },
  policyText: { color: COLORS.muted, flex: 1, fontSize: 12, lineHeight: 18 },
  list: { gap: 10 },
  relationCard: { backgroundColor: COLORS.surface, borderColor: COLORS.border, borderRadius: 16, borderWidth: 1, padding: 15 },
  relationTop: { alignItems: 'center', flexDirection: 'row', justifyContent: 'space-between' },
  relationKind: { color: COLORS.accent, fontSize: 9, fontWeight: '800', letterSpacing: 1.1 },
  relationTitle: { color: COLORS.text, fontSize: 15, fontWeight: '700', lineHeight: 21, marginTop: 8 },
  arrow: { color: COLORS.muted, fontSize: 16 },
  timelineNote: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginBottom: 12 },
  eventCard: { backgroundColor: COLORS.surface, borderColor: COLORS.border, borderRadius: 16, borderWidth: 1, padding: 15 },
  eventTop: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  eventType: { color: COLORS.text, flex: 1, fontSize: 11, fontWeight: '800' },
  eventTime: { color: COLORS.muted, fontSize: 10 },
  detailRow: { borderTopColor: COLORS.border, borderTopWidth: 1, marginTop: 10, paddingTop: 9 },
  detailLabel: { color: COLORS.muted, fontSize: 9, fontWeight: '700' },
  detailValue: { color: COLORS.text, fontSize: 12, lineHeight: 18, marginTop: 3 },
  moreButton: { alignItems: 'center', borderColor: COLORS.border, borderRadius: 12, borderWidth: 1, marginTop: 16, padding: 13 },
  secondaryButton: { alignSelf: 'flex-start', borderColor: COLORS.border, borderRadius: 10, borderWidth: 1, marginTop: 14, paddingHorizontal: 13, paddingVertical: 10 },
  secondaryText: { color: COLORS.text, fontSize: 12, fontWeight: '700' },
  errorCard: { backgroundColor: COLORS.surface, borderColor: 'rgba(255, 140, 140, 0.35)', borderRadius: 18, borderWidth: 1, padding: 20 },
  errorTitle: { color: COLORS.error, fontSize: 18, fontWeight: '800', marginBottom: 8 },
  message: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 14 },
});
