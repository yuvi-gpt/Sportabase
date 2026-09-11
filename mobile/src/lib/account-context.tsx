import { createContext, useContext, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { ClerkProvider, useAuth, useClerk, useUser } from '@clerk/expo';
import { tokenCache } from '@clerk/expo/token-cache';
import { useHostedAuth } from '@clerk/expo/hosted-auth';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import { accountRequest, contract, setTokenGetter, type AccountState, type Preferences } from './account-api';
import { getSportabaseClientId } from './client-identity';
import { clearPushRegistrationAfterBackendRevocation } from './push-notifications';
import { expoAuthConfiguration } from './deployment-config';
import {
  absoluteAuthDestination,
  allowlistedAuthDestination,
  type AuthReturnDestination,
} from './auth-destinations';
import { ACCOUNT_IDENTITY_ERROR, planAccountSession } from './account-session';
import { createAccountResyncCoordinator, createWebAccountReturnTracker } from './account-resync';

const LEGACY_MIGRATION_KEY = 'sportabase:legacy-migration:v1';

type AccountContext = {
  ready: boolean; signedIn: boolean; label: string; error: string;
  state: AccountState | null; preferences: Preferences;
  signIn: (signup?: boolean, destination?: AuthReturnDestination) => Promise<void>; signOut: () => Promise<void>;
  manage: () => Promise<void>; refresh: () => Promise<void>; accept: (state: AccountState) => void;
};
function unavailableAccount(error: string): AccountContext {
  const unavailable = async () => { throw new Error(error); };
  return { ready:true,signedIn:false,label:'Signed out',error,state:null,preferences:contract.defaults,signIn:unavailable,signOut:unavailable,manage:unavailable,refresh:unavailable,accept:()=>{} };
}
const defaults = unavailableAccount('Account sign-in is not configured for this installation.');
const Context = createContext<AccountContext>(defaults);
export const useAccount = () => useContext(Context);

function ConnectedAccount({children}: PropsWithChildren) {
  const { isLoaded, isSignedIn, userId, sessionId, getToken, signOut } = useAuth();
  const { user } = useUser();
  const clerk = useClerk();
  const { startHostedAuth } = useHostedAuth();
  const [state,setState] = useState<AccountState|null>(null);
  const [preferences,setPreferences] = useState<Preferences>(contract.defaults);
  const [error,setError] = useState('');
  const [ready,setReady] = useState(false);
  const session = planAccountSession(isLoaded, isSignedIn, userId, sessionId);
  const sessionRef = useRef(session); sessionRef.current = session;
  const accountSessionKey = useRef('');
  const accountSessionStatus = useRef(session.status);
  const stateSessionKey = useRef('');
  const currentAccountId = useRef('');
  const getTokenRef = useRef(getToken);
  const resync = useRef(createAccountResyncCoordinator()).current;
  const refreshRef = useRef<() => Promise<void>>(async()=>{});
  const webReturn = useRef(createWebAccountReturnTracker(() => {
    if(sessionRef.current.status === 'bootstrap') void refreshRef.current().catch(()=>{});
  })).current;
  function accept(next: AccountState) {
    // Account mutations can finish after Clerk has switched sessions. Only an
    // update for the account established by the current bootstrap may land.
    if(!currentAccountId.current || next.account.id !== currentAccountId.current) return;
    applyAccountState(next);
  }
  function acceptBootstrap(next: AccountState, expectedSessionKey: string) {
    if(accountSessionKey.current !== expectedSessionKey) return;
    currentAccountId.current = next.account.id;
    stateSessionKey.current = expectedSessionKey;
    applyAccountState(next);
  }
  function applyAccountState(next: AccountState) {
    stateSessionKey.current = accountSessionKey.current;
    setState(next); setPreferences(next.effective);
    const keys = [...contract.sections.Appearance, 'analysis_detail', 'date_format', 'language'] as (keyof Preferences)[];
    void AsyncStorage.setItem('sportabase:appearance:v1',JSON.stringify(Object.fromEntries(keys.map(key=>[key,next.effective[key]])))).catch(()=>{});
  }
  async function refresh() {
    const currentSession = sessionRef.current;
    if(currentSession.status !== 'bootstrap') {
      const problem = new Error(currentSession.status === 'identity-error' ? currentSession.error : ACCOUNT_IDENTITY_ERROR);
      setError(problem.message); throw problem;
    }
    const expectedSessionKey = currentSession.key;
    const hasUsableState = stateSessionKey.current === expectedSessionKey;
    if(!hasUsableState) setReady(false);
    setError('');
    return resync.run(expectedSessionKey, async (isCurrent) => {
      try {
        if(!isCurrent()) return;
        const complete = await AsyncStorage.getItem(LEGACY_MIGRATION_KEY) === 'complete';
        if(!isCurrent()) return;
        const legacyClientId = !complete ? await getSportabaseClientId() : '';
        if(!isCurrent()) return;
        const next = await accountRequest<AccountState & {legacy_migration?:{status?:string}}>('/account/bootstrap','POST',{
          platform:'mobile',name:Platform.OS === 'web'?'Mobile web preview':`${Platform.OS} app`,
          ...(!complete?{legacy_client_id:legacyClientId}:{}),
        });
        if(!isCurrent() || accountSessionKey.current !== expectedSessionKey) return;
        if(next.legacy_migration?.status && next.legacy_migration.status !== 'not_requested') {
          await AsyncStorage.setItem(LEGACY_MIGRATION_KEY,'complete');
          if(!isCurrent()) return;
        }
        acceptBootstrap(next, expectedSessionKey); setError('');
      }
      catch (problem) {
        if(!isCurrent()) return;
        const failure = problem instanceof Error ? problem : new Error('Could not sync account.');
        setError(failure.message); throw failure;
      }
      finally { if(isCurrent()) setReady(true); }
    });
  }
  refreshRef.current = refresh;
  useEffect(()=>{ void AsyncStorage.getItem('sportabase:appearance:v1').then(value=>{ if(value) setPreferences({...contract.defaults,...JSON.parse(value)}); }).catch(()=>{}); },[]);
  useEffect(()=>{ getTokenRef.current=getToken; },[getToken]);
  useEffect(()=>{
    accountSessionKey.current = session.status === 'bootstrap' ? session.key : '';
    accountSessionStatus.current = session.status;
    stateSessionKey.current = '';
    currentAccountId.current = '';
    setState(null); setReady(false);
    if(session.status === 'bootstrap') {
      setTokenGetter(()=>getTokenRef.current());
      void refreshRef.current().catch(()=>{});
    } else {
      resync.invalidate(); webReturn.reset();
      setTokenGetter(null);
      setError(session.status === 'identity-error' ? session.error : '');
      if(session.status !== 'loading') setReady(true);
    }
    return ()=>{setTokenGetter(null);};
  },[isLoaded,isSignedIn,userId,sessionId,resync,webReturn]);
  useEffect(()=>{
    if(Platform.OS !== 'web' || typeof window === 'undefined' || typeof document === 'undefined') return;
    const visible = () => document.visibilityState === 'visible';
    const reconcile = () => { webReturn.reconcileIfReturned(visible()); };
    const visibility = () => { if(visible()) reconcile(); else webReturn.markAway(); };
    const pageHide = () => webReturn.markAway();
    window.addEventListener('focus',reconcile);
    window.addEventListener('pageshow',reconcile);
    window.addEventListener('pagehide',pageHide);
    document.addEventListener('visibilitychange',visibility);
    return ()=>{
      window.removeEventListener('focus',reconcile);
      window.removeEventListener('pageshow',reconcile);
      window.removeEventListener('pagehide',pageHide);
      document.removeEventListener('visibilitychange',visibility);
    };
  },[webReturn]);
  const sessionMatches = accountSessionStatus.current === session.status
    && (session.status !== 'bootstrap' || accountSessionKey.current === session.key);
  const visibleState = session.status === 'bootstrap' && stateSessionKey.current === session.key ? state : null;
  const contextReady = ready && Boolean(isLoaded) && sessionMatches;
  const value: AccountContext = { ready:contextReady,signedIn:Boolean(isSignedIn),label:user?.primaryEmailAddress?.emailAddress || user?.fullName || 'Your account',error,state:visibleState,preferences,accept,refresh,
    signIn:async(signup=false,destination='/')=>{
      if(Platform.OS==='web') {
        const redirectUrl=absoluteAuthDestination(allowlistedAuthDestination(destination));
        if(signup) await clerk.redirectToSignUp({signUpForceRedirectUrl:redirectUrl,signUpFallbackRedirectUrl:redirectUrl});
        else await clerk.redirectToSignIn({signInForceRedirectUrl:redirectUrl,signInFallbackRedirectUrl:redirectUrl});
      }
      else await startHostedAuth({mode:signup?'sign-up':'sign-in'});
    },
    signOut:async()=>{
      // Keep the session available until the backend has removed this account's
      // current-device push ownership. A failure deliberately aborts sign-out.
      await accountRequest('/account/device/sign-out','POST');
      try { await clearPushRegistrationAfterBackendRevocation(); }
      catch (problem) { console.warn('Backend push was revoked, but local notification state could not be cleared.', problem); }
      await signOut();
      accountSessionKey.current='';stateSessionKey.current='';currentAccountId.current='';resync.invalidate();webReturn.reset();
      setTokenGetter(null);setState(null);setError('');
    },
    manage:async()=>{
      if(Platform.OS === 'web') webReturn.beginAccountManagement();
      try { await clerk.redirectToUserProfile(); }
      catch (problem) { if(Platform.OS === 'web') webReturn.cancelAccountManagement(); throw problem; }
    },
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function AccountProvider({children}:PropsWithChildren) {
  const auth = expoAuthConfiguration({
    requireWebOrigin: Platform.OS === 'web',
  });
  if(!auth.publishableKey) return <Context.Provider value={unavailableAccount(auth.error)}>{children}</Context.Provider>;
  return <ClerkProvider publishableKey={auth.publishableKey} tokenCache={tokenCache}><ConnectedAccount>{children}</ConnectedAccount></ClerkProvider>;
}
