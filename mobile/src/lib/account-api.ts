import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Crypto from 'expo-crypto';
import contract from '../../../frontend/preferences-contract.json';

export { contract };
export type Preferences = typeof contract.defaults;
export type AccountState = {
  version: string; account: { id: string; status: string }; account_revision: number; device_revision: number;
  device: { device_id: string; platform: string; name: string }; follows_defaults: boolean;
  defaults: Preferences; overrides: Partial<Preferences>; effective: Preferences;
};
export const API_BASE = process.env.EXPO_PUBLIC_SPORTABASE_API_URL || 'https://sportabase-api.onrender.com';
export function canonicalPrivacyUrl() {
  const configured = (process.env.EXPO_PUBLIC_SPORTABASE_WEB_URL || '').trim();
  try {
    const origin = new URL(configured);
    if (origin.protocol !== 'https:' || origin.origin !== configured.replace(/\/$/, '')) return null;
    return `${origin.origin}/privacy.html`;
  } catch { return null; }
}
let tokenGetter: (() => Promise<string | null>) | null = null;
let installation: Promise<string> | null = null;
export function setTokenGetter(getter: typeof tokenGetter) { tokenGetter = getter; }
export function getDeviceId() {
  if (!installation) installation = (async () => {
    let value = await AsyncStorage.getItem('sportabase:device:v1');
    if (!value) { value = Crypto.randomUUID(); await AsyncStorage.setItem('sportabase:device:v1', value); }
    return value;
  })().catch(error => { installation = null; throw error; });
  return installation;
}
export async function accountHeaders() {
  const token = await tokenGetter?.();
  if (!token) throw new Error('Sign in to use Sportabase.');
  return { Authorization: `Bearer ${token}`, 'X-Sportabase-Device-ID': await getDeviceId() };
}
export function privatePath(path: string) { return /^(\/account(?:\/|$)|\/watchlists(?:\/|$)|\/notifications(?:\/|$)|\/analyze(?:\/|$)|\/resolve-content$|\/content\/browser-capture$)/.test(path); }
export async function accountRequest<T = AccountState>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method, headers: { ...await accountHeaders(), 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(typeof payload.detail === 'string' ? payload.detail : `Request failed (${response.status}).`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
