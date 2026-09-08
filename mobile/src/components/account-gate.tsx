import { useState, type PropsWithChildren } from 'react';
import { View } from 'react-native';
import { useAccount } from '../lib/account-context';
import { ProductButton, ProductStatus } from '../product-ui/ProductPrimitives';

export function AccountGate({ children }: PropsWithChildren) {
  const account = useAccount(); const [error, setError] = useState('');
  if (account.ready && account.signedIn && account.state) return children;
  const detail = !account.ready ? 'Checking your Sportabase account.' : 'Sign in to manage synchronized preferences, activity, watches, devices, and private data.';
  return <View style={{ gap: 16 }}><ProductStatus loading={!account.ready} title="Your Sportabase account" detail={detail} />{account.ready ? <View style={{ alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}><ProductButton label={account.signedIn ? 'Retry account connection' : 'Sign in'} onPress={() => void (account.signedIn ? account.refresh() : account.signIn(false, '/settings')).catch((problem) => setError(problem instanceof Error ? problem.message : 'Account access is unavailable.'))} variant="primary" />{!account.signedIn ? <ProductButton label="Create account" onPress={() => void account.signIn(true, '/settings').catch((problem) => setError(problem instanceof Error ? problem.message : 'Account creation is unavailable.'))} /> : null}</View> : null}{error || account.error ? <ProductStatus title="Account access is unavailable" detail={error || account.error} tone="error" /> : null}</View>;
}
