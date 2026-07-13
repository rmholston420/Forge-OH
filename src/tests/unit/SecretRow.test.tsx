import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('./hooks', () => ({
  useRotateSecret: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteSecret: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/components/auth/CanDo', () => ({ CanDo: ({ children }: any) => <>{children}</> }));
vi.mock('./store', () => ({ useSecretsStore: () => ({ setConfirmDeleteId: vi.fn() }) }));
vi.mock('@/lib/utils/format', () => ({ formatDate: () => '2 hours ago' }));

import { SecretRow } from '@/features/secrets/SecretRow';

const MOCK: import('@/features/secrets/schemas').Secret = {
  id: 'sec-1', key: 'OPENAI_API_KEY', scope: 'global',
  maskedValue: '****1234', createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(), createdBy: 'admin', tags: [],
};

describe('SecretRow', () => {
  it('renders key in monospace code element', () => {
    render(<table><tbody><SecretRow secret={MOCK} /></tbody></table>);
    expect(screen.getByTestId('secret-key').querySelector('code')).toHaveTextContent('OPENAI_API_KEY');
  });

  it('renders scope badge', () => {
    render(<table><tbody><SecretRow secret={MOCK} /></tbody></table>);
    expect(screen.getByText('global')).toBeInTheDocument();
  });

  it('hides raw value', () => {
    render(<table><tbody><SecretRow secret={MOCK} /></tbody></table>);
    expect(screen.queryByText('sk-')).not.toBeInTheDocument();
  });

  it('renders Rotate and Delete buttons', () => {
    render(<table><tbody><SecretRow secret={MOCK} /></tbody></table>);
    expect(screen.getByRole('button', { name: /rotate/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });
});
