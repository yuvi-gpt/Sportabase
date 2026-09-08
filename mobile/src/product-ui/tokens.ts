import { Platform } from 'react-native';

export const productPalette = {
  ground: '#070a09', deep: '#0b0f0d', raised: '#101512', high: '#171d19',
  text: '#f4f7f1', secondary: '#c5cec6', muted: '#98a49d',
  lime: '#b5f36b', green: '#82e85b', teal: '#20c9b0', cyan: '#16b8c4',
  line: 'rgba(197, 206, 198, 0.14)', lineStrong: 'rgba(197, 206, 198, 0.32)',
  danger: '#ff9a8f', warning: '#f1c75b',
} as const;

export const productSpacing = { xxs: 4, xs: 8, sm: 12, md: 16, lg: 24, xl: 32, xxl: 48, hero: 72 } as const;
export const productWidths = { reading: 760, settings: 920, content: 1120, wide: 1256 } as const;
export const productRadius = { control: 8, surface: 12, pill: 999 } as const;

export const productFonts = {
  body: Platform.OS === 'web' ? 'SportabaseBarlowRegular' : undefined,
  emphasis: Platform.OS === 'web' ? 'SportabaseBarlowMedium' : undefined,
  label: Platform.OS === 'web' ? 'SportabaseBarlowCondensedSemiBold' : undefined,
  display: Platform.OS === 'web' ? 'SportabaseBarlowSemiCondensedBold' : undefined,
  wordmark: Platform.OS === 'web' ? 'SportabaseOxaniumBold' : undefined,
} as const;
