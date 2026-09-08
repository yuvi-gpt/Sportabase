import { useEffect, useRef, type ReactNode } from 'react';
import { ActivityIndicator, Modal, Platform, Pressable, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions, type TextInputProps, type ViewStyle } from 'react-native';
import { useProductTheme } from '../theme/product-theme';
import { ProductWatermark } from './ProductWatermark';
import { productFonts, productRadius, productWidths } from './tokens';

type Width = keyof typeof productWidths;

export function ProductPage({ children, width = 'content', watermark = false, scroll = true, testID }: { children: ReactNode; width?: Width; watermark?: boolean; scroll?: boolean; testID?: string }) {
  const { colors, spacing, scale } = useProductTheme();
  const viewport = useWindowDimensions();
  const responsiveKey = viewport.width < 600 ? 'narrow' : viewport.width < 900 ? 'compact' : 'wide';
  const horizontal = viewport.width < 390 ? 14 : viewport.width < 720 ? 20 : 32;
  const content = <View style={[styles.pageContent, { gap: spacing.section * scale, maxWidth: productWidths[width], paddingBottom: 72 * scale, paddingHorizontal: horizontal, paddingTop: (viewport.width < 720 ? 24 : 42) * scale }]}>{children}</View>;
  return (
    <SafeAreaView style={[styles.page, { backgroundColor: colors.background }]} testID={testID}>
      {watermark ? <ProductWatermark compact /> : null}
      {scroll ? <ScrollView key={responsiveKey} nativeID="sportabase-page-scroll" contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">{content}</ScrollView> : content}
    </SafeAreaView>
  );
}

export function ProductPageHeader({ label, title, description, aside }: { label?: string; title: string; description?: string; aside?: ReactNode }) {
  const { colors, scale } = useProductTheme();
  return (
    <View style={[styles.pageHeader, { gap: 20 * scale }]}>
      <View style={[styles.headerCopy, { gap: 8 * scale }]}>
        {label ? <Text style={[styles.eyebrow, { color: colors.accent }]}>{label}</Text> : null}
        <Text accessibilityRole="header" aria-level={1} style={[styles.pageTitle, { color: colors.text, fontSize: 42 * scale, lineHeight: 44 * scale }]}>{title}</Text>
        {description ? <Text style={[styles.pageDescription, { color: colors.textMuted, fontSize: 17 * scale, lineHeight: 25 * scale }]}>{description}</Text> : null}
      </View>
      {aside ? <View style={styles.headerAside}>{aside}</View> : null}
    </View>
  );
}

export function ProductSection({ title, description, action, children, style }: { title?: string; description?: string; action?: ReactNode; children: ReactNode; style?: ViewStyle }) {
  const { colors, spacing, scale } = useProductTheme();
  return (
    <View style={[styles.section, { gap: spacing.item * scale }, style]}>
      {title || action ? <View style={styles.sectionHeader}>
        <View style={[styles.sectionCopy, { gap: 3 * scale }]}>
          {title ? <Text accessibilityRole="header" aria-level={2} style={[styles.sectionTitle, { color: colors.text, fontSize: 22 * scale }]}>{title}</Text> : null}
          {description ? <Text style={[styles.sectionDescription, { color: colors.textMuted, fontSize: 15 * scale, lineHeight: 21 * scale }]}>{description}</Text> : null}
        </View>
        {action}
      </View> : null}
      {children}
    </View>
  );
}

export function ProductSurface({ children, elevated = false, style }: { children: ReactNode; elevated?: boolean; style?: ViewStyle }) {
  const { colors, scale } = useProductTheme();
  return <View style={[styles.surface, { backgroundColor: elevated ? colors.surfaceRaised : colors.surface, borderColor: colors.line, borderRadius: productRadius.surface, padding: 20 * scale }, style]}>{children}</View>;
}

type ButtonVariant = 'primary' | 'secondary' | 'quiet' | 'danger';
export function ProductButton({ label, onPress, variant = 'secondary', disabled = false, accessibilityLabel, testID }: { label: string; onPress: () => void; variant?: ButtonVariant; disabled?: boolean; accessibilityLabel?: string; testID?: string }) {
  const { colors, scale } = useProductTheme();
  const primary = variant === 'primary';
  const danger = variant === 'danger';
  return (
    <Pressable accessibilityLabel={accessibilityLabel ?? label} accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress} testID={testID}
      style={({ pressed }) => [styles.button, { backgroundColor: primary ? colors.accent : danger || variant === 'quiet' ? 'transparent' : colors.surfaceRaised, borderColor: danger ? colors.danger : primary ? colors.accent : colors.border, minHeight: 44 * scale, opacity: disabled ? 0.46 : pressed ? 0.78 : 1, paddingHorizontal: 16 * scale }]}>
      <Text style={[styles.buttonLabel, { color: primary ? colors.onAccent : danger ? colors.danger : colors.text, fontSize: 15 * scale }]}>{label}</Text>
    </Pressable>
  );
}

export function ProductTextField({ label, helper, error, multiline, style, ...props }: TextInputProps & { label: string; helper?: string; error?: string }) {
  const { colors, scale } = useProductTheme();
  const labelId = `${String(props.nativeID ?? label).replace(/[^a-z0-9]+/gi, '-').toLowerCase()}-label`;
  return (
    <View style={styles.field}>
      <Text nativeID={labelId} style={[styles.fieldLabel, { color: colors.text, fontSize: 14 * scale }]}>{label}</Text>
      <TextInput {...props} accessibilityLabelledBy={labelId} multiline={multiline} placeholderTextColor={colors.muted}
        style={[styles.input, { backgroundColor: colors.surface, borderColor: error ? colors.danger : colors.border, color: colors.text, fontSize: 16 * scale, minHeight: (multiline ? 112 : 48) * scale, paddingHorizontal: 14 * scale, paddingVertical: multiline ? 12 * scale : 8 * scale }, style]} />
      {error ? <Text accessibilityLiveRegion="polite" style={[styles.fieldHelper, { color: colors.danger }]}>{error}</Text> : helper ? <Text style={[styles.fieldHelper, { color: colors.textMuted }]}>{helper}</Text> : null}
    </View>
  );
}

export function ProductStatus({ title, detail, tone = 'neutral', action, loading = false }: { title: string; detail?: string; tone?: 'neutral' | 'error' | 'success'; action?: ReactNode; loading?: boolean }) {
  const { colors, scale } = useProductTheme();
  const accent = tone === 'error' ? colors.danger : tone === 'success' ? colors.accent : colors.border;
  return (
    <View accessibilityLiveRegion={tone === 'error' ? 'assertive' : 'polite'} style={[styles.status, { backgroundColor: colors.surface, borderColor: accent, gap: 12 * scale, padding: 20 * scale }]}>
      <View style={styles.statusTitleRow}>{loading ? <ActivityIndicator color={colors.accent} /> : null}<Text style={[styles.statusTitle, { color: colors.text, fontSize: 18 * scale }]}>{title}</Text></View>
      {detail ? <Text style={[styles.statusDetail, { color: colors.textMuted, fontSize: 15 * scale, lineHeight: 22 * scale }]}>{detail}</Text> : null}
      {action ? <View style={styles.statusAction}>{action}</View> : null}
    </View>
  );
}

export function ProductRow({ label, title, description, meta, actions, onPress, selected = false }: { label?: string; title: string; description?: string; meta?: string; actions?: ReactNode; onPress?: () => void; selected?: boolean }) {
  const { colors, scale } = useProductTheme();
  const body = <View style={[styles.row, { backgroundColor: selected ? colors.surfaceRaised : colors.surface, borderColor: selected ? colors.accent : colors.line, gap: 16 * scale, padding: 18 * scale }]}>
    <View style={[styles.rowCopy, { gap: 5 * scale }]}>
      {label ? <Text style={[styles.eyebrow, { color: colors.accent }]}>{label}</Text> : null}
      <Text style={[styles.rowTitle, { color: colors.text, fontSize: 18 * scale, lineHeight: 23 * scale }]}>{title}</Text>
      {description ? <Text style={[styles.rowDescription, { color: colors.textMuted, fontSize: 15 * scale, lineHeight: 21 * scale }]}>{description}</Text> : null}
      {meta ? <Text style={[styles.rowMeta, { color: colors.muted }]}>{meta}</Text> : null}
    </View>
    {actions ? <View style={styles.rowActions}>{actions}</View> : null}
  </View>;
  if (!onPress) return body;
  return <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.76 : 1 })}>{body}</Pressable>;
}

export function ProductRule() { const { colors } = useProductTheme(); return <View style={[styles.rule, { backgroundColor: colors.line }]} />; }

export function ProductMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  const { colors, scale } = useProductTheme();
  return <View style={[styles.metric, { borderColor: colors.line, gap: 5 * scale }]}><Text style={[styles.eyebrow, { color: colors.textMuted }]}>{label}</Text><Text style={[styles.metricValue, { color: colors.text, fontSize: 30 * scale }]}>{value}</Text>{detail ? <Text style={[styles.metricDetail, { color: colors.textMuted, fontSize: 14 * scale }]}>{detail}</Text> : null}</View>;
}

export function ProductDialog({ visible, title, description, children, onClose, closeLabel = 'Close' }: { visible: boolean; title: string; description?: string; children: ReactNode; onClose: () => void; closeLabel?: string }) {
  const { colors, reduceMotion, scale } = useProductTheme();
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (Platform.OS !== 'web' || !visible || typeof document === 'undefined') return;
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const timer = window.setTimeout(() => {
      const dialog = document.getElementById('sportabase-dialog');
      dialog?.querySelector<HTMLElement>('[role="button"], button, [href], input, [tabindex]:not([tabindex="-1"])')?.focus();
    }, 0);
    const handleKey = (event: KeyboardEvent) => {
      const dialog = document.getElementById('sportabase-dialog');
      if (!dialog) return;
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
      if (event.key !== 'Tab') return;
      const controls = Array.from(dialog.querySelectorAll<HTMLElement>('[role="button"], button, [href], input, [tabindex]:not([tabindex="-1"])')).filter((node) => !node.hasAttribute('disabled'));
      if (!controls.length) return;
      const first = controls[0]; const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => { window.clearTimeout(timer); document.removeEventListener('keydown', handleKey); window.setTimeout(() => previousFocus.current?.focus(), 0); };
  }, [onClose, visible]);
  return <Modal animationType={reduceMotion ? 'none' : 'fade'} onRequestClose={onClose} transparent visible={visible}>
    <View style={styles.dialogBackdrop}><View accessibilityLabel={title} accessibilityViewIsModal nativeID="sportabase-dialog" role="dialog" style={[styles.dialog, { backgroundColor: colors.surface, borderColor: colors.border, padding: 24 * scale }]}>
      <Text accessibilityRole="header" aria-level={2} style={[styles.dialogTitle, { color: colors.text, fontSize: 24 * scale }]}>{title}</Text>
      {description ? <Text style={[styles.dialogDescription, { color: colors.textMuted, fontSize: 15 * scale, lineHeight: 22 * scale }]}>{description}</Text> : null}
      <View style={styles.dialogClose}><ProductButton label={closeLabel} onPress={onClose} variant="quiet" /></View>
      <View style={styles.dialogContent}>{children}</View>
    </View></View>
  </Modal>;
}

export function formatProductDate(value?: string | null) {
  if (!value) return 'Unknown time';
  const date = new Date(value); if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

const styles = StyleSheet.create({
  page: { flex: 1, minHeight: '100%' }, scrollContent: { flexGrow: 1 }, pageContent: { alignSelf: 'center', position: 'relative', width: '100%' },
  pageHeader: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' }, headerCopy: { flex: 1, minWidth: 240 }, headerAside: { alignItems: 'flex-end', justifyContent: 'center' },
  eyebrow: { fontFamily: productFonts.label, fontSize: 13, letterSpacing: 1.3, textTransform: 'uppercase' }, pageTitle: { fontFamily: productFonts.display, letterSpacing: -0.6 }, pageDescription: { fontFamily: productFonts.body, maxWidth: 700 },
  section: { width: '100%' }, sectionHeader: { alignItems: 'flex-start', flexDirection: 'row', flexWrap: 'wrap', gap: 16, justifyContent: 'space-between' }, sectionCopy: { flex: 1, minWidth: 220 }, sectionTitle: { fontFamily: productFonts.display, letterSpacing: -0.2 }, sectionDescription: { fontFamily: productFonts.body, maxWidth: 720 },
  surface: { borderWidth: 1 }, button: { alignItems: 'center', borderRadius: productRadius.control, borderWidth: 1, flexDirection: 'row', justifyContent: 'center' }, buttonLabel: { fontFamily: productFonts.emphasis },
  field: { gap: 7, width: '100%' }, fieldLabel: { fontFamily: productFonts.emphasis }, input: { borderRadius: productRadius.control, borderWidth: 1, fontFamily: productFonts.body }, fieldHelper: { fontFamily: productFonts.body, fontSize: 13, lineHeight: 18 },
  status: { borderLeftWidth: 3, borderRadius: productRadius.surface }, statusTitleRow: { alignItems: 'center', flexDirection: 'row', gap: 10 }, statusTitle: { fontFamily: productFonts.emphasis }, statusDetail: { fontFamily: productFonts.body, maxWidth: 720 }, statusAction: { alignItems: 'flex-start' },
  row: { alignItems: 'flex-start', borderBottomWidth: 1, flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' }, rowCopy: { flex: 1, minWidth: 200 }, rowTitle: { fontFamily: productFonts.emphasis }, rowDescription: { fontFamily: productFonts.body }, rowMeta: { fontFamily: productFonts.body, fontSize: 13 }, rowActions: { alignItems: 'center', flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  rule: { height: StyleSheet.hairlineWidth, width: '100%' }, metric: { borderTopWidth: 2, flex: 1, minWidth: 150, paddingTop: 12 }, metricValue: { fontFamily: productFonts.display, fontVariant: ['tabular-nums'] }, metricDetail: { fontFamily: productFonts.body, lineHeight: 20 },
  dialogBackdrop: { alignItems: 'center', backgroundColor: 'rgba(0, 0, 0, 0.68)', flex: 1, justifyContent: 'center', padding: 20 }, dialog: { borderRadius: productRadius.surface, borderWidth: 1, maxHeight: '90%', maxWidth: 560, width: '100%' }, dialogTitle: { fontFamily: productFonts.display }, dialogDescription: { fontFamily: productFonts.body, marginTop: 8 }, dialogContent: { gap: 10, marginTop: 20 }, dialogClose: { alignItems: 'flex-start', marginTop: 12 },
});
