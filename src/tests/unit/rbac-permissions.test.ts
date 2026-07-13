/**
 * rbac-permissions.test.ts
 *
 * Verifies the ROLE_PERMISSIONS map in src/lib/rbac/permissions.ts.
 *
 * Why test a static data structure?
 * 1. Admin must always have every permission — a missing entry causes a silent
 *    authorisation hole that is invisible until someone tries to use the feature.
 * 2. Viewer must never gain write/delete permissions — a copy-paste error on
 *    a permission line could silently elevate a viewer to write access.
 * 3. Developer must be a strict subset of admin and a strict superset of viewer.
 * 4. No role should have duplicate permissions (wastes CPU in `can()` loops).
 */
import { describe, it, expect } from 'vitest';
import { Permission, ROLE_PERMISSIONS } from '@/lib/rbac/permissions';

const ALL_PERMISSIONS = Object.values(Permission);

describe('admin role', () => {
  it('contains every defined permission — no accidental omissions', () => {
    const adminPerms = new Set(ROLE_PERMISSIONS.admin);
    for (const perm of ALL_PERMISSIONS) {
      expect(adminPerms.has(perm), `admin is missing: ${perm}`).toBe(true);
    }
  });

  it('has no duplicate entries', () => {
    expect(ROLE_PERMISSIONS.admin.length).toBe(new Set(ROLE_PERMISSIONS.admin).size);
  });
});

describe('developer role', () => {
  it('has no duplicate entries', () => {
    expect(ROLE_PERMISSIONS.developer.length).toBe(new Set(ROLE_PERMISSIONS.developer).size);
  });

  it('is a strict subset of admin', () => {
    const adminSet = new Set(ROLE_PERMISSIONS.admin);
    for (const perm of ROLE_PERMISSIONS.developer) {
      expect(adminSet.has(perm), `developer has perm not in admin: ${perm}`).toBe(true);
    }
  });

  it('does NOT include user-management permissions (admin only)', () => {
    const devSet = new Set(ROLE_PERMISSIONS.developer);
    expect(devSet.has(Permission.USERS_READ)).toBe(false);
    expect(devSet.has(Permission.USERS_INVITE)).toBe(false);
    expect(devSet.has(Permission.USERS_EDIT_ROLE)).toBe(false);
    expect(devSet.has(Permission.USERS_REMOVE)).toBe(false);
  });

  it('does NOT include RUNS_DELETE (admin only)', () => {
    expect(new Set(ROLE_PERMISSIONS.developer).has(Permission.RUNS_DELETE)).toBe(false);
  });

  it('does NOT include WORKSPACES_DELETE (admin only)', () => {
    expect(new Set(ROLE_PERMISSIONS.developer).has(Permission.WORKSPACES_DELETE)).toBe(false);
  });

  it('CAN create runs', () => {
    expect(ROLE_PERMISSIONS.developer).toContain(Permission.RUNS_CREATE);
  });

  it('CAN configure plugins', () => {
    expect(ROLE_PERMISSIONS.developer).toContain(Permission.PLUGINS_CONFIGURE);
  });
});

describe('viewer role', () => {
  it('has no duplicate entries', () => {
    expect(ROLE_PERMISSIONS.viewer.length).toBe(new Set(ROLE_PERMISSIONS.viewer).size);
  });

  it('is a strict subset of developer', () => {
    const devSet = new Set(ROLE_PERMISSIONS.developer);
    for (const perm of ROLE_PERMISSIONS.viewer) {
      expect(devSet.has(perm), `viewer has perm not in developer: ${perm}`).toBe(true);
    }
  });

  it('only has read/ack permissions — no write, create, delete, or rotate', () => {
    const writePerms = [
      Permission.RUNS_CREATE, Permission.RUNS_CONTROL, Permission.RUNS_APPROVE,
      Permission.RUNS_FORK, Permission.RUNS_DELETE,
      Permission.WORKSPACES_CREATE, Permission.WORKSPACES_EDIT,
      Permission.WORKSPACES_RESET, Permission.WORKSPACES_DELETE,
      Permission.MCP_TOGGLE, Permission.MCP_PING,
      Permission.PLUGINS_TOGGLE, Permission.PLUGINS_CONFIGURE,
      Permission.SECRETS_CREATE, Permission.SECRETS_ROTATE, Permission.SECRETS_DELETE,
      Permission.SETTINGS_WRITE,
      Permission.USERS_READ, Permission.USERS_INVITE,
      Permission.USERS_EDIT_ROLE, Permission.USERS_REMOVE,
    ];
    const viewerSet = new Set(ROLE_PERMISSIONS.viewer);
    for (const perm of writePerms) {
      expect(viewerSet.has(perm), `viewer must not have: ${perm}`).toBe(false);
    }
  });

  it('CAN read runs', () => {
    expect(ROLE_PERMISSIONS.viewer).toContain(Permission.RUNS_READ);
  });

  it('CAN acknowledge notifications', () => {
    expect(ROLE_PERMISSIONS.viewer).toContain(Permission.NOTIFICATIONS_ACK);
  });
});

describe('role hierarchy invariant', () => {
  it('viewer ⊂ developer ⊂ admin (strict cardinality)', () => {
    expect(ROLE_PERMISSIONS.viewer.length).toBeLessThan(ROLE_PERMISSIONS.developer.length);
    expect(ROLE_PERMISSIONS.developer.length).toBeLessThan(ROLE_PERMISSIONS.admin.length);
  });

  it('admin permission count equals total permission count', () => {
    expect(ROLE_PERMISSIONS.admin.length).toBe(ALL_PERMISSIONS.length);
  });
});
