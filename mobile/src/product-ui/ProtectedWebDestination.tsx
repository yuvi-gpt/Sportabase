import { useCallback, useEffect, useRef, useState, type PropsWithChildren } from 'react';
import { Platform, View } from 'react-native';
import { useAccount } from '../lib/account-context';
import type { ProtectedWebDestination as Destination } from '../lib/auth-destinations';
import { ProductButton, ProductPage, ProductPageHeader, ProductStatus } from './ProductPrimitives';

type Props = PropsWithChildren<{ destination: Destination; title: string }>;
function attemptKey(destination: Destination) { return `sportabase:auth-attempt:${destination}`; }
function readPendingAttempt(destination: Destination) { return Platform.OS === 'web' && typeof window !== 'undefined' && window.sessionStorage.getItem(attemptKey(destination)) === 'pending'; }
function markPendingAttempt(destination: Destination, pending: boolean) {
  if (Platform.OS !== 'web' || typeof window === 'undefined') return;
  if (pending) window.sessionStorage.setItem(attemptKey(destination), 'pending'); else window.sessionStorage.removeItem(attemptKey(destination));
}

export function ProtectedWebDestination({ children, destination, title }: Props) {
  const account = useAccount();
  const attempted = useRef(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const beginSignIn = useCallback(async (signup = false) => {
    setBusy(true); setMessage(''); markPendingAttempt(destination, true);
    try { await account.signIn(signup, destination); }
    catch (problem) {
      markPendingAttempt(destination, false);
      setMessage(problem instanceof Error ? problem.message : `Sportabase sign-in is unavailable. Try again to open ${title}.`);
      setBusy(false);
    }
  }, [account, destination, title]);

  useEffect(() => {
    if (Platform.OS !== 'web' || !account.ready) return;
    if (account.signedIn) { markPendingAttempt(destination, false); return; }
    if (attempted.current) return;
    attempted.current = true;
    if (readPendingAttempt(destination)) {
      markPendingAttempt(destination, false);
      setMessage(`Sign-in was not completed. Try again to open ${title}.`);
      return;
    }
    void beginSignIn();
  }, [account.ready, account.signedIn, beginSignIn, destination, title]);

  if (Platform.OS !== 'web') return children;
  if (account.ready && account.signedIn && account.state) return children;

  const copy = !account.ready ? `Checking your account before opening ${title}.` : account.signedIn ? `Your Sportabase account could not finish syncing. Retry the connection to open ${title}.` : `Sign in with Sportabase to open ${title}. You will return here after sign-in.`;
  const error = message || account.error;
  return <ProductPage width="reading" watermark testID="protected-account-gate">
    <View style={{ justifyContent: 'center', minHeight: 470 }}>
      <ProductPageHeader label="Account required" title={title} description={copy} />
      <View style={{ alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 24 }}>
        {!account.ready || busy ? <ProductStatus loading title={!account.ready ? 'Checking account' : 'Opening secure sign-in'} /> : <><ProductButton label={account.signedIn ? 'Retry account connection' : 'Sign in'} onPress={() => { if (account.signedIn) void account.refresh().catch((problem) => setMessage(problem instanceof Error ? problem.message : 'Sportabase could not retry the account connection.')); else void beginSignIn(); }} variant="primary" />{!account.signedIn ? <ProductButton label="Create account" onPress={() => void beginSignIn(true)} /> : null}</>}
      </View>
      {error ? <View style={{ marginTop: 18 }}><ProductStatus title="Account access is unavailable" detail={error} tone="error" /></View> : null}
    </View>
  </ProductPage>;
}
