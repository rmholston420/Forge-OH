import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SecretRow } from '@/components/domain/SecretRow';

const secret = {
  id: 'sec-1', name: 'OPENAI_API_KEY',
  scope: 'global' as const, scopeId: null,
  description: 'OpenAI key', masked: true as const,
  lastRotatedAt: null,
  createdAt: '2026-07-12T00:00:00Z', updatedAt: '2026-07-12T00:00:00Z',
};

describe('SecretRow', () => {
  it('renders secret name', () => {
    render(<table><tbody><SecretRow secret={secret} /></tbody></table>);
    expect(screen.getByText('OPENAI_API_KEY')).toBeTruthy();
  });

  it('never renders a visible value', () => {
    render(<table><tbody><SecretRow secret={secret} /></tbody></table>);
    // Should show masked dots, not any real value
    expect(screen.queryByText(/sk-/)).toBeNull();
  });

  it('shows confirm UI on delete click', () => {
    render(<table><tbody><SecretRow secret={secret} /></tbody></table>);
    const deleteBtn = screen.getByRole('button', { name: /Delete/ });
    fireEvent.click(deleteBtn);
    expect(screen.getByRole('button', { name: /Confirm/ })).toBeTruthy();
  });
});
