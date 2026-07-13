import type { Period } from './schemas';

const BASE = process.env.NEXT_PUBLIC_BFF_URL ?? 'http://localhost:8000';
const qs = (period: Period) => `?period=${period}`;

export const fetchMetricsSummary    = (p: Period) => fetch(`${BASE}/metrics/summary${qs(p)}`).then(r => r.json());
export const fetchDailyMetrics      = (p: Period) => fetch(`${BASE}/metrics/daily${qs(p)}`).then(r => r.json());
export const fetchModelBreakdown    = (p: Period) => fetch(`${BASE}/metrics/models${qs(p)}`).then(r => r.json());
export const fetchWorkspaceBreakdown = (p: Period) => fetch(`${BASE}/metrics/workspaces${qs(p)}`).then(r => r.json());
