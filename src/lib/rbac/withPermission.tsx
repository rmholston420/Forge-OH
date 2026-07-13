'use client';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { usePermissions } from './hooks';
import type { PermissionKey } from './permissions';
import type { Route } from 'next';

/**
 * HOC that redirects to `redirectTo` if user lacks `permission`.
 * Use on page-level components to guard entire routes.
 */
export function withPermission<P extends object>(
  Component: React.ComponentType<P>,
  permission: PermissionKey,
  redirectTo = '/runs',
) {
  return function PermissionGuarded(props: P) {
    const { can } = usePermissions();
    const router  = useRouter();

    useEffect(() => {
      if (!can(permission)) router.replace(redirectTo as Route);
    }, [can, router]);

    if (!can(permission)) return null;
    return <Component {...props} />;
  };
}
