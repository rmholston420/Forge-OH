'use client';
import { useEffect, useRef } from 'react';
import { io } from 'socket.io-client';
import type { ToolEvent } from '@/lib/schemas/event';

const BFF_WS = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export interface UseRunStreamOptions {
  runId: string;
  onEvent: (evt: ToolEvent) => void;
  onStatusChange?: (status: string) => void;
  onApprovalRequest?: (data: unknown) => void;
  onError?: (err: unknown) => void;
}

export function useRunStream({
  runId,
  onEvent,
  onStatusChange,
  onApprovalRequest,
  onError,
}: UseRunStreamOptions) {
  // Keep stable refs to all callbacks so the socket handlers always call the
  // latest version without needing to re-register on every render.
  const onEventRef            = useRef(onEvent);
  const onStatusChangeRef     = useRef(onStatusChange);
  const onApprovalRequestRef  = useRef(onApprovalRequest);
  const onErrorRef            = useRef(onError);

  onEventRef.current           = onEvent;
  onStatusChangeRef.current    = onStatusChange;
  onApprovalRequestRef.current = onApprovalRequest;
  onErrorRef.current           = onError;

  useEffect(() => {
    if (!runId) return;

    const socket = io(BFF_WS, {
      autoConnect: false,
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 8000,
    });

    // Stable wrapper handlers — always delegate to the latest ref.
    const handleEvent           = (evt: ToolEvent) => onEventRef.current(evt);
    const handleStatusChange    = (status: string) => onStatusChangeRef.current?.(status);
    const handleApprovalRequest = (data: unknown)  => onApprovalRequestRef.current?.(data);
    const handleError           = (err: unknown)   => onErrorRef.current?.(err);

    socket.on('run:event',            handleEvent);
    socket.on('run:status',           handleStatusChange);
    socket.on('run:approval_request', handleApprovalRequest);
    socket.on('run:error',            handleError);

    return () => {
      socket.off('run:event',            handleEvent);
      socket.off('run:status',           handleStatusChange);
      socket.off('run:approval_request', handleApprovalRequest);
      socket.off('run:error',            handleError);
      socket.disconnect();
    };
  }, [runId]);
}
