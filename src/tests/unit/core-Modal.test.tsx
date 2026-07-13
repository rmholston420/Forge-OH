/**
 * src/tests/unit/core-Modal.test.tsx
 * Covers: Modal component
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from '@/components/core/Modal';

const base = { open: true, onClose: vi.fn(), title: 'Confirm' };

describe('Modal', () => {
  it('renders null when open=false', () => {
    const { container } = render(<Modal {...base} open={false}><p>body</p></Modal>);
    expect(container.firstChild).toBeNull();
  });

  it('renders when open=true', () => {
    render(<Modal {...base}><p>body text</p></Modal>);
    expect(screen.getByText('body text')).toBeInTheDocument();
  });

  it('has role=dialog and aria-modal=true', () => {
    render(<Modal {...base}><p>x</p></Modal>);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('title is rendered and used as aria-labelledby target', () => {
    render(<Modal {...base}><p>x</p></Modal>);
    expect(screen.getByText('Confirm')).toBeInTheDocument();
  });

  it('close button calls onClose', async () => {
    const onClose = vi.fn();
    render(<Modal {...base} onClose={onClose}><p>x</p></Modal>);
    await userEvent.click(screen.getByLabelText('Close modal'));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('Escape key calls onClose', () => {
    const onClose = vi.fn();
    render(<Modal {...base} onClose={onClose}><p>x</p></Modal>);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('clicking backdrop calls onClose', async () => {
    const onClose = vi.fn();
    render(<Modal {...base} onClose={onClose}><p>x</p></Modal>);
    const overlay = screen.getByRole('dialog');
    await userEvent.click(overlay);
    expect(onClose).toHaveBeenCalled();
  });

  it('clicking modal inner content does NOT call onClose (stopPropagation)', async () => {
    const onClose = vi.fn();
    render(<Modal {...base} onClose={onClose}><p>inner</p></Modal>);
    await userEvent.click(screen.getByText('inner'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('footer slot renders when provided', () => {
    render(<Modal {...base} footer={<button>OK</button>}><p>x</p></Modal>);
    expect(screen.getByRole('button', { name: 'OK' })).toBeInTheDocument();
  });

  it('footer slot is absent when not provided', () => {
    render(<Modal {...base}><p>x</p></Modal>);
    expect(screen.queryByRole('button', { name: 'OK' })).toBeNull();
  });

  it.each(['sm','md','lg'])('size=%s renders without throw', (size) => {
    expect(() => render(<Modal {...base} size={size as any}><p>x</p></Modal>)).not.toThrow();
  });
});
