import type { Role } from '@/lib/schemas/auth';

export const Permission = {
  RUNS_READ: 'runs:read',
  RUNS_CREATE: 'runs:create',
  RUNS_CONTROL: 'runs:control',
  RUNS_APPROVE: 'runs:approve',
  RUNS_FORK: 'runs:fork',
  RUNS_DELETE: 'runs:delete',

  WORKSPACES_READ: 'workspaces:read',
  WORKSPACES_CREATE: 'workspaces:create',
  WORKSPACES_EDIT: 'workspaces:edit',
  WORKSPACES_RESET: 'workspaces:reset',
  WORKSPACES_DELETE: 'workspaces:delete',

  MCP_READ: 'mcp:read',
  MCP_TOGGLE: 'mcp:toggle',
  MCP_PING: 'mcp:ping',
  PLUGINS_READ: 'plugins:read',
  PLUGINS_TOGGLE: 'plugins:toggle',
  PLUGINS_CONFIGURE: 'plugins:configure',

  SECRETS_READ: 'secrets:read',
  SECRETS_WRITE: 'secrets:write',
  SECRETS_CREATE: 'secrets:create',
  SECRETS_ROTATE: 'secrets:rotate',
  SECRETS_DELETE: 'secrets:delete',

  SETTINGS_READ: 'settings:read',
  SETTINGS_WRITE: 'settings:write',

  NOTIFICATIONS_READ: 'notifications:read',
  NOTIFICATIONS_ACK: 'notifications:ack',

  USERS_READ: 'users:read',
  USERS_INVITE: 'users:invite',
  USERS_EDIT_ROLE: 'users:edit_role',
  USERS_REMOVE: 'users:remove',
} as const;

export type PermissionKey = typeof Permission[keyof typeof Permission];
const ALL = Object.values(Permission) as PermissionKey[];

export const ROLE_PERMISSIONS: Record<Role, PermissionKey[]> = {
  admin: ALL,
  developer: [
    Permission.RUNS_READ, Permission.RUNS_CREATE, Permission.RUNS_CONTROL,
    Permission.RUNS_APPROVE, Permission.RUNS_FORK,
    Permission.WORKSPACES_READ, Permission.WORKSPACES_CREATE,
    Permission.WORKSPACES_EDIT, Permission.WORKSPACES_RESET,
    Permission.MCP_READ, Permission.MCP_TOGGLE, Permission.MCP_PING,
    Permission.PLUGINS_READ, Permission.PLUGINS_TOGGLE, Permission.PLUGINS_CONFIGURE,
    Permission.SECRETS_READ, Permission.SECRETS_WRITE, Permission.SECRETS_CREATE, Permission.SECRETS_ROTATE,
    Permission.SETTINGS_READ, Permission.SETTINGS_WRITE,
    Permission.NOTIFICATIONS_READ, Permission.NOTIFICATIONS_ACK,
  ],
  editor: [
    Permission.RUNS_READ, Permission.RUNS_CREATE,
    Permission.WORKSPACES_READ,
    Permission.PLUGINS_READ,
    Permission.SECRETS_READ, Permission.SECRETS_WRITE,
    Permission.SETTINGS_READ,
    Permission.NOTIFICATIONS_READ, Permission.NOTIFICATIONS_ACK,
  ],
  viewer: [
    Permission.RUNS_READ,
    Permission.WORKSPACES_READ,
    Permission.MCP_READ,
    Permission.PLUGINS_READ,
    Permission.SECRETS_READ,
    Permission.SETTINGS_READ,
    Permission.NOTIFICATIONS_READ, Permission.NOTIFICATIONS_ACK,
  ],
};
