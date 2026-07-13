/**
 * src/tests/unit/run-detail-store.test.ts
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useRunDetailStore } from '@/features/run-detail/store';
import type { ToolEvent } from '@/lib/schemas/event';

const mockEvent = (id: string): ToolEvent => ({
  id,
  type: 'tool_call',
  tool: 'bash',
  timestamp: '2026-01-01T00:00:00Z',
  data: {},
} as unknown as ToolEvent);

beforeEach(() => useRunDetailStore.getState().reset());

describe('useRunDetailStore', () => {
  it('initial selectedTab is overview', () => {
    expect(useRunDetailStore.getState().selectedTab).toBe('overview');
  });

  it('setSelectedTab updates tab', () => {
    useRunDetailStore.getState().setSelectedTab('events');
    expect(useRunDetailStore.getState().selectedTab).toBe('events');
  });

  it('setSelectedEventId updates selectedEventId', () => {
    useRunDetailStore.getState().setSelectedEventId('evt-5');
    expect(useRunDetailStore.getState().selectedEventId).toBe('evt-5');
  });

  it('setDiffMode updates diffMode', () => {
    useRunDetailStore.getState().setDiffMode('unified');
    expect(useRunDetailStore.getState().diffMode).toBe('unified');
  });

  it('setInspectorOpen updates inspectorOpen', () => {
    useRunDetailStore.getState().setInspectorOpen(true);
    expect(useRunDetailStore.getState().inspectorOpen).toBe(true);
  });

  it('setPendingApprovalBanner sets the flag', () => {
    useRunDetailStore.getState().setPendingApprovalBanner(true);
    expect(useRunDetailStore.getState().pendingApprovalBanner).toBe(true);
  });

  it('appendStreamEvent adds event to streamEvents', () => {
    useRunDetailStore.getState().appendStreamEvent(mockEvent('10'));
    expect(useRunDetailStore.getState().streamEvents).toHaveLength(1);
  });

  it('appendStreamEvent updates latestStreamEventId to max', () => {
    useRunDetailStore.getState().appendStreamEvent(mockEvent('5'));
    useRunDetailStore.getState().appendStreamEvent(mockEvent('12'));
    useRunDetailStore.getState().appendStreamEvent(mockEvent('3'));
    expect(useRunDetailStore.getState().latestStreamEventId).toBe(12);
  });

  it('setStreamConnected updates streamConnected', () => {
    useRunDetailStore.getState().setStreamConnected(true);
    expect(useRunDetailStore.getState().streamConnected).toBe(true);
  });

  it('setStreamReconnecting updates streamReconnecting', () => {
    useRunDetailStore.getState().setStreamReconnecting(true);
    expect(useRunDetailStore.getState().streamReconnecting).toBe(true);
  });

  it('reset restores all defaults', () => {
    useRunDetailStore.getState().setSelectedTab('artifacts');
    useRunDetailStore.getState().setDiffMode('unified');
    useRunDetailStore.getState().appendStreamEvent(mockEvent('99'));
    useRunDetailStore.getState().setStreamConnected(true);
    useRunDetailStore.getState().reset();
    const s = useRunDetailStore.getState();
    expect(s.selectedTab).toBe('overview');
    expect(s.diffMode).toBe('split');
    expect(s.streamEvents).toHaveLength(0);
    expect(s.streamConnected).toBe(false);
    expect(s.latestStreamEventId).toBe(0);
  });
});
