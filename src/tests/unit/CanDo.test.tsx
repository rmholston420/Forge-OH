import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { Permission } from '@/lib/rbac/permissions';

const mockUsePermissions = vi.fn();
vi.mock('@/lib/rbac/hooks', () => ({ usePermissions: mockUsePermissions }));

import { CanDo } from '@/components/auth/CanDo';

describe('CanDo', () => {
  it('renders children when permission granted', () => {
    mockUsePermissions.mockReturnValue({ can: () => true });
    render(
      <CanDo permission={Permission.RUNS_CREATE}>
        <button>New Run</button>
      </CanDo>
    );
    expect(screen.getByRole('button', { name: 'New Run' })).toBeInTheDocument();
  });

  it('renders nothing when permission denied (no fallback)', () => {
    mockUsePermissions.mockReturnValue({ can: () => false });
    render(
      <CanDo permission={Permission.SECRETS_DELETE}>
        <button>Delete</button>
      </CanDo>
    );
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders fallback when permission denied', () => {
    mockUsePermissions.mockReturnValue({ can: () => false });
    render(
      <CanDo permission={Permission.USERS_INVITE}
             fallback={<span>No access</span>}>
        <button>Invite</button>
      </CanDo>
    );
    expect(screen.getByText('No access')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
