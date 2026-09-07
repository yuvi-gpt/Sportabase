import { useLocalSearchParams } from 'expo-router';
import { SportabaseDesignLab } from '../design-lab/SportabaseDesignLab';

export default function DesignLabRoute() {
  const { state, viewport, debug, bg, wordmark } = useLocalSearchParams<{ state?: string; viewport?: string; debug?: string; bg?: string; wordmark?: string }>();
  const allowed = ['home', 'confirmed', 'plausible', 'opinion', 'critical', 'limited', 'contested'];
  const initialState = allowed.includes(state ?? '') ? state as 'home' | 'confirmed' | 'plausible' | 'opinion' | 'critical' | 'limited' | 'contested' : 'home';
  const previewWidth = viewport === '390' ? 390 : viewport === '360' ? 360 : undefined;
  const initialWordmark = wordmark === 'uppercase-a' || wordmark === 'uppercase-c' || wordmark === 'oxanium' ? wordmark : 'uppercase-b';
  return <SportabaseDesignLab initialState={initialState} previewWidth={previewWidth} initialMotionDebug={debug === '1'} initialBackground={bg === 'wordmark' ? 'wordmark' : 'sb'} initialWordmark={initialWordmark} />;
}
