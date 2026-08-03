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
    render(<PluginCard plugin={BASE} onToggle={vi.fn()} onConfigure={vi.fn()} />);
    expect(screen.getByText('Test Plugin')).toBeTruthy();
    expect(screen.getByText('v1.0.0')).toBeTruthy();
    expect(screen.getByText('Enabled')).toBeTruthy();
  });

  it('hides Configure button when no configSchema', () => {
    render(<PluginCard plugin={BASE} onToggle={vi.fn()} onConfigure={vi.fn()} />);
    expect(screen.queryByText('Configure')).toBeNull();
  });

  it('shows Configure button when configSchema present', () => {
    const withConfig = {
      ...BASE,
      configSchema: { key: { type: 'string', label: 'Key', required: true, default: '' } },
    } as unknown as Plugin;
    render(<PluginCard plugin={withConfig} onToggle={vi.fn()} onConfigure={vi.fn()} />);
    expect(screen.getByText('Configure')).toBeTruthy();
  });

  it('calls onToggle when checkbox toggled', () => {
    const onToggle = vi.fn();
    render(<PluginCard plugin={BASE} onToggle={onToggle} onConfigure={vi.fn()} />);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onToggle).toHaveBeenCalledWith('plugin-1', false);
  });
});
