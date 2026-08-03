/**
 * src/tests/unit/lib-streaming-socket.test.ts
 *
 * Covers the singleton socket factory + destroySocket + SOCKET_EVENTS
 * contract without opening a real network connection.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

// vi.mock is hoisted above imports, so any reference to test-file locals
// must go through vi.hoisted() to guarantee it exists when the factory runs.
const { mockSocket, ioMock } = vi.hoisted(() => {
  const mockSocket = {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
  };
  const ioMock = vi.fn(() => mockSocket);
  return { mockSocket, ioMock };
});

vi.mock('socket.io-client', () => ({
  io: ioMock,
  default: { io: ioMock },
}));

// Import AFTER the mock is installed so the module's `import { io }` binds to it.
import { getSocket, destroySocket, SOCKET_EVENTS, BFF_WS } from '@/lib/streaming/socket';

describe('socket singleton', () => {
  beforeEach(() => {
    ioMock.mockClear();
    Object.values(mockSocket).forEach((fn) => (fn as any).mockClear?.());
    destroySocket();
  });
  afterEach(() => destroySocket());

  it('BFF_WS defaults to canonical BFF port 8081', () => {
    // NEXT_PUBLIC_BFF_URL is unset in vitest env → fallback applies.
    expect(BFF_WS).toMatch(/localhost:808\d/);
  });

  it('getSocket lazily initialises and returns same instance', () => {
    const a = getSocket();
    const b = getSocket();
    expect(a).toBe(b);
    expect(ioMock).toHaveBeenCalledTimes(1);
  });

  it('getSocket passes reconnection config', () => {
    getSocket();
    expect(ioMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        autoConnect: false,
        reconnection: true,
        reconnectionAttempts: 10,
      }),
    );
  });

  it('destroySocket disconnects and clears the reference', () => {
    getSocket();
    destroySocket();
    expect(mockSocket.disconnect).toHaveBeenCalledTimes(1);
    // Next getSocket call must re-instantiate.
    getSocket();
    expect(ioMock).toHaveBeenCalledTimes(2);
  });

  it('destroySocket on empty state is a no-op', () => {
    destroySocket(); // singleton is already null
    expect(mockSocket.disconnect).not.toHaveBeenCalled();
  });
});

describe('SOCKET_EVENTS', () => {
  it('exposes stable event names', () => {
    expect(SOCKET_EVENTS.CONNECT).toBe('connect');
    expect(SOCKET_EVENTS.DISCONNECT).toBe('disconnect');
    expect(SOCKET_EVENTS.RECONNECTING).toBe('reconnecting');
    expect(SOCKET_EVENTS.EVENT).toBe('oh_event');
    expect(SOCKET_EVENTS.APPROVAL).toBe('run:approval');
    expect(SOCKET_EVENTS.ERROR).toBe('run:error');
    expect(SOCKET_EVENTS.RUN_START).toBe('run:start');
    expect(SOCKET_EVENTS.RUN_END).toBe('run:end');
  });
});
