'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { bashStreamUrl, fetchRunCommands, startBash, type BashEvent } from './api';

export function useRunCommands(runId: string) {
  return useQuery({
    queryKey: ['runs', runId, 'commands'],
    queryFn: () => fetchRunCommands(runId),
    enabled: !!runId,
    refetchInterval: 3000, // poll while run active
  });
}

// ---------------------------------------------------------------------------
// Live bash (Slice C.1)
// ---------------------------------------------------------------------------

export type LiveBashStatus = 'idle' | 'starting' | 'running' | 'done' | 'error';

export interface UseLiveBashResult {
  status: LiveBashStatus;
  events: BashEvent[];
  exitCode: number | null;
  error: string | null;
  run: (command: string, cwd?: string | null) => Promise<void>;
  reset: () => void;
}

/**
 * Runs a bash command via the BFF and streams its events over SSE.
 * One command at a time; calling `run` again resets state and starts fresh.
 */
export function useLiveBash(runId: string): UseLiveBashResult {
  const [status, setStatus] = useState<LiveBashStatus>('idle');
  const [events, setEvents] = useState<BashEvent[]>([]);
  const [exitCode, setExitCode] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  const closeStream = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    closeStream();
    setStatus('idle');
    setEvents([]);
    setExitCode(null);
    setError(null);
  }, [closeStream]);

  useEffect(() => () => closeStream(), [closeStream]);

  const run = useCallback(
    async (command: string, cwd?: string | null) => {
      closeStream();
      setEvents([]);
      setExitCode(null);
      setError(null);
      setStatus('starting');
      try {
        const started = await startBash(runId, { command, cwd });
        setEvents([started]);
        setStatus('running');

        const url = bashStreamUrl(runId, started.commandId, started.order);
        const es = new EventSource(url);
        sourceRef.current = es;

        es.addEventListener('event', (e: MessageEvent) => {
          try {
            const evt = JSON.parse(e.data) as BashEvent;
            setEvents((prev) => [...prev, evt]);
            if (evt.kind === 'BashOutput' && evt.exitCode !== null) {
              setExitCode(evt.exitCode);
              setStatus('done');
              closeStream();
            }
          } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
          }
        });
        es.addEventListener('error', (e: MessageEvent) => {
          try {
            const payload = e.data ? JSON.parse(e.data) : null;
            if (payload?.detail) setError(String(payload.detail));
          } catch {
            // ignore parse errors
          }
        });
        es.addEventListener('close', () => {
          setStatus((s) => (s === 'error' ? s : 'done'));
          closeStream();
        });
        es.addEventListener('timeout', () => {
          setStatus('done');
          closeStream();
        });
        es.onerror = () => {
          // Only set an error if we haven't already terminated cleanly.
          setStatus((s) => (s === 'done' ? s : 'error'));
          closeStream();
        };
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        setStatus('error');
      }
    },
    [runId, closeStream],
  );

  return { status, events, exitCode, error, run, reset };
}
