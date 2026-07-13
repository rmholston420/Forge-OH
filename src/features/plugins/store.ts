import { create } from 'zustand';
import type { PluginStatus } from '@/lib/schemas/plugin';

interface PluginsStore {
  statusFilter: PluginStatus | 'all';
  installerOpen: boolean;
  setStatusFilter: (s: PluginStatus | 'all') => void;
  openInstaller: () => void;
  closeInstaller: () => void;
}

export const usePluginsStore = create<PluginsStore>((set) => ({
  statusFilter: 'all',
  installerOpen: false,
  setStatusFilter: (statusFilter) => set({ statusFilter }),
  openInstaller: () => set({ installerOpen: true }),
  closeInstaller: () => set({ installerOpen: false }),
}));
