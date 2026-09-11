export const productHomePalettes = {
  dark: {
    ground: '#070A09', deep: '#0B0F0D', raised: '#101512', high: '#171D19',
    text: '#F4F7F1', secondary: '#C5CEC6', muted: '#98A49D',
    lime: '#36B86A', green: '#82E85B', teal: '#20C9B0', cyan: '#16B8C4',
    line: 'rgba(197, 206, 198, 0.14)', danger: '#D87986',
  },
  light: {
    ground: '#C6B498', deep: '#D8C8B1', raised: '#B9A383', high: '#A68F70',
    text: '#18221B', secondary: '#4F5D53', muted: '#6B776E',
    lime: '#4D7C0F', green: '#008A46', teal: '#0F766E', cyan: '#0E7490',
    line: 'rgba(24, 34, 27, 0.16)', danger: '#BE123C',
  },
} as const;

export type ProductHomePalette = typeof productHomePalettes.dark | typeof productHomePalettes.light;

export function getProductHomePalette(dark: boolean): ProductHomePalette {
  return dark ? productHomePalettes.dark : productHomePalettes.light;
}
