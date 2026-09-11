import { Asset } from 'expo-asset';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, Image, Platform, StyleSheet, View, useWindowDimensions } from 'react-native';
import { useProductTheme } from '../theme/product-theme';

const maskModule = require('../../assets/images/sportabase-logo.png');
const maskUri = Asset.fromModule(maskModule).uri;
const nativeDriver = Platform.OS !== 'web';
const homeMaterial = ['#128B98', '#158C7F', '#4C9E49', '#85B850'] as const;
const lightHomeMaterial = ['#24443B', '#31584B', '#3C6552', '#47715A'] as const;

function SatinMaterial({ colors, travel }: { colors: readonly [string, string, ...string[]]; travel: Animated.AnimatedInterpolation<string> }) {
  return (
    <>
      <LinearGradient
        colors={[...colors]}
        end={{ x: 1, y: 0.55 }}
        start={{ x: 0, y: 0.45 }}
        style={StyleSheet.absoluteFill}
      />
      <Animated.View
        style={[styles.satinPass, { transform: [{ translateX: travel }] }]}
        testID="product-watermark-satin"
      >
        <LinearGradient
          colors={[
            'rgba(255,255,255,0)',
            'rgba(218,242,226,0.16)',
            'rgba(255,255,255,0)',
          ]}
          end={{ x: 1, y: 0.5 }}
          start={{ x: 0, y: 0.5 }}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
    </>
  );
}

export function ProductWatermark({ approvedHome = false, compact = false, light = false }: { approvedHome?: boolean; compact?: boolean; light?: boolean }) {
  const { width, height } = useWindowDimensions();
  const { reduceMotion } = useProductTheme();
  const material = useRef(new Animated.Value(reduceMotion ? 0.5 : 0)).current;

  useEffect(() => {
    material.stopAnimation();
    if (reduceMotion) {
      material.setValue(0.5);
      return;
    }

    material.setValue(0);
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(material, {
          duration: 12000,
          easing: Easing.inOut(Easing.sin),
          toValue: 1,
          useNativeDriver: nativeDriver,
        }),
        Animated.timing(material, {
          duration: 12000,
          easing: Easing.inOut(Easing.sin),
          toValue: 0,
          useNativeDriver: nativeDriver,
        }),
      ]),
    );
    animation.start();

    return () => animation.stop();
  }, [material, reduceMotion]);

  const compactGeometry = compact && width < 700;
  const size = useMemo(() => {
    return compactGeometry
      ? Math.min(Math.max(width * 0.76, 270), 320)
      : Math.min(Math.max(width * 0.5, 620), 760);
  }, [compactGeometry, width]);
  const viewportTop = compactGeometry
    ? Math.max(128, height * 0.17)
    : Math.max(92, height * 0.13);
  const webHeaderOffset = Platform.OS === 'web'
    ? approvedHome ? 0 : width < 980 ? 130 : 92
    : 0;
  const position = compactGeometry
    ? { right: -size * 0.1, top: viewportTop - webHeaderOffset }
    : { right: -size * 0.055, top: viewportTop - webHeaderOffset };
  const travel = material.interpolate({
    inputRange: [0, 1],
    outputRange: ['-70%', '150%'],
  });
  const maskStyle = Platform.OS === 'web'
    ? {
        WebkitMaskImage: `url(${maskUri})`,
        WebkitMaskPosition: 'center',
        WebkitMaskRepeat: 'no-repeat',
        WebkitMaskSize: 'contain',
        maskImage: `url(${maskUri})`,
        maskPosition: 'center',
        maskRepeat: 'no-repeat',
        maskSize: 'contain',
      } as never
    : null;

  return (
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" pointerEvents="none" style={styles.layer} testID="product-watermark">
      {Platform.OS === 'web' ? (
        <View
          style={[styles.mark, position, maskStyle, { height: size, opacity: light ? 0.045 : 0.078, width: size }]}
          testID="stationary-sb-watermark"
        >
          <SatinMaterial colors={light ? lightHomeMaterial : homeMaterial} travel={travel} />
        </View>
      ) : (
        <Image
          source={maskModule}
          resizeMode="contain"
          style={[styles.mark, position, { height: size, opacity: 0.078, width: size }]}
          testID="stationary-sb-watermark"
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  layer: { bottom: 0, left: 0, overflow: 'hidden', position: 'absolute', right: 0, top: 0 },
  mark: { overflow: 'hidden', position: 'absolute' },
  satinPass: { bottom: 0, left: '-28%', position: 'absolute', top: 0, width: '34%' },
});
