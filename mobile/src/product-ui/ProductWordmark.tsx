import { StyleSheet, Text, View } from 'react-native';
import { productFonts, productPalette } from './tokens';

export function ProductWordmark({ compact = false }: { compact?: boolean }) {
  return (
    <View accessibilityLabel="Sportabase" accessibilityRole="text" style={[styles.lockup, compact && styles.compactLockup]}>
      <Text accessibilityElementsHidden allowFontScaling={false} importantForAccessibility="no-hide-descendants" style={[styles.word, compact && styles.compactWord]}>SPORTABASE</Text>
      <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={[styles.cut, compact && styles.compactCut]} />
    </View>
  );
}

const styles = StyleSheet.create({
  lockup: { flexShrink: 0, height: 35, justifyContent: 'center', overflow: 'hidden', width: 164 },
  compactLockup: { height: 28, width: 138 },
  word: { color: productPalette.text, fontFamily: productFonts.wordmark, fontSize: 25, letterSpacing: 0.6, lineHeight: 32 },
  compactWord: { fontSize: 18, lineHeight: 24 },
  cut: { backgroundColor: productPalette.ground, bottom: 3, height: 2, left: 1, position: 'absolute', right: 1, transform: [{ skewX: '-20deg' }] },
  compactCut: { bottom: 2 },
});
