import { useProductTheme, scaleStyles } from '../theme/product-theme';
﻿import {
  StyleSheet,
  Text,
  View,
} from 'react-native';

import type {
  VideoAnalyzeResponse,
} from '../lib/api';

type VideoAnalysisResultsProps = {
  result: VideoAnalyzeResponse;
  transcript: {
    segmentCount: number;
    characterCount: number;
  };
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

function clampScore(value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(value),
    ),
  );
}

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

export function VideoAnalysisResults({
  result,
  transcript,
}: VideoAnalysisResultsProps) {
  const { colors: COLORS,scale }=useProductTheme();
  const styles=scaleStyles(makeStyles(COLORS),scale);
  const evidenceScore = clampScore(
    result.evidence_score,
  );

  const logicScore = clampScore(
    result.logic_score,
  );


  const verdict =
    result.localized_verdict.trim() ||
    humanizeLabel(result.verdict);

  const contentType =
    result.localized_content_type.trim() ||
    humanizeLabel(result.content_type);

  const evidenceItems =
    Array.isArray(result.evidence_used)
      ? result.evidence_used.filter(
          (item) => item.trim().length > 0,
        )
      : [];

  return (
    <View style={styles.container}>
      <View style={styles.scoreCard}>
        <View style={styles.scoreTop}>
          <View><Text style={styles.eyebrow}>Verdict</Text></View>

          <View style={styles.verdictPill}>
            <Text style={styles.verdictText}>
              {verdict}
            </Text>
          </View>
        </View>

        <Text style={styles.transcriptMeta}>
          {transcript.segmentCount} transcript segments
          {' · '}
          {transcript.characterCount.toLocaleString()}
          {' '}
          characters analyzed
        </Text>
      </View>

      <View style={styles.claimCard}>
        <Text style={styles.sectionLabel}>
          {result.ui_labels.main_claim ||
            'MAIN CLAIM'}
        </Text>

        <Text style={styles.claimText}>
          {result.claim ||
            'No central claim was returned.'}
        </Text>

        <View style={styles.contentTypePill}>
          <Text style={styles.contentTypeText}>
            {contentType}
          </Text>
        </View>
      </View>

      <View style={styles.metricRow}>
        <View style={styles.metricCard}>
          <Text style={styles.metricLabel}>
            EVIDENCE
          </Text>

          <Text style={styles.metricScore}>
            {evidenceScore}
          </Text>

          <Text style={styles.metricMaximum}>
            /100
          </Text>
        </View>

        <View style={styles.metricCard}>
          <Text style={styles.metricLabel}>
            LOGIC
          </Text>

          <Text style={styles.metricScore}>
            {logicScore}
          </Text>

          <Text style={styles.metricMaximum}>
            /100
          </Text>
        </View>
      </View>

      <View style={styles.detailCard}>
        <Text style={styles.sectionLabel}>
          {result.ui_labels.evidence_used ||
            'EVIDENCE USED'}
        </Text>

        {evidenceItems.length > 0 ? (
          evidenceItems.map((item, index) => (
            <View
              key={`${index}-${item}`}
              style={styles.evidenceItem}
            >
              <View style={styles.evidenceDot} />

              <Text style={styles.detailText}>
                {item}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.detailText}>
            No specific supporting evidence was
            returned.
          </Text>
        )}
      </View>

      <View style={styles.detailCard}>
        <Text style={styles.sectionLabel}>
          {result.ui_labels.logic_check ||
            'LOGIC CHECK'}
        </Text>

        <Text style={styles.detailText}>
          {result.logic_check ||
            'No logic assessment was returned.'}
        </Text>
      </View>

      <View style={styles.detailCard}>
        <Text style={styles.sectionLabel}>
          {result.ui_labels.hype_check ||
            'HYPE CHECK'}
        </Text>

        <Text style={styles.detailText}>
          {result.hype_check ||
            'No presentation assessment was returned.'}
        </Text>
      </View>
    </View>
  );
}

const makeStyles = (COLORS: Record<string,string>) => StyleSheet.create({
  container: {
    gap: 14,
  },
  scoreCard: {
    padding: 22,
    borderRadius: 24,
    backgroundColor: COLORS.accentSoft,
    borderWidth: 1,
    borderColor: 'rgba(118, 245, 63, 0.36)',
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
  verdictPill: {
    maxWidth: '48%',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  verdictText: {
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
    backgroundColor: COLORS.accent,
  },
  transcriptMeta: {
    marginTop: 12,
    color: COLORS.muted,
    fontSize: 11,
    lineHeight: 16,
  },
  claimCard: {
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
  claimText: {
    marginTop: 12,
    color: COLORS.text,
    fontSize: 19,
    lineHeight: 28,
    fontWeight: '700',
  },
  contentTypePill: {
    alignSelf: 'flex-start',
    marginTop: 16,
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  contentTypeText: {
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: '800',
  },
  metricRow: {
    flexDirection: 'row',
    gap: 12,
  },
  metricCard: {
    flex: 1,
    padding: 18,
    borderRadius: 20,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  metricLabel: {
    color: COLORS.muted,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1.2,
  },
  metricScore: {
    marginTop: 8,
    color: COLORS.text,
    fontSize: 34,
    lineHeight: 38,
    fontWeight: '900',
  },
  metricMaximum: {
    color: COLORS.muted,
    fontSize: 11,
    fontWeight: '700',
  },
  detailCard: {
    padding: 20,
    borderRadius: 22,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  detailText: {
    flex: 1,
    color: COLORS.text,
    fontSize: 14,
    lineHeight: 22,
  },
  evidenceItem: {
    marginTop: 14,
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  evidenceDot: {
    width: 7,
    height: 7,
    marginTop: 7,
    borderRadius: 999,
    backgroundColor: COLORS.accent,
  },
});

