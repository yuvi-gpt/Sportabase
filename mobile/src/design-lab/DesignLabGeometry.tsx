import { Asset } from 'expo-asset';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Image, Platform, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { AnalysisResultGeometry, type AnalysisResultGeometryVariant } from '../result-ui/AnalysisResultGeometry.web';
import { useDesignLabTheme } from './DesignLabThemeContext';

export type GeometryMode = 'home' | 'result';
export type BackgroundIdentity = 'sb' | 'wordmark';
export type WatermarkVariant = 'home' | AnalysisResultGeometryVariant;

const logoSource = require('../../assets/images/sportabase-logo.png');
const logoUri = Asset.fromModule(logoSource).uri;
const nativeDriver = Platform.OS !== 'web';
const homeMaterials = {
  dark: ['#128B98', '#158C7F', '#4C9E49', '#85B850'] as const,
  light: ['#24443B', '#31584B', '#3C6552', '#47715A'] as const,
};

function SatinMaterial({ colors, travel }: { colors: readonly [string, string, ...string[]]; travel: Animated.AnimatedInterpolation<string> }) {
  return <><LinearGradient colors={[...colors]} start={{ x: 0, y: .45 }} end={{ x: 1, y: .55 }} style={StyleSheet.absoluteFill} /><Animated.View style={[styles.satinPass, { transform: [{ translateX: travel }] }]}><LinearGradient colors={['rgba(255,255,255,0)', 'rgba(218,242,226,.16)', 'rgba(255,255,255,0)']} start={{ x: 0, y: .5 }} end={{ x: 1, y: .5 }} style={StyleSheet.absoluteFill} /></Animated.View></>;
}

function SbWatermark({ colors, opacity, position, size, travel }: { colors: readonly [string, string, ...string[]]; opacity: ReturnType<typeof Animated.multiply>; position: object; size: number; travel: Animated.AnimatedInterpolation<string> }) {
  if (Platform.OS !== 'web') return <Animated.Image source={logoSource} resizeMode="contain" style={[styles.sbMark, position, { width: size, height: size, opacity }]} />;
  const mask = { WebkitMaskImage: `url(${logoUri})`, maskImage: `url(${logoUri})`, WebkitMaskPosition: 'center', maskPosition: 'center', WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat', WebkitMaskSize: 'contain', maskSize: 'contain', overflow: 'hidden' } as never;
  return <Animated.View testID="stationary-sb-watermark" style={[styles.sbMark, position, mask, { width: size, height: size, opacity }]}><SatinMaterial colors={colors} travel={travel} /></Animated.View>;
}

function WordmarkWatermark({ compact, width, height, colors, progress, opacity }: { compact: boolean; width: number; height: number; colors: readonly [string, string, ...string[]]; progress: Animated.Value; opacity: ReturnType<typeof Animated.multiply> }) {
  const textWidth = compact ? Math.max(430, width * 1.12) : Math.min(Math.max(width * .68, 780), 1040);
  const fontSize = compact ? 62 : Math.min(Math.max(width * .085, 98), 132);
  const right = compact ? -textWidth * .18 : 8;
  const top = compact ? Math.max(210, height * .26) : Math.max(330, height * .36);
  const windowWidth = textWidth * .28;
  const highlightX = progress.interpolate({ inputRange: [0, 1], outputRange: [-windowWidth, textWidth - windowWidth] });
  const inverseX = Animated.multiply(highlightX, -1);
  const gradientText = Platform.OS === 'web' ? { backgroundImage: `linear-gradient(90deg, ${colors.join(',')})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' } as never : { color: colors[1] };
  const highlightText = Platform.OS === 'web' ? { backgroundImage: `linear-gradient(90deg, ${colors[0]}, ${colors[colors.length - 1]}, ${colors[1]})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' } as never : { color: colors[colors.length - 1] };
  const textStyle = [styles.wordmarkText, { width: textWidth, fontSize, lineHeight: fontSize * .94, letterSpacing: compact ? 4 : 8 }];
  return <Animated.View testID="stationary-wordmark-watermark" style={[styles.wordmark, { width: textWidth, height: fontSize * 1.08, right, top, opacity }]}><Text numberOfLines={1} style={[textStyle, gradientText]}>SPRTBS</Text><Animated.View style={[styles.wordmarkHighlight, { width: windowWidth, transform: [{ translateX: highlightX }] }]}><Animated.View style={{ transform: [{ translateX: inverseX }] }}><Text numberOfLines={1} style={[textStyle, highlightText]}>SPRTBS</Text></Animated.View></Animated.View></Animated.View>;
}

function DesignLabHomeGeometry({ compact, identity, motionDebug, theme, transition }: { compact: boolean; identity: BackgroundIdentity; motionDebug: boolean; theme: 'dark' | 'light'; transition?: Animated.Value }) {
  const { width, height } = useWindowDimensions();
  const material = useRef(new Animated.Value(0)).current;
  const entrance = useRef(new Animated.Value(1)).current;
  const duration = motionDebug ? 1600 : 24000;
  useEffect(() => { material.setValue(0); const runner = Animated.loop(Animated.sequence([Animated.timing(material, { toValue: 1, duration: duration / 2, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver }), Animated.timing(material, { toValue: 0, duration: duration / 2, easing: Easing.inOut(Easing.sin), useNativeDriver: nativeDriver })])); runner.start(); return () => runner.stop(); }, [duration, material]);
  useEffect(() => { if (!motionDebug) return; const seen = new Set<number>(); const id = material.addListener(({ value }) => { const sample = Math.min(4, Math.round(value * 4)); if (!seen.has(sample)) { seen.add(sample); console.info(`[Design Lab ${identity} material debug] ${sample * 25}%`, value.toFixed(3)); } }); return () => material.removeListener(id); }, [identity, material, motionDebug]);
  const exitOpacity = transition ? transition.interpolate({ inputRange: [0, .52, 1], outputRange: [1, .72, 0] }) : 1;
  const watermarkOpacity = theme === 'light' ? identity === 'sb' ? .045 : .03 : identity === 'sb' ? .078 : .044;
  const opacity = Animated.multiply(exitOpacity, Animated.multiply(entrance, watermarkOpacity));
  const size = useMemo(() => compact ? Math.min(Math.max(width * .76, 270), 320) : Math.min(Math.max(width * .50, 620), 760), [compact, width]);
  const position = compact ? { right: -size * .10, top: Math.max(128, height * .17) } : { right: -size * .055, top: Math.max(92, height * .13) };
  const travel = material.interpolate({ inputRange: [0, 1], outputRange: ['-70%', '150%'] });
  const colors = homeMaterials[theme];
  return <View style={styles.viewportLayer}>{identity === 'sb' ? <SbWatermark size={size} position={position} colors={colors} travel={travel} opacity={opacity} /> : <WordmarkWatermark compact={compact} width={width} height={height} colors={colors} progress={material} opacity={opacity} />}</View>;
}

export function DesignLabGeometry({ mode, identity = 'sb', variant = mode === 'home' ? 'home' : 'confirmed', compact = false, transition, motionDebug = false }: { mode: GeometryMode; identity?: BackgroundIdentity; variant?: WatermarkVariant; compact?: boolean; transition?: Animated.Value; motionDebug?: boolean }) {
  const { theme } = useDesignLabTheme();
  if (mode === 'result') return <AnalysisResultGeometry compact={compact} identity={identity} light={theme === 'light'} motionDebug={motionDebug} variant={variant === 'home' ? 'confirmed' : variant} />;
  return <DesignLabHomeGeometry compact={compact} identity={identity} motionDebug={motionDebug} theme={theme} transition={transition} />;
}

const styles = StyleSheet.create({
  viewportLayer:{position:'absolute',top:0,right:0,bottom:0,left:0,zIndex:0,overflow:'hidden',pointerEvents:'none'},sbMark:{position:'absolute'},satinPass:{position:'absolute',top:0,bottom:0,left:'-28%',width:'34%'},wordmark:{position:'absolute',overflow:'hidden'},wordmarkText:{position:'absolute',left:0,top:0,fontFamily:Platform.OS === 'web' ? 'Arial Narrow' : undefined,fontWeight:'900'},wordmarkHighlight:{position:'absolute',top:0,bottom:0,left:0,overflow:'hidden'},
});
