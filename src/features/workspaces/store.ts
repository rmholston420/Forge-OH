import { create } from 'zustand';
import type { WorkspaceType } from '@/lib/schemas/workspace';

interface WorkspacesStore {
  typeFilter: WorkspaceType | 'all';
  composerOpen: boolean;
  editingId: string | null;
  setTypeFilter: (t: WorkspaceType | 'all') => void;
  openComposer: (editingId?: string) => void;
  closeComposer: () => void;
}

export const useWorkspacesStore = create<WorkspacesStore>((set) => ({
  typeFilter: 'all',
  composerOpen: false,
  editingId: null,
  setTypeFilter: (typeFilter) => set({ typeFilter }),
  openComposer: (editingId = null) => set({ composerOpen: true, editingId: editingId ?? null }),
  closeComposer: () => set({ composerOpen: false, editingId: null }),
}));
