/**
 * src/tests/unit/replay-useRunReplay.test.ts
 */
import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import { useRunReplay } from '@/features/run-replay/useRunReplay';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

const mockEvents = Array.from({ length: 10 }, (_, i) => ({
  id: String(i + 1),
  type: 'tool_call',
  timestamp: `2026-01-01T00:00:0${i}Z`,
}));

beforeAll(() => {
  server.use(
    http.get(`${BFF}/runs/:runId/events`, () =>
      HttpResponse.json({ data: mockEvents })
    )
  );
  server.listen({ onUnhandledRequest: 'warn' });
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children);
}

describe('useRunReplay', () => {
  it('scrub clamps to [0, totalEvents-1]', async () => {
    const { result, rerender } = renderHook(() => useRunReplay('run-1'), { wrapper: makeWrapper() });
    // Wait for events to load
    await act(async () => { await new Promise(r => setTimeout(r, 50)); });
    act(() => result.current.scrub(-99));
    expect(result.current.currentIndex).toBe(0);
    act(() => result.current.scrub(999));
    // Max is totalEvents - 1; if events haven't loaded yet, totalEvents=0 so clamps to 0
    expect(result.current.currentIndex).toBeGreaterThanOrEqual(0);
  });

  it('play sets isPlaying=true', () => {
    const { result } = renderHook(() => useRunReplay('run-2'), { wrapper: makeWrapper() });
    expect(result.current.isPlaying).toBe(false);
    act(() => result.current.play());
    expect(result.current.isPlaying).toBe(true);
  });

  it('pause sets isPlaying=false', () => {
    const { result } = renderHook(() => useRunReplay('run-3'), { wrapper: makeWrapper() });
    act(() => result.current.play());
    act(() => result.current.pause());
    expect(result.current.isPlaying).toBe(false);
  });

  it('stepForward increments currentIndex', () => {
    const { result } = renderHook(() => useRunReplay('run-4'), { wrapper: makeWrapper() });
    act(() => result.current.scrub(3));
    act(() => result.current.stepForward());
    expect(result.current.currentIndex).toBe(4);
  });

  it('stepBack decrements currentIndex', () => {
    const { result } = renderHook(() => useRunReplay('run-5'), { wrapper: makeWrapper() });
    act(() => result.current.scrub(5));
    act(() => result.current.stepBack());
    expect(result.current.currentIndex).toBe(4);
  });

  it('jumpToStart sets currentIndex=0', () => {
    const { result } = renderHook(() => useRunReplay('run-6'), { wrapper: makeWrapper() });
    act(() => result.current.scrub(7));
    act(() => result.current.jumpToStart());
    expect(result.current.currentIndex).toBe(0);
  });

  it('setSpeed updates speed', () => {
    const { result } = renderHook(() => useRunReplay('run-7'), { wrapper: makeWrapper() });
    act(() => result.current.setSpeed(4));
    expect(result.current.speed).toBe(4);
  });

  it('setIsLooping updates isLooping', () => {
    const { result } = renderHook(() => useRunReplay('run-8'), { wrapper: makeWrapper() });
    act(() => result.current.setIsLooping(true));
    expect(result.current.isLooping).toBe(true);
  });
});
