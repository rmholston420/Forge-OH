/**
 * src/lib/state/ui-store.ts
 *
 * Run Detail UI state (Zustand 5 — UI truth layer).
 *
 * Contains the exact RunDetailUIState interface defined in the build spec:
 *   selectedTab, selectedEventId, diffMode, inspectorOpen,
 *   latestStreamEventId, pendingApprovalBanner
 *
 * Separate from server state (TanStack Query) and stream state (streaming store).
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § State Management Architecture
 */
import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Types — exact interface from build spec
// ---------------------------------------------------------------------------

export type RunDetailTab =
  | 'overview'
  | 'files'
  | 'terminal'
  | 'browser'
  | 'metrics'
  | 'security';

export type DiffMode = 'split' | 'unified';

/**
 * Spec-exact RunDetailUIState interface.
 * Ref: Forge-OH-Build-Plan-Definitive.md § Key TypeScript Interfaces
 */
export interface RunDetailUIState {
  selectedTab: RunDetailTab;
  selectedEventId: string | null;
  diffMode: DiffMode;
  inspectorOpen: boolean;
  latestStreamEventId: number;
  pendingApprovalBanner: boolean;
}

export interface RunDetailUIActions {
  setSelectedTab: (tab: RunDetailTab) => void;
  setSelectedEventId: (id: string | null) => void;
  setDiffMode: (mode: DiffMode) => void;
  setInspectorOpen: (open: boolean) => void;
  toggleInspector: () => void;
  setLatestStreamEventId: (id: number) => void;
  setPendingApprovalBanner: (pending: boolean) => void;
  /**
   * MUST be called when navigating away from one run to another.
   * Resets latestStreamEventId to 0 so the new run's Socket.IO stream
   * reconnects from the beginning instead of skipping events using the
   * previous run's stale cursor.
   */
  resetRunDetailUI: () => void;
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const INITIAL_RUN_DETAIL_STATE: RunDetailUIState = {
  selectedTab: 'overview',
  selectedEventId: null,
  diffMode: 'split',
  inspectorOpen: false,
  latestStreamEventId: 0,
  pendingApprovalBanner: false,
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useRunDetailUIStore = create<RunDetailUIState & RunDetailUIActions>(
  (set) => ({
    ...INITIAL_RUN_DETAIL_STATE,

    setSelectedTab: (tab) => set({ selectedTab: tab }),
    setSelectedEventId: (id) => set({ selectedEventId: id }),
    setDiffMode: (mode) => set({ diffMode: mode }),
    setInspectorOpen: (open) => set({ inspectorOpen: open }),
    toggleInspector: () =>
      set((s) => ({ inspectorOpen: !s.inspectorOpen })),
    setLatestStreamEventId: (id) =>
      set((s) =>
        id > s.latestStreamEventId ? { latestStreamEventId: id } : s
      ),
    setPendingApprovalBanner: (pending) =>
      set({ pendingApprovalBanner: pending }),
    resetRunDetailUI: () => set(INITIAL_RUN_DETAIL_STATE),
  })
);

// ---------------------------------------------------------------------------
// Selectors — memoised slices for performance
// ---------------------------------------------------------------------------

export const selectSelectedTab = (s: RunDetailUIState) => s.selectedTab;
export const selectInspectorOpen = (s: RunDetailUIState) => s.inspectorOpen;
export const selectPendingApprovalBanner = (s: RunDetailUIState) =>
  s.pendingApprovalBanner;
export const selectLatestStreamEventId = (s: RunDetailUIState) =>
  s.latestStreamEventId;
