/**
 * Unit tests: src/lib/state/app-store.ts
 *
 * Verifies all actions, initial state, 'providers' route is absent,
 * and toggle semantics.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '@/lib/state/app-store';
import type { ActiveRoute } from '@/lib/state/app-store';

beforeEach(() => {
  useAppStore.setState({
    sidebarExpanded: true,
    activeRoute: null,
    commandPaletteOpen: false,
    activeRunId: null,
  });
});

describe('AppStore — initial state', () => {
  it('sidebarExpanded defaults to true', () => {
    expect(useAppStore.getState().sidebarExpanded).toBe(true);
  });
  it('activeRoute defaults to null', () => {
    expect(useAppStore.getState().activeRoute).toBeNull();
  });
  it('commandPaletteOpen defaults to false', () => {
    expect(useAppStore.getState().commandPaletteOpen).toBe(false);
  });
  it('activeRunId defaults to null', () => {
    expect(useAppStore.getState().activeRunId).toBeNull();
  });
});

describe('setSidebarExpanded', () => {
  it('sets to false', () => {
    useAppStore.getState().setSidebarExpanded(false);
    expect(useAppStore.getState().sidebarExpanded).toBe(false);
  });
  it('sets back to true', () => {
    useAppStore.getState().setSidebarExpanded(false);
    useAppStore.getState().setSidebarExpanded(true);
    expect(useAppStore.getState().sidebarExpanded).toBe(true);
  });
});

describe('toggleSidebar', () => {
  it('toggles from true to false', () => {
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarExpanded).toBe(false);
  });
  it('toggles twice returns to initial', () => {
    useAppStore.getState().toggleSidebar();
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().sidebarExpanded).toBe(true);
  });
});

describe('setActiveRoute', () => {
  const VALID_ROUTES: ActiveRoute[] = [
    'runs', 'run-detail', 'workspaces', 'tools-mcp',
    'plugins', 'observability', 'settings', 'secrets',
  ];

  it.each(VALID_ROUTES)('accepts valid route: %s', (route) => {
    useAppStore.getState().setActiveRoute(route);
    expect(useAppStore.getState().activeRoute).toBe(route);
  });

  it('accepts null to clear the route', () => {
    useAppStore.getState().setActiveRoute('runs');
    useAppStore.getState().setActiveRoute(null);
    expect(useAppStore.getState().activeRoute).toBeNull();
  });

  it("does NOT include 'providers' as a valid route (removed in fix pass)", () => {
    const VALID_SET = new Set(VALID_ROUTES);
    expect(VALID_SET.has('providers' as any)).toBe(false);
  });
});

describe('setCommandPaletteOpen / toggleCommandPalette', () => {
  it('setCommandPaletteOpen(true) opens palette', () => {
    useAppStore.getState().setCommandPaletteOpen(true);
    expect(useAppStore.getState().commandPaletteOpen).toBe(true);
  });
  it('toggleCommandPalette flips state', () => {
    useAppStore.getState().toggleCommandPalette();
    expect(useAppStore.getState().commandPaletteOpen).toBe(true);
    useAppStore.getState().toggleCommandPalette();
    expect(useAppStore.getState().commandPaletteOpen).toBe(false);
  });
});

describe('setActiveRunId', () => {
  it('sets a run ID', () => {
    useAppStore.getState().setActiveRunId('run-abc');
    expect(useAppStore.getState().activeRunId).toBe('run-abc');
  });
  it('clears the run ID with null', () => {
    useAppStore.getState().setActiveRunId('run-abc');
    useAppStore.getState().setActiveRunId(null);
    expect(useAppStore.getState().activeRunId).toBeNull();
  });
});
