import {
  Platform,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';

import type {
  ArticleAnalyzeResponse,
} from '../lib/api';

import {
  normalizeArticleIntelligence,
} from '../lib/article-intelligence';

import {
  clampScore,
} from '../theme/score-theme';


type ArticleAnalysisResultsProps = {
  result: ArticleAnalyzeResponse;
};


const COLORS = {
  line: '#2b312c',
  lineSoft: '#1d221e',
  text: '#f2f3ef',
  muted: '#a6ada7',
  mutedStrong: '#c9ceca',
  accent: '#b5f36b',
  warning: '#e2b85f',
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


export function ArticleAnalysisResults({
  result,
}: ArticleAnalysisResultsProps) {
  const {
    width,
  } =
    useWindowDimensions();

  const isWide =
    width >= 900;


  const meritScore =
    clampScore(
      result.merit_score,
    );


  const articleType =
    clean(
      result.localized_article_type,
    )
    ||
    clean(
      result.article_type_label,
    )
    ||
    humanizeLabel(
      result.article_type,
    );


  const title =
    clean(
      result.title,
    )
    ||
    'Analyzed story';


  const badge =
    clean(
      result.badge,
    )
    ||
    'Analysis complete';


  const typeConfidence =
    Math.round(
      Math.max(
        0,
        Math.min(
          1,
          Number(
            result.type_confidence,
          )
          || 0,
        ),
      )
      * 100,
    );


  const summaryItems =
    Array.isArray(
      result.tldr,
    )
      ? result.tldr
          .map(clean)
          .filter(Boolean)
      : [];


  const localizedReasons =
    Array.isArray(
      result.localized_reasons,
    )
      ? result.localized_reasons
          .map(clean)
          .filter(Boolean)
      : [];


  const reasons =
    localizedReasons.length > 0
      ? localizedReasons
      : Array.isArray(
          result.reasons,
        )
        ? result.reasons
            .map(clean)
            .filter(Boolean)
        : [];


  const intelligence =
    normalizeArticleIntelligence(
      result.intelligence,
    );


  const evidenceStatus =
    !intelligence
      ? 'Not assessed'
      : intelligence.contested
        ? 'Contested'
        : intelligence.status ===
            'available'
          ? 'Assessed'
          : 'Limited';


  const evidenceStatusStyle =
    intelligence?.contested
      ? styles.evidenceWarning
      : intelligence?.status ===
          'available'
        ? styles.evidencePositive
        : styles.evidenceNeutral;


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
            Article analysis
          </Text>

          <Text
            style={
              styles.metaText
            }
          >
            {articleType}
          </Text>

          <Text
            style={
              styles.metaText
            }
          >
            Type confidence {typeConfidence}%
          </Text>

          <Text
            style={
              styles.metaText
            }
          >
            {badge}
          </Text>
        </View>


        <Text
          style={
            styles.reportTitle
          }
        >
          {title}
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
            Merit
          </Text>

          <Text
            style={
              styles.signalDescription
            }
          >
            Informational value of the reporting.
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
              {meritScore}
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
                    meritScore,
                },
              ]}
            />

            <View
              style={{
                flex:
                  100
                  -
                  meritScore,
              }}
            />
          </View>


          <Text
            style={
              styles.boundaryText
            }
          >
            Merit measures informational quality.
            It is not a probability that a claim
            is true.
          </Text>
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
            Evidence status
          </Text>

          <Text
            style={
              styles.signalDescription
            }
          >
            Current cross-source support and
            verification state.
          </Text>


          <Text
            style={[
              styles.evidenceValue,
              evidenceStatusStyle,
            ]}
          >
            {evidenceStatus}
          </Text>


          <Text
            style={
              styles.evidenceDetail
            }
          >
            {intelligence?.detail
              ||
              'No validated public evidence assessment was returned for this analysis.'}
          </Text>


          <View
            style={
              styles.impactRow
            }
          >
            <Text
              style={
                styles.impactLabel
              }
            >
              Merit impact
            </Text>

            <Text
              style={
                styles.impactValue
              }
            >
              {intelligence
                ?.affectsMeritScore
                ? 'Included in displayed Merit'
                : 'Informational only'}
            </Text>
          </View>
        </View>
      </View>


      <View
        style={[
          styles.bodyGrid,

          isWide
            &&
            styles.bodyGridWide,
        ]}
      >
        <View
          style={[
            styles.bodySection,

            isWide
              &&
              styles.bodySectionFirst,
          ]}
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

            <View
              style={
                styles.sectionHeadingCopy
              }
            >
              <Text
                style={
                  styles.sectionTitle
                }
              >
                What the story says
              </Text>

              <Text
                style={
                  styles.sectionDescription
                }
              >
                The shortest useful version
                of the reporting.
              </Text>
            </View>
          </View>


          <View
            style={
              styles.list
            }
          >
            {(summaryItems.length > 0
              ? summaryItems
              : ['No summary was returned.']
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
                    styles.listRow
                  }
                >
                  <View
                    style={
                      styles.listMark
                    }
                  />

                  <Text
                    style={
                      styles.listText
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
            styles.bodySection
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

            <View
              style={
                styles.sectionHeadingCopy
              }
            >
              <Text
                style={
                  styles.sectionTitle
                }
              >
                Why it earned this Merit
              </Text>

              <Text
                style={
                  styles.sectionDescription
                }
              >
                The factors that influenced
                the displayed score.
              </Text>
            </View>
          </View>


          <View
            style={
              styles.list
            }
          >
            {(reasons.length > 0
              ? reasons
              : ['No score explanation was returned.']
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
                    styles.listRow
                  }
                >
                  <View
                    style={
                      styles.listMark
                    }
                  />

                  <Text
                    style={
                      styles.listText
                    }
                  >
                    {item}
                  </Text>
                </View>
              ),
            )}
          </View>
        </View>
      </View>


      {intelligence ? (
        <View
          style={
            styles.evidenceSection
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

            <View
              style={
                styles.sectionHeadingCopy
              }
            >
              <Text
                style={
                  styles.sectionTitle
                }
              >
                {intelligence.label
                  ||
                  'Evidence intelligence'}
              </Text>

              <Text
                style={
                  styles.sectionDescription
                }
              >
                Evidence remains a separate
                signal from Merit.
              </Text>
            </View>
          </View>


          {intelligence.status ===
          'available' ? (
            <View
              style={
                styles.metricGrid
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
                  Corroboration
                </Text>

                <Text
                  style={
                    styles.metricValue
                  }
                >
                  {intelligence
                    .corroborationLabel}
                </Text>
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
                  Independence
                </Text>

                <Text
                  style={
                    styles.metricValue
                  }
                >
                  {intelligence
                    .independenceLabel}
                </Text>
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
                  Sources located
                </Text>

                <Text
                  style={
                    styles.metricValue
                  }
                >
                  {intelligence
                    .candidateCount}
                </Text>
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
                  Pairs checked
                </Text>

                <Text
                  style={
                    styles.metricValue
                  }
                >
                  {intelligence
                    .verificationPairs}
                </Text>
              </View>
            </View>
          ) : null}


          <Text
            style={
              styles.evidenceNote
            }
          >
            {intelligence
              .affectsMeritScore
              ? 'This validated evidence signal is included in the displayed Merit score.'
              : 'This evidence signal is informational and does not alter the displayed Merit score.'}
          </Text>
        </View>
      ) : null}
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
        39,

      lineHeight:
        47,

      fontWeight:
        '400',

      letterSpacing:
        -0.6,
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

    boundaryText: {
      maxWidth:
        450,

      marginTop:
        15,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        18,
    },

    evidenceValue: {
      marginTop:
        23,

      fontSize:
        38,

      lineHeight:
        43,

      fontWeight:
        '600',

      letterSpacing:
        -1,
    },

    evidencePositive: {
      color:
        COLORS.accent,
    },

    evidenceWarning: {
      color:
        COLORS.warning,
    },

    evidenceNeutral: {
      color:
        COLORS.mutedStrong,
    },

    evidenceDetail: {
      maxWidth:
        580,

      marginTop:
        12,

      color:
        COLORS.mutedStrong,

      fontSize:
        13,

      lineHeight:
        21,
    },

    impactRow: {
      marginTop:
        18,

      paddingTop:
        13,

      flexDirection:
        'row',

      justifyContent:
        'space-between',

      gap:
        18,

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.lineSoft,
    },

    impactLabel: {
      color:
        COLORS.muted,

      fontSize:
        12,
    },

    impactValue: {
      color:
        COLORS.text,

      fontSize:
        12,

      fontWeight:
        '600',
    },

    bodyGrid: {
      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },

    bodyGridWide: {
      flexDirection:
        'row',
    },

    bodySection: {
      flex:
        1,

      paddingTop:
        30,

      paddingBottom:
        34,
    },

    bodySectionFirst: {
      paddingRight:
        36,

      marginRight:
        36,

      borderRightWidth:
        1,

      borderRightColor:
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

    sectionHeadingCopy: {
      flex:
        1,
    },

    sectionTitle: {
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

    sectionDescription: {
      marginTop:
        5,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        18,
    },

    list: {
      marginTop:
        20,

      marginLeft:
        42,

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.lineSoft,
    },

    listRow: {
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

    listMark: {
      width:
        7,

      height:
        2,

      marginTop:
        9,

      backgroundColor:
        COLORS.accent,
    },

    listText: {
      flex:
        1,

      color:
        COLORS.mutedStrong,

      fontSize:
        14,

      lineHeight:
        22,
    },

    evidenceSection: {
      paddingTop:
        30,

      paddingBottom:
        32,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },

    metricGrid: {
      marginTop:
        24,

      marginLeft:
        42,

      flexDirection:
        'row',

      flexWrap:
        'wrap',

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.lineSoft,

      borderLeftWidth:
        1,

      borderLeftColor:
        COLORS.lineSoft,
    },

    metric: {
      minWidth:
        160,

      flex:
        1,

      padding:
        14,

      borderRightWidth:
        1,

      borderRightColor:
        COLORS.lineSoft,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.lineSoft,
    },

    metricLabel: {
      color:
        COLORS.muted,

      fontSize:
        11,

      fontWeight:
        '600',
    },

    metricValue: {
      marginTop:
        7,

      color:
        COLORS.text,

      fontSize:
        14,

      lineHeight:
        19,

      fontWeight:
        '600',
    },

    evidenceNote: {
      maxWidth:
        850,

      marginTop:
        16,

      marginLeft:
        42,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        18,
    },
  });
