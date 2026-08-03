/**
 * src/features/trajectory-memory/api.ts
 *
 * BFF calls for Rec #3 Trajectory Memory (Slice F).
 *
 * NOTE: The trajectories router returns unwrapped JSON (no {data: ...}
 * envelope), like RepoGraph. See bff/routers/trajectories.py.
 */
import { bffGet, bffPost } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import {
  TrajectoryListResponseSchema,
  TrajectoryRecordSchema,
  TrajectorySearchResponseSchema,
  type TrajectoryListResponse,
  type TrajectoryRecord,
  type TrajectorySearchRequest,
  type TrajectorySearchResponse,
} from '@/lib/schemas/trajectory';

export interface ListArgs {
  limit?: number;
  status?: string;
  repoKey?: string;
}

export async function listTrajectories(
  args: ListArgs = {},
): Promise<TrajectoryListResponse> {
  const raw = unwrap(await bffGet<unknown>(ENDPOINTS.TRAJECTORIES.list(args)));
  return TrajectoryListResponseSchema.parse(raw);
}

export async function fetchTrajectory(
  trajectoryId: string,
): Promise<TrajectoryRecord> {
  const raw = unwrap(
    await bffGet<unknown>(ENDPOINTS.TRAJECTORIES.get(trajectoryId)),
  );
  return TrajectoryRecordSchema.parse(raw);
}

export async function searchTrajectories(
  req: TrajectorySearchRequest,
): Promise<TrajectorySearchResponse> {
  const raw = unwrap(
    await bffPost<unknown>(ENDPOINTS.TRAJECTORIES.search(), req),
  );
  return TrajectorySearchResponseSchema.parse(raw);
}
