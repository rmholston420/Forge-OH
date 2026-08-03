const BFF = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';

export async function bffFetch(input: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers ?? {});
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }

  return fetch(`${BFF}${input}`, {
    ...init,
    headers,
  });
}
