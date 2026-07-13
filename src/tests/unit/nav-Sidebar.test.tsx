/**
 * src/tests/unit/nav-Sidebar.test.tsx
 * Covers: Sidebar navigation component
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/navigation/Sidebar';

const mockUseAppStore = vi.fn();
vi.mock('@/lib/state/app-store', () => ({
  useAppStore: (selector: any) => mockUseAppStore(selector),
}));

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => '/runs',
}));

describe('Sidebar', () => {
  beforeEach(() => {
    mockUseAppStore.mockImplementation((sel: any) => {
      const store = {
        sidebarOpen: true,
        activeRoute: 'runs',
        setSidebarOpen: vi.fn(),
        setActiveRoute: vi.fn(),
      };
      return sel ? sel(store) : store;
    });
  });

  it('renders without crashing', () => {
    expect(() => render(<Sidebar />)).not.toThrow();
  });

  it('contains a nav element', () => {
    render(<Sidebar />);
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });

  it('renders Runs link', () => {
    render(<Sidebar />);
    expect(screen.getByText(/runs/i)).toBeInTheDocument();
  });

  it('renders Workspaces link', () => {
    render(<Sidebar />);
    expect(screen.getByText(/workspace/i)).toBeInTheDocument();
  });

  it('renders Settings link', () => {
    render(<Sidebar />);
    expect(screen.getByText(/settings/i)).toBeInTheDocument();
  });

  it('active route item has aria or class indicator', () => {
    render(<Sidebar />);
    // Active link should have aria-current or an active class
    const activeEl =
      screen.queryByRole('link', { current: 'page' }) ??
      document.querySelector('[aria-current="page"]') ??
      document.querySelector('[class*="active"]');
    expect(activeEl).not.toBeNull();
  });
});
