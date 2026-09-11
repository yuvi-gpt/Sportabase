import { StyleSheet, Text, View } from 'react-native';
import { productFonts, productPalette } from './tokens';

export function ProductWordmark({ compact = false, color = productPalette.text }: { compact?: boolean; color?: string }) {
  return (
    <View accessibilityLabel="sportabase." accessibilityRole="text" style={[styles.lockup, compact && styles.compactLockup]}>
      <Text accessibilityElementsHidden allowFontScaling={false} importantForAccessibility="no-hide-descendants" style={[styles.word, compact && styles.compactWord, { color }]}>sportabase.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  lockup: { flexShrink: 0, height: 34, justifyContent: 'center', minWidth: 152, width: 152 },
  compactLockup: { height: 28, minWidth: 126, width: 126 },
  word: { fontFamily: productFonts.wordmark, fontSize: 23, letterSpacing: -0.6, lineHeight: 32 },
  compactWord: { fontSize: 19, letterSpacing: -0.5, lineHeight: 27 },
});
