import { useCallback, useEffect, useRef, useState } from 'react';

import { getAnalysisResultContext, type AnalysisResultContext } from './api';
import type { ProductResultContextPhase } from '../product-ui/ProductAnalysisResult.web';

export function useAnalysisResultContext(sourceUrl: string, enabled: boolean) {
  const [context, setContext] = useState<AnalysisResultContext | null>(null);
  const [phase, setPhase] = useState<ProductResultContextPhase>('empty');
  const [attempt, setAttempt] = useState(0);
  const requestEpoch = useRef(0);

  const retry = useCallback(() => {
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled || !sourceUrl.trim()) {
      requestEpoch.current += 1;
      setContext(null);
      setPhase('empty');
      return;
    }

    const request = requestEpoch.current + 1;
    requestEpoch.current = request;
    setContext(null);
    setPhase('loading');
    void getAnalysisResultContext(sourceUrl).then((result) => {
      if (request !== requestEpoch.current) return;
      if (result.status !== 'ready') {
        setContext(null);
        setPhase('empty');
        return;
      }
      setContext(result);
      setPhase('ready');
    }).catch(() => {
      if (request !== requestEpoch.current) return;
      setContext(null);
      setPhase('error');
    });

    return () => {
      if (request === requestEpoch.current) requestEpoch.current += 1;
    };
  }, [attempt, enabled, sourceUrl]);

  return { context, phase, retry };
}
