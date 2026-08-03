'use client';
import { useEffect, useState } from 'react';
import type { TraceSpan, TraceSummary } from '@/lib/schemas/trace';
import { fetchTrace, fetchTraceSpans } from './api';

export function useTraceSpans(runId?: string) {
  const [data, setData] = useState<TraceSpan[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    setLoading(true);
    fetchTraceSpans(runId)
      .then((spans) => { if (!cancelled) setData(spans); })
      .catch((e: Error) => { if (!cancelled) setError(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId]);

  return { data, isLoading, error };
}

export function useTrace(runId?: string) {
  const [data, setData] = useState<TraceSummary | null>(null);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    setLoading(true);
    fetchTrace(runId)
      .then((t) => { if (!cancelled) setData(t); })
      .catch((e: Error) => { if (!cancelled) setError(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [runId]);

  return { data, isLoading, error };
}
