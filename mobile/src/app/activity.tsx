import { useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { accountRequest } from '../lib/account-api';
import { useAccount } from '../lib/account-context';
import { useProductTheme } from '../theme/product-theme';
type Item={id:string;kind:string;title:string;url:string;created_at:number;platform:string};
export default function ActivityScreen(){
  const {colors,scale,rowPadding}=useProductTheme();const {preferences}=useAccount();const router=useRouter();
  const [items,setItems]=useState<Item[]>([]);const [q,setQ]=useState('');const [kind,setKind]=useState('');
  const [next,setNext]=useState<{before:number;cursor:string}|null>(null);const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  async function load(append=false){setBusy(true);setMessage('Loading activity…');try{
    const params=new URLSearchParams({q,kind,...(append&&next?{before:String(next.before),cursor:next.cursor}:{})});
    const data=await accountRequest<{items:Item[];next:typeof next}>(`/account/activity?${params}`);
    setItems(old=>append?[...old,...data.items]:data.items);setNext(data.next);setMessage(data.items.length?'':'No activity found. Completed analyses appear here when saving is enabled.');
  }catch(e){setMessage(e instanceof Error?e.message:'Could not load activity.');}finally{setBusy(false);}}
  useEffect(()=>{void load();},[kind]);
  const text={color:colors.text,fontSize:16*scale,lineHeight:24*scale};
  const button=(label:string,fn:()=>void,selected=false)=><Pressable key={label} accessibilityRole="button" accessibilityState={{selected}} disabled={busy} onPress={fn} style={{padding:12,minHeight:48,borderWidth:selected?2:1,borderColor:selected?colors.accent:colors.border,borderRadius:6,backgroundColor:selected?colors.accentSoft:'transparent'}}><Text style={[text,{fontWeight:selected?'700':'400'}]}>{label}</Text></Pressable>;
  return <SafeAreaView style={{flex:1,backgroundColor:colors.background}} edges={['top','left','right']}><ScrollView contentContainerStyle={{padding:20,gap:16}}>{button('‹ Settings',()=>router.push('/settings'))}<Text accessibilityRole="header" style={[text,{fontSize:28*scale,lineHeight:36*scale,fontWeight:'600'}]}>My Activity</Text><TextInput accessibilityLabel="Search My Activity" placeholder="Search titles" placeholderTextColor={colors.muted} value={q} onChangeText={setQ} onSubmitEditing={()=>void load()} style={[text,{padding:12,borderWidth:1,borderColor:colors.border,borderRadius:6}]}/>{button('Search',()=>void load())}<View accessibilityRole="tablist" style={{flexDirection:'row',flexWrap:'wrap',gap:8}}>{['','article','video'].map(value=>button(value||'All',()=>setKind(value),kind===value))}</View><Text accessibilityLiveRegion="polite" style={[text,{color:colors.muted}]}>{message}</Text>{items.map(item=>{const canOpen=/^https?:\/\//.test(item.url);return <Pressable key={item.id} {...(canOpen?{accessibilityRole:'link' as const}: {})} disabled={!canOpen} onPress={()=>void Linking.openURL(item.url).catch(()=>setMessage('Could not open source.'))} style={{paddingVertical:rowPadding,borderBottomWidth:1,borderBottomColor:colors.border}}><Text style={[text,{fontWeight:'600'}]}>{item.title}</Text><Text style={[text,{color:colors.muted,fontSize:14*scale}]}>{item.kind==='article'?'Article':'Video'} · {item.platform==='mobile'?'Mobile':item.platform} · {preferences.date_format==='iso'?new Date(item.created_at*1000).toISOString().slice(0,10):new Date(item.created_at*1000).toLocaleString()}</Text></Pressable>;})}{next?button('Load more',()=>void load(true)):null}</ScrollView></SafeAreaView>;
}
