import { Asset } from 'expo-asset';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Image, Platform, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

export type AnalysisResultGeometryIdentity = 'sb' | 'wordmark';
export type AnalysisResultGeometryVariant = 'confirmed' | 'plausible' | 'opinion' | 'critical' | 'limited' | 'contested';

const logoSource = require('../../assets/images/sportabase-logo.png');
const logoUri = Asset.fromModule(logoSource).uri;
const nativeDriver = Platform.OS !== 'web';
const darkMaterials: Record<AnalysisResultGeometryVariant, readonly [string, string, ...string[]]> = {
  confirmed: ['#14392B', '#235C40', '#347A52', '#4D9A63'], plausible: ['#1C2037', '#363F70', '#626B9D'], opinion: ['#251A32', '#49365F', '#75618D'], critical: ['#351B20', '#6B3B42', '#8F4A54'], limited: ['#382A18', '#69522C', '#8C713F'], contested: ['#172E30', '#315355', '#4E7478'],
};
const lightMaterials: Record<AnalysisResultGeometryVariant, readonly [string, string, ...string[]]> = {
  confirmed: ['#052E26', '#064E3B', '#047857', '#059669'], plausible: ['#1E2A55', '#2F4A87', '#445DA0'], opinion: ['#352052', '#59327E', '#75408F'], critical: ['#581B27', '#862F40', '#A63A49'], limited: ['#5C3A16', '#80571E', '#9A6B22'], contested: ['#16474A', '#21666A', '#2B7A80'],
};

function SatinMaterial({ colors, interference, travel }: { colors: readonly [string, string, ...string[]]; interference: boolean; travel: Animated.AnimatedInterpolation<string> }) {
  return <><LinearGradient colors={[...colors]} start={{ x: 0, y: .45 }} end={{ x: 1, y: .55 }} style={StyleSheet.absoluteFill} /><Animated.View style={[styles.satinPass, { transform: [{ translateX: travel }] }]}><LinearGradient colors={['rgba(255,255,255,0)', 'rgba(218,242,226,.16)', 'rgba(255,255,255,0)']} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={StyleSheet.absoluteFill} /></Animated.View>{interference ? <Animated.View style={[styles.tensionPass, { transform: [{ translateX: travel }] }]}><LinearGradient colors={['rgba(123,44,138,0)', 'rgba(176,63,166,.34)', 'rgba(123,44,138,0)']} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={StyleSheet.absoluteFill} /></Animated.View> : null}</>;
}

function SbWatermark({ colors, interference, opacity, position, size, travel }: { colors: readonly [string, string, ...string[]]; interference: boolean; opacity: ReturnType<typeof Animated.multiply>; position: object; size: number; travel: Animated.AnimatedInterpolation<string> }) {
  if (Platform.OS !== 'web') return <Animated.Image source={logoSource} resizeMode="contain" style={[styles.sbMark, position, { width: size, height: size, opacity }]} />;
  const mask = { WebkitMaskImage: `url(${logoUri})`, maskImage: `url(${logoUri})`, WebkitMaskPosition: 'center', maskPosition: 'center', WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat', WebkitMaskSize: 'contain', maskSize: 'contain', overflow: 'hidden' } as never;
  return <Animated.View testID="analysis-result-sb-watermark" style={[styles.sbMark, position, mask, { width: size, height: size, opacity }]}><SatinMaterial colors={colors} travel={travel} interference={interference} /></Animated.View>;
}

function WordmarkWatermark({ colors, compact, height, interference, opacity, progress, width }: { colors: readonly [string, string, ...string[]]; compact: boolean; height: number; interference: boolean; opacity: ReturnType<typeof Animated.multiply>; progress: Animated.Value; width: number }) {
  const textWidth = compact ? Math.max(430, width * 1.12) : Math.min(Math.max(width * .68, 780), 1040);
  const fontSize = compact ? 62 : Math.min(Math.max(width * .085, 98), 132);
  const right = compact ? -textWidth * .18 : 8;
  const top = compact ? Math.max(210, height * .26) : Math.max(330, height * .36);
  const windowWidth = textWidth * .28;
  const highlightX = progress.interpolate({ inputRange: [0, 1], outputRange: [-windowWidth, textWidth - windowWidth] });
  const inverseX = Animated.multiply(highlightX, -1);
  const gradientText = Platform.OS === 'web' ? { backgroundImage: `linear-gradient(90deg, ${colors.join(',')})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' } as never : { color: colors[1] };
  const highlightText = Platform.OS === 'web' ? { backgroundImage: `linear-gradient(90deg, ${colors[0]}, ${interference ? '#8A3C86' : colors[colors.length - 1]}, ${colors[1]})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' } as never : { color: interference ? '#8A3C86' : colors[colors.length - 1] };
  const textStyle = [styles.wordmarkText, { width: textWidth, fontSize, lineHeight: fontSize * .94, letterSpacing: compact ? 4 : 8 }];
  return <Animated.View testID="analysis-result-wordmark-watermark" style={[styles.wordmark, { width: textWidth, height: fontSize * 1.08, right, top, opacity }]}><Text numberOfLines={1} style={[textStyle, gradientText]}>SPRTBS</Text><Animated.View style={[styles.wordmarkHighlight, { width: windowWidth, transform: [{ translateX: highlightX }] }]}><Animated.View style={{ transform: [{ translateX: inverseX }] }}><Text numberOfLines={1} style={[textStyle, highlightText]}>SPRTBS</Text></Animated.View></Animated.View></Animated.View>;
}

export function AnalysisResultGeometry({ compact = false, identity = 'sb', light = false, motionDebug = false, reduceMotion = false, variant = 'confirmed' }: { compact?: boolean; identity?: AnalysisResultGeometryIdentity; light?: boolean; motionDebug?: boolean; reduceMotion?: boolean; variant?: AnalysisResultGeometryVariant }) {
  const { width, height } = useWindowDimensions();
  const material = useRef(new Animated.Value(reduceMotion ? .5 : 0)).current;
  const entrance = useRef(new Animated.Value(reduceMotion ? 1 : 0)).current;
  const duration = motionDebug ? 1600 : 20000;
  useEffect(() => {
    if (reduceMotion) { material.stopAnimation(); material.setValue(.5); return; }
    material.setValue(0);
    const runner = Animated.loop(Animated.sequence([Animated.timing(material, { toValue: 1, duration: duration / 2, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver }), Animated.timing(material, { toValue: 0, duration: duration / 2, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver })]));
    runner.start();
    return () => runner.stop();
  }, [duration, material, reduceMotion]);
  useEffect(() => {
    if (reduceMotion) { entrance.stopAnimation(); entrance.setValue(1); return; }
    const animation = Animated.timing(entrance, { toValue: 1, duration: 520, easing: Easing.out(Easing.cubic), useNativeDriver: nativeDriver });
    animation.start();
    return () => animation.stop();
  }, [entrance, reduceMotion]);
  useEffect(() => { if (!motionDebug || reduceMotion) return; const seen = new Set<number>(); const id = material.addListener(({ value }) => { const sample = Math.min(4, Math.round(value * 4)); if (!seen.has(sample)) { seen.add(sample); console.info(`[Analysis result ${identity} material debug] ${sample * 25}%`, value.toFixed(3)); } }); return () => material.removeListener(id); }, [identity, material, motionDebug, reduceMotion]);
  const watermarkOpacity = light ? identity === 'sb' ? .05 : .034 : identity === 'sb' ? .068 : .040;
  const opacity = Animated.multiply(entrance, watermarkOpacity);
  const size = useMemo(() => compact ? Math.min(Math.max(width * .76, 270), 320) : Math.min(Math.max(width * .50, 620), 760), [compact, width]);
  const position = compact ? { right: -size * .10, top: Math.max(128, height * .17) } : { right: -size * .055, top: Math.max(92, height * .13) };
  const travel = material.interpolate({ inputRange: [0, 1], outputRange: ['-70%', '150%'] });
  const colors = (light ? lightMaterials : darkMaterials)[variant];
  return <View style={styles.viewportLayer} testID="analysis-result-geometry">{identity === 'sb' ? <SbWatermark size={size} position={position} colors={colors} travel={travel} opacity={opacity} interference={variant === 'contested'} /> : <WordmarkWatermark compact={compact} width={width} height={height} colors={colors} progress={material} opacity={opacity} interference={variant === 'contested'} />}</View>;
}

const styles = StyleSheet.create({
  viewportLayer: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none' },
  sbMark: { position: 'absolute' }, satinPass: { position: 'absolute', top: 0, bottom: 0, left: '-28%', width: '34%' }, tensionPass: { position: 'absolute', top: 0, bottom: 0, left: '-18%', width: '13%', opacity: .62 },
  wordmark: { position: 'absolute', overflow: 'hidden' }, wordmarkText: { position: 'absolute', left: 0, top: 0, fontFamily: Platform.OS === 'web' ? 'Arial Narrow' : undefined, fontWeight: '900' }, wordmarkHighlight: { position: 'absolute', top: 0, bottom: 0, left: 0, overflow: 'hidden' },
});
