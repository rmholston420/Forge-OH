import type { Trace, TraceSpan } from '@/lib/schemas/trace';

export function useTraceSpans(_runId?: string) {
  return {
    data: [] as TraceSpan[],
    isLoading: false,
    error: null as Error | null,
  };
}

export function useTrace(_runId?: string) {
  return {
    data: { traceId: 'mock-trace', spans: [] } as Trace,
    isLoading: false,
    error: null as Error | null,
  };
}
