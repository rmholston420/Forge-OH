import { create } from 'zustand';
import type { WorkspaceHealth } from './schemas';

interface WorkspacesUIState {
  selectedWorkspaceId: string | null;
  drawerOpen: boolean;
  healthFilter: WorkspaceHealth | 'all';
  confirmResetId: string | null;

  setSelectedWorkspaceId: (id: string | null) => void;
  openDrawer: (id: string) => void;
  closeDrawer: () => void;
  setHealthFilter: (f: WorkspaceHealth | 'all') => void;
  setConfirmResetId: (id: string | null) => void;
}

export const useWorkspacesStore = create<WorkspacesUIState>((set) => ({
  selectedWorkspaceId: null,
  drawerOpen: false,
  healthFilter: 'all',
  confirmResetId: null,

  setSelectedWorkspaceId: (id) => set({ selectedWorkspaceId: id }),
  openDrawer: (id) => set({ selectedWorkspaceId: id, drawerOpen: true }),
  closeDrawer: () => set({ drawerOpen: false }),
  setHealthFilter: (f) => set({ healthFilter: f }),
  setConfirmResetId: (id) => set({ confirmResetId: id }),
}));
