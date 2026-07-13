import { getSession } from 'next-auth/react';

const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';

export async function bffFetch(input: string, init: RequestInit = {}) {
  const session = await getSession();
  const token = (session?.user as any)?.bffToken as string | undefined;

  const headers = new Headers(init.headers ?? {});
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(`${BFF}${input}`, {
    ...init,
    headers,
  });
}
