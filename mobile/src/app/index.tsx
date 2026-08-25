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


type AnalysisMode =
  'article'
  | 'video';


const COLORS = {
  background:
    '#0a0c0b',

  surface:
    '#111411',

  surfaceRaised:
    '#171a17',

  line:
    '#303631',

  lineSoft:
    '#222722',

  text:
    '#f4f5f1',

  muted:
    '#a6ada7',

  mutedStrong:
    '#c5cac6',

  accent:
    '#b5f36b',

  accentInk:
    '#13200b',

  warning:
    '#e5bd68',

  error:
    '#ef8989',
};


const FEATURES = [
  {
    number:
      '01',

    title:
      'Summary',

    description:
      'The reporting stripped down to the information that matters.',
  },

  {
    number:
      '02',

    title:
      'Merit',

    description:
      'A structured score for the informational value of the story.',
  },

  {
    number:
      '03',

    title:
      'Evidence',

    description:
      'Corroboration and source relationships shown separately from Merit.',
  },
];


export default function HomeScreen() {
  const {
    width,
  } = useWindowDimensions();

  const isWide =
    width >= 980;

  const isCompact =
    width < 620;


  const params =
    useLocalSearchParams<{
      shared?:
        string
        | string[];

      mode?:
        string
        | string[];
    }>();


  const [
    mode,
    setMode,
  ] =
    useState<AnalysisMode>(
      'article'
    );


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
      ArticleAnalyzeResponse
      | null
    >(null);


  const [
    videoResult,
    setVideoResult,
  ] =
    useState<
      VideoAnalyzeResponse
      | null
    >(null);


  const [
    videoTranscriptMeta,
    setVideoTranscriptMeta,
  ] =
    useState<{
      segmentCount: number;
      characterCount: number;
    } | null>(
      null
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
      'checking'
    );


  useEffect(
    () => {
      let active = true;

      getApiHealth()
        .then(
          (
            health
          ) => {
            if (!active) {
              return;
            }

            setApiState(
              health.ok
                ? 'online'
                : 'offline'
            );
          }
        )
        .catch(
          () => {
            if (active) {
              setApiState(
                'offline'
              );
            }
          }
        );

      return () => {
        active = false;
      };
    },
    []
  );


  useEffect(
    () => {
      const sharedValue =
        Array.isArray(
          params.shared
        )
          ? params.shared[0]
          : params.shared;

      const sharedMode =
        Array.isArray(
          params.mode
        )
          ? params.mode[0]
          : params.mode;

      if (!sharedValue) {
        return;
      }

      setLink(
        sharedValue
      );

      setMessage(
        'Shared content is ready for review.'
      );

      if (
        sharedMode ===
        'video'
      ) {
        setMode(
          'video'
        );
      } else {
        setMode(
          'article'
        );
      }

      Sharing
        .clearSharedPayloads();
    },
    [
      params.mode,
      params.shared,
    ]
  );


  function selectMode(
    nextMode:
      AnalysisMode
  ) {
    setMode(
      nextMode
    );

    setMessage('');

    setArticleResult(
      null
    );

    setVideoResult(
      null
    );

    setVideoTranscriptMeta(
      null
    );
  }


  async function validateLink() {
    const value =
      link.trim();

    if (
      !/^https?:\/\/\S+$/i
        .test(value)
    ) {
      setMessage(
        'Enter a complete link beginning with http:// or https://.'
      );

      return;
    }


    if (
      mode ===
        'video'
      &&
      !/youtube\.com|youtu\.be/i
        .test(value)
    ) {
      setMessage(
        'Video analysis currently supports YouTube links.'
      );

      return;
    }


    if (
      mode ===
      'article'
    ) {
      setArticleResult(
        null
      );

      setIsResolving(
        true
      );

      setMessage(
        'Reading the article…'
      );

      try {
        const resolved =
          await resolveContent(
            value
          );

        if (
          resolved.source !==
            'article'
          ||
          resolved.mode !==
            'article'
        ) {
          throw new Error(
            'The shared link was not resolved as an article.'
          );
        }

        const articleTitle =
          resolved.title.trim()
          ||
          'Untitled article';

        setMessage(
          `Article ready · `
          +
          `${resolved.content_characters.toLocaleString()} characters extracted · analyzing…`
        );

        const analysisUrl =
          resolved.normalized_url
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
            fixtureResult
          );

          setMessage(
            `Gradient test loaded locally · ${fixtureResult.merit_score}/100 · Gemini bypassed.`
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
          result
        );

        setMessage(
          'Article analysis complete.'
        );
      }
      catch (
        error
      ) {
        setArticleResult(
          null
        );

        const detail =
          error instanceof Error
            ? error.message
            : 'The article could not be analyzed.';

        setMessage(
          `Article analysis unavailable: ${detail}`
        );
      }
      finally {
        setIsResolving(
          false
        );
      }

      return;
    }


    setVideoResult(
      null
    );

    setVideoTranscriptMeta(
      null
    );

    setIsResolving(
      true
    );

    setMessage(
      'Locating the YouTube transcript…'
    );


    try {
      const [
        transcript,
        videoTitle,
      ] =
        await Promise.all([
          fetchYouTubeTranscript(
            value
          ),

          fetchYouTubeVideoTitle(
            value
          ).catch(
            () =>
              'Shared YouTube video'
          ),
        ]);


      setMessage(
        'Transcript ready · analyzing the video…'
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
              ||
              undefined,

            extraction_method:
              'youtube-transcript-mobile',
          },
        });


      setVideoResult(
        result
      );


      setVideoTranscriptMeta({
        segmentCount:
          transcript.segmentCount,

        characterCount:
          transcript.characterCount,
      });


      setMessage(
        'Video analysis complete.'
      );
    }
    catch (
      error
    ) {
      setVideoResult(
        null
      );

      setVideoTranscriptMeta(
        null
      );

      const detail =
        error instanceof Error
          ? error.message
          : 'The video could not be analyzed.';

      setMessage(
        `Video analysis unavailable: ${detail}`
      );
    }
    finally {
      setIsResolving(
        false
      );
    }
  }


  const hasLink =
    link.trim().length >
    0;


  const hasResults =
    Boolean(
      articleResult
      ||
      (
        videoResult
        &&
        videoTranscriptMeta
      )
    );


  const messageIsError =
    /unavailable|enter a complete|currently supports|not resolved/i
      .test(
        message
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
              styles.content
            }
          >
            <View
              style={
                styles.header
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
                      styles.brandLabel
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


            <View
              style={[
                styles.heroLayout,

                isWide
                  &&
                  styles.heroLayoutWide,

                hasResults
                  &&
                  styles.heroLayoutWithResults,
              ]}
            >
              {!hasResults ? (
                <View
                  style={[
                    styles.heroCopy,

                    isWide
                      &&
                      styles.heroCopyWide,
                  ]}
                >
                  <Text
                    style={[
                      styles.title,

                      isCompact
                        &&
                        styles.titleCompact,
                    ]}
                  >
                    Sports reporting,
                    {'\n'}
                    scored against
                    {'\n'}
                    the evidence.
                  </Text>

                  <Text
                    style={
                      styles.subtitle
                    }
                  >
                    Paste an article or
                    YouTube video. Sportabase
                    resolves the source,
                    analyzes the reporting and
                    separates informational
                    Merit from evidence status.
                  </Text>

                  <View
                    style={
                      styles.capabilityList
                    }
                  >
                    {[
                      'Merit scoring',
                      'Evidence checks',
                      'Source analysis',
                    ].map(
                      (
                        capability
                      ) => (
                        <View
                          key={
                            capability
                          }
                          style={
                            styles.capability
                          }
                        >
                          <View
                            style={
                              styles.capabilityMark
                            }
                          />

                          <Text
                            style={
                              styles.capabilityText
                            }
                          >
                            {capability}
                          </Text>
                        </View>
                      )
                    )}
                  </View>
                </View>
              ) : null}


              <View
                style={[
                  styles.analysisPanel,

                  isWide
                    &&
                    !hasResults
                    &&
                    styles.analysisPanelWide,

                  hasResults
                    &&
                    styles.analysisPanelAfterResults,
                ]}
              >
                <View
                  style={
                    styles.panelIntro
                  }
                >
                  <Text
                    style={
                      styles.panelTitle
                    }
                  >
                    {hasResults
                      ? 'Analyze another source'
                      : 'Analyze a source'}
                  </Text>

                  <Text
                    style={
                      styles.panelDescription
                    }
                  >
                    Articles and YouTube
                    videos use their own
                    analysis pipelines.
                  </Text>
                </View>


                <View
                  style={
                    styles.modeSelector
                  }
                >
                  <Pressable
                    accessibilityRole="button"
                    onPress={
                      () =>
                        selectMode(
                          'article'
                        )
                    }
                    style={({
                      pressed,
                    }) => [
                      styles.modeButton,

                      mode ===
                        'article'
                        &&
                        styles.modeButtonActive,

                      pressed
                        &&
                        styles.pressed,
                    ]}
                  >
                    <Text
                      style={[
                        styles.modeButtonText,

                        mode ===
                          'article'
                          &&
                          styles.modeButtonTextActive,
                      ]}
                    >
                      Article
                    </Text>
                  </Pressable>


                  <Pressable
                    accessibilityRole="button"
                    onPress={
                      () =>
                        selectMode(
                          'video'
                        )
                    }
                    style={({
                      pressed,
                    }) => [
                      styles.modeButton,

                      mode ===
                        'video'
                        &&
                        styles.modeButtonActive,

                      pressed
                        &&
                        styles.pressed,
                    ]}
                  >
                    <Text
                      style={[
                        styles.modeButtonText,

                        mode ===
                          'video'
                          &&
                          styles.modeButtonTextActive,
                      ]}
                    >
                      YouTube
                    </Text>
                  </Pressable>
                </View>


                <Text
                  style={
                    styles.inputLabel
                  }
                >
                  Source URL
                </Text>


                <View
                  style={
                    styles.inputShell
                  }
                >
                  <TextInput
                    value={
                      link
                    }
                    onChangeText={(
                      value
                    ) => {
                      setLink(
                        value
                      );

                      setMessage('');
                    }}
                    placeholder={
                      mode ===
                        'article'
                        ? 'https://bbc.com/sport/...'
                        : 'https://youtube.com/watch?v=...'
                    }
                    placeholderTextColor="#737b74"
                    keyboardType="url"
                    autoCapitalize="none"
                    autoCorrect={
                      false
                    }
                    style={
                      styles.input
                    }
                  />

                  {hasLink ? (
                    <Pressable
                      accessibilityRole="button"
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
                </View>


                <Pressable
                  accessibilityRole="button"
                  disabled={
                    !hasLink
                    ||
                    isResolving
                  }
                  onPress={
                    validateLink
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

                    pressed
                      &&
                      hasLink
                      &&
                      !isResolving
                      &&
                      styles.analyzeButtonPressed,
                  ]}
                >
                  <Text
                    style={
                      styles.analyzeButtonText
                    }
                  >
                    {
                      isResolving
                        ? mode ===
                            'article'
                          ? 'Reading article…'
                          : 'Analyzing video…'
                        : mode ===
                            'article'
                          ? 'Analyze article'
                          : 'Analyze video'
                    }
                  </Text>

                  <Text
                    style={
                      styles.arrow
                    }
                  >
                    →
                  </Text>
                </Pressable>


                {message ? (
                  <Text
                    style={[
                      styles.message,

                      messageIsError
                        ? styles.errorMessage
                        : styles.statusMessage,
                    ]}
                  >
                    {message}
                  </Text>
                ) : null}


                <Text
                  style={
                    styles.disclosure
                  }
                >
                  Analysis begins only
                  after you press the
                  button.
                </Text>
              </View>
            </View>


            {!hasResults ? (
              <>
                <View
                  style={
                    styles.shareSection
                  }
                >
                  <View
                    style={
                      styles.sectionHeading
                    }
                  >
                    <Text
                      style={
                        styles.sectionTitle
                      }
                    >
                      Share from anywhere
                    </Text>

                    <Text
                      style={
                        styles.sectionDescription
                      }
                    >
                      On supported mobile
                      platforms, send a sports
                      story directly to
                      Sportabase from the
                      system Share menu.
                    </Text>
                  </View>


                  <View
                    style={[
                      styles.shareSteps,

                      isCompact
                        &&
                        styles.shareStepsCompact,
                    ]}
                  >
                    {[
                      [
                        '01',
                        'Open',
                        'Open the story or video.',
                      ],

                      [
                        '02',
                        'Share',
                        'Use the platform Share menu.',
                      ],

                      [
                        '03',
                        'Analyze',
                        'Choose Sportabase and review.',
                      ],
                    ].map(
                      (
                        [
                          number,
                          title,
                          description,
                        ]
                      ) => (
                        <View
                          key={
                            number
                          }
                          style={
                            styles.shareStep
                          }
                        >
                          <Text
                            style={
                              styles.shareStepNumber
                            }
                          >
                            {number}
                          </Text>

                          <Text
                            style={
                              styles.shareStepTitle
                            }
                          >
                            {title}
                          </Text>

                          <Text
                            style={
                              styles.shareStepDescription
                            }
                          >
                            {description}
                          </Text>
                        </View>
                      )
                    )}
                  </View>


                  <Text
                    style={
                      styles.sourceLine
                    }
                  >
                    Articles · YouTube · Reddit · X · Instagram · TikTok · Facebook
                  </Text>
                </View>


                <View
                  style={[
                    styles.featureGrid,

                    isCompact
                      &&
                      styles.featureGridCompact,
                  ]}
                >
                  {FEATURES.map(
                    (
                      feature
                    ) => (
                      <View
                        key={
                          feature.number
                        }
                        style={
                          styles.feature
                        }
                      >
                        <Text
                          style={
                            styles.featureNumber
                          }
                        >
                          {feature.number}
                        </Text>

                        <Text
                          style={
                            styles.featureTitle
                          }
                        >
                          {feature.title}
                        </Text>

                        <Text
                          style={
                            styles.featureDescription
                          }
                        >
                          {feature.description}
                        </Text>
                      </View>
                    )
                  )}
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
                  styles.footerText
                }
              >
                Article and video intelligence
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
      flex:
        1,

      backgroundColor:
        COLORS.background,
    },


    safeArea: {
      flex:
        1,
    },


    scrollContent: {
      flexGrow:
        1,

      alignItems:
        'center',

      paddingHorizontal:
        22,

      paddingBottom:
        48,
    },


    content: {
      width:
        '100%',

      maxWidth:
        1180,
    },


    header: {
      minHeight:
        78,

      flexDirection:
        'row',

      alignItems:
        'center',

      justifyContent:
        'space-between',

      gap:
        24,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.lineSoft,
    },


    brand: {
      flexDirection:
        'row',

      alignItems:
        'center',

      gap:
        12,
    },


    logo: {
      width:
        46,

      height:
        46,
    },


    brandName: {
      color:
        COLORS.text,

      fontSize:
        20,

      lineHeight:
        22,

      fontWeight:
        '700',

      letterSpacing:
        -0.35,
    },


    brandLabel: {
      marginTop:
        4,

      color:
        COLORS.muted,

      fontSize:
        11,

      lineHeight:
        13,

      fontWeight:
        '600',
    },


    apiState: {
      flexDirection:
        'row',

      alignItems:
        'center',

      gap:
        9,
    },


    statusDot: {
      width:
        7,

      height:
        7,

      borderRadius:
        999,

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

      fontSize:
        12,

      fontWeight:
        '600',
    },


    resultsSection: {
      marginTop:
        36,

      marginBottom:
        24,
    },


    heroLayout: {
      paddingTop:
        56,

      paddingBottom:
        64,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.lineSoft,

      gap:
        42,
    },


    heroLayoutWide: {
      minHeight:
        560,

      paddingTop:
        78,

      paddingBottom:
        76,

      flexDirection:
        'row',

      alignItems:
        'center',

      justifyContent:
        'space-between',

      gap:
        74,
    },


    heroLayoutWithResults: {
      minHeight:
        0,

      paddingTop:
        18,

      paddingBottom:
        42,
    },


    heroCopy: {
      flex:
        1,

      maxWidth:
        680,
    },


    heroCopyWide: {
      flexBasis:
        0,
    },


    title: {
      color:
        COLORS.text,

      fontSize:
        58,

      lineHeight:
        61,

      fontWeight:
        '500',

      letterSpacing:
        -2.1,
    },


    titleCompact: {
      fontSize:
        43,

      lineHeight:
        46,

      letterSpacing:
        -1.45,
    },


    subtitle: {
      marginTop:
        26,

      maxWidth:
        610,

      color:
        COLORS.mutedStrong,

      fontSize:
        17,

      lineHeight:
        27,

      fontWeight:
        '400',
    },


    capabilityList: {
      marginTop:
        28,

      flexDirection:
        'row',

      flexWrap:
        'wrap',

      gap:
        20,
    },


    capability: {
      flexDirection:
        'row',

      alignItems:
        'center',

      gap:
        9,
    },


    capabilityMark: {
      width:
        7,

      height:
        2,

      backgroundColor:
        COLORS.accent,
    },


    capabilityText: {
      color:
        COLORS.muted,

      fontSize:
        13,

      fontWeight:
        '600',
    },


    analysisPanel: {
      width:
        '100%',

      padding:
        24,

      borderRadius:
        10,

      backgroundColor:
        COLORS.surface,

      borderWidth:
        1,

      borderColor:
        COLORS.line,
    },


    analysisPanelWide: {
      flex:
        1,

      flexBasis:
        0,

      maxWidth:
        500,
    },


    analysisPanelAfterResults: {
      maxWidth:
        680,

      alignSelf:
        'center',
    },


    panelIntro: {
      marginBottom:
        24,
    },


    panelTitle: {
      color:
        COLORS.text,

      fontSize:
        23,

      lineHeight:
        28,

      fontWeight:
        '700',

      letterSpacing:
        -0.45,
    },


    panelDescription: {
      marginTop:
        7,

      color:
        COLORS.muted,

      fontSize:
        14,

      lineHeight:
        21,
    },


    modeSelector: {
      flexDirection:
        'row',

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },


    modeButton: {
      flex:
        1,

      minHeight:
        43,

      alignItems:
        'center',

      justifyContent:
        'center',

      borderBottomWidth:
        2,

      borderBottomColor:
        'transparent',
    },


    modeButtonActive: {
      borderBottomColor:
        COLORS.accent,
    },


    modeButtonText: {
      color:
        COLORS.muted,

      fontSize:
        14,

      fontWeight:
        '600',
    },


    modeButtonTextActive: {
      color:
        COLORS.text,
    },


    inputLabel: {
      marginTop:
        24,

      marginBottom:
        9,

      color:
        COLORS.mutedStrong,

      fontSize:
        12,

      fontWeight:
        '600',
    },


    inputShell: {
      minHeight:
        52,

      flexDirection:
        'row',

      alignItems:
        'center',

      paddingLeft:
        14,

      paddingRight:
        7,

      borderRadius:
        6,

      backgroundColor:
        '#090b09',

      borderWidth:
        1,

      borderColor:
        '#495049',
    },


    input: {
      flex:
        1,

      minHeight:
        50,

      color:
        COLORS.text,

      fontSize:
        15,

      fontWeight:
        '400',
    },


    clearButton: {
      paddingHorizontal:
        10,

      paddingVertical:
        8,
    },


    clearText: {
      color:
        COLORS.muted,

      fontSize:
        12,

      fontWeight:
        '600',
    },


    analyzeButton: {
      minHeight:
        52,

      marginTop:
        10,

      paddingHorizontal:
        18,

      flexDirection:
        'row',

      alignItems:
        'center',

      justifyContent:
        'center',

      gap:
        10,

      borderRadius:
        6,

      backgroundColor:
        COLORS.accent,
    },


    analyzeButtonDisabled: {
      opacity:
        0.36,
    },


    analyzeButtonPressed: {
      opacity:
        0.82,

      transform: [
        {
          translateY:
            1,
        },
      ],
    },


    analyzeButtonText: {
      color:
        COLORS.accentInk,

      fontSize:
        14,

      fontWeight:
        '800',
    },


    arrow: {
      color:
        COLORS.accentInk,

      fontSize:
        18,

      fontWeight:
        '700',
    },


    message: {
      marginTop:
        13,

      fontSize:
        13,

      lineHeight:
        20,

      fontWeight:
        '500',
    },


    statusMessage: {
      color:
        COLORS.mutedStrong,
    },


    errorMessage: {
      color:
        COLORS.error,
    },


    disclosure: {
      marginTop:
        16,

      paddingTop:
        14,

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.lineSoft,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        18,
    },


    shareSection: {
      paddingTop:
        64,

      paddingBottom:
        64,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.lineSoft,
    },


    sectionHeading: {
      maxWidth:
        650,
    },


    sectionTitle: {
      color:
        COLORS.text,

      fontSize:
        30,

      lineHeight:
        35,

      fontWeight:
        '600',

      letterSpacing:
        -0.65,
    },


    sectionDescription: {
      marginTop:
        11,

      color:
        COLORS.muted,

      fontSize:
        14,

      lineHeight:
        22,
    },


    shareSteps: {
      marginTop:
        34,

      flexDirection:
        'row',

      borderTopWidth:
        1,

      borderTopColor:
        COLORS.line,

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.line,
    },


    shareStepsCompact: {
      flexDirection:
        'column',
    },


    shareStep: {
      flex:
        1,

      paddingVertical:
        20,

      paddingHorizontal:
        18,

      borderRightWidth:
        1,

      borderRightColor:
        COLORS.lineSoft,
    },


    shareStepNumber: {
      color:
        COLORS.accent,

      fontSize:
        11,

      fontWeight:
        '700',
    },


    shareStepTitle: {
      marginTop:
        18,

      color:
        COLORS.text,

      fontSize:
        17,

      fontWeight:
        '700',
    },


    shareStepDescription: {
      marginTop:
        6,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        18,
    },


    sourceLine: {
      marginTop:
        18,

      color:
        COLORS.muted,

      fontSize:
        12,

      lineHeight:
        20,
    },


    featureGrid: {
      flexDirection:
        'row',

      borderBottomWidth:
        1,

      borderBottomColor:
        COLORS.lineSoft,
    },


    featureGridCompact: {
      flexDirection:
        'column',
    },


    feature: {
      flex:
        1,

      minHeight:
        170,

      paddingVertical:
        30,

      paddingHorizontal:
        20,

      borderRightWidth:
        1,

      borderRightColor:
        COLORS.lineSoft,
    },


    featureNumber: {
      color:
        COLORS.accent,

      fontSize:
        11,

      fontWeight:
        '700',
    },


    featureTitle: {
      marginTop:
        23,

      color:
        COLORS.text,

      fontSize:
        18,

      fontWeight:
        '700',
    },


    featureDescription: {
      marginTop:
        8,

      color:
        COLORS.muted,

      fontSize:
        13,

      lineHeight:
        20,
    },


    footer: {
      minHeight:
        84,

      flexDirection:
        'row',

      alignItems:
        'center',

      justifyContent:
        'space-between',

      gap:
        20,
    },


    footerBrand: {
      color:
        COLORS.text,

      fontSize:
        12,

      fontWeight:
        '700',
    },


    footerText: {
      color:
        COLORS.muted,

      fontSize:
        12,
    },


    pressed: {
      opacity:
        0.72,
    },
  });
