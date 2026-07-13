'use client';
import { useEffect, useRef } from 'react';
import { getSocket } from './socket';
import type { ToolEvent } from '@/lib/schemas/event';

export interface UseRunStreamOptions {
  runId: string;
  latestEventId: number;
  onEvent: (evt: ToolEvent) => void;
  onConnected: () => void;
  onDisconnected: () => void;
  onReconnecting: () => void;
}

export function useRunStream({
  runId,
  latestEventId,
  onEvent,
  onConnected,
  onDisconnected,
  onReconnecting,
}: UseRunStreamOptions) {
  const latestRef = useRef(latestEventId);
  latestRef.current = latestEventId;

  useEffect(() => {
    if (!runId) return;
    const socket = getSocket();

    socket.connect();
    socket.emit('subscribe_run', { run_id: runId, latest_event_id: latestRef.current });

    socket.on('connect', onConnected);
    socket.on('disconnect', onDisconnected);
    socket.on('reconnecting', onReconnecting);
    socket.on('oh_event', onEvent);

    return () => {
      socket.emit('unsubscribe_run', { run_id: runId });
      socket.off('connect', onConnected);
      socket.off('disconnect', onDisconnected);
      socket.off('reconnecting', onReconnecting);
      socket.off('oh_event', onEvent);
    };
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps
}
