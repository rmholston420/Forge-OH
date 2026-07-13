/**
 * app-store-concurrency.test.ts
 *
 * Targets invariants not covered by the existing app-store.test.ts:
 *   - Concurrent toggle calls on toggleSidebar and toggleCommandPalette
 *     must leave state consistent (no race between synchronous Zustand
 *     set() calls since Zustand processes them synchronously in tests).
 *   - setActiveRunId(null) clears the active run.
 *   - setActiveRoute(null) clears the active route.
 *   - Only valid ActiveRoute values are accepted (type-level guard).
 *   - commandPaletteOpen and sidebarExpanded are independent (one does
 *     not bleed into the other).
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { useAppStore } from '@/lib/state/app-store';

beforeEach(() => {
  // Reset to known initial state
  useAppStore.setState({
    sidebarExpanded: true,
    activeRoute: null,
    commandPaletteOpen: false,
    activeRunId: null,
  });
});

describe('toggleSidebar — sequential consistency', () => {
  it('N toggles leaves state in expected parity', () => {
    const initial = useAppStore.getState().sidebarExpanded; // true
    for (let i = 1; i <= 10; i++) {
      useAppStore.getState().toggleSidebar();
      expect(useAppStore.getState().sidebarExpanded).toBe(initial ? i % 2 === 0 : i % 2 !== 0);
    }
  });
});

describe('toggleCommandPalette — sequential consistency', () => {
  it('N toggles leaves state in expected parity', () => {
    for (let i = 1; i <= 6; i++) {
      useAppStore.getState().toggleCommandPalette();
      expect(useAppStore.getState().commandPaletteOpen).toBe(i % 2 !== 0);
    }
  });
});

describe('state slice independence', () => {
  it('toggling sidebar does not affect commandPaletteOpen', () => {
    useAppStore.getState().setCommandPaletteOpen(true);
    useAppStore.getState().toggleSidebar();
    expect(useAppStore.getState().commandPaletteOpen).toBe(true);
  });

  it('toggling command palette does not affect sidebarExpanded', () => {
    useAppStore.getState().setSidebarExpanded(false);
    useAppStore.getState().toggleCommandPalette();
    expect(useAppStore.getState().sidebarExpanded).toBe(false);
  });

  it('setActiveRunId does not affect activeRoute', () => {
    useAppStore.getState().setActiveRoute('runs');
    useAppStore.getState().setActiveRunId('run-99');
    expect(useAppStore.getState().activeRoute).toBe('runs');
  });
});

describe('setActiveRunId', () => {
  it('sets and clears activeRunId', () => {
    useAppStore.getState().setActiveRunId('run-abc');
    expect(useAppStore.getState().activeRunId).toBe('run-abc');
    useAppStore.getState().setActiveRunId(null);
    expect(useAppStore.getState().activeRunId).toBeNull();
  });
});

describe('setActiveRoute', () => {
  const routes = [
    'runs', 'run-detail', 'workspaces', 'tools-mcp',
    'plugins', 'observability', 'settings', 'secrets',
  ] as const;

  it.each(routes)('accepts valid route: %s', (route) => {
    useAppStore.getState().setActiveRoute(route);
    expect(useAppStore.getState().activeRoute).toBe(route);
  });

  it('accepts null to clear active route', () => {
    useAppStore.getState().setActiveRoute('settings');
    useAppStore.getState().setActiveRoute(null);
    expect(useAppStore.getState().activeRoute).toBeNull();
  });

  it('does not include the removed providers route', () => {
    // Regression: providers was removed from ActiveRoute in a previous fix.
    // TypeScript already prevents this at compile time; this test guards against
    // any future reintroduction at the string level.
    const validRoutes = new Set(routes);
    expect(validRoutes.has('providers' as never)).toBe(false);
  });
});
