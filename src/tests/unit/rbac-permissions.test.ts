/**
 * src/tests/unit/rbac-permissions.test.ts
 *
 * Covers: src/lib/rbac/permissions.ts
 * — ROLE_PERMISSIONS completeness for all three roles
 * — admin has every permission
 * — viewer lacks all write/control permissions
 * — developer lacks admin-only users:* permissions
 * — Permission object has no duplicate values
 */
import { describe, it, expect } from 'vitest';
import { ROLE_PERMISSIONS, Permission } from '@/lib/rbac/permissions';
import type { PermissionKey } from '@/lib/rbac/permissions';

const ALL_PERMS = Object.values(Permission) as PermissionKey[];

describe('Permission registry', () => {
  it('has no duplicate values', () => {
    const vals = Object.values(Permission);
    expect(new Set(vals).size).toBe(vals.length);
  });

  it('every value follows domain:action format', () => {
    for (const p of Object.values(Permission)) {
      expect(p).toMatch(/^[a-z_]+:[a-z_]+$/);
    }
  });
});

describe('admin role', () => {
  const adminPerms = new Set(ROLE_PERMISSIONS.admin);

  it('has every permission', () => {
    for (const p of ALL_PERMS) {
      expect(adminPerms.has(p), `admin missing: ${p}`).toBe(true);
    }
  });

  it('has users:edit_role', () => {
    expect(adminPerms.has(Permission.USERS_EDIT_ROLE)).toBe(true);
  });

  it('has runs:delete', () => {
    expect(adminPerms.has(Permission.RUNS_DELETE)).toBe(true);
  });
});

describe('developer role', () => {
  const devPerms = new Set(ROLE_PERMISSIONS.developer);

  it('can read, create, and control runs', () => {
    expect(devPerms.has(Permission.RUNS_READ)).toBe(true);
    expect(devPerms.has(Permission.RUNS_CREATE)).toBe(true);
    expect(devPerms.has(Permission.RUNS_CONTROL)).toBe(true);
  });

  it('cannot manage users (admin-only)', () => {
    expect(devPerms.has(Permission.USERS_READ)).toBe(false);
    expect(devPerms.has(Permission.USERS_INVITE)).toBe(false);
    expect(devPerms.has(Permission.USERS_EDIT_ROLE)).toBe(false);
    expect(devPerms.has(Permission.USERS_REMOVE)).toBe(false);
  });

  it('cannot delete runs', () => {
    expect(devPerms.has(Permission.RUNS_DELETE)).toBe(false);
  });

  it('can read and write settings', () => {
    expect(devPerms.has(Permission.SETTINGS_READ)).toBe(true);
    expect(devPerms.has(Permission.SETTINGS_WRITE)).toBe(true);
  });

  it('can manage secrets (create, rotate)', () => {
    expect(devPerms.has(Permission.SECRETS_CREATE)).toBe(true);
    expect(devPerms.has(Permission.SECRETS_ROTATE)).toBe(true);
  });
});

describe('viewer role', () => {
  const viewerPerms = new Set(ROLE_PERMISSIONS.viewer);

  it('can read runs', () => {
    expect(viewerPerms.has(Permission.RUNS_READ)).toBe(true);
  });

  it('cannot create or control runs', () => {
    expect(viewerPerms.has(Permission.RUNS_CREATE)).toBe(false);
    expect(viewerPerms.has(Permission.RUNS_CONTROL)).toBe(false);
    expect(viewerPerms.has(Permission.RUNS_APPROVE)).toBe(false);
    expect(viewerPerms.has(Permission.RUNS_FORK)).toBe(false);
  });

  it('cannot write settings', () => {
    expect(viewerPerms.has(Permission.SETTINGS_WRITE)).toBe(false);
  });

  it('cannot create secrets', () => {
    expect(viewerPerms.has(Permission.SECRETS_CREATE)).toBe(false);
    expect(viewerPerms.has(Permission.SECRETS_ROTATE)).toBe(false);
    expect(viewerPerms.has(Permission.SECRETS_DELETE)).toBe(false);
  });

  it('cannot manage users', () => {
    expect(viewerPerms.has(Permission.USERS_READ)).toBe(false);
    expect(viewerPerms.has(Permission.USERS_INVITE)).toBe(false);
  });

  it('can read but NOT toggle MCP', () => {
    expect(viewerPerms.has(Permission.MCP_READ)).toBe(true);
    expect(viewerPerms.has(Permission.MCP_TOGGLE)).toBe(false);
  });

  it('is a strict subset of developer permissions', () => {
    const devPerms = new Set(ROLE_PERMISSIONS.developer);
    for (const p of viewerPerms) {
      expect(devPerms.has(p), `developer missing viewer perm: ${p}`).toBe(true);
    }
  });
});

describe('ROLE_PERMISSIONS — all three roles are defined', () => {
  it('has admin, developer, viewer keys', () => {
    expect(ROLE_PERMISSIONS).toHaveProperty('admin');
    expect(ROLE_PERMISSIONS).toHaveProperty('developer');
    expect(ROLE_PERMISSIONS).toHaveProperty('viewer');
  });

  it('all entries are non-empty arrays', () => {
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      expect(Array.isArray(perms)).toBe(true);
      expect(perms.length).toBeGreaterThan(0);
    }
  });
});
