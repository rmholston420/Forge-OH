import { useEffect } from 'react';
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
  useEffect(() => {
    if (!enabled || !runId) return;

    const socket = io(BFF_WS, {
      transports: ['websocket'],
      query: { runId, latestEventId },
    });

    socket.on('connect', () => onConnected?.());
    socket.on('disconnect', () => onDisconnected?.());
    socket.on('reconnect_attempt', () => onReconnecting?.());

    const forward = (event: unknown) => {
      const e = normalizeEvent(event, runId);
      onEvent?.(e);
      onStatusChange?.(e);
      if (e.type === 'approval_required' || e.type === 'pending_approval') onApprovalRequest?.(e);
      if (e.type === 'error' || e.type === 'run_failed') onError?.(e);
    };

    ['run:event', 'message', 'event', 'status', 'approval_required', 'error'].forEach((name) => socket.on(name, forward));

    return () => {
      ['run:event', 'message', 'event', 'status', 'approval_required', 'error'].forEach((name) => socket.off(name, forward));
      socket.off('connect');
      socket.off('disconnect');
      socket.off('reconnect_attempt');
      socket.disconnect();
    };
  }, [runId, latestEventId, enabled, onEvent, onStatusChange, onApprovalRequest, onError, onConnected, onDisconnected, onReconnecting]);
}
