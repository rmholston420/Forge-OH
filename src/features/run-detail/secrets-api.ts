/**
 * src/features/run-detail/secrets-api.ts
 *
 * BFF call for per-run (per-conversation) secrets. The agent-server exposes
 * only a POST endpoint that upserts the entire secrets map; there is no
 * GET (secrets are write-only once injected into the conversation context).
 */
import { bffPost } from '@/lib/api/client';
import { unwrap } from '@/lib/api/response';
import { ENDPOINTS } from '@/lib/api/endpoints';

export type RunSecretsAck = { ok: boolean; run_id: string };

export async function updateRunSecrets(
  runId: string,
  secrets: Record<string, string>,
): Promise<RunSecretsAck> {
  const result = await bffPost<RunSecretsAck>(ENDPOINTS.RUNS.secrets(runId), { secrets });
  return unwrap(result);
}
