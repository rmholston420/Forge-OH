'use client';
import { useSession as useNextSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import type { SessionUser } from '@/lib/schemas/auth';

export function useSession() {
  const session = useNextSession();
  const user = session.data?.user as SessionUser | undefined;
  return { ...session, user };
}

export function useRequireAuth() {
  const { status, user } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (status === 'unauthenticated') router.replace('/login');
  }, [status, router]);
  return { status, user };
}

export function useSignOut() {
  const router = useRouter();
  return async () => {
    await signOut({ redirect: false });
    router.replace('/login');
  };
}
