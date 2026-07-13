import { render, screen, fireEvent } from '@testing-library/react';
import { SecretRow } from '@/components/domain/secret-row';
import type { SecretRef } from '@/features/secrets/schemas';
import { describe, it, expect, vi } from 'vitest';

const BASE: SecretRef = {
  id: 'secret-1',
  name: 'OPENAI_API_KEY',
  scope: 'global',
  provider: 'env',
  maskedPreview: '••••••••',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  rotatedAt: null,
  usedIn: [],
};

describe('SecretRow', () => {
  it('renders name but NEVER the raw value', () => {
    render(
      <table><tbody>
        <SecretRow secret={BASE} onRotate={vi.fn()} onDelete={vi.fn()} />
      </tbody></table>,
    );
    expect(screen.getByText('OPENAI_API_KEY')).toBeTruthy();
    // masked preview is shown
    expect(screen.getByText('••••••••')).toBeTruthy();
    // there should be no reveal/show button
    expect(screen.queryByText('Show')).toBeNull();
    expect(screen.queryByText('Reveal')).toBeNull();
  });

  it('calls onDelete when Delete is clicked', () => {
    const onDelete = vi.fn();
    render(
      <table><tbody>
        <SecretRow secret={BASE} onRotate={vi.fn()} onDelete={onDelete} />
      </tbody></table>,
    );
    fireEvent.click(screen.getByLabelText('Delete secret OPENAI_API_KEY'));
    expect(onDelete).toHaveBeenCalledWith('secret-1');
  });

  it('shows used-in run count badge when usedIn has entries', () => {
    render(
      <table><tbody>
        <SecretRow secret={{ ...BASE, usedIn: ['run-1', 'run-2'] }} onRotate={vi.fn()} onDelete={vi.fn()} />
      </tbody></table>,
    );
    expect(screen.getByText('2 runs')).toBeTruthy();
  });
});
