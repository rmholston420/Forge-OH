/**
 * ui-store.test.ts
 *
 * Full behavioural coverage for useRunDetailUIStore.
 * Specifically targets the guard inside setLatestStreamEventId (only advances
 * if id > current) which is the most failure-prone path and was previously
 * untested.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useRunDetailUIStore } from '@/lib/state/ui-store';

// Reset Zustand store state between tests
beforeEach(() => {
  useRunDetailUIStore.getState().resetRunDetailUI();
});

describe('useRunDetailUIStore — initial state', () => {
  it('starts with spec-exact defaults', () => {
    const s = useRunDetailUIStore.getState();
    expect(s.selectedTab).toBe('overview');
    expect(s.selectedEventId).toBeNull();
    expect(s.diffMode).toBe('split');
    expect(s.inspectorOpen).toBe(false);
    expect(s.latestStreamEventId).toBe(0);
    expect(s.pendingApprovalBanner).toBe(false);
  });
});

describe('setSelectedTab', () => {
  it('updates to every valid tab', () => {
    const tabs = ['overview', 'files', 'terminal', 'browser', 'metrics', 'security'] as const;
    for (const tab of tabs) {
      useRunDetailUIStore.getState().setSelectedTab(tab);
      expect(useRunDetailUIStore.getState().selectedTab).toBe(tab);
    }
  });
});

describe('setSelectedEventId', () => {
  it('sets a string id', () => {
    useRunDetailUIStore.getState().setSelectedEventId('evt-42');
    expect(useRunDetailUIStore.getState().selectedEventId).toBe('evt-42');
  });

  it('accepts null to clear selection', () => {
    useRunDetailUIStore.getState().setSelectedEventId('evt-1');
    useRunDetailUIStore.getState().setSelectedEventId(null);
    expect(useRunDetailUIStore.getState().selectedEventId).toBeNull();
  });
});

describe('setDiffMode', () => {
  it('switches to unified', () => {
    useRunDetailUIStore.getState().setDiffMode('unified');
    expect(useRunDetailUIStore.getState().diffMode).toBe('unified');
  });

  it('switches back to split', () => {
    useRunDetailUIStore.getState().setDiffMode('unified');
    useRunDetailUIStore.getState().setDiffMode('split');
    expect(useRunDetailUIStore.getState().diffMode).toBe('split');
  });
});

describe('inspector toggle', () => {
  it('setInspectorOpen(true) opens', () => {
    useRunDetailUIStore.getState().setInspectorOpen(true);
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(true);
  });

  it('toggleInspector flips from false to true', () => {
    useRunDetailUIStore.getState().toggleInspector();
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(true);
  });

  it('toggleInspector flips from true to false', () => {
    useRunDetailUIStore.getState().setInspectorOpen(true);
    useRunDetailUIStore.getState().toggleInspector();
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(false);
  });

  it('multiple toggles are idempotent pairs', () => {
    useRunDetailUIStore.getState().toggleInspector();
    useRunDetailUIStore.getState().toggleInspector();
    expect(useRunDetailUIStore.getState().inspectorOpen).toBe(false);
  });
});

describe('setLatestStreamEventId — monotonic guard', () => {
  it('advances when id is greater than current', () => {
    useRunDetailUIStore.getState().setLatestStreamEventId(5);
    expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(5);
  });

  it('does NOT update when id equals current', () => {
    useRunDetailUIStore.getState().setLatestStreamEventId(10);
    const before = useRunDetailUIStore.getState();
    useRunDetailUIStore.getState().setLatestStreamEventId(10);
    // State reference must be identical (guard returns `s` unchanged)
    expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(10);
    expect(useRunDetailUIStore.getState()).toBe(before);
  });

  it('does NOT update when id is less than current', () => {
    useRunDetailUIStore.getState().setLatestStreamEventId(20);
    const before = useRunDetailUIStore.getState();
    useRunDetailUIStore.getState().setLatestStreamEventId(15);
    expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(20);
    expect(useRunDetailUIStore.getState()).toBe(before);
  });

  it('advances monotonically through a stream of out-of-order ids', () => {
    const ids = [3, 1, 7, 5, 12, 9, 12, 15];
    const expected = [3, 3, 7, 7, 12, 12, 12, 15];
    for (let i = 0; i < ids.length; i++) {
      useRunDetailUIStore.getState().setLatestStreamEventId(ids[i]);
      expect(useRunDetailUIStore.getState().latestStreamEventId).toBe(expected[i]);
    }
  });
});

describe('setPendingApprovalBanner', () => {
  it('sets true', () => {
    useRunDetailUIStore.getState().setPendingApprovalBanner(true);
    expect(useRunDetailUIStore.getState().pendingApprovalBanner).toBe(true);
  });

  it('clears back to false', () => {
    useRunDetailUIStore.getState().setPendingApprovalBanner(true);
    useRunDetailUIStore.getState().setPendingApprovalBanner(false);
    expect(useRunDetailUIStore.getState().pendingApprovalBanner).toBe(false);
  });
});

describe('resetRunDetailUI', () => {
  it('restores full initial state after mutations', () => {
    const s = useRunDetailUIStore.getState();
    s.setSelectedTab('terminal');
    s.setSelectedEventId('evt-99');
    s.setDiffMode('unified');
    s.setInspectorOpen(true);
    s.setLatestStreamEventId(42);
    s.setPendingApprovalBanner(true);
    s.resetRunDetailUI();

    const after = useRunDetailUIStore.getState();
    expect(after.selectedTab).toBe('overview');
    expect(after.selectedEventId).toBeNull();
    expect(after.diffMode).toBe('split');
    expect(after.inspectorOpen).toBe(false);
    expect(after.latestStreamEventId).toBe(0);
    expect(after.pendingApprovalBanner).toBe(false);
  });
});

describe('exported selectors', () => {
  it('selectSelectedTab returns selectedTab slice', () => {
    const { selectSelectedTab } = await import('@/lib/state/ui-store');
    const s = useRunDetailUIStore.getState();
    expect(selectSelectedTab(s)).toBe('overview');
  });

  it('selectInspectorOpen returns inspectorOpen slice', async () => {
    const { selectInspectorOpen } = await import('@/lib/state/ui-store');
    useRunDetailUIStore.getState().setInspectorOpen(true);
    expect(selectInspectorOpen(useRunDetailUIStore.getState())).toBe(true);
  });

  it('selectLatestStreamEventId returns latestStreamEventId slice', async () => {
    const { selectLatestStreamEventId } = await import('@/lib/state/ui-store');
    useRunDetailUIStore.getState().setLatestStreamEventId(7);
    expect(selectLatestStreamEventId(useRunDetailUIStore.getState())).toBe(7);
  });

  it('selectPendingApprovalBanner returns pendingApprovalBanner slice', async () => {
    const { selectPendingApprovalBanner } = await import('@/lib/state/ui-store');
    useRunDetailUIStore.getState().setPendingApprovalBanner(true);
    expect(selectPendingApprovalBanner(useRunDetailUIStore.getState())).toBe(true);
  });
});
