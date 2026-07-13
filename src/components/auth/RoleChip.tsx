'use client';
import type { Role } from '@/lib/schemas/auth';

const ROLE_STYLES: Record<Role, string> = {
  admin:     'role-chip role-chip--admin',
  developer: 'role-chip role-chip--developer',
  editor: 'Editor', viewer:    'role-chip role-chip--viewer',
};

const ROLE_LABELS: Record<Role, string> = {
  admin:     'Admin',
  developer: 'Developer',
  editor: 'Editor', viewer:    'Viewer',
};

export function RoleChip({ role }: { role: Role }) {
  return (
    <span className={ROLE_STYLES[role]} aria-label={`Role: ${ROLE_LABELS[role]}`}>
      {ROLE_LABELS[role]}
    </span>
  );
}
