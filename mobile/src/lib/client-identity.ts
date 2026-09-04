import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';

const CLIENT_ID_STORAGE_KEY = 'sportabase:client-id:v1';

let clientIdPromise: Promise<string> | null = null;

async function loadOrCreateClientId(): Promise<string> {
  const storedClientId = (
    await AsyncStorage.getItem(CLIENT_ID_STORAGE_KEY)
  )?.trim();

  if (storedClientId) {
    return storedClientId;
  }

  const clientId = Crypto.randomUUID();

  await AsyncStorage.setItem(
    CLIENT_ID_STORAGE_KEY,
    clientId,
  );

  return clientId;
}

export function getSportabaseClientId(): Promise<string> {
  if (!clientIdPromise) {
    clientIdPromise = loadOrCreateClientId().catch(
      (error) => {
        clientIdPromise = null;
        throw error;
      },
    );
  }

  return clientIdPromise;
}
