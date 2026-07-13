import { create } from 'zustand';
import type { SecretScope } from './schemas';

interface SecretsStore {
  addDrawerOpen:    boolean;
  scopeFilter:      SecretScope | 'all';
  confirmDeleteId:  string | null;

  openAddDrawer:     () => void;
  closeAddDrawer:    () => void;
  setScopeFilter:    (s: SecretScope | 'all') => void;
  setConfirmDeleteId:(id: string | null) => void;
}

export const useSecretsStore = create<SecretsStore>((set) => ({
  addDrawerOpen:    false,
  scopeFilter:      'all',
  confirmDeleteId:  null,

  openAddDrawer:     () => set({ addDrawerOpen: true }),
  closeAddDrawer:    () => set({ addDrawerOpen: false }),
  setScopeFilter:    (s) => set({ scopeFilter: s }),
  setConfirmDeleteId:(id) => set({ confirmDeleteId: id }),
}));
