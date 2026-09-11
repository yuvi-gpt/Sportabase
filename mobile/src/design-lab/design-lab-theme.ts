export type DesignLabTheme = 'dark' | 'light';

export const darkPalette = {
  ground: '#070A09', deep: '#0B0F0D', raised: '#101512', high: '#171D19',
  text: '#F4F7F1', secondary: '#C5CEC6', muted: '#98A49D',
  lime: '#B5F36B', green: '#82E85B', teal: '#20C9B0', cyan: '#16B8C4',
  line: 'rgba(197, 206, 198, 0.14)',
} as const;

export type DesignLabPalette = { [Key in keyof typeof darkPalette]: string };

export const lightPalette: DesignLabPalette = {
  ground: '#C6B498', deep: '#D8C8B1', raised: '#B9A383', high: '#A68F70',
  text: '#18221B', secondary: '#4F5D53', muted: '#6B776E',
  lime: '#4D7C0F', green: '#008A46', teal: '#0F766E', cyan: '#0E7490',
  line: 'rgba(24, 34, 27, 0.16)',
};

export const palette = darkPalette;

export function getDesignLabPalette(theme: DesignLabTheme): DesignLabPalette {
  return theme === 'light' ? lightPalette : darkPalette;
}

export function getMeritBand(score: number, theme: DesignLabTheme = 'dark') {
  return getAnalysisMeritBand(score, theme === 'light');
}

export type EvidenceTone = 'confirmed' | 'plausible' | 'opinion' | 'unsupported' | 'limited' | 'contested';
type EvidenceToneValue = { accent: string; soft: string };

const darkEvidenceTones: Record<EvidenceTone, EvidenceToneValue> = {
  confirmed: { accent: '#36B86A', soft: 'rgba(54, 184, 106, 0.12)' },
  plausible: { accent: '#8D95D6', soft: 'rgba(141, 149, 214, 0.12)' },
  opinion: { accent: '#9D8BC9', soft: 'rgba(157, 139, 201, 0.10)' },
  unsupported: { accent: '#D87986', soft: 'rgba(216, 121, 134, 0.10)' },
  limited: { accent: '#D5AC45', soft: 'rgba(213, 172, 69, 0.09)' },
  contested: { accent: '#C36BCB', soft: 'rgba(195, 107, 203, 0.11)' },
};

const lightEvidenceTones: Record<EvidenceTone, EvidenceToneValue> = {
  confirmed: { accent: '#007A3D', soft: 'rgba(0, 122, 61, 0.10)' },
  plausible: { accent: '#4338CA', soft: 'rgba(67, 56, 202, 0.09)' },
  opinion: { accent: '#6D28D9', soft: 'rgba(109, 40, 217, 0.08)' },
  unsupported: { accent: '#BE123C', soft: 'rgba(190, 18, 60, 0.08)' },
  limited: { accent: '#A16207', soft: 'rgba(161, 98, 7, 0.09)' },
  contested: { accent: '#A21CAF', soft: 'rgba(162, 28, 175, 0.08)' },
};

export function getEvidenceTone(tone: EvidenceTone, theme: DesignLabTheme): EvidenceToneValue {
  return (theme === 'light' ? lightEvidenceTones : darkEvidenceTones)[tone];
}

export const semanticAccents = {
  dark: {
    Developing: '#8D95D6', Substantial: '#C36BCB', Contested: '#C36BCB', Confirmed: '#36B86A', Opinion: '#9D8BC9', Limited: '#D5AC45', Unsupported: '#D87986',
  },
  light: {
    Developing: '#4338CA', Substantial: '#A21CAF', Contested: '#A21CAF', Confirmed: '#007A3D', Opinion: '#6D28D9', Limited: '#A16207', Unsupported: '#BE123C',
  },
} as const;

export function getSemanticAccents(theme: DesignLabTheme) {
  return semanticAccents[theme];
}
import { getAnalysisMeritBand } from '../result-ui/analysis-result-model';
