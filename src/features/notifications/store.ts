import { create } from 'zustand';

export type NotificationFilter = 'all' | 'unread' | 'run_event';

interface NotificationsStore {
  panelOpen: boolean;
  filter: NotificationFilter;
  setPanelOpen: (v: boolean) => void;
  setFilter: (f: NotificationFilter) => void;
}

export const useNotificationsStore = create<NotificationsStore>((set) => ({
  panelOpen: false,
  filter: 'all',
  setPanelOpen: (v) => set({ panelOpen: v }),
  setFilter: (f) => set({ filter: f }),
}));
