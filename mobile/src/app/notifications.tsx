import { useCallback, useState } from 'react';
import { useFocusEffect, useRouter } from 'expo-router';
import { Platform, Text, View } from 'react-native';

import { disablePushNotifications, enablePushNotifications, getPushRegistrationState, type PushRegistrationState } from '../lib/push-notifications';
import { useProductTheme } from '../theme/product-theme';
import { ProductButton, ProductPage, ProductPageHeader, ProductSection, ProductStatus, ProductSurface, formatProductDate } from '../product-ui/ProductPrimitives';
import { ProtectedWebDestination } from '../product-ui/ProtectedWebDestination';
import { productFonts } from '../product-ui/tokens';

function messageFrom(error: unknown) { return error instanceof Error ? error.message : 'Sportabase could not update notification settings.'; }

function NotificationsScreen() {
  const router = useRouter(); const { colors, scale } = useProductTheme();
  const [state, setState] = useState<PushRegistrationState | null>(null); const [loading, setLoading] = useState(true); const [changing, setChanging] = useState(false); const [message, setMessage] = useState(''); const [error, setError] = useState('');
  const load = useCallback(async () => { setLoading(true); setError(''); try { setState(await getPushRegistrationState()); } catch (problem) { setState(null); setError(messageFrom(problem)); } finally { setLoading(false); } }, []);
  useFocusEffect(useCallback(() => { void load(); }, [load]));
  async function enable() { setChanging(true); setMessage(''); setError(''); try { await enablePushNotifications(); await load(); setMessage('Push delivery is enabled for future watch activity on this device.'); } catch (problem) { setError(messageFrom(problem)); } finally { setChanging(false); } }
  async function disable() { setChanging(true); setMessage(''); setError(''); try { await disablePushNotifications(); await load(); setMessage('Push delivery is disabled on this device. In-app Alerts are unchanged.'); } catch (problem) { setError(messageFrom(problem)); } finally { setChanging(false); } }
  const status = loading ? 'Checking push registration' : state?.registered ? 'Push enabled' : 'Push disabled';

  return <ProductPage width="reading" testID="notifications-page">
    <View style={{ alignItems: 'flex-start' }}><ProductButton label="Back to Settings" onPress={() => router.push('/settings')} variant="quiet" /></View>
    <ProductPageHeader label="Delivery on this device" title="Notifications" description="Receive future watch updates. Your persisted Alerts inbox remains available when push delivery is off." />
    {loading ? <ProductStatus loading title={status} /> : <ProductSurface elevated style={{ gap: 14 }}>
      <View style={{ alignItems: 'center', flexDirection: 'row', gap: 12, justifyContent: 'space-between' }}><Text accessibilityRole="header" style={{ color: colors.text, fontFamily: productFonts.display, fontSize: 24 * scale }}>{status}</Text><View accessibilityLabel={state?.registered ? 'Enabled' : 'Disabled'} style={{ backgroundColor: state?.registered ? colors.accent : colors.muted, borderRadius: 6, height: 12, width: 12 }} /></View>
      <Text style={{ color: colors.textMuted, fontFamily: productFonts.body, fontSize: 15 * scale, lineHeight: 22 * scale }}>{state?.reason || (Platform.OS === 'web' ? 'Push notifications are available in the native Sportabase app.' : 'Push registration status is unavailable.')}</Text>
      {state?.device ? <Text style={{ color: colors.muted, fontFamily: productFonts.body, fontSize: 13 * scale }}>{state.device.platform.toUpperCase()} · Expo · Registered {formatProductDate(state.device.created_at)}</Text> : null}
      {state?.supported ? <View style={{ alignItems: 'flex-start' }}><ProductButton label={changing ? 'Updating…' : state.registered ? 'Disable on this device' : 'Enable push notifications'} onPress={() => state.registered ? void disable() : void enable()} variant={state.registered ? 'secondary' : 'primary'} disabled={changing} /></View> : null}
    </ProductSurface>}
    {message ? <ProductStatus title={message} tone="success" /> : null}
    {error ? <ProductStatus title="Notification settings could not be updated" detail={error} tone="error" action={<ProductButton label="Retry" onPress={() => void load()} />} /> : null}
    <ProductSection title="Delivery rules" description="Push delivery follows persisted alerts; it does not change intelligence judgments."><View>{[
      'Only entity, story, claim, and media watches can generate push notifications.',
      'Enabling push establishes a notification baseline, so older alerts are not pushed retroactively.',
      'Each persisted alert can be queued only once per registered device.',
      'A stale Expo device token is disabled when the provider reports DeviceNotRegistered.',
      'The in-app Alerts inbox remains the authoritative persisted notification history.',
    ].map((rule, index) => <ProductSurface key={rule} style={{ alignItems: 'flex-start', borderLeftWidth: 0, borderRightWidth: 0, borderTopWidth: index === 0 ? 1 : 0, flexDirection: 'row', gap: 12 }}><Text style={{ color: colors.accent, fontFamily: productFonts.label }}>0{index + 1}</Text><Text style={{ color: colors.textMuted, flex: 1, fontFamily: productFonts.body, fontSize: 15 * scale, lineHeight: 22 * scale }}>{rule}</Text></ProductSurface>)}</View></ProductSection>
  </ProductPage>;
}

export default function NotificationsRoute() { return <ProtectedWebDestination destination="/notifications" title="Notifications"><NotificationsScreen /></ProtectedWebDestination>; }
