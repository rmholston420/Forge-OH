import { create } from 'zustand';
import type { WorkspaceType } from './schemas';

interface WorkspacesStore {
  selectedId:        string | null;
  filterType:        WorkspaceType | 'all';
  drawerOpen:        boolean;
  editingId:         string | null;
  confirmDeleteId:   string | null;
  confirmDeleteName: string;

  setSelectedId:      (id: string | null) => void;
  setFilterType:      (type: WorkspaceType | 'all') => void;
  openCreateDrawer:   () => void;
  openEditDrawer:     (id: string) => void;
  closeDrawer:        () => void;
  openConfirmDelete:  (id: string, name: string) => void;
  closeConfirmDelete: () => void;
}

export const useWorkspacesStore = create<WorkspacesStore>((set) => ({
  selectedId:        null,
  filterType:        'all',
  drawerOpen:        false,
  editingId:         null,
  confirmDeleteId:   null,
  confirmDeleteName: '',

  setSelectedId:      (id)   => set({ selectedId: id }),
  setFilterType:      (type) => set({ filterType: type }),
  openCreateDrawer:   ()     => set({ drawerOpen: true,  editingId: null }),
  openEditDrawer:     (id)   => set({ drawerOpen: true,  editingId: id }),
  closeDrawer:        ()     => set({ drawerOpen: false, editingId: null }),
  openConfirmDelete:  (id, name) => set({ confirmDeleteId: id, confirmDeleteName: name }),
  closeConfirmDelete: ()     => set({ confirmDeleteId: null, confirmDeleteName: '' }),
}));
