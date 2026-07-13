import { create } from 'zustand';

export interface TraceStore {
  selectedSpanId: string | null;
  expandedSpanIds: string[];
  setSelectedSpanId: (id: string | null) => void;
  selectSpan: (id: string | null) => void;
  toggleSpan: (id: string) => void;
  expandAll: () => void;
  collapseAll: () => void;
}

export const useTraceStore = create<TraceStore>((set) => ({
  selectedSpanId: null,
  expandedSpanIds: [],
  setSelectedSpanId: (selectedSpanId) => set({ selectedSpanId }),
  selectSpan: (selectedSpanId) => set({ selectedSpanId }),
  toggleSpan: (id) =>
    set((state) => ({
      expandedSpanIds: state.expandedSpanIds.includes(id)
        ? state.expandedSpanIds.filter((x) => x !== id)
        : [...state.expandedSpanIds, id],
    })),
  expandAll: () => set({ expandedSpanIds: ['*'] }),
  collapseAll: () => set({ expandedSpanIds: [] }),
}));
