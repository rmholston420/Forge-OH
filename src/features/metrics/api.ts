import type { Period } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8081';
const qs = (period: Period) => `?period=${period}`;

export const fetchMetricsSummary    = (p: Period) => fetch(`${BASE}/api/metrics/summary${qs(p)}`).then(r => r.json());
export const fetchDailyMetrics      = (p: Period) => fetch(`${BASE}/api/metrics/daily${qs(p)}`).then(r => r.json());
export const fetchModelBreakdown    = (p: Period) => fetch(`${BASE}/api/metrics/models${qs(p)}`).then(r => r.json());
export const fetchWorkspaceBreakdown = (p: Period) => fetch(`${BASE}/api/metrics/workspaces${qs(p)}`).then(r => r.json());
