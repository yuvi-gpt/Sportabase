import { Platform, StyleSheet, Text, View } from 'react-native';
import { palette } from './design-lab-theme';
import { designLabFontNames, type WordmarkCandidate } from './design-lab-fonts';

const configs = {
  'uppercase-a': {
    desktop: { width: 169, height: 31, fontSize: 23, lineHeight: 28, letterSpacing: 1.4, scaleX: 1.035 },
    mobile: { width: 133, height: 25, fontSize: 18, lineHeight: 22, letterSpacing: 1.05, scaleX: 1.025 },
    weight: '700' as const,
    cuts: ['terminalT', 'counterB', 'terminalE'] as const,
  },
  'uppercase-b': {
    desktop: { width: 156, height: 30, fontSize: 22, lineHeight: 27, letterSpacing: 1, scaleX: 1 },
    mobile: { width: 122, height: 24, fontSize: 17.2, lineHeight: 21, letterSpacing: 0.75, scaleX: 1 },
    weight: '650' as const,
    cuts: ['counterB', 'terminalE'] as const,
  },
  'uppercase-c': {
    desktop: { width: 143, height: 29, fontSize: 21, lineHeight: 26, letterSpacing: 0.65, scaleX: 0.985 },
    mobile: { width: 112, height: 23, fontSize: 16.3, lineHeight: 20, letterSpacing: 0.48, scaleX: 0.985 },
    weight: '600' as const,
    cuts: ['terminalE'] as const,
  },
  oxanium: {
    desktop: { width: 158, height: 28, fontSize: 18, lineHeight: 23, letterSpacing: 0.18, scaleX: 1 },
    mobile: { width: 128, height: 23, fontSize: 14.5, lineHeight: 19, letterSpacing: 0.12, scaleX: 1 },
    weight: '700' as const,
    cuts: [] as const,
  },
};

const cutStyles = {
  terminalT: { left: '43.5%', top: 7, width: 9, height: 2, transform: [{ rotate: '-12deg' }] },
  counterB: { left: '66.4%', top: 15, width: 7, height: 2, transform: [{ rotate: '-12deg' }] },
  terminalE: { left: '92%', top: 7, width: 8, height: 2, transform: [{ rotate: '-12deg' }] },
} as const;

const gradientText = Platform.OS === 'web' ? {
  backgroundImage: 'linear-gradient(90deg, #16B8C4 0%, #20C9B0 33%, #82E85B 70%, #B5F36B 100%)',
  backgroundClip: 'text',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  color: 'transparent',
} as any : { color: palette.teal };

export function UppercaseSportabaseWordmark({ variant, mobile = false }: { variant: WordmarkCandidate; mobile?: boolean }) {
  const config = configs[variant];
  const size = mobile ? config.mobile : config.desktop;
  return (
    <View accessibilityLabel="SPORTABASE" style={[styles.root, { width: size.width, height: size.height }]}>
      <Text
        allowFontScaling={false}
        numberOfLines={1}
        style={[
          styles.text,
          {
            fontSize: size.fontSize,
            lineHeight: size.lineHeight,
            letterSpacing: size.letterSpacing,
            fontWeight: config.weight,
            transform: [{ scaleX: size.scaleX }],
          },
          gradientText,
        ]}
      >SPORTABASE</Text>
      {config.cuts.map(cut => <View key={cut} pointerEvents="none" style={[styles.cut, cutStyles[cut], mobile && styles.cutMobile]} />)}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flexShrink: 0, justifyContent: 'center', overflow: 'hidden' },
  text: { width: '100%', fontFamily: designLabFontNames.oxaniumWordmark, textAlign: 'left', textAlignVertical: 'center' },
  cut: { position: 'absolute', backgroundColor: palette.ground },
  cutMobile: { height: 1 },
});
