/**
 * Integration test: full auth flow via MSW handlers.
 *
 * Covers login → token issue → authenticated request → logout → 401.
 * Uses the existing MSW server infrastructure from src/tests/mocks/.
 */
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { server } from '../mocks/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

const BASE = 'http://localhost:8000/api';

async function login(email: string, password: string) {
  return fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
}

describe('Auth integration flow', () => {
  it('login with valid credentials returns 200 and a token', async () => {
    const r = await login('admin@forge.dev', 'password123');
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body).toHaveProperty('token');
    expect(body.user.role).toBe('admin');
  });

  it('login with wrong password returns 401', async () => {
    const r = await login('admin@forge.dev', 'wrong');
    expect(r.status).toBe(401);
  });

  it('GET /auth/me with valid token returns the user', async () => {
    const loginRes = await login('dev@forge.dev', 'password123');
    const { token } = await loginRes.json();
    const meRes = await fetch(`${BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(meRes.status).toBe(200);
    const user = await meRes.json();
    expect(user.email).toBe('dev@forge.dev');
  });

  it('GET /auth/me without token returns 401', async () => {
    const r = await fetch(`${BASE}/auth/me`);
    expect(r.status).toBe(401);
  });

  it('POST /auth/logout invalidates the token', async () => {
    const loginRes = await login('viewer@forge.dev', 'password123');
    const { token } = await loginRes.json();

    await fetch(`${BASE}/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });

    const meRes = await fetch(`${BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(meRes.status).toBe(401);
  });
});
