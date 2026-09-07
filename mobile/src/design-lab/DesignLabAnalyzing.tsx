import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useRef } from 'react';
import { Animated, Easing, Platform, StyleSheet, Text, View } from 'react-native';
import { DesignLabHeader } from './DesignLabHeader';
import { palette } from './design-lab-theme';

export const ANALYZING_LOOP_MS = 3200;
const nativeDriver = Platform.OS !== 'web';
const laneSpecs = [
  { width: .88, duration: 2800, delay: 0, direction: 1 },
  { width: .72, duration: 3200, delay: 420, direction: -1 },
  { width: .94, duration: 3650, delay: 780, direction: 1 },
  { width: .64, duration: 3050, delay: 1180, direction: -1 },
] as const;

function VerificationLane({ index, width, spec, mobile, debug, exit }: { index: number; width: number; spec: typeof laneSpecs[number]; mobile: boolean; debug: boolean; exit: Animated.Value }) {
  const progress = useRef(new Animated.Value(0)).current;
  const laneWidth = width * spec.width, signalWidth = mobile ? 44 : 68, travel = Math.max(laneWidth - signalWidth, 20);
  useEffect(() => {
    progress.setValue(0); const duration = debug ? 1500 + index * 130 : spec.duration;
    const runner = Animated.sequence([Animated.delay(debug ? spec.delay * .35 : spec.delay), Animated.loop(Animated.sequence([
      Animated.timing(progress, { toValue: 1, duration, easing: Easing.inOut(Easing.cubic), useNativeDriver: nativeDriver }),
      Animated.timing(progress, { toValue: 0, duration: 0, useNativeDriver: nativeDriver }),
    ]))]); runner.start(); return () => runner.stop();
  }, [debug, index, progress, spec.delay, spec.duration]);
  const x = progress.interpolate({ inputRange: [0, 1], outputRange: spec.direction === 1 ? [0, travel] : [travel, 0] });
  const signalOpacity = progress.interpolate({ inputRange: [0, .15, .72, 1], outputRange: [0, .78, .45, 0] });
  const exitOpacity = exit.interpolate({ inputRange: [0, 1], outputRange: [1, 0] });
  return <Animated.View style={[styles.lane, { width: laneWidth, opacity: exitOpacity }]}><View style={styles.rail} />
    {[.18, .48, .78].map(point => <View key={point} style={[styles.tick, { left: laneWidth * point }]} />)}
    <Animated.View style={[styles.signal, { width: signalWidth, opacity: signalOpacity, transform: [{ translateX: x }] }]}><LinearGradient colors={['rgba(22,184,196,0)', 'rgba(32,201,176,.82)', 'rgba(130,232,91,.10)']} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={StyleSheet.absoluteFill} /></Animated.View>
  </Animated.View>;
}

function VerificationField({ mobile, exiting, motionDebug, onExitComplete }: { mobile: boolean; exiting: boolean; motionDebug: boolean; onExitComplete?: () => void }) {
  const exit = useRef(new Animated.Value(0)).current, resolve = useRef(new Animated.Value(0)).current;
  const fieldWidth = mobile ? 310 : 610;
  useEffect(() => { const runner = Animated.loop(Animated.sequence([Animated.timing(resolve, { toValue: 1, duration: motionDebug ? 900 : 1900, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver }), Animated.timing(resolve, { toValue: 0, duration: motionDebug ? 900 : 1900, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver })])); runner.start(); return () => runner.stop(); }, [motionDebug, resolve]);
  useEffect(() => { if (!exiting) return; Animated.parallel([Animated.timing(exit, { toValue: 1, duration: 540, easing: Easing.inOut(Easing.cubic), useNativeDriver: nativeDriver }), Animated.timing(resolve, { toValue: 1, duration: 420, easing: Easing.out(Easing.cubic), useNativeDriver: nativeDriver })]).start(({ finished }) => finished && onExitComplete?.()); }, [exit, exiting, onExitComplete, resolve]);
  useEffect(() => { if (motionDebug) console.info('[Design Lab verification debug]', { lanes: mobile ? 3 : 4, cyclesMs: mobile ? [1500, 1630, 1760] : [1500, 1630, 1760, 1890] }); }, [mobile, motionDebug]);
  const visible = mobile ? laneSpecs.slice(0, 3) : laneSpecs;
  return <Animated.View style={[styles.field, mobile && styles.fieldMobile, { opacity: exit.interpolate({ inputRange: [0, 1], outputRange: [1, 0] }), transform: [{ translateY: exit.interpolate({ inputRange: [0, 1], outputRange: [0, 8] }) }] }]}>
    <View style={[styles.axis, { left: fieldWidth * .58 }]}><Animated.View style={[styles.axisActive, { opacity: resolve.interpolate({ inputRange: [0, 1], outputRange: [.18, .58] }) }]} /></View>
    {visible.map((spec, index) => <VerificationLane key={index} index={index} width={fieldWidth} spec={spec} mobile={mobile} debug={motionDebug} exit={exit} />)}
    <View style={styles.resolveLine}><Animated.View style={[styles.resolveMark, { opacity: resolve }]} /></View>
  </Animated.View>;
}

export function DesignLabAnalyzing({ mobile, url, exiting = false, onExitComplete, motionDebug = false }: { mobile: boolean; url: string; exiting?: boolean; onExitComplete?: () => void; motionDebug?: boolean }) {
  const copy = useRef(new Animated.Value(exiting ? 0 : 1)).current;
  useEffect(() => { Animated.timing(copy, { toValue: exiting ? 0 : 1, duration: exiting ? 160 : 210, useNativeDriver: nativeDriver }).start(); }, [copy, exiting]);
  const copyStyle = { opacity: copy, transform: [{ translateY: copy.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }] };
  return <View style={[styles.page, mobile && styles.pageMobile]}><DesignLabHeader mobile={mobile} onHome={() => {}} onAnother={() => {}} showAnother={false} /><View style={[styles.composition, mobile && styles.compositionMobile]}><Animated.View style={[styles.copy, mobile && styles.copyMobile, copyStyle]}><Text style={[styles.title, mobile && styles.titleMobile]}>Analyzing...</Text>{mobile ? <><Text style={styles.support}>Reading the claim and checking what supports it.</Text><Text numberOfLines={2} style={styles.url}>{url}</Text></> : <><Text numberOfLines={2} style={styles.url}>{url}</Text><Text style={styles.support}>Reading the claim and checking what supports it.</Text></>}</Animated.View><VerificationField mobile={mobile} exiting={exiting} motionDebug={motionDebug} onExitComplete={onExitComplete} /></View></View>;
}

const styles = StyleSheet.create({
  page: { position: 'relative', minHeight: 720 }, pageMobile: { minHeight: 700 }, composition: { minHeight: 580, position: 'relative', flexDirection: 'row', alignItems: 'stretch' }, compositionMobile: { flexDirection: 'column', minHeight: 610 },
  copy: { width: '40%', maxWidth: 450, paddingTop: 126, paddingLeft: 4, zIndex: 2 }, copyMobile: { width: '100%', maxWidth: 340, paddingTop: 54, paddingLeft: 0 }, title: { color: palette.text, fontSize: 34, lineHeight: 42, fontWeight: '800', letterSpacing: -.6 }, titleMobile: { fontSize: 31, lineHeight: 38 }, url: { color: palette.muted, fontSize: 13, lineHeight: 19, marginTop: 12, maxWidth: 430 }, support: { color: palette.secondary, fontSize: 16, lineHeight: 24, marginTop: 14, maxWidth: 430 },
  field: { position: 'absolute', top: 116, right: 0, width: 610, height: 330, justifyContent: 'center', gap: 48, paddingHorizontal: 0 }, fieldMobile: { position: 'relative', top: 0, right: 'auto', width: 310, height: 280, marginTop: 44, alignSelf: 'flex-end', gap: 38 },
  lane: { position: 'relative', height: 10, justifyContent: 'center', alignSelf: 'flex-end' }, rail: { height: 1, backgroundColor: 'rgba(128,159,145,.20)' }, tick: { position: 'absolute', top: 2, width: 1, height: 6, backgroundColor: 'rgba(130,232,91,.22)' }, signal: { position: 'absolute', top: 4, height: 2 },
  axis: { position: 'absolute', top: 22, bottom: 42, width: 1, backgroundColor: 'rgba(128,159,145,.10)' }, axisActive: { position: 'absolute', top: '28%', width: 1, height: '28%', backgroundColor: palette.teal },
  resolveLine: { position: 'absolute', right: 0, bottom: 4, flexDirection: 'row', alignItems: 'center', gap: 10 }, resolveLabel: { color: 'rgba(152,164,157,.48)', fontSize: 9, fontWeight: '800', letterSpacing: 1.5 }, resolveMark: { width: 28, height: 1, backgroundColor: palette.lime },
});
