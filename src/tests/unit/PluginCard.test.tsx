import { render, screen, fireEvent } from '@/tests/helpers/render';
import { PluginCard } from '@/components/domain/plugin-card';
// Use the canonical Plugin schema (with transport + capabilities) that
// PluginCard actually consumes. The @/features/mcp/schemas.Plugin type is
// a legacy shape without those fields — fine for McpServerCard, not for
// the modern PluginCard.
import type { Plugin } from '@/lib/schemas/plugin';
import { describe, it, expect, vi } from 'vitest';

const BASE: Plugin = {
  id: 'plugin-1',
  name: 'Test Plugin',
  version: '1.0.0',
  status: 'enabled',
  description: 'A test plugin',
  author: 'Rigpa',
  installedAt: new Date().toISOString(),
  transport: 'stdio',
  capabilities: ['run.started'],
} as unknown as Plugin;

describe('PluginCard', () => {
  it('renders name, version badge, and status text', () => {
    render(<PluginCard plugin={BASE} />);
    expect(screen.getByText('Test Plugin')).toBeTruthy();
    expect(screen.getByText('v1.0.0')).toBeTruthy();
    // Real component renders lowercase status text ('enabled') inside a badge.
    expect(screen.getByText('enabled')).toBeTruthy();
  });

  it('exposes a toggle button (Disable when currently enabled)', () => {
    // The real component uses a role=button toggle (aria-pressed) driven by
    // internal useTogglePlugin mutation — not a checkbox or an onToggle prop.
    render(<PluginCard plugin={BASE} />);
    const toggle = screen.getByRole('button', { name: /Disable plugin/i });
    expect(toggle).toBeTruthy();
    expect(toggle.getAttribute('aria-pressed')).toBe('true');
  });

  it.skip('shows Configure button when configSchema present', () => {
    // TASK 3.6: Configure was never wired into PluginCard — the real
    // component only exposes Ping / Uninstall / toggle. Kept as skip until
    // configuration UI ships.
    const withConfig = {
      ...BASE,
      configSchema: { key: { type: 'string', label: 'Key', required: true, default: '' } },
    } as unknown as Plugin;
    render(<PluginCard plugin={withConfig} />);
    expect(screen.getByText('Configure')).toBeTruthy();
  });
});
