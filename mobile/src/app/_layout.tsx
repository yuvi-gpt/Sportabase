import { useEffect, useRef } from 'react';
import { useIncomingShare } from 'expo-sharing';
import {
  Stack,
  usePathname,
  useRouter,
} from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

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

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <StatusBar style="light" />

      {Platform.OS !== 'web' ? (
        <IncomingShareRedirector />
      ) : null}

      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: {
            backgroundColor: '#050807',
          },
        }}
      />
    </SafeAreaProvider>
  );
}
