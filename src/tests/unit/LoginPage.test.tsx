import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

// Mock next-auth signIn
vi.mock('next-auth/react', () => ({
  signIn: vi.fn().mockResolvedValue({ error: null }),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

import LoginPage from '@/app/(auth)/login/page';

describe('LoginPage', () => {
  it('renders email and password fields', () => {
    render(<LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('shows validation error for invalid email', async () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'not-an-email' } });
    fireEvent.submit(screen.getByRole('form') ?? screen.getByText(/sign in/i).closest('form')!);
    await waitFor(() =>
      expect(screen.getByText(/valid email/i)).toBeInTheDocument()
    );
  });

  it('shows auth error on failed sign-in', async () => {
    const { signIn } = await import('next-auth/react');
    (signIn as any).mockResolvedValueOnce({ error: 'CredentialsSignin' });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'admin@forge.dev' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrongpass' } });
    fireEvent.submit(screen.getByLabelText(/email/i).closest('form')!);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/invalid email or password/i)
    );
  });
});
