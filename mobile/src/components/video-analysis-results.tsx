import {
  Platform,
  StyleSheet,
  Text,
  useWindowDimensions,
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
  line: '#2b312c',
  lineSoft: '#1d221e',
  text: '#f2f3ef',
  muted: '#a6ada7',
  mutedStrong: '#c9ceca',
  accent: '#b5f36b',
};


const DISPLAY_FONT =
  Platform.select({
    web: 'Georgia',
    ios: 'Georgia',
    default: 'serif',
  }) ?? 'serif';


function clean(
  value: unknown,
) {
  return String(
    value ?? '',
  )
    .trim()
    .replace(
      /\s+/g,
      ' ',
    );
}


function clampScore(
  value: number,
) {
  if (
    !Number.isFinite(
      value,
    )
  ) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(
        value,
      ),
    ),
  );
}


function humanizeLabel(
  value: unknown,
) {
  const normalized =
    clean(value)
      .replace(
        /[_-]+/g,
        ' ',
      );

  if (!normalized) {
    return 'Analysis complete';
  }

  return normalized.replace(
    /\b\w/g,
    (character) =>
      character.toUpperCase(),
  );
}


export function VideoAnalysisResults({
  result,
  transcript,
}: VideoAnalysisResultsProps) {
  const {
    width,
  } =
    useWindowDimensions();

  const isWide =
    width >= 900;


  const evidenceScore =
    clampScore(
      result.evidence_score,
    );


  const logicScore =
    clampScore(
      result.logic_score,
    );


  const supportScore =
    Math.round(
      (
        evidenceScore
        +
        logicScore
      )
      / 2,
    );


  const verdict =
    clean(
      result.localized_verdict,
    )
    ||
    humanizeLabel(
      result.verdict,
    );


  const contentType =
    clean(
      result.localized_content_type,
    )
    ||
    humanizeLabel(
      result.content_type,
    );


  const claim =
    clean(
      result.claim,
    )
    ||
    'No central claim was returned.';


  const evidenceItems =
    Array.isArray(
      result.evidence_used,
    )
      ? result.evidence_used
          .map(clean)
          .filter(Boolean)
      : [];


  const evidenceLabel =
    clean(
      result.ui_labels
        .evidence_used,
    )
    ||
    'Evidence used';


  const logicLabel =
    clean(
      result.ui_labels
        .logic_check,
    )
    ||
    'Logic check';


  const hypeLabel =
    clean(
      result.ui_labels
        .hype_check,
    )
    ||
    'Hype check';


  return (
    <View
      style={
        styles.report
      }
    >
      <View
        style={
          styles.reportHeader
        }
      >
        <View
          style={
            styles.metaRow
          }
        >
          <Text
            style={
              styles.metaStrong
            }
          >
            Video analysis
          </Text>

          <Text
            style={
              styles.metaText
            }
          >
            {contentType}
          </Text>

          <Text
            style={
              styles.metaText
            }
          >
            {transcript
              .segmentCount
              .toLocaleString()} transcript segments
          </Text>

          <Text
            style={
              styles.metaText
            }
          >
            {transcript
              .characterCount
              .toLocaleString()} characters
          </Text>
        </View>


        <Text
          style={
            styles.reportTitle
          }
        >
          {claim}
        </Text>
      </View>


      <View
        style={[
          styles.signalGrid,

          isWide
            &&
            styles.signalGridWide,
        ]}
      >
        <View
          style={[
            styles.signalPanel,

            isWide
              &&
              styles.signalPanelFirst,
          ]}
        >
          <Text
            style={
              styles.signalLabel
            }
          >
            Overall support
          </Text>

          <Text
            style={
              styles.signalDescription
            }
          >
            Combined evidence and logic assessment.
          </Text>


          <View
            style={
              styles.scoreRow
            }
          >
            <Text
              style={
                styles.score
              }
            >
              {supportScore}
            </Text>

            <Text
              style={
                styles.scoreMaximum
              }
            >
              /100
            </Text>
          </View>


          <View
            style={
              styles.scoreTrack
            }
          >
            <View
              style={[
                styles.scoreFill,

                {
                  flex:
                    supportScore,
                },
              ]}
            />

            <View
              style={{
                flex:
                  100
                  -
                  supportScore,
              }}
            />
          </View>
        </View>


        <View
          style={
            styles.signalPanel
          }
        >
          <Text
            style={
              styles.signalLabel
            }
          >
            Verdict
          </Text>

          <Text
            style={
              styles.signalDescription
            }
          >
            Structured reading of the video's
            support and reasoning.
          </Text>


          <Text
            style={
              styles.verdict
            }
          >
            {verdict}
          </Text>
        </View>
      </View>


      <View
        style={
          styles.metricRow
        }
      >
        <View
          style={
            styles.metric
          }
        >
          <Text
            style={
              styles.metricLabel
            }
          >
            Evidence
          </Text>

          <View
            style={
              styles.metricValueRow
            }
          >
            <Text
              style={
                styles.metricScore
              }
            >
              {evidenceScore}
            </Text>

            <Text
              style={
                styles.metricMaximum
              }
            >
              /100
            </Text>
          </View>
        </View>


        <View
          style={
            styles.metric
          }
        >
          <Text
            style={
              styles.metricLabel
            }
          >
            Logic
          </Text>

          <View
            style={
              styles.metricValueRow
            }
          >
            <Text
              style={
                styles.metricScore
              }
            >
              {logicScore}
            </Text>

            <Text
              style={
                styles.metricMaximum
              }
            >
              /100
            </Text>
          </View>
        </View>
      </View>


      <View
        style={
          styles.detailSection
        }
      >
        <View
          style={
            styles.sectionHeading
          }
        >
          <Text
            style={
              styles.sectionNumber
            }
          >
            01
          </Text>

          <Text
            style={
              styles.sectionTitle
            }
          >
            {evidenceLabel}
          </Text>
        </View>


        <View
          style={
            styles.sectionBody
          }
        >
          {(evidenceItems.length > 0
            ? evidenceItems
            : ['No specific supporting evidence was returned.']
          ).map(
            (
              item,
              index,
            ) => (
              <View
                key={
                  `${index}-${item}`
                }
                style={
                  styles.evidenceRow
                }
              >
                <View
                  style={
                    styles.evidenceMark
                  }
                />

                <Text
                  style={
                    styles.detailText
                  }
                >
                  {item}
                </Text>
              </View>
            ),
          )}
        </View>
      </View>


      <View
        style={
          styles.detailSection
        }
      >
        <View
          style={
            styles.sectionHeading
          }
        >
          <Text
            style={
              styles.sectionNumber
            }
          >
            02
          </Text>

          <Text
            style={
              styles.sectionTitle
            }
          >
            {logicLabel}
          </Text>
        </View>


        <Text
          style={
            styles.prose
          }
        >
          {clean(
            result.logic_check,
          )
          ||
          'No logic assessment was returned.'}
        </Text>
      </View>


      <View
        style={
          styles.detailSection
        }
      >
        <View
          style={
            styles.sectionHeading
          }
        >
          <Text
            style={
              styles.sectionNumber
            }
          >
            03
          </Text>

          <Text
            style={
              styles.sectionTitle
            }
          >
            {hypeLabel}
          </Text>
        </View>


        <Text
          style={
            styles.prose
          }
        >
          {clean(
            result.hype_check,
          )
          ||
          'No presentation assessment was returned.'}
        </Text>
      </View>
    </View>
  );
}


const styles =
  StyleSheet.create({
    report: {
      width:
        '100%',
    },

    reportHeader: {
      paddingTop:
        28,

      paddingBottom:
        30,

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.line,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },

    metaRow: {
      flexDirection:
        'row',

      flexWrap:
        'wrap',

      gap:
        16,
    },

    metaStrong: {
      color:
        COLORS.text,

      fontSize:
        12,

      fontWeight:
        '700',
    },

    metaText: {
      color:
        COLORS.muted,

      fontSize:
        12,

      fontWeight:
        '500',
    },

    reportTitle: {
      maxWidth:
        940,

      marginTop:
        20,

      color:
        COLORS.text,

      fontFamily:
        DISPLAY_FONT,

      fontSize:
        38,

      lineHeight:
        47,

      fontWeight:
        '400',

      letterSpacing:
        -0.55,
    },

    signalGrid: {
      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },

    signalGridWide: {
      flexDirection:
        'row',
    },

    signalPanel: {
      flex:
        1,

      paddingTop:
        28,

      paddingBottom:
        30,
    },

    signalPanelFirst: {
      paddingRight:
        36,

      marginRight:
        36,

      borderRightWidth:
        1,

      borderRightColor:
        COLORS.line,
    },

    signalLabel: {
      color:
        COLORS.text,

      fontSize:
        13,

      fontWeight:
        '700',
    },

    signalDescription: {
      maxWidth:
        500,

      marginTop:
        6,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        18,
    },

    scoreRow: {
      marginTop:
        20,

      flexDirection:
        'row',

      alignItems:
        'flex-end',
    },

    score: {
      color:
        COLORS.text,

      fontSize:
        66,

      lineHeight:
        68,

      fontWeight:
        '600',

      letterSpacing:
        -2,
    },

    scoreMaximum: {
      marginBottom:
        8,

      color:
        COLORS.muted,

      fontSize:
        14,

      fontWeight:
        '600',
    },

    scoreTrack: {
      height:
        3,

      marginTop:
        16,

      flexDirection:
        'row',

      backgroundColor:
        COLORS.lineSoft,

      overflow:
        'hidden',
    },

    scoreFill: {
      backgroundColor:
        COLORS.accent,
    },

    verdict: {
      maxWidth:
        580,

      marginTop:
        23,

      color:
        COLORS.text,

      fontFamily:
        DISPLAY_FONT,

      fontSize:
        31,

      lineHeight:
        39,

      fontWeight:
        '400',
    },

    metricRow: {
      flexDirection:
        'row',

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },

    metric: {
      flex:
        1,

      paddingTop:
        23,

      paddingBottom:
        25,

      borderRightWidth:
        1,

      borderRightColor:
        COLORS.lineSoft,
    },

    metricLabel: {
      color:
        COLORS.muted,

      fontSize:
        12,

      fontWeight:
        '600',
    },

    metricValueRow: {
      marginTop:
        7,

      flexDirection:
        'row',

      alignItems:
        'flex-end',
    },

    metricScore: {
      color:
        COLORS.text,

      fontSize:
        32,

      lineHeight:
        36,

      fontWeight:
        '600',
    },

    metricMaximum: {
      marginBottom:
        3,

      color:
        COLORS.muted,

      fontSize:
        11,

      fontWeight:
        '600',
    },

    detailSection: {
      paddingTop:
        29,

      paddingBottom:
        31,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },

    sectionHeading: {
      flexDirection:
        'row',

      alignItems:
        'flex-start',

      gap:
        14,
    },

    sectionNumber: {
      width:
        28,

      color:
        COLORS.accent,

      fontSize:
        11,

      fontWeight:
        '700',
    },

    sectionTitle: {
      flex:
        1,

      color:
        COLORS.text,

      fontSize:
        18,

      lineHeight:
        23,

      fontWeight:
        '700',

      letterSpacing:
        -0.25,
    },

    sectionBody: {
      marginTop:
        20,

      marginLeft:
        42,

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.lineSoft,
    },

    evidenceRow: {
      flexDirection:
        'row',

      alignItems:
        'flex-start',

      gap:
        12,

      paddingTop:
        14,

      paddingBottom:
        14,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.lineSoft,
    },

    evidenceMark: {
      width:
        7,

      height:
        2,

      marginTop:
        9,

      backgroundColor:
        COLORS.accent,
    },

    detailText: {
      flex:
        1,

      maxWidth:
        920,

      color:
        COLORS.mutedStrong,

      fontSize:
        14,

      lineHeight:
        23,
    },

    prose: {
      maxWidth:
        920,

      marginTop:
        20,

      marginLeft:
        42,

      color:
        COLORS.mutedStrong,

      fontSize:
        14,

      lineHeight:
        23,
    },
  });
