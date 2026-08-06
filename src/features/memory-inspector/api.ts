import { RecentWritesResponseSchema, type MemoryWriteRecord } from './schemas';

const BASE = (process.env.NEXT_PUBLIC_BFF_URL ?? '') + '/api';

export async function fetchRecentWrites(limit = 50): Promise<MemoryWriteRecord[]> {
  const res = await fetch(`${BASE}/memory/recent-writes?limit=${limit}`);
  if (res.status === 503) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body?.detail ?? 'Memory service unavailable');
    (err as Error & { code?: string }).code = 'MEMORY_UNAVAILABLE';
    throw err;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch memory writes (${res.status})`);
  }
  const parsed = RecentWritesResponseSchema.parse(await res.json());
  return parsed.data;
}
