import { create } from 'zustand';
import type { SecretScope } from './schemas';

interface SecretsUIState {
  addModalOpen: boolean;
  confirmDeleteId: string | null;
  searchQuery: string;
  scopeFilter: SecretScope | 'all';

  openAddModal: () => void;
  closeAddModal: () => void;
  setConfirmDeleteId: (id: string | null) => void;
  setSearchQuery: (q: string) => void;
  setScopeFilter: (f: SecretScope | 'all') => void;
}

export const useSecretsStore = create<SecretsUIState>((set) => ({
  addModalOpen: false,
  confirmDeleteId: null,
  searchQuery: '',
  scopeFilter: 'all',

  openAddModal: () => set({ addModalOpen: true }),
  closeAddModal: () => set({ addModalOpen: false }),
  setConfirmDeleteId: (id) => set({ confirmDeleteId: id }),
  setSearchQuery: (q) => set({ searchQuery: q }),
  setScopeFilter: (f) => set({ scopeFilter: f }),
}));
