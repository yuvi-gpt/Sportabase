import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useMemo, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';

import type { ProductAnalysisPhase } from '../lib/product-analysis';
import { useProductTheme } from '../theme/product-theme';
import { getProductHomePalette, type ProductHomePalette } from './ProductHomeTheme';
import { productFonts } from './tokens';

const laneSpecs = [
  { width: 0.88, duration: 2800, delay: 0, direction: 1 },
  { width: 0.72, duration: 3200, delay: 420, direction: -1 },
  { width: 0.94, duration: 3650, delay: 780, direction: 1 },
  { width: 0.64, duration: 3050, delay: 1180, direction: -1 },
] as const;

const frozenLaneProgress = [0.28, 0.7, 0.46, 0.82] as const;

type LaneSpec = (typeof laneSpecs)[number];

function VerificationLane({
  index,
  fieldWidth,
  mobile,
  palette,
  reduceMotion,
  spec,
}: {
  index: number;
  fieldWidth: number;
  mobile: boolean;
  palette: ProductHomePalette;
  reduceMotion: boolean;
  spec: LaneSpec;
}) {
  const styles = useMemo(() => createStyles(palette), [palette]);
  const progress = useRef(new Animated.Value(frozenLaneProgress[index])).current;
  const laneWidth = fieldWidth * spec.width;
  const signalWidth = mobile ? 44 : 68;
  const travel = Math.max(laneWidth - signalWidth, 20);

  useEffect(() => {
    if (reduceMotion) {
      progress.stopAnimation();
      progress.setValue(frozenLaneProgress[index]);
      return;
    }

    progress.setValue(0);
    const runner = Animated.sequence([
      Animated.delay(spec.delay),
      Animated.loop(Animated.sequence([
        Animated.timing(progress, {
          toValue: 1,
          duration: spec.duration,
          easing: Easing.inOut(Easing.cubic),
          useNativeDriver: false,
        }),
        Animated.timing(progress, {
          toValue: 0,
          duration: 0,
          useNativeDriver: false,
        }),
      ])),
    ]);
    runner.start();
    return () => runner.stop();
  }, [index, progress, reduceMotion, spec.delay, spec.duration]);

  const translateX = progress.interpolate({
    inputRange: [0, 1],
    outputRange: spec.direction === 1 ? [0, travel] : [travel, 0],
  });
  const opacity = progress.interpolate({
    inputRange: [0, 0.15, 0.72, 1],
    outputRange: [0.18, 0.78, 0.45, 0.18],
  });

  return (
    <View style={[styles.lane, { width: laneWidth }]}>
      <View style={styles.rail} />
      {[0.18, 0.48, 0.78].map((point) => (
        <View key={point} style={[styles.tick, { left: laneWidth * point }]} />
      ))}
      <Animated.View
        style={[
          styles.signal,
          {
            width: signalWidth,
            opacity,
            transform: [{ translateX }],
          },
        ]}
      >
        <LinearGradient
          colors={['transparent', palette.teal, 'transparent']}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={StyleSheet.absoluteFill}
        />
      </Animated.View>
    </View>
  );
}

function VerificationField({
  mobile,
  palette,
  phase,
  reduceMotion,
}: {
  mobile: boolean;
  palette: ProductHomePalette;
  phase: ProductAnalysisPhase;
  reduceMotion: boolean;
}) {
  const styles = useMemo(() => createStyles(palette), [palette]);
  const marker = useRef(new Animated.Value(0.58)).current;
  const fieldWidth = mobile ? 310 : 610;

  useEffect(() => {
    if (reduceMotion) {
      marker.stopAnimation();
      marker.setValue(0.58);
      return;
    }

    const runner = Animated.loop(Animated.sequence([
      Animated.timing(marker, {
        toValue: 1,
        duration: 1900,
        easing: Easing.inOut(Easing.sin),
        useNativeDriver: false,
      }),
      Animated.timing(marker, {
        toValue: 0.18,
        duration: 1900,
        easing: Easing.inOut(Easing.sin),
        useNativeDriver: false,
      }),
    ]));
    runner.start();
    return () => runner.stop();
  }, [marker, reduceMotion]);

  const visibleLanes = mobile ? laneSpecs.slice(0, 3) : laneSpecs;

  return (
    <View style={[styles.field, mobile && styles.fieldMobile]}>
      <View style={[styles.axis, { left: fieldWidth * 0.58 }]}>
        <Animated.View style={[styles.axisActive, { opacity: marker }]} />
      </View>
      {visibleLanes.map((spec, index) => (
        <VerificationLane
          key={index}
          index={index}
          fieldWidth={fieldWidth}
          mobile={mobile}
          palette={palette}
          reduceMotion={reduceMotion}
          spec={spec}
        />
      ))}
      <View style={styles.markerLine}>
        <Text style={styles.markerLabel}>
          {phase === 'resolving' ? 'EXTRACTING SOURCE' : 'VERIFYING SIGNALS'}
        </Text>
        <Animated.View style={[styles.marker, { opacity: marker }]} />
      </View>
    </View>
  );
}

export function ProductAnalysisLoader({
  mobile,
  phase,
  url,
}: {
  mobile: boolean;
  phase: ProductAnalysisPhase;
  url: string;
}) {
  const { dark, reduceMotion, scale } = useProductTheme();
  const palette = getProductHomePalette(dark);
  const styles = useMemo(() => createStyles(palette), [palette]);
  const title = phase === 'resolving' ? 'Reading the source...' : 'Analyzing...';
  const support = phase === 'resolving'
    ? 'Sportabase is extracting the article or transcript.'
    : 'Reading the claim and checking what supports it.';

  return (
    <View
      accessibilityLabel={`${title} ${support}`}
      accessibilityLiveRegion="polite"
      accessible
      style={[styles.page, mobile && styles.pageMobile]}
      testID="product-analysis-loader"
    >
      <View style={[styles.composition, mobile && styles.compositionMobile]}>
        <View style={[styles.copyBlock, mobile && styles.copyBlockMobile]}>
          <Text
            accessibilityRole="header"
            aria-level={1}
            style={[
              styles.title,
              mobile && styles.titleMobile,
              { fontSize: (mobile ? 38 : 48) * scale, lineHeight: (mobile ? 44 : 55) * scale },
            ]}
          >
            {title}
          </Text>
          {mobile ? (
            <>
              <Text style={[styles.support, { fontSize: 16 * scale, lineHeight: 24 * scale }]}>{support}</Text>
              <Text numberOfLines={2} style={styles.url}>{url}</Text>
            </>
          ) : (
            <>
              <Text numberOfLines={2} style={styles.url}>{url}</Text>
              <Text style={[styles.support, { fontSize: 16 * scale, lineHeight: 24 * scale }]}>{support}</Text>
            </>
          )}
        </View>
        <VerificationField
          mobile={mobile}
          palette={palette}
          phase={phase}
          reduceMotion={reduceMotion}
        />
      </View>
    </View>
  );
}

const createStyles = (palette: ProductHomePalette) => StyleSheet.create({
  page: {
    minHeight: 650,
    position: 'relative',
  },
  pageMobile: {
    minHeight: 610,
  },
  composition: {
    alignItems: 'stretch',
    flexDirection: 'row',
    minHeight: 580,
    position: 'relative',
  },
  compositionMobile: {
    flexDirection: 'column',
    minHeight: 560,
  },
  copyBlock: {
    maxWidth: 460,
    paddingLeft: 4,
    paddingTop: 126,
    width: '40%',
    zIndex: 2,
  },
  copyBlockMobile: {
    maxWidth: 360,
    paddingLeft: 0,
    paddingTop: 54,
    width: '100%',
  },
  title: {
    color: palette.text,
    fontFamily: productFonts.display,
    fontWeight: '800',
    letterSpacing: -1,
  },
  titleMobile: {
    letterSpacing: -0.7,
  },
  url: {
    color: palette.muted,
    fontFamily: productFonts.body,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 13,
    maxWidth: 430,
  },
  support: {
    color: palette.secondary,
    fontFamily: productFonts.body,
    marginTop: 15,
    maxWidth: 430,
  },
  field: {
    gap: 48,
    height: 330,
    justifyContent: 'center',
    paddingHorizontal: 0,
    position: 'absolute',
    right: 0,
    top: 116,
    width: 610,
  },
  fieldMobile: {
    alignSelf: 'flex-end',
    gap: 38,
    height: 280,
    marginTop: 44,
    position: 'relative',
    right: 'auto',
    top: 0,
    width: 310,
  },
  lane: {
    alignSelf: 'flex-end',
    height: 10,
    justifyContent: 'center',
    position: 'relative',
  },
  rail: {
    backgroundColor: palette.line,
    height: 1,
  },
  tick: {
    backgroundColor: palette.green,
    height: 6,
    opacity: 0.22,
    position: 'absolute',
    top: 2,
    width: 1,
  },
  signal: {
    height: 2,
    position: 'absolute',
    top: 4,
  },
  axis: {
    backgroundColor: palette.line,
    bottom: 42,
    opacity: 0.7,
    position: 'absolute',
    top: 22,
    width: 1,
  },
  axisActive: {
    backgroundColor: palette.teal,
    height: '28%',
    position: 'absolute',
    top: '28%',
    width: 1,
  },
  markerLine: {
    alignItems: 'center',
    bottom: 4,
    flexDirection: 'row',
    gap: 10,
    position: 'absolute',
    right: 0,
  },
  markerLabel: {
    color: palette.muted,
    fontFamily: productFonts.label,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1.5,
    opacity: 0.58,
  },
  marker: {
    backgroundColor: palette.lime,
    height: 1,
    width: 28,
  },
});
