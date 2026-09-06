import { createContext, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { ClerkProvider, useAuth, useClerk, useUser } from '@clerk/expo';
import { tokenCache } from '@clerk/expo/token-cache';
import { useHostedAuth } from '@clerk/expo/hosted-auth';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import { accountRequest, contract, setTokenGetter, type AccountState, type Preferences } from './account-api';
import { getSportabaseClientId } from './client-identity';
import { clearPushRegistrationAfterBackendRevocation } from './push-notifications';

const LEGACY_MIGRATION_KEY = 'sportabase:legacy-migration:v1';

type AccountContext = {
  ready: boolean; signedIn: boolean; label: string; error: string;
  state: AccountState | null; preferences: Preferences;
  signIn: (signup?: boolean) => Promise<void>; signOut: () => Promise<void>;
  manage: () => Promise<void>; refresh: () => Promise<void>; accept: (state: AccountState) => void;
};
const unavailable = async () => { throw new Error('Account sign-in is not configured for this installation.'); };
const defaults: AccountContext = { ready:true,signedIn:false,label:'Signed out',error:'Account sign-in is not configured for this installation.',state:null,preferences:contract.defaults,signIn:unavailable,signOut:unavailable,manage:unavailable,refresh:unavailable,accept:()=>{} };
const Context = createContext<AccountContext>(defaults);
export const useAccount = () => useContext(Context);

function ConnectedAccount({children}: PropsWithChildren) {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const { user } = useUser();
  const clerk = useClerk();
  const { startHostedAuth } = useHostedAuth();
  const [state,setState] = useState<AccountState|null>(null);
  const [preferences,setPreferences] = useState<Preferences>(contract.defaults);
  const [error,setError] = useState('');
  const [ready,setReady] = useState(false);
  const accountIdentity = useRef('');
  const refreshEpoch = useRef(0);
  function accept(next: AccountState) {
    setState(next); setPreferences(next.effective);
    const keys = [...contract.sections.Appearance, 'analysis_detail', 'date_format', 'language'] as (keyof Preferences)[];
    void AsyncStorage.setItem('sportabase:appearance:v1',JSON.stringify(Object.fromEntries(keys.map(key=>[key,next.effective[key]])))).catch(()=>{});
  }
  async function refresh() {
    const epoch = ++refreshEpoch.current;
    const expectedIdentity = accountIdentity.current;
    const isCurrent = () => Boolean(expectedIdentity)
      && epoch === refreshEpoch.current
      && accountIdentity.current === expectedIdentity;
    setError('');
    try {
      const complete = await AsyncStorage.getItem(LEGACY_MIGRATION_KEY) === 'complete';
      const next = await accountRequest<AccountState & {legacy_migration?:{status?:string}}>('/account/bootstrap','POST',{
        platform:'mobile',name:Platform.OS === 'web'?'Mobile web preview':`${Platform.OS} app`,
        ...(!complete?{legacy_client_id:await getSportabaseClientId()}:{}),
      });
      if(next.legacy_migration?.status && next.legacy_migration.status !== 'not_requested') {
        await AsyncStorage.setItem(LEGACY_MIGRATION_KEY,'complete');
      }
      if(!isCurrent()) return;
      accept(next);
    }
    catch (problem) { if(isCurrent()) setError(problem instanceof Error?problem.message:'Could not sync account.'); }
  }
  useEffect(()=>{ void AsyncStorage.getItem('sportabase:appearance:v1').then(value=>{ if(value) setPreferences({...contract.defaults,...JSON.parse(value)}); }).catch(()=>{}); },[]);
  useEffect(()=>{
    let active = true;
    const identity = isSignedIn ? user?.id || '' : '';
    accountIdentity.current = identity;
    refreshEpoch.current += 1;
    setState(null); setReady(false);
    setTokenGetter(isSignedIn?getToken:null);
    if(isLoaded && isSignedIn && identity) void refresh().finally(()=>{if(active)setReady(true);});
    else if(isLoaded) setReady(true);
    return ()=>{active=false;setTokenGetter(null);};
  },[isLoaded,isSignedIn,user?.id,getToken]);
  const value: AccountContext = { ready:ready&&Boolean(isLoaded),signedIn:Boolean(isSignedIn),label:user?.primaryEmailAddress?.emailAddress || user?.fullName || 'Your account',error,state,preferences,accept,refresh,
    signIn:async(signup=false)=>{
      if(Platform.OS==='web') { if(signup) await clerk.redirectToSignUp(); else await clerk.redirectToSignIn(); }
      else await startHostedAuth({mode:signup?'sign-up':'sign-in'});
    },
    signOut:async()=>{
      // Keep the session available until the backend has removed this account's
      // current-device push ownership. A failure deliberately aborts sign-out.
      await accountRequest('/account/device/sign-out','POST');
      try { await clearPushRegistrationAfterBackendRevocation(); }
      catch (problem) { console.warn('Backend push was revoked, but local notification state could not be cleared.', problem); }
      await signOut();
      accountIdentity.current='';refreshEpoch.current+=1;
      setTokenGetter(null);setState(null);
    },
    manage:async()=>{ await clerk.redirectToUserProfile(); },
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function AccountProvider({children}:PropsWithChildren) {
  const key = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if(!key) return <Context.Provider value={defaults}>{children}</Context.Provider>;
  return <ClerkProvider publishableKey={key} tokenCache={tokenCache}><ConnectedAccount>{children}</ConnectedAccount></ClerkProvider>;
}
