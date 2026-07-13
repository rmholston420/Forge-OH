/**
 * src/tests/unit/core-EmptyState.test.tsx
 * Covers: EmptyState component
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState } from '@/components/core/EmptyState';

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="No runs yet" />);
    expect(screen.getByText('No runs yet')).toBeInTheDocument();
  });

  it('has role=status', () => {
    render(<EmptyState title="Empty" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(<EmptyState title="Empty" description="Create your first run" />);
    expect(screen.getByText('Create your first run')).toBeInTheDocument();
  });

  it('does not render description when omitted', () => {
    render(<EmptyState title="Empty" />);
    expect(screen.queryByText('Create your first run')).toBeNull();
  });

  it('renders action when provided', () => {
    render(<EmptyState title="Empty" action={<button>New Run</button>} />);
    expect(screen.getByRole('button', { name: 'New Run' })).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(<EmptyState title="Empty" icon={<svg data-testid="icon" />} />);
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('does not render icon slot when icon omitted', () => {
    const { container } = render(<EmptyState title="Empty" />);
    // icon wrapper div should not be present
    expect(container.querySelectorAll('svg')).toHaveLength(0);
  });
});
