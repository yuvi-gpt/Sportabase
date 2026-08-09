import { useEffect, useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
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
  }, [params.mode, params.shared]);

  function selectMode(nextMode: AnalysisMode) {
    setMode(nextMode);
    setMessage('');
  }

  function validateLink() {
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

    setMessage(
      'Link accepted. Backend analysis connection comes next.',
    );
  }

  const hasLink = link.trim().length > 0;

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
                <View style={styles.statusDot} />

                <Text style={styles.alphaText}>
                  MOBILE ALPHA
                </Text>
              </View>
            </View>

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
                Paste a sports article or YouTube link.
                Sportabase will surface the summary, evidence,
                merit and reasoning behind it.
              </Text>
            </View>

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
                disabled={!hasLink}
                onPress={validateLink}
                style={({ pressed }) => [
                  styles.analyzeButton,
                  !hasLink &&
                    styles.analyzeButtonDisabled,
                  pressed &&
                    hasLink &&
                    styles.analyzeButtonPressed,
                ]}
              >
                <Text style={styles.analyzeButtonText}>
                  Analyze {mode}
                </Text>

                <Text style={styles.arrow}>↑</Text>
              </Pressable>

              {message ? (
                <Text
                  style={[
                    styles.message,
                    message.startsWith('Link accepted')
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
