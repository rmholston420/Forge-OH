import { useQuery } from '@tanstack/react-query';
import * as api from './api';
import type { Period } from './schemas';

const STALE = 5 * 60 * 1000; // 5 min

export const useMetricsSummary     = (p: Period) => useQuery({ queryKey: ['metrics','summary',p],     queryFn: () => api.fetchMetricsSummary(p),     staleTime: STALE });
export const useDailyMetrics       = (p: Period) => useQuery({ queryKey: ['metrics','daily',p],       queryFn: () => api.fetchDailyMetrics(p),       staleTime: STALE });
export const useModelBreakdown     = (p: Period) => useQuery({ queryKey: ['metrics','models',p],      queryFn: () => api.fetchModelBreakdown(p),     staleTime: STALE });
export const useWorkspaceBreakdown = (p: Period) => useQuery({ queryKey: ['metrics','workspaces',p], queryFn: () => api.fetchWorkspaceBreakdown(p), staleTime: STALE });
