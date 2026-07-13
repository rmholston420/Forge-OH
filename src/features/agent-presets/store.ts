import { create } from 'zustand';

interface AgentPresetStore {
  drawerOpen:      boolean;
  editingId:       string | null;
  confirmDeleteId: string | null;

  openCreateDrawer: () => void;
  openEditDrawer:   (id: string) => void;
  closeDrawer:      () => void;
  setConfirmDelete: (id: string | null) => void;
}

export const useAgentPresetStore = create<AgentPresetStore>((set) => ({
  drawerOpen:      false,
  editingId:       null,
  confirmDeleteId: null,

  openCreateDrawer: () => set({ drawerOpen: true, editingId: null }),
  openEditDrawer:   (id) => set({ drawerOpen: true, editingId: id }),
  closeDrawer:      () => set({ drawerOpen: false, editingId: null }),
  setConfirmDelete: (id) => set({ confirmDeleteId: id }),
}));
