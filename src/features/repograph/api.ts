/**
 * src/features/repograph/api.ts
 *
 * BFF calls for the RepoGraph feature (Slice D).
 *
 * NOTE: RepoGraph endpoints return unwrapped JSON (no {data: ...} envelope),
 * unlike observability/runs/etc. This is intentional \u2014 the router is
 * plain-typed with Pydantic response models.
 */
import { bffGet, bffPost } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';
import type {
  RepoGraphCallee,
  RepoGraphCaller,
  RepoGraphCoChangedResponse,
  RepoGraphHealth,
  RepoGraphIndexResponse,
  RepoGraphSymbol,
} from '@/lib/schemas/repograph';

export async function fetchRepoGraphHealth(): Promise<RepoGraphHealth> {
  return unwrap(await bffGet<RepoGraphHealth>(ENDPOINTS.REPOGRAPH.health()));
}

export interface IndexArgs {
  workspacePath: string;
  computePagerank?: boolean;
}

export async function indexWorkspace(
  args: IndexArgs,
): Promise<RepoGraphIndexResponse> {
  return unwrap(
    await bffPost<RepoGraphIndexResponse>(ENDPOINTS.REPOGRAPH.index(), {
      workspace_path: args.workspacePath,
      compute_pagerank: args.computePagerank ?? true,
    }),
  );
}

export async function searchSymbols(
  repoKey: string,
  q: string,
  limit = 20,
): Promise<RepoGraphSymbol[]> {
  return unwrap(
    await bffGet<RepoGraphSymbol[]>(
      ENDPOINTS.REPOGRAPH.search(repoKey, q, limit),
    ),
  );
}

export async function fetchCallers(
  repoKey: string,
  name: string,
  relPath?: string,
  limit = 20,
): Promise<RepoGraphCaller[]> {
  return unwrap(
    await bffGet<RepoGraphCaller[]>(
      ENDPOINTS.REPOGRAPH.callers(repoKey, name, relPath, limit),
    ),
  );
}

export async function fetchCallees(
  repoKey: string,
  relPath: string,
  limit = 20,
): Promise<RepoGraphCallee[]> {
  return unwrap(
    await bffGet<RepoGraphCallee[]>(
      ENDPOINTS.REPOGRAPH.callees(repoKey, relPath, limit),
    ),
  );
}

export async function fetchCoChanged(
  repoKey: string,
  relPath: string,
  window = 50,
  limit = 10,
): Promise<RepoGraphCoChangedResponse> {
  return unwrap(
    await bffGet<RepoGraphCoChangedResponse>(
      ENDPOINTS.REPOGRAPH.coChanged(repoKey, relPath, window, limit),
    ),
  );
}

export interface ContextBundleArgs {
  repoKey: string;
  seeds: string[];
  limit?: number;
}

export async function fetchContextBundle(
  args: ContextBundleArgs,
): Promise<RepoGraphSymbol[]> {
  return unwrap(
    await bffPost<RepoGraphSymbol[]>(ENDPOINTS.REPOGRAPH.contextBundle(), {
      repo_key: args.repoKey,
      seeds: args.seeds,
      limit: args.limit ?? 20,
    }),
  );
}
