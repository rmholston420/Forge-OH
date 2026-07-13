/**
 * src/lib/state/app-store.ts
 *
 * Global application UI state (Zustand 5 — UI truth layer).
 *
 * Owns: sidebar collapse, active route, command-palette visibility, theme.
 * Does NOT own: server data (TanStack Query), stream events (streaming store).
 *
 * Ref: Forge-OH-Build-Plan-Definitive.md § State Management Architecture
 */
import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ActiveRoute =
  | 'runs'
  | 'run-detail'
  | 'workspaces'
  | 'tools-mcp'
  | 'plugins'
  | 'observability'
  | 'settings'
  | 'secrets'
  | 'providers';

export interface AppState {
  /** Whether the left sidebar is in its expanded (248px) state. */
  sidebarExpanded: boolean;

  /** The currently active top-level route for sidebar highlight. */
  activeRoute: ActiveRoute | null;

  /** Whether the Cmd+K command palette is open. */
  commandPaletteOpen: boolean;

  /** The active run ID being viewed (if any). */
  activeRunId: string | null;
}

export interface AppActions {
  setSidebarExpanded: (expanded: boolean) => void;
  toggleSidebar: () => void;
  setActiveRoute: (route: ActiveRoute | null) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  setActiveRunId: (runId: string | null) => void;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState & AppActions>((set) => ({
  // Initial state
  sidebarExpanded: true,
  activeRoute: null,
  commandPaletteOpen: false,
  activeRunId: null,

  // Actions
  setSidebarExpanded: (expanded) => set({ sidebarExpanded: expanded }),
  toggleSidebar: () =>
    set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),
  setActiveRoute: (route) => set({ activeRoute: route }),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  toggleCommandPalette: () =>
    set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),
  setActiveRunId: (runId) => set({ activeRunId: runId }),
}));
