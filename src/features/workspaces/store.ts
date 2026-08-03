import { create } from 'zustand';

/**
 * Stage 6: only `local` workspaces are supported. The filter is retained so
 * existing UI code paths keep compiling, but 'all' and 'local' collapse to
 * the same set.
 */
export type WorkspaceTypeFilter = 'all' | 'local';

export interface WorkspacesStore {
  typeFilter: WorkspaceTypeFilter;
  filterType: WorkspaceTypeFilter;
  composerOpen: boolean;
  drawerOpen: boolean;
  editingId: string | null;
  confirmDeleteId: string | null;
  confirmDeleteName: string | null;
  setTypeFilter: (value: WorkspaceTypeFilter) => void;
  setFilterType: (value: WorkspaceTypeFilter) => void;
  openComposer: () => void;
  closeComposer: () => void;
  openCreateDrawer: () => void;
  openEditDrawer: (id: string) => void;
  closeDrawer: () => void;
  openConfirmDelete: (id: string, name?: string | null) => void;
  closeConfirmDelete: () => void;
}

export const useWorkspacesStore = create<WorkspacesStore>((set) => ({
  typeFilter: 'all',
  filterType: 'all',
  composerOpen: false,
  drawerOpen: false,
  editingId: null,
  confirmDeleteId: null,
  confirmDeleteName: null,
  setTypeFilter: (typeFilter) => set({ typeFilter, filterType: typeFilter }),
  setFilterType: (filterType) => set({ filterType, typeFilter: filterType }),
  openComposer: () => set({ composerOpen: true, drawerOpen: true }),
  closeComposer: () => set({ composerOpen: false, drawerOpen: false, editingId: null }),
  openCreateDrawer: () => set({ composerOpen: true, drawerOpen: true, editingId: null }),
  openEditDrawer: (editingId) => set({ composerOpen: true, drawerOpen: true, editingId }),
  closeDrawer: () => set({ composerOpen: false, drawerOpen: false, editingId: null }),
  openConfirmDelete: (confirmDeleteId, confirmDeleteName = null) => set({ confirmDeleteId, confirmDeleteName }),
  closeConfirmDelete: () => set({ confirmDeleteId: null, confirmDeleteName: null }),
}));
