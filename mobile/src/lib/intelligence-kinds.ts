import type { WatchTargetKind } from './api';

export type IntelligenceKind =
  | WatchTargetKind
  | 'source'
  | 'reporter';

export function isIntelligenceKind(
  value: string | undefined,
): value is IntelligenceKind {
  return (
    value === 'entity' ||
    value === 'story' ||
    value === 'claim' ||
    value === 'media' ||
    value === 'source' ||
    value === 'reporter'
  );
}

export function isWatchableIntelligenceKind(
  value: IntelligenceKind,
): value is WatchTargetKind {
  return (
    value === 'entity' ||
    value === 'story' ||
    value === 'claim' ||
    value === 'media'
  );
}

export function inspectableIntelligenceRoute(
  kind: IntelligenceKind,
  id: string,
) {
  return {
    pathname: '/intelligence' as const,
    params: { kind, id },
  };
}
