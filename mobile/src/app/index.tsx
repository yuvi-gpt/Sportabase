import { useEffect, useState } from 'react';
import * as Sharing from 'expo-sharing';
import { useLocalSearchParams } from 'expo-router';
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
import { ArticleAnalysisResults } from '../components/article-analysis-results';
import { VideoAnalysisResults } from '../components/video-analysis-results';
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
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

type AnalysisMode = 'article' | 'video';

const COLORS = {
  background: '#050807',
  surface: '#101412',
  surfaceRaised: '#171c19',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  accent: '#76f53f',
  accentSoft: 'rgba(118, 245, 63, 0.12)',
  cyan: '#2fd4db',
  error: '#ff7b7b',
};

const FEATURES = [
  {
    number: '01',
    title: 'Summary',
    description: 'The important details without the filler.',
  },
  {
    number: '02',
    title: 'Merit',
    description: 'A structured assessment of the story.',
  },
  {
    number: '03',
    title: 'Evidence',
    description: 'See what the article actually supports.',
  },
];

export default function HomeScreen() {
  const params = useLocalSearchParams<{
    shared?: string | string[];
    mode?: string | string[];
  }>();

  const [mode, setMode] =
    useState<AnalysisMode>('article');

  const [link, setLink] = useState('');
  const [message, setMessage] = useState('');
  const [isResolving, setIsResolving] =
    useState(false);

  const [articleResult, setArticleResult] =
    useState<ArticleAnalyzeResponse | null>(null);

  const [videoResult, setVideoResult] =
    useState<VideoAnalyzeResponse | null>(null);

  const [
    videoTranscriptMeta,
    setVideoTranscriptMeta,
  ] = useState<{
    segmentCount: number;
    characterCount: number;
  } | null>(null);

  const [apiState, setApiState] = useState<
    'checking' | 'online' | 'offline'
  >('checking');

  useEffect(() => {
    let active = true;

    getApiHealth()
      .then((health) => {
        if (!active) {
          return;
        }

        setApiState(
          health.ok ? 'online' : 'offline',
        );
      })
      .catch(() => {
        if (active) {
          setApiState('offline');
        }
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const sharedValue = Array.isArray(params.shared)
      ? params.shared[0]
      : params.shared;

    const sharedMode = Array.isArray(params.mode)
      ? params.mode[0]
      : params.mode;

    if (!sharedValue) {
      return;
    }

    setLink(sharedValue);
    setMessage('Shared content is ready for review.');

    if (sharedMode === 'video') {
      setMode('video');
    } else {
      setMode('article');
    }

    Sharing.clearSharedPayloads();
  }, [params.mode, params.shared]);

  function selectMode(nextMode: AnalysisMode) {
    setMode(nextMode);
    setMessage('');
    setArticleResult(null);
    setVideoResult(null);
    setVideoTranscriptMeta(null);
  }

  async function validateLink() {
    const value = link.trim();

    if (!/^https?:\/\/\S+$/i.test(value)) {
      setMessage(
        'Enter a complete link beginning with http:// or https://.',
      );

      return;
    }

    if (
      mode === 'video' &&
      !/(youtube\.com|youtu\.be)/i.test(value)
    ) {
      setMessage(
        'Video analysis currently supports YouTube links.',
      );

      return;
    }

    if (mode === 'article') {
      setArticleResult(null);
      setIsResolving(true);
      setMessage('Reading the article...');

      try {
        const resolved = await resolveContent(value);

        if (
          resolved.source !== 'article' ||
          resolved.mode !== 'article'
        ) {
          throw new Error(
            'The shared link was not resolved as an article.',
          );
        }

        const articleTitle =
          resolved.title.trim() || 'Untitled article';

        setMessage(
          `Article ready: ${articleTitle} · ` +
            `${resolved.content_characters.toLocaleString()} ` +
            'characters extracted. Analyzing...',
        );

        const analysisUrl =
          resolved.normalized_url || value;

        const fixtureResult =
          getArticleGradientFixture({
            url: analysisUrl,
            title: articleTitle,
            text: resolved.content,
          });

        if (fixtureResult) {
          setArticleResult(fixtureResult);

          setMessage(
            `Gradient test loaded locally: ` +
              `${fixtureResult.merit_score}/100. ` +
              'Gemini bypassed.',
          );

          return;
        }

        const result = await analyzeArticle({
          title: articleTitle,
          url: analysisUrl,
          text: resolved.content,
          max_bullets: 3,
        });

        setArticleResult(result);
        setMessage('Article analysis complete.');
      } catch (error) {
        setArticleResult(null);

        const detail =
          error instanceof Error
            ? error.message
            : 'The article could not be analyzed.';

        setMessage(
          `Article analysis unavailable: ${detail}`,
        );
      } finally {
        setIsResolving(false);
      }

      return;
    }

    setVideoResult(null);
    setVideoTranscriptMeta(null);
    setIsResolving(true);

    setMessage(
      'Locating the YouTube transcript...',
    );

    try {
      const [
        transcript,
        videoTitle,
      ] = await Promise.all([
        fetchYouTubeTranscript(value),
        fetchYouTubeVideoTitle(value).catch(
          () => 'Shared YouTube video',
        ),
      ]);

      setMessage(
        'Transcript ready. Analyzing the video...',
      );

      const result = await analyzeVideo({
        title: videoTitle,
        transcript: transcript.transcript,
        url: value,
        transcript_metadata: {
          segment_count:
            transcript.segmentCount,
          character_count:
            transcript.characterCount,
          language:
            transcript.language || undefined,
          extraction_method:
            'youtube-transcript-mobile',
        },
      });

      setVideoResult(result);

      setVideoTranscriptMeta({
        segmentCount:
          transcript.segmentCount,
        characterCount:
          transcript.characterCount,
      });

      setMessage(
        'Video analysis complete.',
      );
    } catch (error) {
      setVideoResult(null);
      setVideoTranscriptMeta(null);

      const detail =
        error instanceof Error
          ? error.message
          : 'The video could not be analyzed.';

      setMessage(
        `Video analysis unavailable: ${detail}`,
      );
    } finally {
      setIsResolving(false);
    }
  }

  const hasLink = link.trim().length > 0;

  const hasResults = Boolean(
    articleResult ||
      (videoResult && videoTranscriptMeta),
  );

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scrollContent}
        >
          <View style={styles.content}>
            <View style={styles.header}>
              <View style={styles.brand}>
                <View style={styles.logoShell}>
                  <Image
                    source={require(
                      '../../assets/images/sportabase-logo.png'
                    )}
                    style={styles.logo}
                    resizeMode="contain"
                  />
                </View>

                <View>
                  <Text style={styles.brandName}>
                    Sportabase
                  </Text>

                  <Text style={styles.brandLabel}>
                    SPORTS INTELLIGENCE
                  </Text>
                </View>
              </View>

              <View style={styles.alphaBadge}>
                <View
                  style={[
                    styles.statusDot,
                    apiState === 'offline' &&
                      styles.statusDotOffline,
                  ]}
                />

                <Text style={styles.alphaText}>
                  {apiState === 'checking'
                    ? 'API CHECKING'
                    : apiState === 'online'
                      ? 'API ONLINE'
                      : 'API OFFLINE'}
                </Text>
              </View>
            </View>

            {articleResult ? (
              <View style={styles.resultsSection}>
                <ArticleAnalysisResults
                  result={articleResult}
                />
              </View>
            ) : null}

            {videoResult && videoTranscriptMeta ? (
              <View style={styles.resultsSection}>
                <VideoAnalysisResults
                  result={videoResult}
                  transcript={videoTranscriptMeta}
                />
              </View>
            ) : null}
            {!hasResults ? (
              <View style={styles.hero}>
              <Text style={styles.eyebrow}>
                EVIDENCE-FIRST ANALYSIS
              </Text>

              <Text style={styles.title}>
                Understand the story,
                {'\n'}
                not just the headline.
              </Text>

              <Text style={styles.subtitle}>
                Share sports content directly from the app
                you are using. Sportabase receives the link,
                identifies the source and prepares it for
                analysis.
              </Text>
              </View>
            ) : null}

            <View style={styles.shareFirstCard}>
              <View style={styles.shareCardTop}>
                <View style={styles.shareIcon}>
                  <Image
                    source={require(
                      '../../assets/images/sportabase-logo.png'
                    )}
                    style={styles.shareIconImage}
                    resizeMode="contain"
                  />
                </View>

                <View style={styles.shareCardHeading}>
                  <Text style={styles.shareBadge}>
                    PRIMARY EXPERIENCE
                  </Text>

                  <Text style={styles.shareTitle}>
                    Share it with Sportabase
                  </Text>
                </View>
              </View>

              <Text style={styles.shareDescription}>
                Open the Share menu on an article, video or
                social post and choose Sportabase. You will
                review the detected content before anything
                is analyzed.
              </Text>

              <View style={styles.shareSteps}>
                <View style={styles.shareStep}>
                  <Text style={styles.shareStepNumber}>1</Text>

                  <Text style={styles.shareStepText}>
                    Open any sports story
                  </Text>
                </View>

                <Text style={styles.shareStepArrow}>→</Text>

                <View style={styles.shareStep}>
                  <Text style={styles.shareStepNumber}>2</Text>

                  <Text style={styles.shareStepText}>
                    Tap Share
                  </Text>
                </View>

                <Text style={styles.shareStepArrow}>→</Text>

                <View style={styles.shareStep}>
                  <Text style={styles.shareStepNumber}>3</Text>

                  <Text style={styles.shareStepText}>
                    Choose Sportabase
                  </Text>
                </View>
              </View>

              <View style={styles.sourceList}>
                {[
                  'Articles',
                  'YouTube',
                  'Reddit',
                  'X',
                  'Instagram',
                  'TikTok',
                  'Facebook',
                ].map((source) => (
                  <View
                    key={source}
                    style={styles.sourceChip}
                  >
                    <Text style={styles.sourceChipText}>
                      {source}
                    </Text>
                  </View>
                ))}
              </View>
            </View>

            <Text style={styles.manualLabel}>
              OR PASTE A LINK MANUALLY
            </Text>

            <View style={styles.analysisCard}>
              <View style={styles.modeSelector}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => selectMode('article')}
                  style={({ pressed }) => [
                    styles.modeButton,
                    mode === 'article' &&
                      styles.modeButtonActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.modeButtonText,
                      mode === 'article' &&
                        styles.modeButtonTextActive,
                    ]}
                  >
                    Article
                  </Text>
                </Pressable>

                <Pressable
                  accessibilityRole="button"
                  onPress={() => selectMode('video')}
                  style={({ pressed }) => [
                    styles.modeButton,
                    mode === 'video' &&
                      styles.modeButtonActive,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.modeButtonText,
                      mode === 'video' &&
                        styles.modeButtonTextActive,
                    ]}
                  >
                    YouTube
                  </Text>
                </Pressable>
              </View>

              <Text style={styles.inputLabel}>
                {mode === 'article'
                  ? 'SPORTS ARTICLE LINK'
                  : 'YOUTUBE VIDEO LINK'}
              </Text>

              <View style={styles.inputShell}>
                <TextInput
                  value={link}
                  onChangeText={(value) => {
                    setLink(value);
                    setMessage('');
                  }}
                  placeholder={
                    mode === 'article'
                      ? 'https://example.com/sports-story'
                      : 'https://youtube.com/watch?v=...'
                  }
                  placeholderTextColor="#657068"
                  keyboardType="url"
                  autoCapitalize="none"
                  autoCorrect={false}
                  style={styles.input}
                />

                {hasLink ? (
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => {
                      setLink('');
                      setMessage('');
                    }}
                    style={({ pressed }) => [
                      styles.clearButton,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.clearText}>
                      Clear
                    </Text>
                  </Pressable>
                ) : null}
              </View>

              <Pressable
                accessibilityRole="button"
                disabled={!hasLink || isResolving}
                onPress={validateLink}
                style={({ pressed }) => [
                  styles.analyzeButton,
                  (!hasLink || isResolving) &&
                    styles.analyzeButtonDisabled,
                  pressed &&
                    hasLink &&
                    !isResolving &&
                    styles.analyzeButtonPressed,
                ]}
              >
                <Text style={styles.analyzeButtonText}>
                  {isResolving
                    ? mode === 'article'
                      ? 'Reading article...'
                      : 'Analyzing video...'
                    : `Analyze ${mode}`}
                </Text>

                <Text style={styles.arrow}>↑</Text>
              </Pressable>

              {message ? (
                <Text
                  style={[
                    styles.message,
                    message.startsWith('Link accepted') ||
                    message.startsWith('Reading the article') ||
                    message.startsWith('Article ready') ||
                    message.startsWith('Transcript ready') ||
                    message.startsWith('Video analysis complete')
                      ? styles.successMessage
                      : styles.errorMessage,
                  ]}
                >
                  {message}
                </Text>
              ) : null}

              <Text style={styles.disclosure}>
                Analysis is only performed after you press the
                button. The mobile app will use the same secure
                Sportabase backend as the extension.
              </Text>
            </View>


            <View style={styles.featureGrid}>
              {FEATURES.map((feature) => (
                <View
                  key={feature.number}
                  style={styles.featureCard}
                >
                  <Text style={styles.featureNumber}>
                    {feature.number}
                  </Text>

                  <Text style={styles.featureTitle}>
                    {feature.title}
                  </Text>

                  <Text style={styles.featureDescription}>
                    {feature.description}
                  </Text>
                </View>
              ))}
            </View>

            <View style={styles.footer}>
              <View style={styles.footerLine} />

              <Text style={styles.footerText}>
                SPORTABASE · ARTICLE AND VIDEO INTELLIGENCE
              </Text>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  safeArea: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 48,
  },
  content: {
    width: '100%',
    maxWidth: 680,
  },
  header: {
    minHeight: 64,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  logoShell: {
    width: 48,
    height: 48,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  logo: {
    width: 36,
    height: 36,
  },
  brandName: {
    color: COLORS.text,
    fontSize: 19,
    lineHeight: 22,
    fontWeight: '800',
    letterSpacing: -0.4,
  },
  brandLabel: {
    marginTop: 3,
    color: COLORS.muted,
    fontSize: 9,
    lineHeight: 11,
    fontWeight: '700',
    letterSpacing: 1.3,
  },
  alphaBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
    paddingHorizontal: 11,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 999,
    backgroundColor: COLORS.accent,
  },
  statusDotOffline: {
    backgroundColor: COLORS.error,
  },
  alphaText: {
    color: COLORS.muted,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  hero: {
    paddingTop: 68,
    paddingBottom: 38,
  },
  eyebrow: {
    color: COLORS.accent,
    fontSize: 11,
    lineHeight: 14,
    fontWeight: '800',
    letterSpacing: 1.8,
  },
  title: {
    marginTop: 15,
    color: COLORS.text,
    fontSize: 44,
    lineHeight: 49,
    fontWeight: '900',
    letterSpacing: -1.7,
  },
  subtitle: {
    marginTop: 20,
    maxWidth: 590,
    color: COLORS.muted,
    fontSize: 16,
    lineHeight: 25,
    fontWeight: '500',
  },
  shareFirstCard: {
    padding: 22,
    marginBottom: 18,
    borderRadius: 24,
    backgroundColor: COLORS.accentSoft,
    borderWidth: 1,
    borderColor: 'rgba(118, 245, 63, 0.34)',
  },
  shareCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  shareIcon: {
    width: 50,
    height: 50,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 15,
    backgroundColor: '#07100a',
    borderWidth: 1,
    borderColor: 'rgba(118, 245, 63, 0.58)',
    shadowColor: COLORS.accent,
    shadowOpacity: 0.24,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 0,
    },
    elevation: 4,
  },
  shareIconImage: {
    width: 39,
    height: 39,
  },
  shareCardHeading: {
    flex: 1,
  },
  shareBadge: {
    color: COLORS.accent,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1.3,
  },
  shareTitle: {
    marginTop: 5,
    color: COLORS.text,
    fontSize: 21,
    lineHeight: 25,
    fontWeight: '900',
    letterSpacing: -0.5,
  },
  shareDescription: {
    marginTop: 18,
    color: COLORS.muted,
    fontSize: 14,
    lineHeight: 22,
  },
  shareSteps: {
    marginTop: 20,
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    gap: 8,
  },
  shareStep: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },
  shareStepNumber: {
    width: 22,
    height: 22,
    color: '#071004',
    backgroundColor: COLORS.accent,
    borderRadius: 999,
    fontSize: 11,
    lineHeight: 22,
    fontWeight: '900',
    textAlign: 'center',
  },
  shareStepText: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: '700',
  },
  shareStepArrow: {
    color: COLORS.muted,
    fontSize: 13,
    fontWeight: '800',
  },
  sourceList: {
    marginTop: 20,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  sourceChip: {
    paddingHorizontal: 11,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  sourceChipText: {
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: '700',
  },
  manualLabel: {
    marginBottom: 10,
    color: COLORS.muted,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1.4,
    textAlign: 'center',
  },
  analysisCard: {
    padding: 20,
    borderRadius: 24,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  modeSelector: {
    flexDirection: 'row',
    gap: 6,
    padding: 5,
    borderRadius: 14,
    backgroundColor: COLORS.background,
  },
  modeButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
    borderRadius: 10,
  },
  modeButtonActive: {
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: '#364039',
  },
  modeButtonText: {
    color: COLORS.muted,
    fontSize: 14,
    fontWeight: '700',
  },
  modeButtonTextActive: {
    color: COLORS.text,
  },
  inputLabel: {
    marginTop: 24,
    marginBottom: 10,
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.4,
  },
  inputShell: {
    minHeight: 58,
    flexDirection: 'row',
    alignItems: 'center',
    paddingLeft: 16,
    paddingRight: 8,
    borderRadius: 14,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  input: {
    flex: 1,
    minHeight: 56,
    color: COLORS.text,
    fontSize: 15,
    fontWeight: '500',
  },
  clearButton: {
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  clearText: {
    color: COLORS.muted,
    fontSize: 12,
    fontWeight: '700',
  },
  analyzeButton: {
    minHeight: 58,
    marginTop: 14,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    borderRadius: 14,
    backgroundColor: COLORS.accent,
  },
  analyzeButtonDisabled: {
    opacity: 0.35,
  },
  analyzeButtonPressed: {
    transform: [{ scale: 0.99 }],
    opacity: 0.86,
  },
  analyzeButtonText: {
    color: '#071004',
    fontSize: 15,
    fontWeight: '900',
    textTransform: 'capitalize',
  },
  arrow: {
    color: '#071004',
    fontSize: 18,
    fontWeight: '900',
  },
  message: {
    marginTop: 12,
    fontSize: 13,
    lineHeight: 19,
    fontWeight: '600',
  },
  successMessage: {
    color: COLORS.accent,
  },
  errorMessage: {
    color: COLORS.error,
  },
  disclosure: {
    marginTop: 16,
    color: COLORS.muted,
    fontSize: 11,
    lineHeight: 17,
    textAlign: 'center',
  },
  resultsSection: {
    marginTop: 18,
  },
  featureGrid: {
    marginTop: 18,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  featureCard: {
    flexGrow: 1,
    flexBasis: 180,
    minHeight: 142,
    padding: 18,
    borderRadius: 18,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  featureNumber: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.1,
  },
  featureTitle: {
    marginTop: 20,
    color: COLORS.text,
    fontSize: 17,
    fontWeight: '800',
  },
  featureDescription: {
    marginTop: 7,
    color: COLORS.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  footer: {
    alignItems: 'center',
    marginTop: 42,
  },
  footerLine: {
    width: 32,
    height: 2,
    borderRadius: 999,
    backgroundColor: COLORS.cyan,
  },
  footerText: {
    marginTop: 13,
    color: '#606a63',
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 1.2,
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.72,
  },
});
