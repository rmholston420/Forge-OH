'use client';
import { usePermissions } from '@/lib/rbac/hooks';
import type { PermissionKey } from '@/lib/rbac/permissions';

interface Props {
  permission:  PermissionKey;
  fallback?:   React.ReactNode;
  children:    React.ReactNode;
}

/**
 * Declarative permission gate.
 * Renders `children` when the current user has `permission`.
 * Renders `fallback` (default: null) otherwise.
 *
 * @example
 * <CanDo permission="runs:create">
 *   <button>New Run</button>
 * </CanDo>
 */
export function CanDo({ permission, fallback = null, children }: Props) {
  const { can } = usePermissions();
  return can(permission) ? <>{children}</> : <>{fallback}</>;
}
