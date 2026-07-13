import { create } from 'zustand';

export type ActiveRoute =
  | 'runs'
  | 'run-detail'
  | 'workspaces'
  | 'tools-mcp'
  | 'plugins'
  | 'observability'
  | 'settings'
  | 'secrets';

export interface AppState {
  sidebarExpanded: boolean;
  sidebarOpen: boolean;
  activeRoute: ActiveRoute | null;
  commandPaletteOpen: boolean;
  cmdPaletteOpen: boolean;
  activeRunId: string | null;
  unreadCount: number;
}

export interface AppActions {
  setSidebarExpanded: (expanded: boolean) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setActiveRoute: (route: ActiveRoute | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setCmdPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  setActiveRunId: (runId: string | null) => void;
  incrementUnread: () => void;
  clearUnread: () => void;
}

export const useAppStore = create<AppState & AppActions>((set) => ({
  sidebarExpanded: true,
  sidebarOpen: false,
  activeRoute: null,
  commandPaletteOpen: false,
  cmdPaletteOpen: false,
  activeRunId: null,
  unreadCount: 0,

  setSidebarExpanded: (expanded) =>
    set({ sidebarExpanded: expanded, sidebarOpen: expanded }),

  toggleSidebar: () =>
    set((s) => ({
      sidebarExpanded: !s.sidebarExpanded,
      sidebarOpen: !s.sidebarOpen,
    })),

  setSidebarOpen: (open) =>
    set({ sidebarOpen: open, sidebarExpanded: open }),

  setActiveRoute: (route) => set({ activeRoute: route }),

  setCommandPaletteOpen: (open) =>
    set({ commandPaletteOpen: open, cmdPaletteOpen: open }),

  setCmdPaletteOpen: (open) =>
    set({ cmdPaletteOpen: open, commandPaletteOpen: open }),

  toggleCommandPalette: () =>
    set((s) => ({
      commandPaletteOpen: !s.commandPaletteOpen,
      cmdPaletteOpen: !s.cmdPaletteOpen,
    })),

  setActiveRunId: (runId) => set({ activeRunId: runId }),

  incrementUnread: () =>
    set((s) => ({ unreadCount: s.unreadCount + 1 })),

  clearUnread: () => set({ unreadCount: 0 }),
}));
