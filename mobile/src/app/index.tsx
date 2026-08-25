import {
  useEffect,
  useState,
} from 'react';

import * as Sharing from 'expo-sharing';

import {
  useLocalSearchParams,
} from 'expo-router';

import {
  analyzeArticle,
  analyzeVideo,
  getApiHealth,
  resolveContent,
  type ArticleAnalyzeResponse,
  type VideoAnalyzeResponse,
} from '../lib/api';

import {
  getArticleGradientFixture,
} from '../lib/article-gradient-fixtures';

import {
  ArticleAnalysisResults,
} from '../components/article-analysis-results';

import {
  VideoAnalysisResults,
} from '../components/video-analysis-results';

import {
  fetchYouTubeTranscript,
  fetchYouTubeVideoTitle,
} from '../lib/youtube-transcript';

import {
  Image,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from 'react-native';

import {
  SafeAreaView,
} from 'react-native-safe-area-context';


const COLORS = {
  background: '#090b0a',
  surface: '#0f120f',
  line: '#2b312c',
  lineSoft: '#1d221e',
  text: '#f2f3ef',
  muted: '#b2b8b3',
  mutedStrong: '#d0d4d0',
  accent: '#b5f36b',
  accentInk: '#14200c',
  warning: '#e2b85f',
  error: '#e77878',
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
  ).trim();
}


function validHttpUrl(
  value: string,
) {
  return /^https?:\/\/\S+$/i.test(
    value,
  );
}


function isYouTubeUrl(
  value: string,
) {
  return /(?:youtube(?:-nocookie)?\.com|youtu\.be)/i.test(
    value,
  );
}


export default function HomeScreen() {
  const {
    width,
  } = useWindowDimensions();

  const [
    layoutReady,
    setLayoutReady,
  ] =
    useState(false);


  const isWide =
    layoutReady &&
    width >= 920;

  const isCompact =
    !layoutReady ||
    width < 620;


  const params =
    useLocalSearchParams<{
      shared?: string | string[];
      mode?: string | string[];
    }>();


  const [
    link,
    setLink,
  ] =
    useState('');


  const [
    message,
    setMessage,
  ] =
    useState('');


  const [
    isResolving,
    setIsResolving,
  ] =
    useState(false);


  const [
    articleResult,
    setArticleResult,
  ] =
    useState<
      ArticleAnalyzeResponse | null
    >(null);


  const [
    videoResult,
    setVideoResult,
  ] =
    useState<
      VideoAnalyzeResponse | null
    >(null);


  const [
    videoTranscriptMeta,
    setVideoTranscriptMeta,
  ] =
    useState<{
      segmentCount: number;
      characterCount: number;
    } | null>(
      null,
    );


  const [
    apiState,
    setApiState,
  ] =
    useState<
      'checking'
      | 'online'
      | 'offline'
    >(
      'checking',
    );


  useEffect(
    () => {
      setLayoutReady(true);
    },
    [],
  );


  useEffect(
    () => {
      let active = true;

      getApiHealth()
        .then(
          (
            health,
          ) => {
            if (!active) {
              return;
            }

            setApiState(
              health.ok
                ? 'online'
                : 'offline',
            );
          },
        )
        .catch(
          () => {
            if (active) {
              setApiState(
                'offline',
              );
            }
          },
        );

      return () => {
        active = false;
      };
    },
    [],
  );


  useEffect(
    () => {
      const sharedValue =
        Array.isArray(
          params.shared,
        )
          ? params.shared[0]
          : params.shared;

      if (!sharedValue) {
        return;
      }

      setLink(
        sharedValue,
      );

      setMessage(
        'Shared source ready for analysis.',
      );

      void Sharing
        .clearSharedPayloads();
    },
    [
      params.shared,
    ],
  );


  async function analyzeSource() {
    const value =
      clean(link);

    if (
      !value
      ||
      !validHttpUrl(value)
    ) {
      setMessage(
        'Enter a complete http:// or https:// source URL.',
      );

      return;
    }


    setArticleResult(
      null,
    );

    setVideoResult(
      null,
    );

    setVideoTranscriptMeta(
      null,
    );

    setIsResolving(
      true,
    );


    try {
      if (
        isYouTubeUrl(
          value,
        )
      ) {
        setMessage(
          'Preparing the source transcript...',
        );


        const [
          transcript,
          videoTitle,
        ] =
          await Promise.all([
            fetchYouTubeTranscript(
              value,
            ),

            fetchYouTubeVideoTitle(
              value,
            ).catch(
              () =>
                'YouTube source',
            ),
          ]);


        setMessage(
          'Source resolved - running video intelligence...',
        );


        const result =
          await analyzeVideo({
            title:
              videoTitle,

            transcript:
              transcript.transcript,

            url:
              value,

            transcript_metadata: {
              segment_count:
                transcript.segmentCount,

              character_count:
                transcript.characterCount,

              language:
                transcript.language
                || undefined,

              extraction_method:
                'youtube-transcript-mobile',
            },
          });


        setVideoResult(
          result,
        );


        setVideoTranscriptMeta({
          segmentCount:
            transcript.segmentCount,

          characterCount:
            transcript.characterCount,
        });


        setMessage(
          'Video analysis complete.',
        );

        return;
      }


      setMessage(
        'Resolving the source...',
      );


      const resolved =
        await resolveContent(
          value,
        );


      if (
        resolved.source !==
          'article'
        ||
        resolved.mode !==
          'article'
      ) {
        throw new Error(
          'Sportabase could not resolve this source as a supported article.',
        );
      }


      const articleTitle =
        clean(
          resolved.title,
        )
        ||
        'Untitled article';


      setMessage(
        `Source resolved - ${resolved.content_characters.toLocaleString()} readable characters - analyzing...`,
      );


      const analysisUrl =
        clean(
          resolved.normalized_url,
        )
        ||
        value;


      const fixtureResult =
        getArticleGradientFixture({
          url:
            analysisUrl,

          title:
            articleTitle,

          text:
            resolved.content,
        });


      if (
        fixtureResult
      ) {
        setArticleResult(
          fixtureResult,
        );

        setMessage(
          `Local evaluation fixture - ${fixtureResult.merit_score}/100 - provider bypassed.`,
        );

        return;
      }


      const result =
        await analyzeArticle({
          title:
            articleTitle,

          url:
            analysisUrl,

          text:
            resolved.content,

          max_bullets:
            3,
        });


      setArticleResult(
        result,
      );


      setMessage(
        'Article analysis complete.',
      );
    }
    catch (error) {
      const detail =
        error instanceof Error
          ? error.message
          : 'The source could not be analyzed.';

      setMessage(
        `Analysis unavailable: ${detail}`,
      );
    }
    finally {
      setIsResolving(
        false,
      );
    }
  }


  const hasLink =
    clean(link).length > 0;


  const hasResults =
    Boolean(
      articleResult
      ||
      (
        videoResult
        &&
        videoTranscriptMeta
      ),
    );


  const messageIsError =
    /unavailable|enter a complete|could not|not supported|failed/i.test(
      message,
    );


  const apiLabel =
    apiState ===
      'checking'
      ? 'Checking'
      : apiState ===
          'online'
        ? 'Connected'
        : 'Offline';


  return (
    <View
      style={
        styles.screen
      }
    >
      <SafeAreaView
        style={
          styles.safeArea
        }
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={
            false
          }
          contentContainerStyle={
            styles.scrollContent
          }
        >
          <View
            style={
              styles.page
            }
          >
            <View
              style={
                styles.masthead
              }
            >
              <View
                style={
                  styles.brand
                }
              >
                <Image
                  source={
                    require(
                      '../../assets/images/sportabase-logo.png'
                    )
                  }
                  style={
                    styles.logo
                  }
                  resizeMode="contain"
                />

                <View>
                  <Text
                    style={
                      styles.brandName
                    }
                  >
                    Sportabase
                  </Text>

                  <Text
                    style={
                      styles.brandDescriptor
                    }
                  >
                    Sports intelligence
                  </Text>
                </View>
              </View>


              <View
                style={
                  styles.apiState
                }
              >
                <View
                  style={[
                    styles.statusDot,

                    apiState ===
                      'offline'
                      &&
                      styles.statusDotOffline,

                    apiState ===
                      'checking'
                      &&
                      styles.statusDotChecking,
                  ]}
                />

                {!isCompact ? (
                  <Text
                    style={
                      styles.apiText
                    }
                  >
                    {apiLabel}
                  </Text>
                ) : null}
              </View>
            </View>


            {!hasResults ? (
              <View
                style={
                  styles.lead
                }
              >
                <Text
                  style={[
                    styles.headline,

                    isCompact
                      &&
                      styles.headlineCompact,
                  ]}
                >
                  Know what the story
                  {'\n'}
                  actually supports.
                </Text>


                <View
                  style={[
                    styles.leadLower,

                    isWide
                      &&
                      styles.leadLowerWide,
                  ]}
                >
                  <Text
                    style={
                      styles.leadCopy
                    }
                  >
                    Sportabase reads sports
                    reporting for informational
                    Merit, source support and
                    evidence before the reaction
                    becomes the story.
                  </Text>


                  <View
                    style={
                      styles.leadPrinciple
                    }
                  >
                    <Text
                      style={
                        styles.principleTitle
                      }
                    >
                      Merit and evidence are
                      different signals.
                    </Text>

                    <Text
                      style={
                        styles.principleCopy
                      }
                    >
                      A useful scoop can still be
                      unverified. Lack of
                      corroboration alone is not
                      treated as falsehood.
                    </Text>
                  </View>
                </View>
              </View>
            ) : null}


            <View
              style={[
                styles.sourceWorkspace,

                hasResults &&
                styles.sourceWorkspaceCompact,
              ]}
            >
              {!hasResults ? (
                <View
                  style={[
                    styles.workspaceHeading,

                    isWide &&
                    styles.workspaceHeadingWide,
                  ]}
                >
                  <View>
                    <Text
                      style={
                        styles.workspaceTitle
                      }
                    >
                      Analyze a source
                    </Text>

                    <Text
                      style={
                        styles.workspaceCopy
                      }
                    >
                      Paste a sports article or
                      YouTube link. Sportabase
                      routes it automatically.
                    </Text>
                  </View>
                </View>
              ) : null}


              <View
                style={[
                  styles.sourceBar,

                  isCompact
                    &&
                    styles.sourceBarCompact,
                ]}
              >
                <TextInput
                  value={
                    link
                  }
                  onChangeText={(
                    value,
                  ) => {
                    setLink(
                      value,
                    );

                    setMessage('');
                  }}
                  placeholder="Paste article or YouTube URL"
                  placeholderTextColor="#727a73"
                  keyboardType="url"
                  autoCapitalize="none"
                  autoCorrect={
                    false
                  }
                  style={
                    styles.sourceInput
                  }
                  onSubmitEditing={
                    () => {
                      if (
                        hasLink
                        &&
                        !isResolving
                      ) {
                        void analyzeSource();
                      }
                    }
                  }
                />


                {hasLink ? (
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel="Clear source URL"
                    onPress={
                      () => {
                        setLink('');
                        setMessage('');
                      }
                    }
                    style={({
                      pressed,
                    }) => [
                      styles.clearButton,

                      pressed
                        &&
                        styles.pressed,
                    ]}
                  >
                    <Text
                      style={
                        styles.clearText
                      }
                    >
                      Clear
                    </Text>
                  </Pressable>
                ) : null}


                <Pressable
                  accessibilityRole="button"
                  disabled={
                    !hasLink
                    ||
                    isResolving
                  }
                  onPress={
                    () => {
                      void analyzeSource();
                    }
                  }
                  style={({
                    pressed,
                  }) => [
                    styles.analyzeButton,

                    (
                      !hasLink
                      ||
                      isResolving
                    )
                      &&
                      styles.analyzeButtonDisabled,

                    (
                      pressed
                      &&
                      hasLink
                      &&
                      !isResolving
                    )
                      &&
                      styles.analyzeButtonPressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.analyzeButtonText,
                      (!hasLink || isResolving) &&
                        styles.analyzeButtonTextDisabled,
                    ]}
                  >
                    {isResolving
                      ? 'Analyzing...'
                      : hasResults
                        ? 'Analyze another'
                        : 'Analyze source'}
                  </Text>

                  <Text
                    style={[
                      styles.analyzeArrow,
                      (!hasLink || isResolving) &&
                        styles.analyzeArrowDisabled,
                    ]}
                  >
                    →
                  </Text>
                </Pressable>
              </View>


              {!hasResults ? (
                <View
                  style={
                    styles.workspaceFooter
                  }
                >
                  <Text
                    style={[
                      styles.message,

                      messageIsError
                        ? styles.errorMessage
                        : styles.statusMessage,
                    ]}
                  >
                    {message
                      ||
                      'Analysis begins only after you submit the source.'}
                  </Text>
                </View>
              ) : null}


              {!hasResults ? (
                <View
                  style={
                    styles.intelligenceStrip
                  }
                >
                  {[
                    'Merit',
                    'Evidence',
                    'Independence',
                    'Claim status',
                  ].map(
                    (
                      signal
                    ) => (
                      <Text
                        key={
                          signal
                        }
                        style={
                          styles.intelligenceStripItem
                        }
                      >
                        {signal}
                      </Text>
                    ),
                  )}
                </View>
              ) : null}


            </View>


            {articleResult ? (
              <View
                style={
                  styles.resultsSection
                }
              >
                <ArticleAnalysisResults
                  result={
                    articleResult
                  }
                />
              </View>
            ) : null}


            {
              videoResult
              &&
              videoTranscriptMeta
                ? (
                  <View
                    style={
                      styles.resultsSection
                    }
                  >
                    <VideoAnalysisResults
                      result={
                        videoResult
                      }
                      transcript={
                        videoTranscriptMeta
                      }
                    />
                  </View>
                )
                : null
            }


            {!hasResults ? (
              <>
                <View
                  style={[
                    styles.methodSection,

                    isWide
                      &&
                      styles.methodSectionWide,
                  ]}
                >
                  <View
                    style={
                      styles.methodIntro
                    }
                  >
                    <Text
                      style={
                        styles.sectionHeading
                      }
                    >
                      Three questions,
                      one report.
                    </Text>

                    <Text
                      style={
                        styles.sectionCopy
                      }
                    >
                      Sportabase keeps the story,
                      its informational value and
                      its evidence state visible
                      at the same time.
                    </Text>
                  </View>


                  <View
                    style={
                      styles.methodRows
                    }
                  >
                    {[
                      [
                        '01',
                        'Reporting',
                        'What is this source actually saying?',
                      ],

                      [
                        '02',
                        'Merit',
                        'How much informational value does the reporting earn?',
                      ],

                      [
                        '03',
                        'Evidence',
                        'What does independent or authoritative evidence support?',
                      ],
                    ].map(
                      (
                        [
                          number,
                          title,
                          description,
                        ],
                      ) => (
                        <View
                          key={
                            number
                          }
                          style={
                            styles.methodRow
                          }
                        >
                          <Text
                            style={
                              styles.methodNumber
                            }
                          >
                            {number}
                          </Text>

                          <Text
                            style={
                              styles.methodTitle
                            }
                          >
                            {title}
                          </Text>

                          <Text
                            style={
                              styles.methodDescription
                            }
                          >
                            {description}
                          </Text>
                        </View>
                      ),
                    )}
                  </View>
                </View>


                <View
                  style={[
                    styles.shareStrip,

                    isWide
                      &&
                      styles.shareStripWide,
                  ]}
                >
                  <View>
                    <Text
                      style={
                        styles.shareTitle
                      }
                    >
                      Share directly to Sportabase
                    </Text>

                    <Text
                      style={
                        styles.shareCopy
                      }
                    >
                      On supported mobile
                      platforms, send the source
                      from the system Share menu
                      instead of copying its URL.
                    </Text>
                  </View>


                  <Text
                    style={
                      styles.shareFlow
                    }
                  >
                    Open source  →  Share  →  Sportabase
                  </Text>
                </View>
              </>
            ) : null}


            <View
              style={
                styles.footer
              }
            >
              <Text
                style={
                  styles.footerBrand
                }
              >
                Sportabase
              </Text>

              <Text
                style={
                  styles.footerCopy
                }
              >
                Evidence-first sports intelligence
              </Text>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}


const styles =
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor:
        COLORS.background,
    },

    safeArea: {
      flex: 1,
    },

    scrollContent: {
      flexGrow: 1,
      alignItems: 'center',
      paddingHorizontal: 22,
      paddingBottom: 44,
    },

    page: {
      width: '100%',
      maxWidth: 1240,
    },

    masthead: {
      minHeight: 76,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 24,
      borderBottomWidth: 1,
      borderBottomColor:
        COLORS.lineSoft,
    },

    brand: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 11,
    },

    logo: {
      width: 46,
      height: 46,
    },

    brandName: {
      color: COLORS.text,
      fontSize: 20,
      lineHeight: 22,
      fontWeight: '700',
      letterSpacing: -0.35,
    },

    brandDescriptor: {
      marginTop: 3,
      color: COLORS.muted,
      fontSize: 11,
      lineHeight: 14,
      fontWeight: '500',
    },

    apiState: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
    },

    statusDot: {
      width: 7,
      height: 7,
      borderRadius: 999,
      backgroundColor:
        COLORS.accent,
    },

    statusDotOffline: {
      backgroundColor:
        COLORS.error,
    },

    statusDotChecking: {
      backgroundColor:
        COLORS.warning,
    },

    apiText: {
      color:
        COLORS.mutedStrong,
      fontSize: 12,
      fontWeight: '600',
    },

    lead: {
      paddingTop: 82,
      paddingBottom: 54,
    },

    headline: {
      maxWidth: 880,
      color: COLORS.text,
      fontFamily:
        DISPLAY_FONT,
      fontSize: 62,
      lineHeight: 66,
      fontWeight: '400',
      letterSpacing: -1.2,
    },

    headlineCompact: {
      fontSize: 40,
      lineHeight: 44,
      letterSpacing: -0.6,
    },

    leadLower: {
      marginTop: 38,
      gap: 28,
    },

    leadLowerWide: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      justifyContent:
        'space-between',
    },

    leadCopy: {
      maxWidth: 650,
      color:
        COLORS.mutedStrong,
      fontSize: 17,
      lineHeight: 28,
    },

    leadPrinciple: {
      maxWidth: 360,
    },

    principleTitle: {
      color: COLORS.text,
      fontSize: 14,
      lineHeight: 20,
      fontWeight: '700',
    },

    principleCopy: {
      marginTop: 8,
      color: COLORS.muted,
      fontSize: 13,
      lineHeight: 21,
    },

    sourceWorkspace: {
      paddingTop: 28,
      paddingBottom: 28,
      borderTopWidth: 1,
      borderTopColor:
        COLORS.line,
      borderBottomWidth: 1,
      borderBottomColor:
        COLORS.line,
    },

    sourceWorkspaceCompact: {
      paddingTop: 14,
      paddingBottom: 14,
    },

    workspaceHeading: {
      gap: 12,
      marginBottom: 18,
    },

    workspaceHeadingWide: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      justifyContent:
        'space-between',
    },

    workspaceTitle: {
      color: COLORS.text,
      fontSize: 22,
      lineHeight: 27,
      fontWeight: '600',
      letterSpacing: -0.3,
    },

    workspaceCopy: {
      marginTop: 5,
      color: COLORS.muted,
      fontSize: 13,
      lineHeight: 20,
    },

    workspaceMeta: {
      color: COLORS.muted,
      fontSize: 12,
    },

    sourceBar: {
      minHeight: 62,
      flexDirection: 'row',
      alignItems: 'stretch',
      backgroundColor:
        '#0c0f0d',
      borderWidth: 1,
      borderColor:
        '#414941',
      borderRadius: 4,
      overflow: 'hidden',
    },

    sourceBarCompact: {
      flexWrap: 'wrap',
    },

    sourceInput: {
      flex: 1,
      minWidth: 220,
      minHeight: 60,
      paddingHorizontal: 16,
      color: COLORS.text,
      fontSize: 15,
      fontWeight: '400',
    },

    clearButton: {
      minHeight: 60,
      justifyContent: 'center',
      paddingHorizontal: 13,
    },

    clearText: {
      color: COLORS.muted,
      fontSize: 12,
      fontWeight: '600',
    },

    analyzeButton: {
      minHeight: 60,
      minWidth: 170,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 10,
      paddingHorizontal: 20,
      backgroundColor:
        COLORS.accent,
      borderLeftWidth: 1,
      borderLeftColor:
        COLORS.line,
    },

    analyzeButtonDisabled: {
      opacity: 1,
      backgroundColor: '#242a25',
    },

    analyzeButtonTextDisabled: {
      color: '#b8beb9',
    },

    analyzeArrowDisabled: {
      color: '#b8beb9',
    },

    analyzeButtonPressed: {
      opacity: 0.82,
    },

    analyzeButtonText: {
      color:
        COLORS.accentInk,
      fontSize: 14,
      fontWeight: '800',
    },

    analyzeArrow: {
      color:
        COLORS.accentInk,
      fontSize: 18,
      fontWeight: '700',
    },

    workspaceFooter: {
      marginTop: 12,
      flexDirection: 'row',
      alignItems:
        'flex-start',
      justifyContent:
        'space-between',
      gap: 20,
    },

    message: {
      flex: 1,
      fontSize: 12,
      lineHeight: 18,
      fontWeight: '500',
    },

    statusMessage: {
      color: COLORS.muted,
    },

    errorMessage: {
      color: COLORS.error,
    },

    supportedText: {
      color: COLORS.muted,
      fontSize: 12,
    },

    resultsSection: {
      paddingTop: 24,
      paddingBottom: 36,
    },

    intelligenceStrip: {
      minHeight: 46,
      flexDirection: 'row',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: 26,
      marginTop: 18,
      paddingTop: 14,
      borderTopWidth: 1,
      borderTopColor:
        COLORS.lineSoft,
    },

    intelligenceStripItem: {
      color:
        COLORS.mutedStrong,
      fontSize: 12,
      lineHeight: 18,
      fontWeight: '600',
    },

    methodSection: {
      paddingTop: 70,
      paddingBottom: 70,
      gap: 40,
      borderBottomWidth: 1,
      borderBottomColor:
        COLORS.lineSoft,
    },

    methodSectionWide: {
      flexDirection: 'row',
      alignItems:
        'flex-start',
      justifyContent:
        'space-between',
      gap: 72,
    },

    methodIntro: {
      flex: 1,
      maxWidth: 440,
    },

    sectionHeading: {
      color: COLORS.text,
      fontFamily:
        DISPLAY_FONT,
      fontSize: 32,
      lineHeight: 39,
      fontWeight: '400',
      letterSpacing: -0.35,
    },

    sectionCopy: {
      marginTop: 13,
      color: COLORS.muted,
      fontSize: 14,
      lineHeight: 22,
    },

    methodRows: {
      flex: 1,
      maxWidth: 620,
      borderTopWidth: 1,
      borderTopColor:
        COLORS.line,
    },

    methodRow: {
      minHeight: 88,
      flexDirection: 'row',
      alignItems:
        'flex-start',
      gap: 18,
      paddingVertical: 18,
      borderBottomWidth: 1,
      borderBottomColor:
        COLORS.line,
    },

    methodNumber: {
      width: 30,
      color:
        COLORS.accent,
      fontSize: 11,
      fontWeight: '700',
    },

    methodTitle: {
      width: 92,
      color: COLORS.text,
      fontSize: 14,
      fontWeight: '700',
    },

    methodDescription: {
      flex: 1,
      color: COLORS.muted,
      fontSize: 13,
      lineHeight: 20,
    },

    shareStrip: {
      paddingTop: 34,
      paddingBottom: 34,
      gap: 22,
      borderBottomWidth: 1,
      borderBottomColor:
        COLORS.lineSoft,
    },

    shareStripWide: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent:
        'space-between',
    },

    shareTitle: {
      color: COLORS.text,
      fontSize: 17,
      fontWeight: '700',
    },

    shareCopy: {
      maxWidth: 570,
      marginTop: 6,
      color: COLORS.muted,
      fontSize: 13,
      lineHeight: 20,
    },

    shareFlow: {
      color:
        COLORS.mutedStrong,
      fontSize: 12,
      fontWeight: '600',
    },

    footer: {
      minHeight: 86,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent:
        'space-between',
      gap: 20,
    },

    footerBrand: {
      color: COLORS.text,
      fontSize: 12,
      fontWeight: '700',
    },

    footerCopy: {
      color: COLORS.muted,
      fontSize: 12,
    },

    pressed: {
      opacity: 0.72,
    },
  });
