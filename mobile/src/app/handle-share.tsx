import { useProductTheme, scaleStyles } from '../theme/product-theme';
import { useIncomingShare } from 'expo-sharing';
import { useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const COLORS = {
  background: '#050807',
  surface: '#101412',
  surfaceRaised: '#171c19',
  border: '#283029',
  text: '#f4f7f4',
  muted: '#98a39b',
  accent: '#76f53f',
  error: '#ff7b7b',
};

function extractFirstUrl(value: string) {
  const match = value.match(
    /https?:\/\/[^\s<>"']+/i,
  );

  if (!match) {
    return '';
  }

  return match[0].replace(/[),.;!?]+$/, '');
}

function detectSource(value: string) {
  const normalized = value.toLowerCase();

  if (
    normalized.includes('youtube.com') ||
    normalized.includes('youtu.be')
  ) {
    return {
      label: 'YouTube video',
      mode: 'video',
    };
  }

  if (normalized.includes('reddit.com')) {
    return {
      label: 'Reddit thread',
      mode: 'article',
    };
  }

  if (
    normalized.includes('twitter.com') ||
    normalized.includes('x.com')
  ) {
    return {
      label: 'X post',
      mode: 'article',
    };
  }

  if (normalized.includes('instagram.com')) {
    return {
      label: 'Instagram post',
      mode: 'article',
    };
  }

  if (normalized.includes('tiktok.com')) {
    return {
      label: 'TikTok post',
      mode: 'article',
    };
  }

  if (normalized.includes('facebook.com')) {
    return {
      label: 'Facebook post',
      mode: 'article',
    };
  }

  return {
    label: 'Sports content',
    mode: 'article',
  };
}

export default function HandleShareScreen() {
  const { colors: COLORS,scale }=useProductTheme();
  const styles=scaleStyles(makeStyles(COLORS),scale);
  const router = useRouter();

  const {
    sharedPayloads,
    isResolving,
    error,
    clearSharedPayloads,
    refreshSharePayloads,
  } = useIncomingShare();

  const rawValue =
    sharedPayloads[0]?.value?.trim() ?? '';

  const detectedUrl = extractFirstUrl(rawValue);
  const content = detectedUrl || rawValue;
  const source = detectSource(content);

  function continueToSportabase() {
    if (!content) {
      return;
    }

    const sharedContent = content;
    const sharedMode = source.mode;

    clearSharedPayloads();

    setTimeout(() => {
      router.replace({
        pathname: '/',
        params: {
          shared: sharedContent,
          mode: sharedMode,
        },
      });
    }, 100);
  }

  function returnHome() {
    router.replace('/');

    setTimeout(() => {
      clearSharedPayloads();
    }, 0);
  }

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.content}>
            <View style={styles.header}>
              <Image
                source={require(
                  '../../assets/images/sportabase-logo.png'
                )}
                style={styles.logo}
                resizeMode="contain"
              />

              <View style={styles.headerText}>
                <Text style={styles.brandName}>
                  Sportabase
                </Text>

                <Text style={styles.brandLabel}>
                  SHARED CONTENT
                </Text>
              </View>
            </View>

            <View style={styles.hero}>
              <Text style={styles.eyebrow}>
                SHARED WITH SPORTABASE
              </Text>

              <Text style={styles.title}>
                Let’s understand
                {'\n'}
                what you just saw.
              </Text>

              <Text style={styles.subtitle}>
                Sportabase received content from another
                application. Review it before continuing.
              </Text>
            </View>

            {isResolving && !content ? (
              <View style={styles.stateCard}>
                <ActivityIndicator
                  size="large"
                  color={COLORS.accent}
                />

                <Text style={styles.stateTitle}>
                  Reading shared content
                </Text>

                <Text style={styles.stateDescription}>
                  Sportabase is checking what the other app
                  provided.
                </Text>
              </View>
            ) : null}

            {error ? (
              <View style={styles.stateCard}>
                <Text style={styles.errorTitle}>
                  Shared content could not be read
                </Text>

                <Text style={styles.stateDescription}>
                  {error.message}
                </Text>

                <Pressable
                  onPress={refreshSharePayloads}
                  style={({ pressed }) => [
                    styles.secondaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.secondaryButtonText}>
                    Try again
                  </Text>
                </Pressable>
              </View>
            ) : null}

            {!isResolving && !error && content ? (
              <View style={styles.shareCard}>
                <View style={styles.detectedRow}>
                  <View style={styles.statusDot} />

                  <Text style={styles.detectedLabel}>
                    {source.label.toUpperCase()} DETECTED
                  </Text>
                </View>

                <Text style={styles.previewLabel}>
                  RECEIVED CONTENT
                </Text>

                <View style={styles.previewBox}>
                  <Text
                    selectable
                    numberOfLines={8}
                    style={styles.previewText}
                  >
                    {content}
                  </Text>
                </View>

                <Pressable
                  onPress={continueToSportabase}
                  style={({ pressed }) => [
                    styles.primaryButton,
                    pressed && styles.primaryPressed,
                  ]}
                >
                  <Text style={styles.primaryButtonText}>
                    Continue to Sportabase
                  </Text>

                  <Text style={styles.primaryArrow}>
                    →
                  </Text>
                </Pressable>

                <Pressable
                  onPress={returnHome}
                  style={({ pressed }) => [
                    styles.cancelButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.cancelButtonText}>
                    Cancel
                  </Text>
                </Pressable>

                <Text style={styles.disclosure}>
                  Nothing is analyzed until you continue and
                  explicitly start an analysis.
                </Text>
              </View>
            ) : null}

            {!isResolving && !error && !content ? (
              <View style={styles.stateCard}>
                <Text style={styles.stateTitle}>
                  Nothing was shared
                </Text>

                <Text style={styles.stateDescription}>
                  Return to another app, open its Share menu,
                  and choose Sportabase.
                </Text>

                <Pressable
                  onPress={returnHome}
                  style={({ pressed }) => [
                    styles.secondaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text style={styles.secondaryButtonText}>
                    Return home
                  </Text>
                </Pressable>
              </View>
            ) : null}
          </View>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const makeStyles = (COLORS: Record<string,string>) => StyleSheet.create({
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
    paddingTop: 24,
    paddingBottom: 48,
  },
  content: {
    width: '100%',
    maxWidth: 680,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  logo: {
    width: 46,
    height: 46,
  },
  headerText: {
    gap: 3,
  },
  brandName: {
    color: COLORS.text,
    fontSize: 19,
    fontWeight: '800',
  },
  brandLabel: {
    color: COLORS.muted,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.4,
  },
  hero: {
    paddingTop: 70,
    paddingBottom: 36,
  },
  eyebrow: {
    color: COLORS.accent,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.8,
  },
  title: {
    marginTop: 15,
    color: COLORS.text,
    fontSize: 42,
    lineHeight: 47,
    fontWeight: '900',
    letterSpacing: -1.5,
  },
  subtitle: {
    marginTop: 18,
    maxWidth: 560,
    color: COLORS.muted,
    fontSize: 16,
    lineHeight: 25,
  },
  shareCard: {
    padding: 20,
    borderRadius: 24,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  detectedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 999,
    backgroundColor: COLORS.accent,
  },
  detectedLabel: {
    color: COLORS.accent,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.2,
  },
  previewLabel: {
    marginTop: 24,
    marginBottom: 10,
    color: COLORS.muted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.3,
  },
  previewBox: {
    minHeight: 110,
    padding: 16,
    justifyContent: 'center',
    borderRadius: 14,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  previewText: {
    color: COLORS.text,
    fontSize: 14,
    lineHeight: 22,
  },
  primaryButton: {
    minHeight: 58,
    marginTop: 18,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    borderRadius: 14,
    backgroundColor: COLORS.accent,
  },
  primaryPressed: {
    opacity: 0.85,
    transform: [{ scale: 0.99 }],
  },
  primaryButtonText: {
    color: '#071004',
    fontSize: 15,
    fontWeight: '900',
  },
  primaryArrow: {
    color: '#071004',
    fontSize: 18,
    fontWeight: '900',
  },
  cancelButton: {
    minHeight: 46,
    marginTop: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelButtonText: {
    color: COLORS.muted,
    fontSize: 13,
    fontWeight: '700',
  },
  disclosure: {
    marginTop: 10,
    color: COLORS.muted,
    fontSize: 11,
    lineHeight: 17,
    textAlign: 'center',
  },
  stateCard: {
    minHeight: 260,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 24,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  stateTitle: {
    marginTop: 18,
    color: COLORS.text,
    fontSize: 20,
    fontWeight: '800',
    textAlign: 'center',
  },
  errorTitle: {
    color: COLORS.error,
    fontSize: 20,
    fontWeight: '800',
    textAlign: 'center',
  },
  stateDescription: {
    marginTop: 10,
    maxWidth: 430,
    color: COLORS.muted,
    fontSize: 14,
    lineHeight: 22,
    textAlign: 'center',
  },
  secondaryButton: {
    minHeight: 48,
    marginTop: 22,
    paddingHorizontal: 22,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    backgroundColor: COLORS.surfaceRaised,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  secondaryButtonText: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: '800',
  },
  pressed: {
    opacity: 0.7,
  },
});
