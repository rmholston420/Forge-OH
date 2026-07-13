import { create } from 'zustand';
import type { McpStatus } from './schemas';

interface McpStore {
  registerDrawerOpen: boolean;
  statusFilter:       McpStatus | 'all';
  confirmDeleteId:    string | null;

  openRegisterDrawer:  () => void;
  closeRegisterDrawer: () => void;
  setStatusFilter:     (s: McpStatus | 'all') => void;
  setConfirmDeleteId:  (id: string | null) => void;
}

export const useMcpStore = create<McpStore>((set) => ({
  registerDrawerOpen: false,
  statusFilter:       'all',
  confirmDeleteId:    null,

  openRegisterDrawer:  () => set({ registerDrawerOpen: true }),
  closeRegisterDrawer: () => set({ registerDrawerOpen: false }),
  setStatusFilter:     (s) => set({ statusFilter: s }),
  setConfirmDeleteId:  (id) => set({ confirmDeleteId: id }),
}));
