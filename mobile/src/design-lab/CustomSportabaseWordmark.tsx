import { Image } from 'expo-image';
import { createElement } from 'react';
import { Platform, StyleSheet, View } from 'react-native';

export type CustomWordmarkVariant = 'custom-a' | 'custom-b' | 'custom-c';

type Glyph = { id: string; advance: number; path: string };

const glyphs: Record<string, Glyph> = {
  S: { id: 'S', advance: 35, path: 'M10 4H38L34 12H17Q13 12 12 16Q11 19 16 19H28Q37 19 35 28Q33 40 21 42H0L4 34H23Q27 34 28 30Q29 27 24 27H12Q3 27 5 18Q7 7 10 4Z' },
  p: { id: 'p', advance: 32, path: 'M7 13H16L15 17Q20 13 27 13Q37 13 35 24Q33 35 23 35H13L10 48H0L7 13ZM16 20L14 29H22Q27 29 28 24Q29 20 24 20H16Z' },
  o: { id: 'o', advance: 32, path: 'M10 13H27Q37 13 35 23L34 27Q32 36 22 36H8Q0 36 2 27L3 22Q5 13 10 13ZM13 20Q11 20 10 24L9 27Q8 30 12 30H22Q25 30 26 27L27 23Q28 20 24 20H13Z' },
  r: { id: 'r', advance: 26, path: 'M7 13H16L15 18Q21 12 30 14L27 22Q20 19 14 23L11 36H1L7 13Z' },
  t: { id: 't', advance: 27, path: 'M13 5H23L21 13H32L30 20H20L18 28Q17 31 22 31H26L24 37H17Q6 37 9 28L11 20H4L6 13H12L13 5Z' },
  a: { id: 'a', advance: 32, path: 'M9 13H36L30 36H21L22 32Q17 36 10 36Q0 36 2 26L3 22Q5 13 9 13ZM14 20Q11 20 10 24L9 27Q8 30 12 30H20Q24 30 25 27L27 20H14Z' },
  b: { id: 'b', advance: 33, path: 'M9 4H19L16 17Q21 13 28 13Q38 13 36 24L35 27Q33 36 23 36H0L9 4ZM16 20L14 30H22Q27 30 28 26L29 23Q30 20 26 20H16Z' },
  s: { id: 's', advance: 29, path: 'M8 13H32L29 20H14Q11 20 11 22Q10 24 14 24H24Q32 24 30 31Q29 36 20 37H0L3 30H19Q22 30 22 28Q23 27 19 27H9Q1 27 3 20Q4 15 8 13Z' },
  e: { id: 'e', advance: 32, path: 'M10 13H28Q38 13 35 24L34 28H10Q10 31 15 31H29L27 37H10Q0 37 2 27L3 22Q5 13 10 13ZM13 19Q11 19 10 23H27Q28 19 24 19H13Z' },
};

const sequence = ['S', 'p', 'o', 'r', 't', 'a', 'b', 'a', 's', 'e'] as const;

const variants = {
  'custom-a': { scaleX: 0.92, spacing: 2.1, slant: 8, desktopWidth: 206, mobileWidth: 166, cuts: 'extended' },
  'custom-b': { scaleX: 0.83, spacing: 1.7, slant: 7, desktopWidth: 184, mobileWidth: 150, cuts: 'balanced' },
  'custom-c': { scaleX: 0.75, spacing: 1.3, slant: 6, desktopWidth: 166, mobileWidth: 137, cuts: 'technical' },
} as const;

function buildGeometry(variant: CustomWordmarkVariant) {
  const config = variants[variant];
  let cursor = 8;
  const starts: number[] = [];
  const paths = sequence.map((letter, index) => {
    const glyph = glyphs[letter];
    starts.push(cursor);
    const element = { key: `${glyph.id}-${index}`, d: glyph.path, transform: `translate(${cursor} 0) skewX(-${config.slant}) scale(${config.scaleX} 1)` };
    cursor += glyph.advance * config.scaleX + config.spacing;
    return element;
  });
  return { config, paths, starts, viewWidth: Math.ceil(cursor + 5) };
}

function cutShapes(variant: CustomWordmarkVariant, starts: number[], scaleX: number) {
  const shapes: { points: string }[] = [];
  const s = starts[0];
  const t = starts[4];
  const b = starts[6];
  shapes.push({ points: `${s + 25 * scaleX},8 ${s + 35 * scaleX},8 ${s + 33 * scaleX},10 ${s + 24 * scaleX},10` });
  if (variant !== 'custom-c') {
    shapes.push({ points: `${t + 17 * scaleX},13 ${t + 27 * scaleX},13 ${t + 26 * scaleX},15 ${t + 16 * scaleX},15` });
    shapes.push({ points: `${b + 21 * scaleX},18 ${b + 31 * scaleX},18 ${b + 30 * scaleX},20 ${b + 20 * scaleX},20` });
  }
  if (variant === 'custom-a') {
    const e = starts[9];
    shapes.push({ points: `${e + 22 * scaleX},29 ${e + 31 * scaleX},29 ${e + 30 * scaleX},31 ${e + 21 * scaleX},31` });
  }
  return shapes;
}

function svgChildren(variant: CustomWordmarkVariant) {
  const { paths, starts, config, viewWidth } = buildGeometry(variant);
  const gradientId = `sportabase-custom-gradient-${variant}`;
  const maskId = `sportabase-custom-mask-${variant}`;
  const pathNodes = paths.map(path => createElement('path', { ...path, fill: '#fff', fillRule: 'evenodd', clipRule: 'evenodd' }));
  const cuts = cutShapes(variant, starts, config.scaleX).map((shape, index) => createElement('polygon', { key: `cut-${index}`, points: shape.points, fill: '#000' }));
  const gradient = createElement('linearGradient', { id: gradientId, x1: -82, y1: 0, x2: viewWidth, y2: 0, gradientUnits: 'userSpaceOnUse' },
    createElement('stop', { offset: '0%', stopColor: '#16B8C4' }),
    createElement('stop', { offset: '34%', stopColor: '#20C9B0' }),
    createElement('stop', { offset: '70%', stopColor: '#82E85B' }),
    createElement('stop', { offset: '100%', stopColor: '#B5F36B' }),
  );
  const mask = createElement('mask', { id: maskId, x: 0, y: 0, width: viewWidth, height: 52, maskUnits: 'userSpaceOnUse' }, ...pathNodes, ...cuts);
  return { viewWidth, gradientId, maskId, defs: createElement('defs', null, gradient, mask) };
}

function buildSvgMarkup(variant: CustomWordmarkVariant) {
  const { paths, starts, config, viewWidth } = buildGeometry(variant);
  const cuts = cutShapes(variant, starts, config.scaleX);
  const pathMarkup = paths.map(path => `<path d="${path.d}" transform="${path.transform}" fill="#fff" fill-rule="evenodd"/>`).join('');
  const cutMarkup = cuts.map(shape => `<polygon points="${shape.points}" fill="#000"/>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${viewWidth} 52"><defs><linearGradient id="g" x1="-82" y1="0" x2="${viewWidth}" y2="0" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#16B8C4"/><stop offset=".34" stop-color="#20C9B0"/><stop offset=".70" stop-color="#82E85B"/><stop offset="1" stop-color="#B5F36B"/></linearGradient><mask id="m"><g>${pathMarkup}</g>${cutMarkup}</mask></defs><rect width="${viewWidth}" height="52" fill="url(#g)" mask="url(#m)"/></svg>`;
}

export function CustomSportabaseWordmark({ variant, mobile = false }: { variant: CustomWordmarkVariant; mobile?: boolean }) {
  const { config, viewWidth } = buildGeometry(variant);
  const sizeStyle = { width: mobile ? config.mobileWidth : config.desktopWidth, height: mobile ? 29 : 36 };
  if (Platform.OS !== 'web') {
    const uri = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(buildSvgMarkup(variant))}`;
    return <Image accessibilityLabel="Sportabase" source={{ uri }} contentFit="contain" style={sizeStyle} />;
  }
  const { gradientId, maskId, defs } = svgChildren(variant);
  const svg = createElement('svg', {
    viewBox: `0 0 ${viewWidth} 52`, width: '100%', height: '100%', preserveAspectRatio: 'xMinYMid meet',
    role: 'img', 'aria-label': 'Sportabase', focusable: false,
  }, defs, createElement('rect', { x: 0, y: 0, width: viewWidth, height: 52, fill: `url(#${gradientId})`, mask: `url(#${maskId})` }));
  return <View style={[styles.root, sizeStyle]}>{svg}</View>;
}

const styles = StyleSheet.create({ root: { flexShrink: 0, overflow: 'visible' } });
