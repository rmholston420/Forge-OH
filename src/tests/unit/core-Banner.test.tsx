/**
 * src/tests/unit/core-Banner.test.tsx
 * Covers: Banner component
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Banner } from '@/components/core/Banner';

describe('Banner', () => {
  it('renders children', () => {
    render(<Banner>Your run completed</Banner>);
    expect(screen.getByText('Your run completed')).toBeInTheDocument();
  });

  it('has role=alert', () => {
    render(<Banner>msg</Banner>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('renders title when provided', () => {
    render(<Banner title="Heads up">detail</Banner>);
    expect(screen.getByText('Heads up')).toBeInTheDocument();
  });

  it('does not render title element when omitted', () => {
    render(<Banner>detail</Banner>);
    expect(screen.queryByText('Heads up')).toBeNull();
  });

  it('renders dismiss button when onDismiss is provided', () => {
    render(<Banner onDismiss={() => {}}>msg</Banner>);
    expect(screen.getByLabelText('Dismiss banner')).toBeInTheDocument();
  });

  it('does not render dismiss button when onDismiss is omitted', () => {
    render(<Banner>msg</Banner>);
    expect(screen.queryByLabelText('Dismiss banner')).toBeNull();
  });

  it('calls onDismiss when dismiss button is clicked', async () => {
    const onDismiss = vi.fn();
    render(<Banner onDismiss={onDismiss}>msg</Banner>);
    await userEvent.click(screen.getByLabelText('Dismiss banner'));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it.each(['info','success','warning','error'])('variant=%s renders without throw', (variant) => {
    expect(() => render(<Banner variant={variant as any}>x</Banner>)).not.toThrow();
  });

  it('applies variant class to container', () => {
    const { container } = render(<Banner variant="error">msg</Banner>);
    expect(container.firstChild).toBeDefined();
    expect((container.firstChild as HTMLElement).className).toMatch(/error/);
  });
});
