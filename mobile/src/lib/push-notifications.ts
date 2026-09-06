import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as Device from 'expo-device';
import { Platform } from 'react-native';

import { SportabaseApiError, type WatchTargetKind } from './api';
import {
  listNotificationDevices,
  registerNotificationDevice,
  unregisterNotificationDevice,
  type NotificationDevice,
  type NotificationPlatform,
} from './notification-api';

const DEVICE_STORAGE_KEY = 'sportabase_notification_device_v1';
const CHANNEL_ID = 'sportabase-intelligence';
const WATCHABLE = new Set<WatchTargetKind>([
  'entity',
  'story',
  'claim',
  'media',
]);

let foregroundHandlerInstalled = false;

export type PushRegistrationState = {
  supported: boolean;
  registered: boolean;
  device: NotificationDevice | null;
  reason: string;
};

export type PushNotificationTarget = {
  kind: WatchTargetKind;
  id: string;
  alertId: string;
};

function nativePlatform(): NotificationPlatform | null {
  if (Platform.OS === 'ios' || Platform.OS === 'android') {
    return Platform.OS;
  }
  return null;
}

function projectId() {
  const expoExtra = Constants.expoConfig?.extra as
    | { eas?: { projectId?: string } }
    | undefined;
  return (
    Constants.easConfig?.projectId ||
    expoExtra?.eas?.projectId ||
    ''
  ).trim();
}

async function notificationsModule() {
  return import('expo-notifications');
}

async function installForegroundHandler() {
  if (foregroundHandlerInstalled || Platform.OS === 'web') return;
  const Notifications = await notificationsModule();
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldPlaySound: true,
      shouldSetBadge: false,
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });
  foregroundHandlerInstalled = true;
}

async function ensureAndroidChannel() {
  if (Platform.OS !== 'android') return;
  const Notifications = await notificationsModule();
  await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
    name: 'Sportabase intelligence',
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: 'default',
  });
}

export async function getPushRegistrationState(): Promise<PushRegistrationState> {
  const platform = nativePlatform();
  if (!platform) {
    return {
      supported: false,
      registered: false,
      device: null,
      reason: 'Push notifications are available in the native Sportabase app.',
    };
  }
  if (!Device.isDevice) {
    return {
      supported: false,
      registered: false,
      device: null,
      reason: 'Expo push tokens require a physical iOS or Android device.',
    };
  }

  const localDeviceId = (await AsyncStorage.getItem(DEVICE_STORAGE_KEY))?.trim() || '';
  if (!localDeviceId) {
    return {
      supported: true,
      registered: false,
      device: null,
      reason: 'Push delivery is not enabled on this device.',
    };
  }

  const response = await listNotificationDevices();
  const device = response.items.find((item) => item.id === localDeviceId) || null;
  if (!device) {
    await AsyncStorage.removeItem(DEVICE_STORAGE_KEY);
    return {
      supported: true,
      registered: false,
      device: null,
      reason: 'Push delivery is not enabled on this device.',
    };
  }

  return {
    supported: true,
    registered: true,
    device,
    reason: 'This device is registered for future watch notifications.',
  };
}

export async function enablePushNotifications(): Promise<NotificationDevice> {
  const platform = nativePlatform();
  if (!platform) {
    throw new Error('Push notifications are only available in the native Sportabase app.');
  }
  if (!Device.isDevice) {
    throw new Error('Expo push notifications require a physical iOS or Android device.');
  }

  const resolvedProjectId = projectId();
  if (!resolvedProjectId) {
    throw new Error('Sportabase Expo project identity is not configured.');
  }

  const Notifications = await notificationsModule();
  await installForegroundHandler();
  await ensureAndroidChannel();

  let permission = await Notifications.getPermissionsAsync();
  if (permission.status !== 'granted') {
    permission = await Notifications.requestPermissionsAsync();
  }
  if (permission.status !== 'granted') {
    throw new Error('Notification permission was not granted on this device.');
  }

  const token = await Notifications.getExpoPushTokenAsync({
    projectId: resolvedProjectId,
  });
  const response = await registerNotificationDevice(token.data, platform);
  await AsyncStorage.setItem(DEVICE_STORAGE_KEY, response.device.id);
  return response.device;
}

export async function disablePushNotifications(): Promise<void> {
  const deviceId = (await AsyncStorage.getItem(DEVICE_STORAGE_KEY))?.trim() || '';
  if (!deviceId) return;

  try {
    await unregisterNotificationDevice(deviceId);
  } catch (error) {
    if (!(error instanceof SportabaseApiError && error.status === 404)) {
      throw error;
    }
  } finally {
    await AsyncStorage.removeItem(DEVICE_STORAGE_KEY);
  }
}

export async function clearPushRegistrationAfterBackendRevocation(): Promise<void> {
  await AsyncStorage.removeItem(DEVICE_STORAGE_KEY);
}

function targetFromData(data: unknown): PushNotificationTarget | null {
  if (!data || typeof data !== 'object') return null;
  const record = data as Record<string, unknown>;
  const kind = typeof record.target_kind === 'string' ? record.target_kind : '';
  const id = typeof record.target_id === 'string' ? record.target_id.trim() : '';
  const alertId = typeof record.alert_id === 'string' ? record.alert_id.trim() : '';
  if (!WATCHABLE.has(kind as WatchTargetKind) || !id || !alertId) return null;
  return {
    kind: kind as WatchTargetKind,
    id,
    alertId,
  };
}

export async function subscribeToPushNavigation(
  onTarget: (target: PushNotificationTarget) => void,
): Promise<() => void> {
  if (Platform.OS === 'web') return () => {};

  const Notifications = await notificationsModule();
  await installForegroundHandler();

  const consume = (response: unknown) => {
    const data = (
      response as {
        notification?: {
          request?: {
            content?: { data?: unknown };
          };
        };
      }
    )?.notification?.request?.content?.data;
    const target = targetFromData(data);
    if (target) onTarget(target);
  };

  const lastResponse = await Notifications.getLastNotificationResponseAsync();
  if (lastResponse) {
    consume(lastResponse);
    if (typeof Notifications.clearLastNotificationResponseAsync === 'function') {
      await Notifications.clearLastNotificationResponseAsync();
    }
  }

  const subscription = Notifications.addNotificationResponseReceivedListener(consume);
  return () => subscription.remove();
}
