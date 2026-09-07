import { Image } from 'expo-image';
import { useContext } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { palette } from './design-lab-theme';
import { WordmarkContext } from './design-lab-fonts';
import { UppercaseSportabaseWordmark } from './UppercaseSportabaseWordmark';

export function DesignLabHeader({ onHome, onAnother, showAnother, mobile = false }: { onHome: () => void; onAnother: () => void; showAnother: boolean; mobile?: boolean }) {
  const wordmark = useContext(WordmarkContext);
  return (
    <View style={[styles.header, mobile && styles.headerMobile]}>
      <Pressable accessibilityRole="button" accessibilityLabel="Return to Sportabase design lab home" onPress={onHome} style={({ pressed }) => [styles.brandButton, mobile && styles.brandButtonMobile, pressed && styles.pressed]}>
        <Image source={require('../../assets/images/sportabase-logo.png')} contentFit="contain" style={[styles.logo, mobile && styles.logoMobile]} />
        <UppercaseSportabaseWordmark variant={wordmark} mobile={mobile} />
      </Pressable>
      {showAnother ? (
        <Pressable accessibilityRole="button" onPress={onAnother} style={({ pressed }) => [styles.another, pressed && styles.pressed]}>
          <View style={styles.anotherMark} />
          <Text style={styles.anotherText}>{mobile ? 'New story' : 'Analyze another story'}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { minHeight: 92, paddingTop: 10, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: palette.line, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 24 },
  headerMobile: { minHeight: 76, paddingTop: 7, paddingBottom: 6, gap: 12 },
  brandButton: { minHeight: 58, flexDirection: 'row', alignItems: 'center', gap: 8, borderRadius: 7, paddingRight: 8 },
  brandButtonMobile: { minHeight: 48, gap: 7, paddingRight: 2 },
  logo: { width: 54, height: 54 },
  logoMobile: { width: 42, height: 42 },
  another: { flexDirection: 'row', alignItems: 'center', gap: 9, minHeight: 44, paddingHorizontal: 4 },
  anotherMark: { width: 9, height: 9, borderRadius: 5, borderWidth: 2, borderColor: palette.teal },
  anotherText: { color: palette.secondary, fontSize: 14, fontWeight: '700', letterSpacing: -0.1 },
  pressed: { opacity: 0.68 },
});
