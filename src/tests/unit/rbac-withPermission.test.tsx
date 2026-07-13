/**
 * src/tests/unit/rbac-withPermission.test.tsx
 *
 * Covers: src/lib/rbac/withPermission.tsx
 * — Renders children when the user has the required permission
 * — Renders fallback when the user lacks the permission
 * — Renders null when fallback is omitted and permission is missing
 * — Works for both admin and developer roles
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { withPermission } from '@/lib/rbac/withPermission';
import { Permission } from '@/lib/rbac/permissions';

// Mock usePermissions so tests control the session without a provider
const mockCan = vi.fn();
vi.mock('@/lib/rbac/hooks', () => ({
  usePermissions: () => ({ can: mockCan }),
}));

const ProtectedButton = withPermission(
  () => <button>Secret Action</button>,
  Permission.RUNS_DELETE,
);

const FallbackMessage = () => <span>Not allowed</span>;

const ProtectedWithFallback = withPermission(
  () => <button>Admin Only</button>,
  Permission.USERS_EDIT_ROLE,
  <FallbackMessage />,
);

describe('withPermission HOC', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders children when can() returns true', () => {
    mockCan.mockReturnValue(true);
    render(<ProtectedButton />);
    expect(screen.getByText('Secret Action')).toBeInTheDocument();
  });

  it('renders nothing when can() returns false and no fallback', () => {
    mockCan.mockReturnValue(false);
    const { container } = render(<ProtectedButton />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText('Secret Action')).toBeNull();
  });

  it('renders fallback when can() returns false and fallback provided', () => {
    mockCan.mockReturnValue(false);
    render(<ProtectedWithFallback />);
    expect(screen.getByText('Not allowed')).toBeInTheDocument();
    expect(screen.queryByText('Admin Only')).toBeNull();
  });

  it('hides fallback when can() returns true', () => {
    mockCan.mockReturnValue(true);
    render(<ProtectedWithFallback />);
    expect(screen.getByText('Admin Only')).toBeInTheDocument();
    expect(screen.queryByText('Not allowed')).toBeNull();
  });

  it('passes the correct permission key to can()', () => {
    mockCan.mockReturnValue(true);
    render(<ProtectedButton />);
    expect(mockCan).toHaveBeenCalledWith(Permission.RUNS_DELETE);
  });

  it('passes correct permission key for fallback variant', () => {
    mockCan.mockReturnValue(false);
    render(<ProtectedWithFallback />);
    expect(mockCan).toHaveBeenCalledWith(Permission.USERS_EDIT_ROLE);
  });
});
