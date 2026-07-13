'use client';
import { useMemo } from 'react';
import { useSession } from '@/lib/auth/hooks';
import { ROLE_PERMISSIONS, Permission } from './permissions';
import type { PermissionKey } from './permissions';
import type { Role } from '@/lib/schemas/auth';

export function usePermissions() {
  const { user } = useSession();

  const permissions = useMemo(() => {
    if (!user?.role) return new Set<PermissionKey>();
    return new Set(ROLE_PERMISSIONS[user.role as Role] ?? []);
  }, [user?.role]);

  return {
    can: (p: PermissionKey): boolean => permissions.has(p),
    hasRole: (role: Role): boolean => user?.role === role,
    role: user?.role as Role | undefined,
    permissions,
  };
}
