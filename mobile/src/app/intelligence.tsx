import { useLocalSearchParams } from 'expo-router';

import { IntelligenceDetailScreen } from '../components/intelligence-detail-screen';
import { SourceReporterDetailScreen } from '../components/source-reporter-detail-screen';
import {
  isIntelligenceKind,
  isWatchableIntelligenceKind,
} from '../lib/intelligence-kinds';
import { ProductButton, ProductPage, ProductPageHeader, ProductStatus } from '../product-ui/ProductPrimitives';
import { useRouter } from 'expo-router';

export default function IntelligenceDetailRoute() {
  const router = useRouter();
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

  if (!isIntelligenceKind(kind) || !id?.trim()) {
    return <ProductPage width="reading" testID="intelligence-empty-page"><ProductPageHeader label="Persisted intelligence" title="Intelligence" description="Inspect canonical Sportabase objects and their recorded chronology." /><ProductStatus title="Choose an intelligence object" detail="This URL does not identify a supported entity, story, claim, media, source, or reporter object." action={<ProductButton label="Open Discover" onPress={() => router.push('/explore')} variant="primary" />} /></ProductPage>;
  }

  if (kind === 'source' || kind === 'reporter') {
    return (
      <SourceReporterDetailScreen
        kind={kind}
        id={id.trim()}
      />
    );
  }

  if (isWatchableIntelligenceKind(kind)) {
    return (
      <IntelligenceDetailScreen
        kind={kind}
        id={id.trim()}
      />
    );
  }

  return null;
}
