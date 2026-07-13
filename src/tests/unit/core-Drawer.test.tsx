/**
 * src/tests/unit/core-Drawer.test.tsx
 * Covers: Drawer component
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Drawer } from '@/components/core/Drawer';

const baseProps = { open: true, onClose: vi.fn(), title: 'Settings', children: <p>Content</p> };

describe('Drawer', () => {
  it('renders children when open', () => {
    render(<Drawer {...baseProps} />);
    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  it('renders title', () => {
    render(<Drawer {...baseProps} />);
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('has role=complementary', () => {
    render(<Drawer {...baseProps} />);
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });

  it('close button calls onClose', async () => {
    const onClose = vi.fn();
    render(<Drawer {...baseProps} onClose={onClose} />);
    await userEvent.click(screen.getByLabelText('Close drawer'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('backdrop click calls onClose', async () => {
    const onClose = vi.fn();
    const { container } = render(<Drawer {...baseProps} onClose={onClose} />);
    // backdrop is aria-hidden div before the drawer
    const backdrop = container.querySelector('[aria-hidden="true"]');
    expect(backdrop).not.toBeNull();
    await userEvent.click(backdrop!);
    expect(onClose).toHaveBeenCalled();
  });

  it('Escape key calls onClose', () => {
    const onClose = vi.fn();
    render(<Drawer {...baseProps} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('does not render backdrop when closed', () => {
    const { container } = render(<Drawer {...baseProps} open={false} />);
    expect(container.querySelector('[aria-hidden="true"]')).toBeNull();
  });

  it('side prop applies to class name', () => {
    render(<Drawer {...baseProps} side="left" />);
    expect(screen.getByRole('complementary').className).toMatch(/left/);
  });
});
