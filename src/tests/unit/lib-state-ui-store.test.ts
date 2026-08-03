/**
 * src/tests/unit/lib-state-ui-store.test.ts
 *
 * Full coverage of RunDetail UI store (Zustand): every action + selector +
 * monotonic latestStreamEventId guard + reset semantics.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  useRunDetailUIStore,
  selectSelectedTab,
  selectInspectorOpen,
  selectPendingApprovalBanner,
  selectLatestStreamEventId,
} from '@/lib/state/ui-store';

const reset = () => {
  useRunDetailUIStore.getState().resetRunDetailUI();
};

describe('useRunDetailUIStore', () => {
  beforeEach(reset);

  it('initial state matches spec', () => {
    const s = useRunDetailUIStore.getState();
    expect(s.selectedTab).toBe('overview');
    expect(s.selectedEventId).toBeNull();
    expect(s.diffMode).toBe('split');
    expect(s.inspectorOpen).toBe(false);
    expect(s.latestStreamEventId).toBe(0);
    expect(s.pendingApprovalBanner).toBe(false);
  });

  it('setSelectedTab / setSelectedEventId / setDiffMode', () => {
    const s = useRunDetailUIStore.getState();
    s.setSelectedTab('files');
    s.setSelectedEventId('evt-42');
    s.setDiffMode('unified');
    const next = useRunDetailUIStore.getState();
    expect(next.selectedTab).toBe('files');
    expect(next.selectedEventId).toBe('evt-42');
    expect(next.diffMode).toBe('unified');
  });

  it('setInspectorOpen and toggleInspector are consistent', () => {
    useRunDetailUIStore.getState().setInspectorOpen(true);
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(true);
    useRunDetailUIStore.getState().toggleInspector();
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(false);
    useRunDetailUIStore.getState().toggleInspector();
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(true);
  });

  it('setLatestStreamEventId is monotonic — never regresses', () => {
    const { setLatestStreamEventId } = useRunDetailUIStore.getState();
    setLatestStreamEventId(5);
    expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(5);
    setLatestStreamEventId(3); // out-of-order — ignored
    expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(5);
    setLatestStreamEventId(10);
    expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(10);
  });

  it('setPendingApprovalBanner toggles', () => {
    useRunDetailUIStore.getState().setPendingApprovalBanner(true);
    expect(useRunDetailUIStore.getState().pendingApprovalBanner).toBe(true);
    useRunDetailUIStore.getState().setPendingApprovalBanner(false);
    expect(useRunDetailUIStore.getState().pendingApprovalBanner).toBe(false);
  });

  it('resetRunDetailUI wipes back to INITIAL', () => {
    const s = useRunDetailUIStore.getState();
    s.setSelectedTab('metrics');
    s.setSelectedEventId('evt');
    s.setLatestStreamEventId(99);
    s.setInspectorOpen(true);
    s.setPendingApprovalBanner(true);
    s.setDiffMode('unified');
    s.resetRunDetailUI();
    const after = useRunDetailUIStore.getState();
    expect(after.selectedTab).toBe('overview');
    expect(after.selectedEventId).toBeNull();
    expect(after.latestStreamEventId).toBe(0);
    expect(after.inspectorOpen).toBe(false);
    expect(after.pendingApprovalBanner).toBe(false);
    expect(after.diffMode).toBe('split');
  });
});

describe('ui-store selectors', () => {
  it('selectSelectedTab falls back to overview when unset', () => {
    expect(selectSelectedTab({} as any)).toBe('overview');
    expect(selectSelectedTab({ selectedTab: 'browser' } as any)).toBe('browser');
  });
  it('other selectors are pure projections', () => {
    const s = {
      selectedTab: 'files' as const,
      selectedEventId: null,
      diffMode: 'split' as const,
      inspectorOpen: true,
      latestStreamEventId: 42,
      pendingApprovalBanner: true,
    };
    expect(selectInspectorOpen(s)).toBe(true);
    expect(selectPendingApprovalBanner(s)).toBe(true);
    expect(selectLatestStreamEventId(s)).toBe(42);
  });
});
