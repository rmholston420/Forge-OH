/**
 * src/tests/unit/core-Input.test.tsx
 * Covers: Input component
 */
import React, { createRef } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/core/Input';

describe('Input', () => {
  it('renders an input element', () => {
    render(<Input />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('label renders and is associated via htmlFor', () => {
    render(<Input label="API Key" />);
    const label = screen.getByText('API Key');
    const input = screen.getByRole('textbox');
    expect(label.getAttribute('for')).toBe(input.id);
  });

  it('error message is shown with role=alert', () => {
    render(<Input label="Key" error="This field is required" />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('This field is required');
  });

  it('aria-invalid is set when error is present', () => {
    render(<Input label="Key" error="bad" />);
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true');
  });

  it('aria-invalid is absent when no error', () => {
    render(<Input label="Key" />);
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'false');
  });

  it('hint renders when no error', () => {
    render(<Input label="Key" hint="Must be 32 chars" />);
    expect(screen.getByText('Must be 32 chars')).toBeInTheDocument();
  });

  it('hint is hidden when error is present', () => {
    render(<Input label="Key" hint="hint text" error="error text" />);
    expect(screen.queryByText('hint text')).toBeNull();
    expect(screen.getByText('error text')).toBeInTheDocument();
  });

  it('variant=secret renders type=password', () => {
    render(<Input variant="secret" label="Secret" />);
    // password input is not role=textbox
    expect(screen.queryByRole('textbox')).toBeNull();
    const input = document.querySelector('input[type="password"]');
    expect(input).not.toBeNull();
  });

  it('accepts user input', async () => {
    render(<Input label="Name" />);
    const input = screen.getByRole('textbox');
    await userEvent.type(input, 'forge');
    expect((input as HTMLInputElement).value).toBe('forge');
  });

  it('forwards ref to the input element', () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input ref={ref} label="Ref" />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });
});
