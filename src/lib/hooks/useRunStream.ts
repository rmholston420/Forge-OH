/**
 * src/lib/hooks/useRunStream.ts
 *
 * Subscribes to the OpenHands Socket.IO event stream for a single run.
 *
 * Wire-protocol (Slice 1B spec):
 *   - Socket.IO namespace: /
 *   - Query param:         conversationId (NOT runId)
 *   - Event name:          oh-event
 *
 * On run navigation (runId changes), resets the UI store so
 * latestStreamEventId starts from 0 and the stream reconnects from
 * the beginning rather than from a stale cursor.
 */
import { useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useRunDetailUIStore } from '@/lib/state/ui-store';
import type { RunEvent } from '@/lib/schemas/event';

const BFF_URL =
  process.env.NEXT_PUBLIC_BFF_URL ??
  (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8081');

export function useRunStream(
  runId: string | null,
  onEvent: (event: RunEvent) => void,
): void {
  const socketRef = useRef<Socket | null>(null);
  const latestStreamEventId = useRunDetailUIStore(
    (s) => s.latestStreamEventId,
  );
  const setLatestStreamEventId = useRunDetailUIStore(
    (s) => s.setLatestStreamEventId,
  );
  const resetRunDetailUI = useRunDetailUIStore((s) => s.resetRunDetailUI);
  // Track previous runId to detect navigation between runs
  const prevRunIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!runId) return;

    // On run change: reset UI so stream restarts from event 0
    if (prevRunIdRef.current !== null && prevRunIdRef.current !== runId) {
      resetRunDetailUI();
    }
    prevRunIdRef.current = runId;

    // Disconnect any existing socket before opening a new one
    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    const socket = io(BFF_URL, {
      // Spec: query param is `conversationId`, not `runId`
      query: {
        conversationId: runId,
        lastEventId: latestStreamEventId,
      },
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
    });

    socketRef.current = socket;

    // Spec: event name is `oh-event`
    socket.on('oh-event', (event: RunEvent) => {
      onEvent(event);
      if (typeof event.id === 'number') {
        setLatestStreamEventId(event.id);
      }
    });

    socket.on('connect_error', (err: Error) => {
      console.warn('[useRunStream] connect_error:', err.message);
    });

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);
}
