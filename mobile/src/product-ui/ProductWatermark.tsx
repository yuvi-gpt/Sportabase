import { Asset } from 'expo-asset';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Image, Platform, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useProductTheme } from '../theme/product-theme';
import { productPalette } from './tokens';

const maskModule = require('../../assets/images/sportabase-logo.png');

export function ProductWatermark({ compact = false }: { compact?: boolean }) {
  const { width, height } = useWindowDimensions();
  const { reduceMotion } = useProductTheme();
  const drift = useRef(new Animated.Value(reduceMotion ? 0.5 : 0)).current;
  const rotation = useRef(new Animated.Value(reduceMotion ? 0.22 : 0)).current;
  useEffect(() => {
    drift.stopAnimation(); rotation.stopAnimation();
    if (reduceMotion) { drift.setValue(0.5); rotation.setValue(0.22); return; }
    drift.setValue(0); rotation.setValue(0);
    const animation = Animated.loop(Animated.parallel([
      Animated.timing(drift, { toValue: 1, duration: 24000, easing: Easing.linear, useNativeDriver: true }),
      Animated.timing(rotation, { toValue: 1, duration: 30000, easing: Easing.linear, useNativeDriver: true }),
    ]));
    animation.start(); return () => animation.stop();
  }, [drift, reduceMotion, rotation]);
  const size = useMemo(() => {
    const basis = compact ? Math.min(Math.max(width * 1.1, 420), 560) : Math.min(Math.max(width * 0.82, 420), 1080);
    return Math.min(basis, Math.max(height * 0.88, 420));
  }, [compact, height, width]);
  const maskStyle = Platform.OS === 'web' ? { WebkitMaskImage: `url(${Asset.fromModule(maskModule).uri})`, maskImage: `url(${Asset.fromModule(maskModule).uri})`, WebkitMaskPosition: 'center', maskPosition: 'center', WebkitMaskRepeat: 'no-repeat', maskRepeat: 'no-repeat', WebkitMaskSize: 'contain', maskSize: 'contain' } as never : null;
  return (
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" pointerEvents="none" style={styles.layer} testID="product-watermark">
      <Animated.View style={[styles.mark, maskStyle, { height: size, opacity: compact ? 0.1 : 0.16, width: size, transform: [
        { translateX: drift.interpolate({ inputRange: [0, 0.5, 1], outputRange: [-18, 18, -18] }) },
        { translateY: drift.interpolate({ inputRange: [0, 0.5, 1], outputRange: [10, -12, 10] }) },
        { rotate: rotation.interpolate({ inputRange: [0, 1], outputRange: ['-1deg', '2deg'] }) },
      ] }]}>
        {Platform.OS === 'web' ? <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ translateX: drift.interpolate({ inputRange: [0, 0.5, 1], outputRange: [-size * 0.16, size * 0.16, -size * 0.16] }) }] }]}><LinearGradient colors={[productPalette.cyan, productPalette.teal, productPalette.green, productPalette.lime]} end={{ x: 1, y: 1 }} start={{ x: 0, y: 0 }} style={StyleSheet.absoluteFill} /></Animated.View> : <Image source={maskModule} resizeMode="contain" style={StyleSheet.absoluteFill} />}
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  layer: { alignItems: 'center', bottom: 0, justifyContent: 'center', left: 0, overflow: 'hidden', position: 'absolute', right: 0, top: 0 },
  mark: { alignSelf: 'center' },
});
