import { create } from 'zustand';
import type { RunDetailUIState } from '@/lib/schemas/run';
import type { ToolEvent } from '@/lib/schemas/event';

interface RunDetailStore extends RunDetailUIState {
  streamEvents: ToolEvent[];
  streamConnected: boolean;
  streamReconnecting: boolean;
  setSelectedTab: (tab: RunDetailUIState['selectedTab']) => void;
  setSelectedEventId: (id: string | null) => void;
  setDiffMode: (mode: 'split' | 'unified') => void;
  setInspectorOpen: (open: boolean) => void;
  setPendingApprovalBanner: (val: boolean) => void;
  appendStreamEvent: (evt: ToolEvent) => void;
  setStreamConnected: (val: boolean) => void;
  setStreamReconnecting: (val: boolean) => void;
  reset: () => void;
}

const DEFAULTS: RunDetailUIState = {
  selectedTab: 'overview',
  selectedEventId: null,
  diffMode: 'split',
  inspectorOpen: false,
  latestStreamEventId: 0,
  pendingApprovalBanner: false,
};

export const useRunDetailStore = create<RunDetailStore>((set) => ({
  ...DEFAULTS,
  streamEvents: [],
  streamConnected: false,
  streamReconnecting: false,
  setSelectedTab: (tab) => set({ selectedTab: tab }),
  setSelectedEventId: (id) => set({ selectedEventId: id }),
  setDiffMode: (mode) => set({ diffMode: mode }),
  setInspectorOpen: (open) => set({ inspectorOpen: open }),
  setPendingApprovalBanner: (val) => set({ pendingApprovalBanner: val }),
  appendStreamEvent: (evt) =>
    set((s) => ({
      streamEvents: [...s.streamEvents, evt],
      latestStreamEventId: Math.max(s.latestStreamEventId, parseInt(evt.id, 10) || 0),
    })),
  setStreamConnected: (val) => set({ streamConnected: val }),
  setStreamReconnecting: (val) => set({ streamReconnecting: val }),
  reset: () => set({ ...DEFAULTS, streamEvents: [], streamConnected: false, streamReconnecting: false }),
}));
