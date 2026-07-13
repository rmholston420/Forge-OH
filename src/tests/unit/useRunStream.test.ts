/**
 * useRunStream.test.ts
 *
 * Tests for src/lib/streaming/useRunStream.ts.
 *
 * Strategy: mock getSocket() to return a fake EventEmitter-like socket so we
 * can control connect/disconnect/oh_event emissions in-process without a real
 * Socket.IO server. Verifies the subscribe_run / unsubscribe_run emit contract
 * and the stable-ref callback pattern.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRunStream } from '@/lib/streaming/useRunStream';

// ---------------------------------------------------------------------------
// Minimal fake socket
// ---------------------------------------------------------------------------
function makeFakeSocket() {
  const listeners: Map<string, Set<(...args: unknown[]) => void>> = new Map();
  const emitted: Array<[string, ...unknown[]]> = [];

  const socket = {
    connect: vi.fn(),
    emit(event: string, ...args: unknown[]) {
      emitted.push([event, ...args]);
    },
    on(event: string, handler: (...args: unknown[]) => void) {
      if (!listeners.has(event)) listeners.set(event, new Set());
      listeners.get(event)!.add(handler);
    },
    off(event: string, handler: (...args: unknown[]) => void) {
      listeners.get(event)?.delete(handler);
    },
    // Helper to trigger a server→client event
    trigger(event: string, ...args: unknown[]) {
      listeners.get(event)?.forEach((h) => h(...args));
    },
    emitted,
    listeners,
  };
  return socket;
}

type FakeSocket = ReturnType<typeof makeFakeSocket>;
let fakeSocket: FakeSocket;

vi.mock('@/lib/streaming/socket', () => ({
  getSocket: () => fakeSocket,
}));

beforeEach(() => {
  fakeSocket = makeFakeSocket();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('useRunStream — mount behaviour', () => {
  it('calls socket.connect() on mount', () => {
    renderHook(() =>
      useRunStream({
        runId: 'run-1',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    expect(fakeSocket.connect).toHaveBeenCalledOnce();
  });

  it('emits subscribe_run with correct runId and latestEventId', () => {
    renderHook(() =>
      useRunStream({
        runId: 'run-42',
        latestEventId: 7,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    expect(fakeSocket.emitted[0]).toEqual([
      'subscribe_run',
      { run_id: 'run-42', latest_event_id: 7 },
    ]);
  });

  it('registers handlers for connect, disconnect, reconnecting, oh_event', () => {
    renderHook(() =>
      useRunStream({
        runId: 'run-1',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    expect(fakeSocket.listeners.has('connect')).toBe(true);
    expect(fakeSocket.listeners.has('disconnect')).toBe(true);
    expect(fakeSocket.listeners.has('reconnecting')).toBe(true);
    expect(fakeSocket.listeners.has('oh_event')).toBe(true);
  });

  it('does nothing when runId is empty string', () => {
    renderHook(() =>
      useRunStream({
        runId: '',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    expect(fakeSocket.connect).not.toHaveBeenCalled();
    expect(fakeSocket.emitted).toHaveLength(0);
  });
});

describe('useRunStream — event callbacks', () => {
  it('calls onConnected when connect event fires', () => {
    const onConnected = vi.fn();
    renderHook(() =>
      useRunStream({
        runId: 'r1',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected,
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    act(() => fakeSocket.trigger('connect'));
    expect(onConnected).toHaveBeenCalledOnce();
  });

  it('calls onDisconnected when disconnect event fires', () => {
    const onDisconnected = vi.fn();
    renderHook(() =>
      useRunStream({
        runId: 'r1',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected,
        onReconnecting: vi.fn(),
      }),
    );
    act(() => fakeSocket.trigger('disconnect'));
    expect(onDisconnected).toHaveBeenCalledOnce();
  });

  it('calls onReconnecting when reconnecting event fires', () => {
    const onReconnecting = vi.fn();
    renderHook(() =>
      useRunStream({
        runId: 'r1',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting,
      }),
    );
    act(() => fakeSocket.trigger('reconnecting'));
    expect(onReconnecting).toHaveBeenCalledOnce();
  });

  it('calls onEvent with the event payload when oh_event fires', () => {
    const onEvent = vi.fn();
    const fakeEvent = { id: 1, type: 'tool_call', timestamp: new Date().toISOString() };
    renderHook(() =>
      useRunStream({
        runId: 'r1',
        latestEventId: 0,
        onEvent,
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    act(() => fakeSocket.trigger('oh_event', fakeEvent));
    expect(onEvent).toHaveBeenCalledWith(fakeEvent);
  });
});

describe('useRunStream — stable-ref callback pattern', () => {
  it('calls the LATEST onEvent ref, not the stale one from mount', () => {
    const firstCallback = vi.fn();
    const secondCallback = vi.fn();
    let currentCallback = firstCallback;

    const { rerender } = renderHook(() =>
      useRunStream({
        runId: 'r1',
        latestEventId: 0,
        onEvent: currentCallback,
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );

    // Swap the callback and re-render (simulates parent state update)
    currentCallback = secondCallback;
    rerender();

    act(() => fakeSocket.trigger('oh_event', { id: 2 }));

    expect(firstCallback).not.toHaveBeenCalled();
    expect(secondCallback).toHaveBeenCalledWith({ id: 2 });
  });
});

describe('useRunStream — cleanup on unmount', () => {
  it('emits unsubscribe_run on unmount', () => {
    const { unmount } = renderHook(() =>
      useRunStream({
        runId: 'run-7',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    unmount();
    const unsubCall = fakeSocket.emitted.find(([e]) => e === 'unsubscribe_run');
    expect(unsubCall).toBeDefined();
    expect(unsubCall![1]).toEqual({ run_id: 'run-7' });
  });

  it('deregisters all four socket event handlers on unmount', () => {
    const { unmount } = renderHook(() =>
      useRunStream({
        runId: 'run-7',
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );
    unmount();
    // After unmount every listener set should be empty
    for (const event of ['connect', 'disconnect', 'reconnecting', 'oh_event']) {
      expect(fakeSocket.listeners.get(event)?.size ?? 0).toBe(0);
    }
  });
});

describe('useRunStream — runId change re-subscribes', () => {
  it('re-emits subscribe_run when runId prop changes', () => {
    let runId = 'run-A';
    const { rerender } = renderHook(() =>
      useRunStream({
        runId,
        latestEventId: 0,
        onEvent: vi.fn(),
        onConnected: vi.fn(),
        onDisconnected: vi.fn(),
        onReconnecting: vi.fn(),
      }),
    );

    runId = 'run-B';
    rerender();

    const subscribeCalls = fakeSocket.emitted.filter(([e]) => e === 'subscribe_run');
    expect(subscribeCalls.length).toBe(2);
    expect(subscribeCalls[1][1]).toMatchObject({ run_id: 'run-B' });
  });
});
