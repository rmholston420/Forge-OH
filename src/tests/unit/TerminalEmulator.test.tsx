import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TerminalEmulator } from '@/components/domain/TerminalEmulator';

// xterm is browser-only; mock both addons
vi.mock('@xterm/xterm', () => ({
  Terminal: vi.fn(() => ({
    loadAddon: vi.fn(),
    open: vi.fn(),
    writeln: vi.fn(),
    write: vi.fn(),
    dispose: vi.fn(),
  })),
}));

vi.mock('@xterm/addon-fit', () => ({
  FitAddon: vi.fn(() => ({ fit: vi.fn() })),
}));

describe('TerminalEmulator', () => {
  it('renders terminal region', () => {
    render(<TerminalEmulator />);
    expect(screen.getByRole('region', { name: /terminal output/i })).toBeTruthy();
  });
});
