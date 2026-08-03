'use client';

/**
 * src/features/trajectory-memory/hooks.ts
 *
 * TanStack Query hooks for the Slice F trajectory memory widget.
 */
import { useQuery } from '@tanstack/react-query';
import { QUERY_KEYS } from '@/lib/query/query-keys';
import {
  fetchTrajectory,
  listTrajectories,
  searchTrajectories,
  type ListArgs,
} from './api';
import type { TrajectorySearchRequest } from '@/lib/schemas/trajectory';

const STALE_MS = 30_000;

export function useTrajectoryList(args: ListArgs = {}, enabled = true) {
  return useQuery({
    queryKey: QUERY_KEYS.trajectories.list(args as Record<string, unknown>),
    queryFn: () => listTrajectories(args),
    enabled,
    staleTime: STALE_MS,
  });
}

export function useTrajectoryDetail(
  trajectoryId: string | undefined,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.trajectories.detail(trajectoryId ?? ''),
    queryFn: () => fetchTrajectory(trajectoryId!),
    enabled: enabled && Boolean(trajectoryId),
    staleTime: STALE_MS,
  });
}

/**
 * Proactive search hook for the Overview widget. The query is disabled
 * until a non-empty task_description is provided, so mounting the panel
 * for a run without a taskPrompt is safe (no wasted network).
 */
export function useTrajectorySearch(
  req: TrajectorySearchRequest | undefined,
  enabled = true,
) {
  const active =
    enabled && Boolean(req?.task_description?.trim());
  return useQuery({
    queryKey: QUERY_KEYS.trajectories.search(
      (req as unknown as Record<string, unknown>) ?? {},
    ),
    queryFn: () => searchTrajectories(req!),
    enabled: active,
    staleTime: STALE_MS,
  });
}
