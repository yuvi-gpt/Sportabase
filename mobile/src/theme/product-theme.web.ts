import { useEffect, useState } from 'react';
import { AccessibilityInfo, type ImageStyle, type TextStyle, type ViewStyle } from 'react-native';

import { useColorScheme } from '../hooks/use-color-scheme';
import { useAccount } from '../lib/account-context';
import { getProductHomePalette } from '../product-ui/ProductHomeTheme';

export function useProductTheme() {
  const { preferences } = useAccount();
  const system = useColorScheme();
  const [systemReduced, setSystemReduced] = useState(false);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setSystemReduced);
    const subscription = AccessibilityInfo.addEventListener('reduceMotionChanged', setSystemReduced);
    return () => subscription.remove();
  }, []);

  const dark = preferences.appearance === 'dark' || (preferences.appearance === 'system' && system === 'dark');
  const high = preferences.contrast === 'high';
  const palette = getProductHomePalette(dark);
  const colors: Record<string, string> = {
    background: palette.ground,
    surface: palette.deep,
    surfaceRaised: palette.raised,
    raised: palette.high,
    text: high ? dark ? '#FFFFFF' : '#000000' : palette.text,
    textMuted: high ? dark ? '#EEEEEE' : '#19291E' : palette.secondary,
    muted: high ? dark ? '#EEEEEE' : '#19291E' : palette.muted,
    border: high ? dark ? '#FFFFFF' : palette.text : palette.line,
    line: high ? dark ? '#FFFFFF' : palette.text : palette.line,
    accent: palette.lime,
    accentSoft: dark ? 'rgba(54, 184, 106, 0.12)' : 'rgba(77, 124, 15, 0.10)',
    danger: dark ? '#FF9A8F' : '#8D2119',
    error: dark ? '#FF9A8F' : '#8D2119',
    teal: palette.teal,
    cyan: palette.cyan,
    lime: palette.lime,
    onAccent: dark ? '#071006' : '#F4F7F1',
  };

  return {
    colors,
    dark,
    high,
    scale: preferences.text_size === 'large' ? 1.2 : preferences.text_size === 'small' ? 0.9375 : 1,
    rowPadding: preferences.density === 'compact' ? 8 : 16,
    spacing: {
      item: preferences.density === 'compact' ? 12 : 16,
      section: preferences.density === 'compact' ? 24 : 32,
    },
    reduceMotion: preferences.motion === 'reduce' || (preferences.motion === 'system' && systemReduced),
  };
}

export function scaleStyles<T extends Record<string, ViewStyle | TextStyle | ImageStyle>>(styles: T, scale: number): T {
  return Object.fromEntries(Object.entries(styles).map(([key, value]) => [key, {
    ...value,
    ...('fontSize' in value && typeof value.fontSize === 'number' ? { fontSize: value.fontSize * scale } : {}),
    ...('lineHeight' in value && typeof value.lineHeight === 'number' ? { lineHeight: value.lineHeight * scale } : {}),
  }])) as T;
}
