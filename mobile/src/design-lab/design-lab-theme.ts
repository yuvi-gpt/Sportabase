export const palette = {
  ground: '#070A09',
  deep: '#0B0F0D',
  raised: '#101512',
  high: '#171D19',
  text: '#F4F7F1',
  secondary: '#C5CEC6',
  muted: '#98A49D',
  lime: '#B5F36B',
  green: '#82E85B',
  teal: '#20C9B0',
  cyan: '#16B8C4',
  line: 'rgba(197, 206, 198, 0.14)',
} as const;

export const meritBands = [
  { key: 'critical', min: 0, colors: ['#FB7185', '#DC2626'] as const },
  { key: 'weak', min: 35, colors: ['#EA580C', '#FACC15'] as const },
  { key: 'developing', min: 50, colors: ['#2563EB', '#818CF8'] as const },
  { key: 'substantial', min: 65, colors: ['#6D28D9', '#D946EF'] as const },
  { key: 'strong', min: 80, colors: ['#0F766E', '#22D3EE'] as const },
  { key: 'high', min: 90, colors: ['#16A34A', '#BEF264'] as const },
] as const;

export function getMeritBand(score: number) {
  return [...meritBands].reverse().find((band) => score >= band.min) ?? meritBands[0];
}

export type EvidenceTone = 'confirmed' | 'plausible' | 'opinion' | 'unsupported' | 'limited' | 'contested';

export const evidenceTones: Record<EvidenceTone, { accent: string; soft: string }> = {
  confirmed: { accent: '#20C9B0', soft: 'rgba(32, 201, 176, 0.12)' },
  plausible: { accent: '#818CF8', soft: 'rgba(129, 140, 248, 0.12)' },
  opinion: { accent: '#60A5FA', soft: 'rgba(96, 165, 250, 0.10)' },
  unsupported: { accent: '#FB7185', soft: 'rgba(251, 113, 133, 0.10)' },
  limited: { accent: '#FACC15', soft: 'rgba(250, 204, 21, 0.09)' },
  contested: { accent: '#D946EF', soft: 'rgba(217, 70, 239, 0.11)' },
};
