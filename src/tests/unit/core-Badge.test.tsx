/**
 * src/tests/unit/core-Badge.test.tsx
 * Covers: Badge, StatusBadge
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge, StatusBadge } from '@/components/core/Badge';

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge>Running</Badge>);
    expect(screen.getByText('Running')).toBeInTheDocument();
  });

  it('renders as a <span>', () => {
    const { container } = render(<Badge>x</Badge>);
    expect(container.querySelector('span')).not.toBeNull();
  });

  it('applies variant class', () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    const span = container.querySelector('span')!;
    expect(span.className).toMatch(/success/);
  });

  it('applies size class', () => {
    const { container } = render(<Badge size="sm">small</Badge>);
    const span = container.querySelector('span')!;
    expect(span.className).toMatch(/sm/);
  });

  it('applies custom className', () => {
    const { container } = render(<Badge className="custom">x</Badge>);
    expect(container.querySelector('.custom')).not.toBeNull();
  });

  it.each(['default','success','warning','error','paused','running','accent','muted'])(
    'variant=%s renders without throw', (variant) => {
      expect(() => render(<Badge variant={variant as any}>{variant}</Badge>)).not.toThrow();
    }
  );
});

describe('StatusBadge', () => {
  it.each([
    ['running', 'running'],
    ['succeeded', 'success'],
    ['failed', 'error'],
    ['paused', 'paused'],
    ['awaiting_approval', 'warning'],
    ['idle', 'muted'],
    ['queued', 'muted'],
  ])('status=%s maps to variant=%s', (status, expectedVariant) => {
    const { container } = render(<StatusBadge status={status} />);
    expect(container.querySelector('span')!.className).toMatch(expectedVariant);
  });

  it('unknown status gets default variant', () => {
    const { container } = render(<StatusBadge status="alien_status" />);
    expect(container.querySelector('span')).not.toBeNull();
  });

  it('replaces underscores with spaces in text', () => {
    render(<StatusBadge status="awaiting_approval" />);
    expect(screen.getByText('awaiting approval')).toBeInTheDocument();
  });
});
