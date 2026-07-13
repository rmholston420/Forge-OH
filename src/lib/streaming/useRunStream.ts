import { useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import { BFF_WS } from './socket';

export interface StreamEvent {
  id: string | number;
  eventId?: string | number;
  type: string;
  timestamp: string;
  runId?: string;
  source?: string;
  payload?: Record<string, unknown>;
  rawPayload?: Record<string, unknown>;
  summary?: string;
  raw?: unknown;
  [key: string]: unknown;
}

export interface UseRunStreamOptions {
  runId?: string;
  latestEventId?: string | number;
  enabled?: boolean;
  onEvent?: (event: StreamEvent) => void;
  onStatusChange?: (event: StreamEvent) => void;
  onApprovalRequest?: (event: StreamEvent) => void;
  onError?: (event: StreamEvent) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
  onReconnecting?: () => void;
}

function normalizeEvent(event: unknown, runId?: string): StreamEvent {
  const e = (event ?? {}) as Record<string, unknown>;
  return {
    id: (e.id ?? e.eventId ?? `${runId ?? 'run'}:${Date.now()}`) as string | number,
    eventId: e.eventId as string | number | undefined,
    type: String(e.type ?? 'message'),
    timestamp: String(e.timestamp ?? new Date().toISOString()),
    runId: (e.runId as string | undefined) ?? runId,
    source: e.source as string | undefined,
    payload: (e.payload as Record<string, unknown> | undefined) ?? {},
    rawPayload: (e.rawPayload as Record<string, unknown> | undefined) ?? {},
    summary: e.summary as string | undefined,
    raw: e.raw,
    ...e,
  };
}

export function useRunStream({
  runId,
  latestEventId,
  enabled = true,
  onEvent,
  onStatusChange,
  onApprovalRequest,
  onError,
  onConnected,
  onDisconnected,
  onReconnecting,
}: UseRunStreamOptions) {
  // Stabilize all callbacks in refs so inline arrow functions passed by the
  // parent don't cause the socket to disconnect/reconnect on every render.
  // The useEffect dep array only contains the stable primitive values
  // (runId, latestEventId, enabled) — not the callbacks.
  const onEventRef = useRef(onEvent);
  const onStatusChangeRef = useRef(onStatusChange);
  const onApprovalRequestRef = useRef(onApprovalRequest);
  const onErrorRef = useRef(onError);
  const onConnectedRef = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);
  const onReconnectingRef = useRef(onReconnecting);

  // Keep refs current on every render without triggering the effect.
  onEventRef.current = onEvent;
  onStatusChangeRef.current = onStatusChange;
  onApprovalRequestRef.current = onApprovalRequest;
  onErrorRef.current = onError;
  onConnectedRef.current = onConnected;
  onDisconnectedRef.current = onDisconnected;
  onReconnectingRef.current = onReconnecting;

  useEffect(() => {
    if (!enabled || !runId) return;

    const socket = io(BFF_WS, {
      transports: ['websocket'],
      query: { runId, latestEventId },
    });

    socket.on('connect', () => onConnectedRef.current?.());
    socket.on('disconnect', () => onDisconnectedRef.current?.());
    socket.on('reconnect_attempt', () => onReconnectingRef.current?.());

    const forward = (event: unknown) => {
      const e = normalizeEvent(event, runId);
      onEventRef.current?.(e);
      onStatusChangeRef.current?.(e);
      if (e.type === 'approval_required' || e.type === 'pending_approval') onApprovalRequestRef.current?.(e);
      if (e.type === 'error' || e.type === 'run_failed') onErrorRef.current?.(e);
    };

    ['run:event', 'message', 'event', 'status', 'approval_required', 'error'].forEach((name) => socket.on(name, forward));

    return () => {
      ['run:event', 'message', 'event', 'status', 'approval_required', 'error'].forEach((name) => socket.off(name, forward));
      socket.off('connect');
      socket.off('disconnect');
      socket.off('reconnect_attempt');
      socket.disconnect();
    };
  // Intentionally excludes callback functions — those are stabilized via refs above.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, latestEventId, enabled]);
}
