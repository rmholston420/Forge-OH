import { create } from 'zustand';

export type SecretScopeFilter = 'all' | 'global' | 'workspace' | 'run' | 'user' | 'deployment';

export interface SecretsStore {
  composerOpen: boolean;
  rotatingId: string | null;
  scopeFilter: SecretScopeFilter;
  confirmDeleteId: string | null;
  openComposer: () => void;
  closeComposer: () => void;
  openAddDrawer: () => void;
  setRotatingId: (value: string | null) => void;
  setScopeFilter: (value: SecretScopeFilter) => void;
  setConfirmDeleteId: (value: string | null) => void;
}

export const useSecretsStore = create<SecretsStore>((set) => ({
  composerOpen: false,
  rotatingId: null,
  scopeFilter: 'all',
  confirmDeleteId: null,
  openComposer: () => set({ composerOpen: true }),
  closeComposer: () => set({ composerOpen: false }),
  openAddDrawer: () => set({ composerOpen: true }),
  setRotatingId: (rotatingId) => set({ rotatingId }),
  setScopeFilter: (scopeFilter) => set({ scopeFilter }),
  setConfirmDeleteId: (confirmDeleteId) => set({ confirmDeleteId }),
}));
