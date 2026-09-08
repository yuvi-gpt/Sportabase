import { AccountProvider, useAccount } from '../lib/account-context';
import { useProductTheme } from '../theme/product-theme';
import { useEffect, useRef } from 'react';
import { useIncomingShare } from 'expo-sharing';
import {
  Stack,
  usePathname,
  useRouter,
} from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ProductNav } from '../components/product-nav';
import { markAlertRead } from '../lib/api';
import { intelligenceRoute } from '../lib/intelligence-history';
import { subscribeToPushNavigation } from '../lib/push-notifications';
import { ProductShellProvider } from '../product-ui/ProductShellContext';
import { ProductWebShell } from '../product-ui/ProductWebShell';

function IncomingShareRedirector() {
  const router = useRouter();
  const pathname = usePathname();

  const { sharedPayloads } = useIncomingShare();

  const handledPayloadRef = useRef('');
  const hasSharedPayload = sharedPayloads.length > 0;
  const payloadKey = JSON.stringify(sharedPayloads);

  useEffect(() => {
    if (!hasSharedPayload) {
      handledPayloadRef.current = '';
      return;
    }

    if (pathname === '/handle-share') {
      handledPayloadRef.current = payloadKey;
      return;
    }

    if (handledPayloadRef.current === payloadKey) {
      return;
    }

    handledPayloadRef.current = payloadKey;
    router.replace('/handle-share');
  }, [
    hasSharedPayload,
    pathname,
    payloadKey,
    router,
  ]);

  return null;
}

function PushNotificationRedirector() {
  const router = useRouter();

  useEffect(() => {
    if (Platform.OS === 'web') return;

    let disposed = false;
    let unsubscribe: (() => void) | null = null;

    void subscribeToPushNavigation((target) => {
      if (disposed) return;

      void markAlertRead(target.alertId).catch((error) => {
        console.warn('[sportabase] Could not mark pushed alert read:', error);
      });

      router.push(intelligenceRoute(target.kind, target.id));
    })
      .then((cleanup) => {
        if (disposed) {
          cleanup();
        } else {
          unsubscribe = cleanup;
        }
      })
      .catch((error) => {
        console.warn('[sportabase] Push navigation unavailable:', error);
      });

    return () => {
      disposed = true;
      unsubscribe?.();
    };
  }, [router]);

  return null;
}

function AppFrame() {
  const account = useAccount();
  const { colors } = useProductTheme();
  const pathname = usePathname();
  const showProductNav = Platform.OS !== 'web' && pathname !== '/handle-share';

  const navigator = (
    <View style={styles.stack}>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: {
            backgroundColor: colors.background,
          },
        }}
      >
        <Stack.Screen name="settings" />
        <Stack.Screen name="explore" />
        <Stack.Screen name="intelligence" />
        {Platform.OS === 'web' ? <Stack.Screen name="watchlists" /> : null}
        {Platform.OS === 'web' ? <Stack.Screen name="alerts" /> : null}
        {Platform.OS === 'web' ? <Stack.Screen name="notifications" /> : null}
        {Platform.OS === 'web' ? <Stack.Screen name="activity" /> : null}
        {Platform.OS !== 'web' ? (
          <Stack.Protected guard={account.ready && account.signedIn && Boolean(account.state)}>
            <Stack.Screen name="watchlists" />
            <Stack.Screen name="alerts" />
            <Stack.Screen name="notifications" />
            <Stack.Screen name="activity" />
            <Stack.Screen name="handle-share" />
          </Stack.Protected>
        ) : null}
        {Platform.OS === 'web' ? (
          <Stack.Protected guard={account.ready && account.signedIn && Boolean(account.state)}>
            <Stack.Screen name="handle-share" />
          </Stack.Protected>
        ) : null}
      </Stack>
    </View>
  );

  return (
    <ProductShellProvider>
      {Platform.OS === 'web' ? (
        <ProductWebShell>{navigator}</ProductWebShell>
      ) : (
        <View style={[styles.frame,{backgroundColor:colors.background}]}>
          {navigator}

          {showProductNav ? <ProductNav /> : null}
        </View>
      )}
    </ProductShellProvider>
  );
}

function RootContent() {
  const {dark}=useProductTheme();
  return (
    <SafeAreaProvider>
      <StatusBar style={dark?"light":"dark"} />

      {Platform.OS !== 'web' ? (
        <>
          <IncomingShareRedirector />
          <PushNotificationRedirector />
        </>
      ) : null}

      <AppFrame />
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  frame: {
    backgroundColor: '#050807',
    flex: 1,
  },
  stack: {
    flex: 1,
  },
});

export default function RootLayout() { return <AccountProvider><RootContent /></AccountProvider>; }
