import { Asset } from 'expo-asset';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Image, Platform, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

export type GeometryMode = 'home' | 'result';
export type BackgroundIdentity = 'sb' | 'wordmark';
export type WatermarkVariant = 'home' | 'confirmed' | 'plausible' | 'opinion' | 'critical' | 'limited' | 'contested';
const logoSource = require('../../assets/images/sportabase-logo.png');
const logoUri = Asset.fromModule(logoSource).uri;
const nativeDriver = Platform.OS !== 'web';
const materials: Record<WatermarkVariant, readonly [string, string, ...string[]]> = {
  home: ['#128B98', '#158C7F', '#4C9E49', '#85B850'], confirmed: ['#0B552F', '#157A3D', '#4E9C42', '#83B84C'],
  plausible: ['#111936', '#203F8E', '#505AA7'], opinion: ['#251240', '#4B267D', '#8C3B8A'], critical: ['#351119', '#77313F', '#9E3239'],
  limited: ['#3A2112', '#89501F', '#A98432'], contested: ['#0B3436', '#17696C', '#2D8B94'],
};

function SatinMaterial({ colors, travel, interference }: { colors: readonly [string, string, ...string[]]; travel: Animated.AnimatedInterpolation<string>; interference: boolean }) {
  return <><LinearGradient colors={[...colors]} start={{ x: 0, y: .45 }} end={{ x: 1, y: .55 }} style={StyleSheet.absoluteFill} />
    <Animated.View style={[styles.satinPass, { transform: [{ translateX: travel }] }]}><LinearGradient colors={['rgba(255,255,255,0)', 'rgba(218,242,226,.16)', 'rgba(255,255,255,0)']} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={StyleSheet.absoluteFill} /></Animated.View>
    {interference ? <Animated.View style={[styles.tensionPass, { transform: [{ translateX: travel }] }]}><LinearGradient colors={['rgba(123,44,138,0)', 'rgba(176,63,166,.34)', 'rgba(123,44,138,0)']} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={StyleSheet.absoluteFill} /></Animated.View> : null}</>;
}

function SbWatermark({ size, position, colors, travel, opacity, interference }: { size: number; position: object; colors: readonly [string, string, ...string[]]; travel: Animated.AnimatedInterpolation<string>; opacity: ReturnType<typeof Animated.multiply>; interference: boolean }) {
  if (Platform.OS !== 'web') return <Animated.Image source={logoSource} resizeMode="contain" style={[styles.sbMark, position, { width: size, height: size, opacity }]} />;
  const mask = { WebkitMaskImage: `url(${logoUri})`, maskImage: `url(${logoUri})`, WebkitMaskPosition: 'center', maskPosition: 'center', WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat', WebkitMaskSize: 'contain', maskSize: 'contain', overflow: 'hidden' } as never;
  return <Animated.View testID="stationary-sb-watermark" style={[styles.sbMark, position, mask, { width: size, height: size, opacity }]}><SatinMaterial colors={colors} travel={travel} interference={interference} /></Animated.View>;
}

function WordmarkWatermark({ compact, width, height, colors, progress, opacity, interference }: { compact: boolean; width: number; height: number; colors: readonly [string, string, ...string[]]; progress: Animated.Value; opacity: ReturnType<typeof Animated.multiply>; interference: boolean }) {
  const textWidth = compact ? Math.max(430, width * 1.12) : Math.min(Math.max(width * .68, 780), 1040);
  const fontSize = compact ? 62 : Math.min(Math.max(width * .085, 98), 132);
  const right = compact ? -textWidth * .18 : 8, top = compact ? Math.max(210, height * .26) : Math.max(330, height * .36);
  const windowWidth = textWidth * .28, windowTravel = textWidth - windowWidth;
  const highlightX = progress.interpolate({ inputRange: [0, 1], outputRange: [-windowWidth, windowTravel] });
  const inverseX = Animated.multiply(highlightX, -1);
  const gradientText = Platform.OS === 'web' ? { backgroundImage: `linear-gradient(90deg, ${colors.join(',')})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' } as never : { color: colors[1] };
  const highlightText = Platform.OS === 'web' ? { backgroundImage: `linear-gradient(90deg, ${colors[0]}, ${interference ? '#8A3C86' : colors[colors.length - 1]}, ${colors[1]})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' } as never : { color: interference ? '#8A3C86' : colors[colors.length - 1] };
  const textStyle = [styles.wordmarkText, { width: textWidth, fontSize, lineHeight: fontSize * .94, letterSpacing: compact ? 4 : 8 }];
  return <Animated.View testID="stationary-wordmark-watermark" style={[styles.wordmark, { width: textWidth, height: fontSize * 1.08, right, top, opacity }]}>
    <Text numberOfLines={1} style={[textStyle, gradientText]}>SPRTBS</Text>
    <Animated.View style={[styles.wordmarkHighlight, { width: windowWidth, transform: [{ translateX: highlightX }] }]}><Animated.View style={{ transform: [{ translateX: inverseX }] }}><Text numberOfLines={1} style={[textStyle, highlightText]}>SPRTBS</Text></Animated.View></Animated.View>
  </Animated.View>;
}

export function DesignLabGeometry({ mode, identity = 'sb', variant = mode === 'home' ? 'home' : 'confirmed', compact = false, transition, motionDebug = false }: { mode: GeometryMode; identity?: BackgroundIdentity; variant?: WatermarkVariant; compact?: boolean; transition?: Animated.Value; motionDebug?: boolean }) {
  const { width, height } = useWindowDimensions();
  const material = useRef(new Animated.Value(0)).current, entrance = useRef(new Animated.Value(mode === 'home' ? 1 : 0)).current;
  const duration = motionDebug ? 1600 : mode === 'home' ? 24000 : 20000;
  useEffect(() => { material.setValue(0); const runner = Animated.loop(Animated.sequence([Animated.timing(material, { toValue: 1, duration: duration / 2, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver }), Animated.timing(material, { toValue: 0, duration: duration / 2, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver })])); runner.start(); return () => runner.stop(); }, [duration, material]);
  useEffect(() => { if (mode === 'result') Animated.timing(entrance, { toValue: 1, duration: 520, easing: Easing.out(Easing.cubic), useNativeDriver: nativeDriver }).start(); }, [entrance, mode]);
  useEffect(() => { if (!motionDebug) return; const seen = new Set<number>(); const id = material.addListener(({ value }) => { const sample = Math.min(4, Math.round(value * 4)); if (!seen.has(sample)) { seen.add(sample); console.info(`[Design Lab ${identity} material debug] ${sample * 25}%`, value.toFixed(3)); } }); return () => material.removeListener(id); }, [identity, material, motionDebug]);
  const exitOpacity = transition ? transition.interpolate({ inputRange: [0, .52, 1], outputRange: [1, .72, 0] }) : 1;
  const opacity = Animated.multiply(exitOpacity, Animated.multiply(entrance, identity === 'sb' ? mode === 'home' ? .078 : .068 : mode === 'home' ? .044 : .040));
  const size = useMemo(() => compact ? Math.min(Math.max(width * .76, 270), 320) : Math.min(Math.max(width * .50, 620), 760), [compact, width]);
  const position = compact ? { right: -size * .10, top: Math.max(128, height * .17) } : { right: -size * .055, top: Math.max(92, height * .13) };
  const travel = material.interpolate({ inputRange: [0, 1], outputRange: ['-70%', '150%'] });
  return <View style={styles.viewportLayer}>{identity === 'sb' ? <SbWatermark size={size} position={position} colors={materials[variant]} travel={travel} opacity={opacity} interference={variant === 'contested'} /> : <WordmarkWatermark compact={compact} width={width} height={height} colors={materials[variant]} progress={material} opacity={opacity} interference={variant === 'contested'} />}</View>;
}

const styles = StyleSheet.create({
  viewportLayer: { position: 'absolute', top: 0, right: 0, bottom: 0, left: 0, zIndex: 0, overflow: 'hidden', pointerEvents: 'none' }, sbMark: { position: 'absolute' },
  satinPass: { position: 'absolute', top: 0, bottom: 0, left: '-28%', width: '34%' }, tensionPass: { position: 'absolute', top: 0, bottom: 0, left: '-18%', width: '13%', opacity: .62 },
  wordmark: { position: 'absolute', overflow: 'hidden' }, wordmarkText: { position: 'absolute', left: 0, top: 0, fontFamily: Platform.OS === 'web' ? 'Arial Narrow' : undefined, fontWeight: '900' }, wordmarkHighlight: { position: 'absolute', top: 0, bottom: 0, left: 0, overflow: 'hidden' },
});
