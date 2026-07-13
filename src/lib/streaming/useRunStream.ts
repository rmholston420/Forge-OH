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
  // Keep a stable ref to the latest latestEventId so subscribe_run sends the
  // correct cursor even if the component re-renders before the effect fires.
  const latestEventIdRef = useRef(latestEventId);
  latestEventIdRef.current = latestEventId;

  // Keep stable refs to all callbacks so the socket handlers always call the
  // latest version without needing to re-register on every render.
  const onEventRef        = useRef(onEvent);
  const onConnectedRef    = useRef(onConnected);
  const onDisconnectedRef = useRef(onDisconnected);
  const onReconnectingRef = useRef(onReconnecting);

  onEventRef.current        = onEvent;
  onConnectedRef.current    = onConnected;
  onDisconnectedRef.current = onDisconnected;
  onReconnectingRef.current = onReconnecting;

  useEffect(() => {
    if (!runId) return;

    const socket = getSocket();

    // Stable wrapper handlers — always delegate to the latest ref.
    const handleEvent        = (evt: ToolEvent) => onEventRef.current(evt);
    const handleConnected    = () => onConnectedRef.current();
    const handleDisconnected = () => onDisconnectedRef.current();
    const handleReconnecting = () => onReconnectingRef.current();

    socket.connect();
    socket.emit('subscribe_run', { run_id: runId, latest_event_id: latestEventIdRef.current });

    socket.on('connect',      handleConnected);
    socket.on('disconnect',   handleDisconnected);
    socket.on('reconnecting', handleReconnecting);
    socket.on('oh_event',     handleEvent);

    return () => {
      socket.emit('unsubscribe_run', { run_id: runId });
      socket.off('connect',      handleConnected);
      socket.off('disconnect',   handleDisconnected);
      socket.off('reconnecting', handleReconnecting);
      socket.off('oh_event',     handleEvent);
    };
  }, [runId]);
}
