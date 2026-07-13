import { create } from 'zustand';
import type { SecretScope } from '@/lib/schemas/secret';

interface SecretsStore {
  scopeFilter: SecretScope | 'all';
  composerOpen: boolean;
  rotatingId: string | null;
  setScopeFilter: (s: SecretScope | 'all') => void;
  openComposer: () => void;
  closeComposer: () => void;
  setRotatingId: (id: string | null) => void;
}

export const useSecretsStore = create<SecretsStore>((set) => ({
  scopeFilter: 'all',
  composerOpen: false,
  rotatingId: null,
  setScopeFilter: (scopeFilter) => set({ scopeFilter }),
  openComposer: () => set({ composerOpen: true }),
  closeComposer: () => set({ composerOpen: false }),
  setRotatingId: (rotatingId) => set({ rotatingId }),
}));
