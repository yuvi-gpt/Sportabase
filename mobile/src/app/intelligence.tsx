import { useLocalSearchParams } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { IntelligenceDetailScreen } from '../components/intelligence-detail-screen';
import { isWatchTargetKind } from '../lib/intelligence-history';

export default function IntelligenceDetailRoute() {
  const params = useLocalSearchParams<{
    kind?: string | string[];
    id?: string | string[];
  }>();

  const kind = Array.isArray(params.kind)
    ? params.kind[0]
    : params.kind;
  const id = Array.isArray(params.id)
    ? params.id[0]
    : params.id;

  if (!isWatchTargetKind(kind) || !id?.trim()) {
    return (
      <View style={styles.screen}>
        <SafeAreaView style={styles.safeArea}>
          <Text style={styles.title}>
            Intelligence object unavailable
          </Text>
          <Text style={styles.copy}>
            This route does not identify a supported entity,
            story, claim or media object.
          </Text>
        </SafeAreaView>
      </View>
    );
  }

  return (
    <IntelligenceDetailScreen
      kind={kind}
      id={id.trim()}
    />
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: '#050807',
    flex: 1,
  },
  safeArea: {
    alignSelf: 'center',
    maxWidth: 760,
    padding: 24,
    width: '100%',
  },
  title: {
    color: '#f4f7f4',
    fontSize: 24,
    fontWeight: '800',
  },
  copy: {
    color: '#98a39b',
    fontSize: 14,
    lineHeight: 21,
    marginTop: 10,
  },
});
