/**
 * Unit tests: src/lib/streaming/useRunStream.ts
 *
 * Verifies the stale-closure fix: callbacks are always dispatched
 * through their latest ref, even when the component re-renders
 * without the socket reconnecting.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRunStream } from '@/lib/streaming/useRunStream';

// ---------------------------------------------------------------------------
// Mock socket
// ---------------------------------------------------------------------------
const mockSocket = {
  connect:    vi.fn(),
  emit:       vi.fn(),
  on:         vi.fn(),
  off:        vi.fn(),
  disconnect: vi.fn(),
};

vi.mock('@/lib/streaming/socket', () => ({
  getSocket: () => mockSocket,
}));

beforeEach(() => {
  vi.clearAllMocks();
  mockSocket.on.mockImplementation(() => {});
});

// ---------------------------------------------------------------------------
// Helper to capture the registered socket handler for a given event
// ---------------------------------------------------------------------------
function captureHandler(event: string): (...args: any[]) => void {
  const call = mockSocket.on.mock.calls.find(([e]) => e === event);
  if (!call) throw new Error(`No handler registered for '${event}'`);
  return call[1];
}

describe('useRunStream — socket lifecycle', () => {
  it('calls socket.connect on mount', () => {
    renderHook(() => useRunStream({
      runId: 'run-1', latestEventId: 0,
      onEvent: vi.fn(), onConnected: vi.fn(),
      onDisconnected: vi.fn(), onReconnecting: vi.fn(),
    }));
    expect(mockSocket.connect).toHaveBeenCalledOnce();
  });

  it('emits subscribe_run with correct run_id and latest_event_id', () => {
    renderHook(() => useRunStream({
      runId: 'run-42', latestEventId: 7,
      onEvent: vi.fn(), onConnected: vi.fn(),
      onDisconnected: vi.fn(), onReconnecting: vi.fn(),
    }));
    expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_run', {
      run_id: 'run-42', latest_event_id: 7,
    });
  });

  it('registers handlers for connect, disconnect, reconnecting, oh_event', () => {
    renderHook(() => useRunStream({
      runId: 'run-1', latestEventId: 0,
      onEvent: vi.fn(), onConnected: vi.fn(),
      onDisconnected: vi.fn(), onReconnecting: vi.fn(),
    }));
    const registeredEvents = mockSocket.on.mock.calls.map(([e]) => e);
    expect(registeredEvents).toContain('connect');
    expect(registeredEvents).toContain('disconnect');
    expect(registeredEvents).toContain('reconnecting');
    expect(registeredEvents).toContain('oh_event');
  });

  it('emits unsubscribe_run and removes handlers on unmount', () => {
    const { unmount } = renderHook(() => useRunStream({
      runId: 'run-1', latestEventId: 0,
      onEvent: vi.fn(), onConnected: vi.fn(),
      onDisconnected: vi.fn(), onReconnecting: vi.fn(),
    }));
    unmount();
    expect(mockSocket.emit).toHaveBeenCalledWith('unsubscribe_run', { run_id: 'run-1' });
    expect(mockSocket.off).toHaveBeenCalledWith('connect', expect.any(Function));
    expect(mockSocket.off).toHaveBeenCalledWith('oh_event', expect.any(Function));
  });

  it('does nothing when runId is empty string', () => {
    renderHook(() => useRunStream({
      runId: '', latestEventId: 0,
      onEvent: vi.fn(), onConnected: vi.fn(),
      onDisconnected: vi.fn(), onReconnecting: vi.fn(),
    }));
    expect(mockSocket.connect).not.toHaveBeenCalled();
  });
});

describe('useRunStream — stale-closure fix', () => {
  it('calls the latest onEvent ref even after re-render without runId change', () => {
    const firstHandler  = vi.fn();
    const secondHandler = vi.fn();

    const { rerender } = renderHook(
      ({ handler }: { handler: typeof firstHandler }) =>
        useRunStream({
          runId: 'run-1', latestEventId: 0,
          onEvent: handler, onConnected: vi.fn(),
          onDisconnected: vi.fn(), onReconnecting: vi.fn(),
        }),
      { initialProps: { handler: firstHandler } },
    );

    rerender({ handler: secondHandler });

    const ohEventHandler = captureHandler('oh_event');
    act(() => ohEventHandler({ type: 'tool_call', id: 99 } as any));

    expect(secondHandler).toHaveBeenCalledOnce();
    expect(firstHandler).not.toHaveBeenCalled();
  });

  it('calls the latest onConnected ref after re-render', () => {
    const first  = vi.fn();
    const second = vi.fn();

    const { rerender } = renderHook(
      ({ cb }: { cb: () => void }) =>
        useRunStream({
          runId: 'run-1', latestEventId: 0,
          onEvent: vi.fn(), onConnected: cb,
          onDisconnected: vi.fn(), onReconnecting: vi.fn(),
        }),
      { initialProps: { cb: first } },
    );

    rerender({ cb: second });

    const connectHandler = captureHandler('connect');
    act(() => connectHandler());

    expect(second).toHaveBeenCalledOnce();
    expect(first).not.toHaveBeenCalled();
  });

  it('uses the latest latestEventId in subscribe_run', () => {
    renderHook(() => useRunStream({
      runId: 'run-1', latestEventId: 5,
      onEvent: vi.fn(), onConnected: vi.fn(),
      onDisconnected: vi.fn(), onReconnecting: vi.fn(),
    }));
    expect(mockSocket.emit).toHaveBeenCalledWith('subscribe_run', {
      run_id: 'run-1', latest_event_id: 5,
    });
  });
});
