import { create } from 'zustand';

interface TraceStore {
  expandedSpanIds: Set<string>;
  selectedSpanId: string | null;
  toggleSpan: (id: string) => void;
  selectSpan: (id: string | null) => void;
  expandAll: (ids: string[]) => void;
  collapseAll: () => void;
}

export const useTraceStore = create<TraceStore>((set) => ({
  expandedSpanIds: new Set(),
  selectedSpanId: null,
  toggleSpan: (id) => set((s) => {
    const next = new Set(s.expandedSpanIds);
    next.has(id) ? next.delete(id) : next.add(id);
    return { expandedSpanIds: next };
  }),
  selectSpan: (selectedSpanId) => set({ selectedSpanId }),
  expandAll: (ids) => set({ expandedSpanIds: new Set(ids) }),
  collapseAll: () => set({ expandedSpanIds: new Set() }),
}));
