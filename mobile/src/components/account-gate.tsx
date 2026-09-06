import { useState, type PropsWithChildren } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { useAccount } from '../lib/account-context';
import { useProductTheme } from '../theme/product-theme';

export function AccountGate({children}:PropsWithChildren) {
  const account=useAccount(); const {colors,scale}=useProductTheme(); const [error,setError]=useState('');
  if(account.ready&&account.signedIn&&account.state) return children;
  return <View style={{flex:1,justifyContent:'center',padding:24,backgroundColor:colors.background,gap:16}}>
    <Text accessibilityRole="header" style={{color:colors.text,fontSize:26*scale,fontWeight:'600'}}>Your Sportabase account</Text>
    <Text style={{color:colors.muted,fontSize:16*scale,lineHeight:24*scale}}>Sign in to analyze, save activity, manage watches and sync settings.</Text>
    {!account.ready?<ActivityIndicator accessibilityLabel="Loading account" color={colors.accent}/>:<>
      <Text accessibilityLiveRegion="polite" style={{color:colors.error,fontSize:16}}>{error||account.error}</Text>
      {[[account.signedIn?'Retry account connection':'Sign in',()=>account.signedIn?account.refresh():account.signIn()],['Create account',()=>account.signIn(true)]].map(([label,fn])=><Pressable key={String(label)} accessibilityRole="button" onPress={()=>void (fn as ()=>Promise<void>)().catch(e=>setError(e.message))} style={{padding:14,minHeight:48,borderRadius:6,backgroundColor:colors.accent}}><Text style={{color:colors.onAccent,fontSize:16*scale,fontWeight:'600'}}>{String(label)}</Text></Pressable>)}
    </>}
  </View>;
}
