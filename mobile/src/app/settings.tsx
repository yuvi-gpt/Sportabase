import { useEffect, useState } from 'react';
import { Linking, Modal, Pressable, ScrollView, Share, Switch, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAccount } from '../lib/account-context';
import { accountRequest, canonicalPrivacyUrl, contract, type AccountState } from '../lib/account-api';
import { AccountGate } from '../components/account-gate';
import { useProductTheme } from '../theme/product-theme';
import Constants from 'expo-constants';

const sectionGroups=[
  {label:'Account',items:['Account','Devices/Sessions']},
  {label:'Preferences',items:['Appearance','Notifications','Analysis','Language & Region']},
  {label:'Your data',items:['My Activity','Privacy & Data']},
  {label:'Support',items:['Support/About']},
];
const valueLabels:Record<string,string>={system:'System setting',en:'English',full:'Full detail',essential:'Essential detail',comfortable:'Comfortable',compact:'Compact',standard:'Standard',high:'High contrast',reduce:'Reduce motion',light:'Light',dark:'Dark',small:'Smaller',large:'Larger',iso:'YYYY-MM-DD'};
const valueLabel=(value:unknown)=>valueLabels[String(value)]||String(value);
type Field={label:string;options?:string[];type?:string;accountOnly?:boolean};
const fields=contract.fields as Record<string,Field>;
const grouped=contract.sections as Record<string,string[]>;
export default function SettingsScreen() {
  const account=useAccount();const theme=useProductTheme();const {colors,scale}=theme;const router=useRouter();
  const [section,setSection]=useState('');const [scope,setScope]=useState<'device'|'account'>('device');
  const [message,setMessage]=useState('');const [messageTone,setMessageTone]=useState<'neutral'|'success'|'error'>('neutral');const [busy,setBusy]=useState(false);
  const [selection,setSelection]=useState<string|null>(null);const [draft,setDraft]=useState<Record<string,unknown>>({});
  const [devices,setDevices]=useState<{device_id:string;name:string;platform:string;current:boolean}[]>([]);
  const [confirmation,setConfirmation]=useState<'activity'|'account'|null>(null);
  useEffect(()=>{if(account.state) void accountRequest('/account/events','POST',{event:'settings_opened'}).catch(()=>{});},[account.state?.account.id]);
  useEffect(()=>{setDraft({}); if(section==='Devices/Sessions')void accountRequest<{items:typeof devices}>('/account/devices').then(data=>setDevices(data.items)).catch(e=>{setMessageTone('error');setMessage(e.message);});},[section]);
  const text={color:colors.text,fontSize:16*scale,lineHeight:24*scale};
  const row={paddingVertical:theme.rowPadding,minHeight:52,borderBottomWidth:theme.high?2:1,borderBottomColor:colors.border,gap:10};
  async function run(fn:()=>Promise<unknown>) {setBusy(true);setMessage('');setMessageTone('neutral');try{await fn();}catch(e){setMessageTone('error');setMessage(e instanceof Error?e.message:'Could not complete action.');}finally{setBusy(false);}}
  const button=(label:string,fn:()=>void,danger=false)=><Pressable key={label} accessibilityRole="button" disabled={busy} onPress={fn} style={({pressed})=>[row,{opacity:busy?.6:pressed?.68:1}]}><Text style={[text,{fontWeight:'600',color:danger?colors.error:colors.text}]}>{label}</Text></Pressable>;
  const destination=(label:string,fn:()=>void,detail='')=><Pressable key={label} accessibilityRole="button" onPress={fn} style={({pressed})=>[row,{flexDirection:'row',alignItems:'center',justifyContent:'space-between',opacity:pressed?.68:1}]}><View style={{flex:1}}><Text style={[text,{fontWeight:'600'}]}>{label}</Text>{detail?<Text style={[text,{color:colors.muted,fontSize:14*scale}]}>{detail}</Text>:null}</View><Text accessible={false} style={[text,{color:colors.accent,fontSize:24*scale}]}>›</Text></Pressable>;
  const currentScope=section==='Privacy & Data'?'account':scope;
  const values={...(currentScope==='account'?account.state?.defaults:account.state?.effective),...draft} as Record<string,unknown>;
  const disabled=busy||(currentScope==='device'&&Boolean(account.state?.follows_defaults));
  async function save(patch=draft,follows?:boolean){
    if(!account.state)return;
    await run(async()=>{const next=await accountRequest<AccountState>('/account/preferences','PATCH',{version:contract.version,scope:currentScope,revision:currentScope==='account'?account.state!.account_revision:account.state!.device_revision,preferences:patch,...(follows===undefined?{}:{follows_defaults:follows})});account.accept(next);setDraft({});setMessageTone('success');setMessage(currentScope==='account'?'Saved to account defaults':next.follows_defaults?'This device now follows account defaults':'Saved on this device');});
  }
  async function exportData(){await run(async()=>{const data=await accountRequest('/account/export');await Share.share({message:JSON.stringify(data,null,2),title:'Sportabase personal data'});});}
  return <SafeAreaView style={{flex:1,backgroundColor:colors.background}} edges={['top','left','right']}><ScrollView contentContainerStyle={{padding:20,paddingBottom:40}}>
    {section?<Pressable accessibilityRole="button" accessibilityLabel="Back to Settings" onPress={()=>setSection('')} style={{alignSelf:'flex-start',minHeight:44,justifyContent:'center'}}><Text style={[text,{color:colors.accent,fontWeight:'600'}]}>‹ Settings</Text></Pressable>:null}
    <Text accessibilityRole="header" style={[text,{fontSize:28*scale,lineHeight:36*scale,fontWeight:'600',marginTop:section?4:16,marginBottom:16}]}>{section||'Settings'}</Text>
    {!section?<>
      <View style={{padding:16,borderWidth:theme.high?2:1,borderColor:colors.border,borderRadius:10,backgroundColor:colors.surface,marginBottom:12}}><Text style={[text,{fontWeight:'600'}]}>{account.signedIn?account.label:'Sportabase account'}</Text><Text style={[text,{color:colors.muted,fontSize:14*scale}]}>{account.signedIn?(account.state?.follows_defaults?'Synced · Account defaults':'Synced · Device overrides'):'Sign in to use product actions'}</Text></View>
      {sectionGroups.map(group=><View key={group.label} style={{marginTop:18}}><Text style={[text,{color:colors.muted,fontSize:14*scale,fontWeight:'600',marginBottom:4}]}>{group.label}</Text>{group.items.map(name=>destination(name,()=>name==='My Activity'?router.push('/activity'):setSection(name),name==='Notifications'?'Push and quiet hours':name==='Privacy & Data'?'Activity, export and deletion':'') )}</View>)}
    </>:section==='Support/About'?<><Text style={text}>Sportabase {Constants.expoConfig?.version||'product lab'}</Text><Text style={[text,{marginTop:16}]}>Your account preferences sync across installations. Device overrides stay specific to this installation. Optional usage sharing stores narrow event counts; necessary account, device, watch and notification records remain while the account is active. Article bodies, transcripts and credentials are excluded from analytics.</Text>{canonicalPrivacyUrl()?button('Privacy and data policy',()=>void Linking.openURL(canonicalPrivacyUrl()!)):<Text style={[text,{marginTop:16,color:colors.muted}]}>The canonical privacy page is not configured for this build.</Text>}</>:<AccountGate>
      {section==='Account'?<>
        <Text style={text}>{account.label}</Text><Text style={[text,{color:colors.muted}]}>Connected · {account.state?.follows_defaults?'Using account defaults':'Device overrides enabled'}</Text>
        {button('Manage account / sessions',()=>void run(account.manage))}{button('Sign out',()=>void run(account.signOut))}{button('Refresh account',()=>void run(account.refresh))}
      </>:section==='Devices/Sessions'?<>{devices.map(device=><Text key={device.device_id} style={[text,row]}>{device.name} · {device.platform}{device.current?' · This device':''}</Text>)}{button('Manage sign-in sessions',()=>void run(account.manage))}</>:<>
        {section!=='Privacy & Data'?destination('Settings location',()=>setSelection('__scope'),currentScope==='account'?'Account defaults':'This device'):null}
        {currentScope==='device'?<View style={row}><Text style={text}>Use account defaults on this device</Text><Switch accessibilityLabel="Use account defaults on this device" value={account.state?.follows_defaults} disabled={busy} onValueChange={value=>void save({},value)}/></View>:null}
        {(grouped[section]||[]).map(key=>{
          const field=fields[key],value=values[key];
          const notificationChild=section==='Notifications'&&['entity_alerts','story_alerts','claim_alerts','media_alerts','quiet_hours_enabled','quiet_hours_start','quiet_hours_end','timezone'].includes(key);
          const quietChild=section==='Notifications'&&['quiet_hours_start','quiet_hours_end','timezone'].includes(key);
          if(quietChild&&!Boolean(values.quiet_hours_enabled))return null;
          const fieldDisabled=disabled||(notificationChild&&!Boolean(values.notifications_enabled))||(quietChild&&!Boolean(values.quiet_hours_enabled));
          return <View key={key} style={row}><Text style={text}>{field.label}</Text>
            {typeof value==='boolean'?<Switch accessibilityLabel={field.label} disabled={fieldDisabled} value={value} onValueChange={next=>setDraft({...draft,[key]:next})}/>:field.options?<Pressable accessibilityRole="button" accessibilityLabel={`${field.label}: ${valueLabel(value)}`} disabled={fieldDisabled} onPress={()=>setSelection(key)} style={{padding:12,borderWidth:1,borderColor:colors.border,borderRadius:6,minHeight:48,opacity:fieldDisabled?.55:1}}><Text style={text}>{valueLabel(value)}</Text></Pressable>:<TextInput accessibilityLabel={field.label} editable={!fieldDisabled} value={String(value??'')} autoCapitalize="none" autoCorrect={false} maxLength={80} onChangeText={next=>setDraft({...draft,[key]:next})} style={[text,{padding:12,borderWidth:1,borderColor:colors.border,borderRadius:6,minHeight:48,opacity:fieldDisabled?.55:1}]} />}
          </View>;
        })}
        {Object.keys(draft).length?button('Save changes',()=>void save()):null}
        {section==='Notifications'?<><Text style={[text,{marginTop:16,color:colors.muted}]}>Choose a city-based timezone such as Asia/Kolkata. Alerts remain in your inbox while push delivery is paused.</Text>{button('Push status on this device',()=>router.push('/notifications'))}</>:null}
        {section==='Analysis'?<Text style={[text,{marginTop:16}]}>Essential detail collapses supplemental explanation. Evidence and logic scores remain separate; score definitions and qualifications stay visible.</Text>:null}
        {section==='Language & Region'?<Text style={[text,{marginTop:16}]}>English is the currently supported interface language. System uses English. Analysis keeps its existing language support.</Text>:null}
        {section==='Privacy & Data'?<><Text style={[text,{marginTop:16}]}>Optional usage sharing stores narrow product event counts. Disabling it removes those optional events, but necessary account lifecycle, device, watch ownership and notification registration records remain while your account is active. Activity includes safe titles and sanitized revisit links until cleared.</Text>{button('Export personal data',()=>void exportData())}{button('Clear My Activity',()=>setConfirmation('activity'),true)}{button('Delete account',()=>setConfirmation('account'),true)}</>:null}
      </>}
    </AccountGate>}
    <Text accessibilityLiveRegion="polite" style={[text,{color:messageTone==='error'?colors.error:messageTone==='success'?colors.accent:colors.muted,marginTop:16}]}>{message}</Text>
  </ScrollView>
  <Modal visible={Boolean(selection)} transparent animationType={theme.reduceMotion?'none':'fade'} onRequestClose={()=>setSelection(null)}><View style={{flex:1,justifyContent:'center',padding:24,backgroundColor:'#0009'}}><View accessibilityViewIsModal style={{backgroundColor:colors.surface,padding:20,borderRadius:12}}><Text accessibilityRole="header" style={[text,{fontWeight:'600',marginBottom:8}]}>{selection==='__scope'?'Settings location':selection?fields[selection].label:''}</Text>{(selection==='__scope'?['device','account']:selection?fields[selection].options||[]:[]).map(option=><Pressable key={option} accessibilityRole="button" accessibilityState={{selected:selection==='__scope'?scope===option:values[selection!]===option}} onPress={()=>{if(selection==='__scope'){setScope(option as 'device'|'account');setDraft({});}else setDraft({...draft,[selection!]:option});setSelection(null);}} style={row}><Text style={[text,{fontWeight:(selection==='__scope'?scope===option:values[selection!]===option)?'700':'400',color:(selection==='__scope'?scope===option:values[selection!]===option)?colors.accent:colors.text}]}>{selection==='__scope'?(option==='account'?'Account defaults':'This device'):valueLabel(option)}</Text></Pressable>)}{button('Cancel',()=>setSelection(null))}</View></View></Modal>
  <Modal visible={Boolean(confirmation)} transparent animationType="none" onRequestClose={()=>setConfirmation(null)}><View style={{flex:1,justifyContent:'center',padding:24,backgroundColor:'#0009'}}><View accessibilityViewIsModal style={{backgroundColor:colors.surface,padding:20,borderRadius:12}}><Text style={text}>{confirmation==='account'?'Delete your account and private Sportabase data? A recent account verification is required.':'Clear My Activity on every device? Canonical intelligence remains available.'}</Text>{button('Cancel',()=>setConfirmation(null))}{button(confirmation==='account'?'Delete account':'Clear My Activity',()=>void run(async()=>{const deletingAccount=confirmation==='account';await accountRequest(deletingAccount?'/account':'/account/activity','DELETE',{confirmation:deletingAccount?'DELETE MY ACCOUNT':'CLEAR MY ACTIVITY'});setConfirmation(null);setMessageTone('success');setMessage(deletingAccount?'Sportabase account deleted':'My Activity cleared');if(deletingAccount)await account.signOut();}),true)}</View></View></Modal>
  </SafeAreaView>;
}
