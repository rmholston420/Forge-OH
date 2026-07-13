/**
 * src/tests/unit/core-Button.test.tsx
 * Covers: Button component
 */
import React, { createRef } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/core/Button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('fires onClick when clicked', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Button disabled>No</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('loading=true sets aria-busy and disabled', () => {
    render(<Button loading>Saving...</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
  });

  it('loading=true does not fire onClick', async () => {
    const onClick = vi.fn();
    render(<Button loading onClick={onClick}>Saving</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it.each(['primary','secondary','tertiary','destructive'])('variant=%s renders without throw', (variant) => {
    expect(() => render(<Button variant={variant as any}>x</Button>)).not.toThrow();
  });

  it.each(['sm','md','lg'])('size=%s renders without throw', (size) => {
    expect(() => render(<Button size={size as any}>x</Button>)).not.toThrow();
  });

  it('forwards ref to the button element', () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Ref</Button>);
    expect(ref.current).toBeInstanceOf(HTMLButtonElement);
  });

  it('passes through HTML button attributes', () => {
    render(<Button type="submit" form="my-form">Submit</Button>);
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('type', 'submit');
    expect(btn).toHaveAttribute('form', 'my-form');
  });
});
