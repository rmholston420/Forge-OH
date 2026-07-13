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
  streamConnected: false,
  streamReconnecting: false,
};

export interface RunDetailStore {
  selectedTab: 'overview' | 'events' | 'files' | 'artifacts' | 'terminal' | 'browser' | 'metrics' | 'security';
  selectedEventId: string | null;
  selectedArtifactId: string | null;
  diffMode: 'split' | 'unified';
  terminalFilter: 'all' | 'errors' | 'commands';
  inspectorOpen: boolean;
  latestStreamEventId: number;
  pendingApprovalBanner: boolean;
  streamEvents: StreamEvent[];
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
  appendStreamEvent: (event) => set((state) => ({ streamEvents: [...state.streamEvents, event].slice(-200) })),
  clearStreamEvents: () => set({ streamEvents: [] }),
  setStreamConnected: (streamConnected) => set({ streamConnected }),
  setStreamReconnecting: (streamReconnecting) => set({ streamReconnecting }),
  reset: () => set({ ...initialState }),
}));
