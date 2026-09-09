import { useProductTheme, scaleStyles } from '../theme/product-theme';
import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  disablePushNotifications,
  enablePushNotifications,
  getPushRegistrationState,
  type PushRegistrationState,
} from '../lib/push-notifications';

function messageFrom(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Sportabase could not update notification settings.';
}

export default function NotificationsScreen() {
  const router=useRouter();
  const { colors: COLORS,scale,high }=useProductTheme();
  const styles=scaleStyles(makeStyles(COLORS,high),scale);
  const [state, setState] = useState<PushRegistrationState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isChanging, setIsChanging] = useState(false);
  const [message, setMessage] = useState('');
  const [messageIsError, setMessageIsError] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setMessage('');
    setMessageIsError(false);
    try {
      setState(await getPushRegistrationState());
    } catch (error) {
      setState(null);
      setMessageIsError(true);
      setMessage(messageFrom(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  async function enable() {
    setIsChanging(true);
    setMessage('');
    setMessageIsError(false);
    try {
      await enablePushNotifications();
      await load();
      setMessage('Push delivery is enabled for future watch activity on this device.');
    } catch (error) {
      setMessageIsError(true);
      setMessage(messageFrom(error));
    } finally {
      setIsChanging(false);
    }
  }

  async function disable() {
    setIsChanging(true);
    setMessage('');
    setMessageIsError(false);
    try {
      await disablePushNotifications();
      await load();
      setMessage('Push delivery is disabled on this device. In-app Alerts are unchanged.');
    } catch (error) {
      setMessageIsError(true);
      setMessage(messageFrom(error));
    } finally {
      setIsChanging(false);
    }
  }

  return (
    <View style={styles.screen}>
      <SafeAreaView style={styles.safeArea}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          <Pressable accessibilityRole="button" onPress={()=>router.push('/settings')} style={{paddingVertical:12,minHeight:48}}><Text style={{color:COLORS.text,fontSize:16}}>Back to Settings</Text></Pressable>
          <Text style={styles.title}>Notifications</Text>
          <Text style={styles.subtitle}>Receive updates from your watches. Your Alerts inbox remains available when push is off.</Text>

          <View style={styles.statusCard}>
            <View style={styles.statusTop}>
              <View>
                <Text style={styles.statusLabel}>THIS DEVICE</Text>
                <Text style={styles.statusTitle}>
                  {isLoading
                    ? 'Checking push registration…'
                    : state?.registered
                      ? 'Push enabled'
                      : 'Push disabled'}
                </Text>
              </View>
              <View
                style={[
                  styles.statusDot,
                  state?.registered && styles.statusDotActive,
                ]}
              />
            </View>

            {isLoading ? (
              <ActivityIndicator color={COLORS.accent} style={styles.loader} />
            ) : (
              <>
                <Text style={styles.statusCopy}>
                  {state?.reason ||
                    (Platform.OS === 'web'
                      ? 'Push notifications are available in the native Sportabase app.'
                      : 'Push registration status is unavailable.')}
                </Text>

                {state?.device ? (
                  <View style={styles.deviceMeta}>
                    <Text style={styles.deviceMetaText}>
                      {state.device.platform.toUpperCase()} · EXPO
                    </Text>
                    <Text style={styles.deviceMetaText}>
                      Registered {new Date(state.device.created_at).toLocaleString()}
                    </Text>
                  </View>
                ) : null}

                {state?.supported ? (
                  <Pressable
                    accessibilityRole="button"
                    disabled={isChanging}
                    onPress={() =>
                      state.registered ? void disable() : void enable()
                    }
                    style={({ pressed }) => [
                      styles.actionButton,
                      state.registered && styles.actionButtonSecondary,
                      pressed && styles.pressed,
                    ]}
                  >
                    {isChanging ? (
                      <ActivityIndicator
                        color={state.registered ? COLORS.text : '#071006'}
                      />
                    ) : (
                      <Text
                        style={[
                          styles.actionText,
                          state.registered && styles.actionTextSecondary,
                        ]}
                      >
                        {state.registered
                          ? 'Disable on this device'
                          : 'Enable push notifications'}
                      </Text>
                    )}
                  </Pressable>
                ) : null}
              </>
            )}
          </View>

          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Delivery rules</Text>
            {[
              'Only entity, story, claim and media watches can generate push notifications in V1.',
              'Enabling push establishes a notification baseline, so older alerts are not pushed retroactively.',
              'Each persisted alert can be queued only once per registered device.',
              'A stale Expo device token is disabled when the provider reports DeviceNotRegistered.',
              'The in-app Alerts inbox remains the authoritative persisted notification history.',
            ].map((rule) => (
              <View key={rule} style={styles.ruleRow}>
                <View style={styles.ruleDot} />
                <Text style={styles.ruleText}>{rule}</Text>
              </View>
            ))}
          </View>

          {message ? (
            <Text
              style={[
                styles.message,
                messageIsError && styles.errorMessage,
              ]}
            >
              {message}
            </Text>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const makeStyles = (COLORS: Record<string,string>, high: boolean) => StyleSheet.create({
  screen: { backgroundColor: COLORS.background, flex: 1 },
  safeArea: { flex: 1 },
  content: {
    alignSelf: 'center',
    maxWidth: 760,
    paddingBottom: 44,
    paddingHorizontal: 20,
    paddingTop: 22,
    width: '100%',
  },
  eyebrow: {
    color: COLORS.accent,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.8,
  },
  title: {
    color: COLORS.text,
    fontSize: 28,
    fontWeight: '600',
    letterSpacing: -0.6,
    marginTop: 8,
  },
  subtitle: {
    color: COLORS.muted,
    fontSize: 15,
    lineHeight: 23,
    marginTop: 10,
  },
  boundaryCard: {
    backgroundColor: COLORS.surface,
    borderColor: COLORS.border,
    borderRadius: 18,
    borderWidth: high ? 2 : 1,
    marginTop: 22,
    padding: 17,
  },
  boundaryTitle: {
    color: COLORS.accent,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.3,
  },
  boundaryCopy: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 8,
  },
  statusCard: {
    backgroundColor: COLORS.raised,
    borderColor: COLORS.border,
    borderRadius: 20,
    borderWidth: high ? 2 : 1,
    marginTop: 18,
    padding: 18,
  },
  statusTop: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  statusLabel: {
    color: COLORS.muted,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  statusTitle: {
    color: COLORS.text,
    fontSize: 21,
    fontWeight: '800',
    marginTop: 5,
  },
  statusDot: {
    backgroundColor: '#4b554e',
    borderRadius: 999,
    height: 10,
    width: 10,
  },
  statusDotActive: { backgroundColor: COLORS.accent },
  loader: { marginTop: 20 },
  statusCopy: {
    color: COLORS.muted,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 14,
  },
  deviceMeta: {
    borderTopColor: COLORS.border,
    borderTopWidth: 1,
    gap: 4,
    marginTop: 14,
    paddingTop: 12,
  },
  deviceMetaText: {
    color: COLORS.muted,
    fontSize: 13,
    fontWeight: '700',
  },
  actionButton: {
    alignItems: 'center',
    backgroundColor: COLORS.accent,
    borderRadius: 12,
    justifyContent: 'center',
    marginTop: 18,
    minHeight: 46,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  actionButtonSecondary: {
    backgroundColor: 'transparent',
    borderColor: COLORS.border,
    borderWidth: high ? 2 : 1,
  },
  actionText: { color: '#071006', fontSize: 14, fontWeight: '800' },
  actionTextSecondary: { color: COLORS.text },
  section: { marginTop: 28 },
  sectionTitle: { color: COLORS.text, fontSize: 19, fontWeight: '800' },
  ruleRow: {
    alignItems: 'flex-start',
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  ruleDot: {
    backgroundColor: COLORS.accent,
    borderRadius: 999,
    height: 6,
    marginTop: 6,
    width: 6,
  },
  ruleText: { color: COLORS.muted, flex: 1, fontSize: 14, lineHeight: 21 },
  message: {
    color: COLORS.muted,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 18,
  },
  errorMessage: { color: COLORS.error },
  pressed: { opacity: 0.72 },
});
