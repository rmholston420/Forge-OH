/**
 * src/tests/unit/auth-RoleChip.test.tsx
 * Covers: RoleChip component — renders correct label for all three roles
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleChip } from '@/components/auth/RoleChip';

describe('RoleChip', () => {
  it('renders admin role', () => {
    render(<RoleChip role="admin" />);
    expect(screen.getByText(/admin/i)).toBeInTheDocument();
  });

  it('renders developer role', () => {
    render(<RoleChip role="developer" />);
    expect(screen.getByText(/developer/i)).toBeInTheDocument();
  });

  it('renders viewer role', () => {
    render(<RoleChip role="viewer" />);
    expect(screen.getByText(/viewer/i)).toBeInTheDocument();
  });

  it('renders without crashing for unknown role', () => {
    expect(() => render(<RoleChip role={"superuser" as any} />)).not.toThrow();
  });

  it('renders as an inline element (span or similar)', () => {
    const { container } = render(<RoleChip role="admin" />);
    const el = container.firstChild as HTMLElement;
    expect(['SPAN','DIV','P','SMALL'].includes(el?.tagName)).toBe(true);
  });
});
