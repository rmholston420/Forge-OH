import { renderHook } from '@testing-library/react';
import { vi } from 'vitest';
import { Permission } from '@/lib/rbac/permissions';

const mockUseSession = vi.fn();
vi.mock('@/lib/auth/hooks', () => ({ useSession: mockUseSession }));

import { usePermissions } from '@/lib/rbac/hooks';

describe('usePermissions', () => {
  it('admin has all permissions', () => {
    mockUseSession.mockReturnValue({ user: { role: 'admin' } });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can(Permission.SECRETS_DELETE)).toBe(true);
    expect(result.current.can(Permission.USERS_REMOVE)).toBe(true);
    expect(result.current.can(Permission.RUNS_APPROVE)).toBe(true);
  });

  it('viewer cannot create runs or delete secrets', () => {
    mockUseSession.mockReturnValue({ user: { role: 'viewer' } });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can(Permission.RUNS_CREATE)).toBe(false);
    expect(result.current.can(Permission.SECRETS_DELETE)).toBe(false);
    expect(result.current.can(Permission.RUNS_READ)).toBe(true);
  });

  it('developer can create runs but not manage users', () => {
    mockUseSession.mockReturnValue({ user: { role: 'developer' } });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.can(Permission.RUNS_CREATE)).toBe(true);
    expect(result.current.can(Permission.USERS_INVITE)).toBe(false);
  });

  it('returns empty set when no user', () => {
    mockUseSession.mockReturnValue({ user: undefined });
    const { result } = renderHook(() => usePermissions());
    expect(result.current.permissions.size).toBe(0);
  });
});
