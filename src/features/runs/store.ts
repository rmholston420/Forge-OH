import { create } from 'zustand';
import type { RunsFilter } from './schemas';

interface RunsUIState {
  filter: RunsFilter;
  composerOpen: boolean;
  setFilter: (f: Partial<RunsFilter>) => void;
  setComposerOpen: (open: boolean) => void;
  resetFilter: () => void;
}

const DEFAULT_FILTER: RunsFilter = {};

export const useRunsStore = create<RunsUIState>((set) => ({
  filter: DEFAULT_FILTER,
  composerOpen: false,
  setFilter: (f) => set((s) => ({ filter: { ...s.filter, ...f } })),
  setComposerOpen: (open) => set({ composerOpen: open }),
  resetFilter: () => set({ filter: DEFAULT_FILTER }),
}));
