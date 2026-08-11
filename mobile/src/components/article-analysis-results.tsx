import {
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { LinearGradient } from 'expo-linear-gradient';

import type {
  ArticleAnalyzeResponse,
} from '../lib/api';

import {
  clampScore,
  getScoreTheme,
} from '../theme/score-theme';

type ArticleAnalysisResultsProps = {
  result: ArticleAnalyzeResponse;
};

const COLORS = {
  surface: '#101412',
  surfaceRaised: '#171c19',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  accent: '#76f53f',
  accentSoft: 'rgba(118, 245, 63, 0.12)',
};


function humanizeLabel(value: string) {
  const normalized = String(
    value || 'Analysis complete',
  )
    .trim()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ');

  return normalized.replace(
    /\b\w/g,
    (character) => character.toUpperCase(),
  );
}

export function ArticleAnalysisResults({
  result,
}: ArticleAnalysisResultsProps) {
  const meritScore = clampScore(
    result.merit_score,
  );

  const scoreTheme = getScoreTheme(
    meritScore,
  );

  const articleType =
    result.localized_article_type.trim() ||
    result.article_type_label.trim() ||
    humanizeLabel(result.article_type);

  const summaryItems = Array.isArray(result.tldr)
    ? result.tldr.filter(
        (item) => item.trim().length > 0,
      )
    : [];

  const localizedReasons =
    Array.isArray(result.localized_reasons)
      ? result.localized_reasons.filter(
          (item) => item.trim().length > 0,
        )
      : [];

  const reasons =
    localizedReasons.length > 0
      ? localizedReasons
      : Array.isArray(result.reasons)
        ? result.reasons.filter(
            (item) => item.trim().length > 0,
          )
        : [];

  const badge =
    result.badge.trim() ||
    'Analysis complete';

  return (
    <View style={styles.container}>
      <LinearGradient
        colors={[
          `${scoreTheme.start}30`,
          `${scoreTheme.end}18`,
          COLORS.surface,
        ]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={[
          styles.scoreCard,
          {
            borderColor: `${scoreTheme.start}88`,
          },
        ]}
      >
        <View style={styles.scoreTop}>
          <View>
            <Text
              style={[
                styles.eyebrow,
                {
                  color: scoreTheme.start,
                },
              ]}
            >
              MERIT SCORE
            </Text>

            <View style={styles.scoreRow}>
              <Text style={styles.score}>
                {meritScore}
              </Text>

              <Text style={styles.scoreMaximum}>
                /100
              </Text>
            </View>
          </View>

          <View
            style={[
              styles.badgePill,
              {
                borderColor: `${scoreTheme.end}66`,
              },
            ]}
          >
            <Text style={styles.badgeText}>
              {badge}
            </Text>
          </View>
        </View>

        <View style={styles.scoreTrack}>
          <LinearGradient
            colors={[
              scoreTheme.start,
              scoreTheme.end,
            ]}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 0 }}
            style={[
              styles.scoreFill,
              {
                width: `${meritScore}%`,
              },
            ]}
          />
        </View>

        <Text style={styles.articleTitle}>
          {result.title}
        </Text>

        <View
          style={[
            styles.typePill,
            {
              borderColor: `${scoreTheme.start}66`,
            },
          ]}
        >
          <Text style={styles.typeText}>
            {articleType}
          </Text>
        </View>
      </LinearGradient>

      <View style={styles.detailCard}>
        <Text
          style={[
            styles.sectionLabel,
            {
              color: scoreTheme.start,
            },
          ]}
        >
          TLDR
        </Text>

        {summaryItems.length > 0 ? (
          summaryItems.map((item, index) => (
            <View
              key={`${index}-${item}`}
              style={styles.listItem}
            >
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor:
                      scoreTheme.start,
                  },
                ]}
              />

              <Text style={styles.detailText}>
                {item}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>
            No summary was returned.
          </Text>
        )}
      </View>

      <View style={styles.detailCard}>
        <Text
          style={[
            styles.sectionLabel,
            {
              color: scoreTheme.start,
            },
          ]}
        >
          WHY THIS SCORE
        </Text>

        {reasons.length > 0 ? (
          reasons.map((item, index) => (
            <View
              key={`${index}-${item}`}
              style={styles.listItem}
            >
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor:
                      scoreTheme.start,
                  },
                ]}
              />

              <Text style={styles.detailText}>
                {item}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>
            No score explanation was returned.
          </Text>
        )}
      </View>

      <View style={styles.metaCard}>
        <View style={styles.metaItem}>
          <Text style={styles.metaLabel}>
            TYPE
          </Text>

          <Text style={styles.metaValue}>
            {articleType}
          </Text>
        </View>

        <View style={styles.metaItem}>
          <Text style={styles.metaLabel}>
            CONFIDENCE
          </Text>

          <Text style={styles.metaValue}>
            {Math.round(
              Math.max(
                0,
                Math.min(
                  1,
                  result.type_confidence || 0,
                ),
              ) * 100,
            )}
            %
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 14,
  },
  scoreCard: {
    padding: 22,
    borderRadius: 24,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    elevation: 5,
  },
  scoreTop: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 18,
  },
  eyebrow: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.4,
  },
  scoreRow: {
    marginTop: 6,
    flexDirection: 'row',
    alignItems: 'flex-end',
  },
  score: {
    color: COLORS.text,
    fontSize: 52,
    lineHeight: 56,
    fontWeight: '900',
    letterSpacing: -2,
  },
  scoreMaximum: {
    marginBottom: 8,
    color: COLORS.muted,
    fontSize: 15,
    fontWeight: '700',
  },
  badgePill: {
    maxWidth: '48%',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  badgeText: {
    color: COLORS.text,
    fontSize: 11,
    lineHeight: 15,
    fontWeight: '800',
    textAlign: 'center',
  },
  scoreTrack: {
    height: 7,
    marginTop: 18,
    overflow: 'hidden',
    borderRadius: 999,
    backgroundColor: COLORS.surfaceRaised,
  },
  scoreFill: {
    height: '100%',
    borderRadius: 999,
  },
  articleTitle: {
    marginTop: 18,
    color: COLORS.text,
    fontSize: 18,
    lineHeight: 26,
    fontWeight: '800',
  },
  typePill: {
    alignSelf: 'flex-start',
    marginTop: 12,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  typeText: {
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: '800',
  },
  detailCard: {
    padding: 20,
    borderRadius: 22,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  sectionLabel: {
    color: COLORS.accent,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1.3,
  },
  listItem: {
    marginTop: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  dot: {
    width: 7,
    height: 7,
    marginTop: 7,
    borderRadius: 999,
    backgroundColor: COLORS.accent,
  },
  detailText: {
    flex: 1,
    color: COLORS.text,
    fontSize: 14,
    lineHeight: 22,
  },
  emptyText: {
    marginTop: 14,
    color: COLORS.muted,
    fontSize: 14,
    lineHeight: 22,
  },
  metaCard: {
    flexDirection: 'row',
    gap: 12,
  },
  metaItem: {
    flex: 1,
    padding: 18,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  metaLabel: {
    color: COLORS.muted,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1.2,
  },
  metaValue: {
    marginTop: 8,
    color: COLORS.text,
    fontSize: 14,
    lineHeight: 20,
    fontWeight: '800',
  },
});