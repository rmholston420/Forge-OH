import { create } from 'zustand';

type StreamEvent = Record<string, unknown>;

const initialState = {
  selectedTab: 'overview' as const,
  selectedEventId: null as string | null,
  selectedArtifactId: null as string | null,
  diffMode: 'split' as const,
  terminalFilter: 'all' as const,
  inspectorOpen: true,
  latestStreamEventId: 0,
  pendingApprovalBanner: false,
  streamEvents: [] as StreamEvent[],
  streamEventIds: new Set<string | number>(),
  streamConnected: false,
  streamReconnecting: false,
};

export interface RunDetailStore {
  // Tab union must match TABS array in page.tsx AND the Zod schema in src/lib/schemas/run.ts.
  // Canonical tab set as of Phase 0: overview | files | terminal | browser | metrics | security | trace
  selectedTab: 'overview' | 'files' | 'terminal' | 'browser' | 'metrics' | 'security' | 'trace';
  selectedEventId: string | null;
  selectedArtifactId: string | null;
  diffMode: 'split' | 'unified';
  terminalFilter: 'all' | 'errors' | 'commands';
  inspectorOpen: boolean;
  latestStreamEventId: number;
  pendingApprovalBanner: boolean;
  streamEvents: StreamEvent[];
  /** Tracks IDs of events that have been streamed so duplicate replay after the
   *  200-event slice rollover doesn't re-add already-seen events. */
  streamEventIds: Set<string | number>;
  streamConnected: boolean;
  streamReconnecting: boolean;

  setSelectedTab: (tab: RunDetailStore['selectedTab']) => void;
  setSelectedEventId: (id: string | null) => void;
  setSelectedArtifactId: (id: string | null) => void;
  setDiffMode: (mode: RunDetailStore['diffMode']) => void;
  setTerminalFilter: (filter: RunDetailStore['terminalFilter']) => void;
  setInspectorOpen: (open: boolean) => void;
  setLatestStreamEventId: (id: number) => void;
  setPendingApprovalBanner: (value: boolean) => void;
  appendStreamEvent: (event: StreamEvent) => void;
  clearStreamEvents: () => void;
  setStreamConnected: (value: boolean) => void;
  setStreamReconnecting: (value: boolean) => void;
  reset: () => void;
}

export const useRunDetailStore = create<RunDetailStore>((set) => ({
  ...initialState,
  setSelectedTab: (selectedTab) => set({ selectedTab }),
  setSelectedEventId: (selectedEventId) => set({ selectedEventId }),
  setSelectedArtifactId: (selectedArtifactId) => set({ selectedArtifactId }),
  setDiffMode: (diffMode) => set({ diffMode }),
  setTerminalFilter: (terminalFilter) => set({ terminalFilter }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
  setLatestStreamEventId: (latestStreamEventId) => set({ latestStreamEventId }),
  setPendingApprovalBanner: (pendingApprovalBanner) => set({ pendingApprovalBanner }),
  appendStreamEvent: (event) =>
    set((state) => {
      const id = (event.id ?? event.eventId) as string | number | undefined;
      // Dedup: skip events whose ID we've already seen (prevents duplicate replay
      // after the 200-event slice rolls over latestStreamEventId).
      if (id !== undefined && state.streamEventIds.has(id)) return state;
      const newEvents = [...state.streamEvents, event].slice(-200);
      const newIds = new Set(state.streamEventIds);
      if (id !== undefined) newIds.add(id);
      return { streamEvents: newEvents, streamEventIds: newIds };
    }),
  clearStreamEvents: () => set({ streamEvents: [], streamEventIds: new Set() }),
  setStreamConnected: (streamConnected) => set({ streamConnected }),
  setStreamReconnecting: (streamReconnecting) => set({ streamReconnecting }),
  reset: () => set({ ...initialState, streamEventIds: new Set() }),
}));
