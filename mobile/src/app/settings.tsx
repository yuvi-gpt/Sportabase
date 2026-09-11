import { useCallback, useEffect, useState } from 'react';
import { Linking, Platform, Share, Switch, Text, TextInput, View, useWindowDimensions } from 'react-native';
import { useRouter } from 'expo-router';
import Constants from 'expo-constants';

import { AccountGate } from '../components/account-gate';
import { accountRequest, canonicalPrivacyUrl, contract, type AccountState } from '../lib/account-api';
import { useAccount } from '../lib/account-context';
import { useProductTheme } from '../theme/product-theme';
import { ProductButton, ProductDialog, ProductPage, ProductPageHeader, ProductRow, ProductSection, ProductStatus, ProductSurface } from '../product-ui/ProductPrimitives';
import { productFonts } from '../product-ui/tokens';

const sectionGroups = [
  { label: 'Account', items: ['Account', 'Devices/Sessions'] },
  { label: 'Preferences', items: ['Appearance', 'Notifications', 'Analysis', 'Language & Region'] },
  { label: 'Your data', items: ['My Activity', 'Privacy & Data'] },
  { label: 'Support', items: ['Support/About'] },
] as const;
const descriptions: Record<string, string> = {
  Account: 'Identity, connection, and account access', 'Devices/Sessions': 'Known installations and sign-in sessions', Appearance: 'Theme, contrast, text, density, and motion', Notifications: 'Push categories and quiet hours', Analysis: 'Amount of supporting analysis shown', 'My Activity': 'Saved article and video analyses', 'Language & Region': 'Interface language and date display', 'Privacy & Data': 'Usage counts, activity, export, and deletion', 'Support/About': 'Version, privacy policy, and data boundaries',
};
const valueLabels: Record<string, string> = { system: 'System setting', en: 'English', full: 'Full detail', essential: 'Essential detail', comfortable: 'Comfortable', compact: 'Compact', standard: 'Standard', high: 'High contrast', reduce: 'Reduce motion', light: 'Light', dark: 'Dark', small: 'Smaller', large: 'Larger', iso: 'YYYY-MM-DD' };
const valueLabel = (value: unknown) => valueLabels[String(value)] || String(value);
type Field = { label: string; options?: string[]; type?: string; accountOnly?: boolean };
const fields = contract.fields as Record<string, Field>;
const grouped = contract.sections as Record<string, string[]>;

export default function SettingsScreen() {
  const account = useAccount(); const theme = useProductTheme(); const { colors, scale } = theme; const router = useRouter(); const { width } = useWindowDimensions(); const desktop = width >= 900;
  const [section, setSection] = useState(''); const [scope, setScope] = useState<'device' | 'account'>('device'); const [message, setMessage] = useState(''); const [messageTone, setMessageTone] = useState<'neutral' | 'success' | 'error'>('neutral'); const [busy, setBusy] = useState(false); const [draft, setDraft] = useState<Record<string, unknown>>({}); const [devices, setDevices] = useState<{ device_id: string; name: string; platform: string; current: boolean }[]>([]); const [confirmation, setConfirmation] = useState<'activity' | 'account' | null>(null);
  useEffect(() => { if (account.state) void accountRequest('/account/events', 'POST', { event: 'settings_opened' }).catch(() => {}); }, [account.state?.account.id]);
  useEffect(() => { setDraft({}); if (section === 'Devices/Sessions') void accountRequest<{ items: typeof devices }>('/account/devices').then((data) => setDevices(data.items)).catch((problem) => { setMessageTone('error'); setMessage(problem instanceof Error ? problem.message : 'Could not load devices.'); }); }, [section]);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined' || Object.keys(draft).length === 0) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [draft]);
  const closeConfirmation = useCallback(() => setConfirmation(null), []);
  async function run(action: () => Promise<unknown>) { setBusy(true); setMessage(''); setMessageTone('neutral'); try { await action(); } catch (problem) { setMessageTone('error'); setMessage(problem instanceof Error ? problem.message : 'Could not complete action.'); } finally { setBusy(false); } }
  const currentScope = section === 'Privacy & Data' ? 'account' : scope;
  const values = { ...(currentScope === 'account' ? account.state?.defaults : account.state?.effective), ...draft } as Record<string, unknown>;
  const fieldsDisabled = busy || (currentScope === 'device' && Boolean(account.state?.follows_defaults));
  async function save(patch = draft, follows?: boolean) {
    if (!account.state) return;
    await run(async () => { const next = await accountRequest<AccountState>('/account/preferences', 'PATCH', { version: contract.version, scope: currentScope, revision: currentScope === 'account' ? account.state!.account_revision : account.state!.device_revision, preferences: patch, ...(follows === undefined ? {} : { follows_defaults: follows }) }); account.accept(next); setDraft({}); setMessageTone('success'); setMessage(currentScope === 'account' ? 'Saved to account defaults' : next.follows_defaults ? 'This device now follows account defaults' : 'Saved on this device'); });
  }
  async function exportData() { await run(async () => { const data = await accountRequest('/account/export'); await Share.share({ message: JSON.stringify(data, null, 2), title: 'Sportabase personal data' }); }); }
  function scrollSettingsTop() { if (Platform.OS === 'web' && typeof document !== 'undefined') window.requestAnimationFrame(() => document.getElementById('sportabase-page-scroll')?.scrollTo({ top: 0 })); }
  function openSection(name: string) {
    if (name !== section && Object.keys(draft).length) { setMessageTone('error'); setMessage('Save or discard the current changes before leaving this section.'); return; }
    if (name === 'My Activity') router.push('/activity'); else { setSection(name); setMessage(''); setMessageTone('neutral'); scrollSettingsTop(); }
  }

  const navigation = <View style={{ gap: 22 }}>{sectionGroups.map((group) => <ProductSection key={group.label} title={group.label}><View>{group.items.map((name) => <ProductRow key={name} title={name} description={descriptions[name]} onPress={() => openSection(name)} selected={section === name} />)}</View></ProductSection>)}</View>;

  function fieldRows() {
    return <View>{(grouped[section] || []).map((key) => {
      const field = fields[key]; const value = values[key];
      const notificationChild = section === 'Notifications' && ['entity_alerts', 'story_alerts', 'claim_alerts', 'media_alerts', 'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end', 'timezone'].includes(key);
      const quietChild = section === 'Notifications' && ['quiet_hours_start', 'quiet_hours_end', 'timezone'].includes(key);
      if (quietChild && !Boolean(values.quiet_hours_enabled)) return null;
      const disabled = fieldsDisabled || (notificationChild && !Boolean(values.notifications_enabled));
      return <ProductSurface key={key} style={{ borderLeftWidth: 0, borderRightWidth: 0, borderTopWidth: 0, gap: 12 }}>
        <View style={{ alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' }}><Text style={{ color: colors.text, flex: 1, fontFamily: productFonts.emphasis, fontSize: 16 * scale, minWidth: 180 }}>{field.label}</Text>
          {typeof value === 'boolean' ? <Switch accessibilityLabel={field.label} disabled={disabled} value={value} onValueChange={(next) => setDraft((current) => ({ ...current, [key]: next }))} trackColor={{ false: colors.surfaceRaised, true: colors.accentSoft }} thumbColor={value ? colors.accent : colors.muted} /> : field.options ? <View accessibilityRole="radiogroup" style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{field.options.map((option) => <ProductButton key={option} label={valueLabel(option)} accessibilityLabel={`${field.label}: ${valueLabel(option)}`} onPress={() => setDraft((current) => ({ ...current, [key]: option }))} variant={value === option ? 'primary' : 'secondary'} disabled={disabled} />)}</View> : <TextInput accessibilityLabel={field.label} editable={!disabled} value={String(value ?? '')} autoCapitalize="none" autoCorrect={false} maxLength={80} onChangeText={(next) => setDraft((current) => ({ ...current, [key]: next }))} style={{ backgroundColor: colors.surfaceRaised, borderColor: colors.border, borderRadius: 8, borderWidth: 1, color: colors.text, fontFamily: productFonts.body, fontSize: 16 * scale, minHeight: 48, minWidth: 190, padding: 12 }} />}
        </View>
      </ProductSurface>;
    })}</View>;
  }

  function workspace() {
    if (!section) return <ProductStatus title="Choose a Settings section" detail="Account and product preferences are grouped by purpose. Settings never change intelligence scores, evidence judgments, graph relationships, or reconciliation." />;
    if (section === 'Support/About') return <ProductSection title="Support/About"><ProductSurface style={{ gap: 14 }}><Text style={{ color: colors.text, fontFamily: productFonts.emphasis, fontSize: 18 * scale }}>Sportabase {Constants.expoConfig?.version || 'local build'}</Text><Text style={{ color: colors.textMuted, fontFamily: productFonts.body, fontSize: 15 * scale, lineHeight: 22 * scale }}>Account preferences sync across installations; device overrides remain local. Optional usage sharing stores narrow event counts. Article bodies, transcripts, and credentials are excluded from analytics.</Text>{canonicalPrivacyUrl() ? <View style={{ alignItems: 'flex-start' }}><ProductButton label="Open privacy and data policy" onPress={() => void Linking.openURL(canonicalPrivacyUrl()!)} /></View> : <ProductStatus title="Privacy page not configured" detail="The canonical privacy page is unavailable in this build." />}</ProductSurface></ProductSection>;
    return <AccountGate><View style={{ gap: 24 }}>
      {section === 'Account' ? <ProductSection title="Account"><ProductSurface style={{ gap: 14 }}><Text style={{ color: colors.text, fontFamily: productFonts.emphasis, fontSize: 18 * scale }}>{account.label}</Text><Text style={{ color: colors.textMuted, fontFamily: productFonts.body }}>{account.state?.follows_defaults ? 'Connected · using account defaults' : 'Connected · device overrides enabled'}</Text><View style={{ alignItems: 'flex-start', gap: 8 }}><ProductButton label="Manage account and sessions" onPress={() => void run(account.manage)} /><ProductButton label="Refresh account" onPress={() => void run(account.refresh)} /><ProductButton label="Sign out" onPress={() => void run(account.signOut)} variant="danger" /></View></ProductSurface></ProductSection> : section === 'Devices/Sessions' ? <ProductSection title="Devices/Sessions" description="Known Sportabase installations; session controls are handled by the supported account provider."><View>{devices.length ? devices.map((device) => <ProductRow key={device.device_id} label={device.current ? 'This device' : device.platform} title={device.name} description={device.platform} />) : <ProductStatus title="No device records are available" />}</View><View style={{ alignItems: 'flex-start' }}><ProductButton label="Manage sign-in sessions" onPress={() => void run(account.manage)} /></View></ProductSection> : <>
        {section !== 'Privacy & Data' ? <ProductSection title="Settings location" description="Choose whether edits become account defaults or apply only to this device."><View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}><ProductButton label="This device" onPress={() => { setScope('device'); setDraft({}); }} variant={scope === 'device' ? 'primary' : 'secondary'} /><ProductButton label="Account defaults" onPress={() => { setScope('account'); setDraft({}); }} variant={scope === 'account' ? 'primary' : 'secondary'} /></View>{currentScope === 'device' ? <ProductSurface style={{ alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' }}><Text style={{ color: colors.text, flex: 1, fontFamily: productFonts.emphasis, fontSize: 16 * scale }}>Use account defaults on this device</Text><Switch accessibilityLabel="Use account defaults on this device" value={Boolean(account.state?.follows_defaults)} disabled={busy} onValueChange={(value) => void save({}, value)} /></ProductSurface> : null}</ProductSection> : null}
        <ProductSection title={section} description={descriptions[section]}>{fieldRows()}</ProductSection>
        {Object.keys(draft).length ? <View style={{ alignItems: 'flex-start' }}><ProductButton label={busy ? 'Saving…' : 'Save changes'} onPress={() => void save()} variant="primary" disabled={busy} /></View> : null}
        {section === 'Notifications' ? <><ProductStatus title="Quiet hours use a city-based timezone" detail="Use an IANA timezone such as Asia/Kolkata. Alerts remain in your inbox while push delivery is paused." /><View style={{ alignItems: 'flex-start' }}><ProductButton label="Push status on this device" onPress={() => router.push('/notifications')} /></View></> : null}
        {section === 'Analysis' ? <ProductStatus title="Display detail only" detail="Essential detail may collapse supplemental explanation. Score definitions, qualifications, Evidence Score, Logic Score, and Verdict remain visible and separate." /> : null}
        {section === 'Language & Region' ? <ProductStatus title="English is currently supported" detail="System uses English. Analysis retains its existing language support." /> : null}
        {section === 'Privacy & Data' ? <ProductSection title="Data actions" description="Optional usage sharing stores narrow product event counts. Necessary account, device, watch, and notification records remain while the account is active."><View style={{ alignItems: 'flex-start', gap: 8 }}><ProductButton label="Export personal data" onPress={() => void exportData()} /><ProductButton label="Clear My Activity" onPress={() => setConfirmation('activity')} variant="danger" /><ProductButton label="Delete account" onPress={() => setConfirmation('account')} variant="danger" /></View></ProductSection> : null}
      </>}
    </View></AccountGate>;
  }

  return <><ProductPage width="settings" testID="settings-page">
    {!desktop && section ? <View style={{ alignItems: 'flex-start' }}><ProductButton label="Back to Settings" onPress={() => openSection('')} variant="quiet" /></View> : null}
    <ProductPageHeader label="Product controls" title={desktop || !section ? 'Settings' : section} description={desktop || !section ? 'Operational preferences for your account and this installation.' : descriptions[section]} />
    <ProductSurface elevated style={{ gap: 4 }}><Text style={{ color: colors.text, fontFamily: productFonts.emphasis, fontSize: 17 * scale }}>{account.signedIn ? account.label : 'Sportabase account'}</Text><Text style={{ color: colors.textMuted, fontFamily: productFonts.body, fontSize: 14 * scale }}>{account.signedIn ? account.state?.follows_defaults ? 'Synced · account defaults' : 'Synced · device overrides' : 'Signed out · public Settings remain available'}</Text></ProductSurface>
    {desktop ? <View style={{ alignItems: 'flex-start', flexDirection: 'row', gap: 32 }}><View style={{ flexBasis: 300, flexShrink: 0 }}>{navigation}</View><View style={{ flex: 1, minWidth: 0 }}>{workspace()}</View></View> : section ? workspace() : navigation}
    {message ? <ProductStatus title={messageTone === 'error' ? 'Settings could not be updated' : message} detail={messageTone === 'error' ? message : undefined} tone={messageTone === 'error' ? 'error' : messageTone === 'success' ? 'success' : 'neutral'} /> : null}
  </ProductPage>
  <ProductDialog visible={Boolean(confirmation)} title={confirmation === 'account' ? 'Delete Sportabase account?' : 'Clear My Activity?'} description={confirmation === 'account' ? 'This deletes your account and private Sportabase data. A recent account verification is required.' : 'This clears saved activity on every device. Canonical intelligence remains available.'} onClose={closeConfirmation} closeLabel="Cancel"><ProductButton label={busy ? 'Working…' : confirmation === 'account' ? 'Delete account' : 'Clear My Activity'} onPress={() => void run(async () => { const deletingAccount = confirmation === 'account'; await accountRequest(deletingAccount ? '/account' : '/account/activity', 'DELETE', { confirmation: deletingAccount ? 'DELETE MY ACCOUNT' : 'CLEAR MY ACTIVITY' }); setConfirmation(null); setMessageTone('success'); setMessage(deletingAccount ? 'Sportabase account deleted' : 'My Activity cleared'); if (deletingAccount) await account.signOut(); })} variant="danger" disabled={busy} /></ProductDialog>
  </>;
}
