import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

vi.mock('@/lib/auth/hooks', () => ({
  useRequireAuth: vi.fn().mockReturnValue({ status: 'authenticated', user: {
    id: '1', email: 'admin@forge.dev', name: 'Admin', role: 'admin',
  }}),
}));

import { AuthGuard } from '@/components/auth/AuthGuard';

describe('AuthGuard', () => {
  it('renders children when authenticated', () => {
    render(<AuthGuard><div>Protected content</div></AuthGuard>);
    expect(screen.getByText('Protected content')).toBeInTheDocument();
  });

  it('renders skeleton when loading', async () => {
    const { useRequireAuth } = await import('@/lib/auth/hooks');
    (useRequireAuth as any).mockReturnValueOnce({ status: 'loading', user: undefined });
    render(<AuthGuard><div>Protected content</div></AuthGuard>);
    expect(screen.getByLabelText(/checking authentication/i)).toBeInTheDocument();
  });
});
