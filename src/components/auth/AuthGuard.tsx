'use client';
import { useRequireAuth } from '@/lib/auth/hooks';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status } = useRequireAuth();

  if (status === 'loading') {
    return (
      <div className="auth-guard-skeleton" aria-busy="true"
           aria-label="Checking authentication">
        <div className="skeleton" style={{ width: 200, height: 32 }} />
        <div className="skeleton" style={{ width: '100%', height: 400, marginTop: 16 }} />
      </div>
    );
  }

  if (status === 'unauthenticated') return null; // router.replace fires in hook

  return <>{children}</>;
}
