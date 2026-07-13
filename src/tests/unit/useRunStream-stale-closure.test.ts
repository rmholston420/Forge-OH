/**
 * Regression tests for the stale-closure fix in useRunStream.
 * Verifies that socket callbacks always invoke the *latest* handler
 * version without the effect re-running on every render.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// Mock socket.io-client before importing the hook
const mockSocket = {
  on: vi.fn(),
  off: vi.fn(),
  disconnect: vi.fn(),
};
vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket),
}));

import { useRunStream } from '../../lib/streaming/useRunStream';

const DEFAULT_OPTS = {
  runId: 'run-001',
  onEvent: vi.fn(),
  onStatusChange: vi.fn(),
  onApprovalRequest: vi.fn(),
  onError: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useRunStream — socket setup', () => {
  it('registers exactly one listener per event name', () => {
    renderHook(() => useRunStream(DEFAULT_OPTS));
    const registeredEvents = mockSocket.on.mock.calls.map(([ev]) => ev);
    const unique = new Set(registeredEvents);
    // Each event name appears exactly once
    expect(registeredEvents.length).toBe(unique.size);
  });

  it('does not re-register listeners when callbacks change identity', () => {
    const { rerender } = renderHook(
      (opts) => useRunStream(opts),
      { initialProps: { ...DEFAULT_OPTS, onEvent: vi.fn() } },
    );
    const callCountAfterMount = mockSocket.on.mock.calls.length;
    // Re-render with a brand new function reference
    rerender({ ...DEFAULT_OPTS, onEvent: vi.fn() });
    // on() should NOT have been called again — ref pattern prevents re-subscription
    expect(mockSocket.on.mock.calls.length).toBe(callCountAfterMount);
  });

  it('calls the latest onEvent callback, not the stale one', () => {
    const staleHandler = vi.fn();
    const freshHandler = vi.fn();

    const { rerender } = renderHook(
      (opts) => useRunStream(opts),
      { initialProps: { ...DEFAULT_OPTS, onEvent: staleHandler } },
    );

    // Capture the wrapper function registered with socket.on for 'event'
    const eventRegistration = mockSocket.on.mock.calls.find(([ev]) => ev === 'run:event');
    const socketWrapper = eventRegistration?.[1];

    // Now update to fresh handler
    rerender({ ...DEFAULT_OPTS, onEvent: freshHandler });

    // Fire the socket event through the original (stable) wrapper
    act(() => { socketWrapper?.({ type: 'assistant', content: 'hello' }); });

    expect(freshHandler).toHaveBeenCalledTimes(1);
    expect(staleHandler).not.toHaveBeenCalled();
  });
});

describe('useRunStream — cleanup', () => {
  it('disconnects socket on unmount', () => {
    const { unmount } = renderHook(() => useRunStream(DEFAULT_OPTS));
    unmount();
    expect(mockSocket.disconnect).toHaveBeenCalled();
  });

  it('re-creates socket when runId changes', () => {
    const { rerender } = renderHook(
      (opts) => useRunStream(opts),
      { initialProps: { ...DEFAULT_OPTS, runId: 'run-001' } },
    );
    const disconnectCallsBefore = mockSocket.disconnect.mock.calls.length;
    rerender({ ...DEFAULT_OPTS, runId: 'run-002' });
    expect(mockSocket.disconnect.mock.calls.length).toBeGreaterThan(disconnectCallsBefore);
  });
});
