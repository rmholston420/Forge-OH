/**
 * src/tests/unit/domain-StreamBanner.test.tsx
 */
import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StreamBanner } from '@/components/domain/StreamBanner';

describe('StreamBanner', () => {
  it('renders null when state=connected', () => {
    const { container } = render(<StreamBanner state="connected" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders role=status when disconnected', () => {
    render(<StreamBanner state="disconnected" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders role=status when reconnecting', () => {
    render(<StreamBanner state="reconnecting" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has aria-live=polite', () => {
    render(<StreamBanner state="disconnected" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });

  it('disconnected shows disconnected message', () => {
    render(<StreamBanner state="disconnected" />);
    expect(screen.getByText(/disconnected from run stream/i)).toBeInTheDocument();
  });

  it('reconnecting shows reconnecting message', () => {
    render(<StreamBanner state="reconnecting" />);
    expect(screen.getByText(/reconnecting/i)).toBeInTheDocument();
  });

  it('reconnecting renders pulse element', () => {
    const { container } = render(<StreamBanner state="reconnecting" />);
    expect(container.querySelector('[class*="pulse"]')).not.toBeNull();
  });
});
