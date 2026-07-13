import { render, screen, fireEvent } from '@testing-library/react';
import { PluginCard } from '@/components/domain/plugin-card';
import type { Plugin } from '@/features/mcp/schemas';
import { describe, it, expect, vi } from 'vitest';

const BASE: Plugin = {
  id: 'plugin-1',
  name: 'Test Plugin',
  version: '1.0.0',
  status: 'enabled',
  description: 'A test plugin',
  author: 'Rigpa',
  installedAt: new Date().toISOString(),
};

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
    const withConfig: Plugin = {
      ...BASE,
      configSchema: { key: { type: 'string', label: 'Key', required: true, default: '' } },
    };
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
