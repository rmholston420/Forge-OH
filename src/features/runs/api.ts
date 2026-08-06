/**
 * src/features/runs/api.ts
 *
 * All BFF calls for the Runs feature.
 * Uses the canonical bffGet/bffPost from lib/api/client — never raw fetch.
 */
import type { RunSummary } from '@/lib/schemas/run';
import type { AgentPreset, CreateRunRequest } from './schemas';
import { bffGet, bffPost } from '@/lib/api/client';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { unwrap } from '@/lib/api/response';

export async function fetchRuns(): Promise<RunSummary[]> {
  const result = await bffGet<{ data: RunSummary[] }>(ENDPOINTS.RUNS.list());
  return unwrap(result).data;
}

export async function createRun(req: CreateRunRequest): Promise<RunSummary> {
  const result = await bffPost<{ data: RunSummary }>(ENDPOINTS.RUNS.create(), req);
  return unwrap(result).data;
}

export async function fetchAgentPresets(): Promise<AgentPreset[]> {
  const result = await bffGet<{ data: AgentPreset[] }>(ENDPOINTS.AGENTS.listPresets());
  return unwrap(result).data;
}

// ---------------------------------------------------------------------------
// Stage 5 — lifecycle actions. All return the raw BFF ack; the caller triggers
// a run refetch so the RunSummary.status transitions land in the UI.
// ---------------------------------------------------------------------------

export type LifecycleAck = {
  ok: boolean;
  run_id: string;
  status: string;
  agent_server?: unknown;
};

export async function pauseRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.pause(runId), {});
  return unwrap(result);
}

export async function resumeRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.resume(runId), {});
  return unwrap(result);
}

export async function stopRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.stop(runId), {});
  return unwrap(result);
}

export async function approveRun(runId: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(ENDPOINTS.RUNS.approve(runId), {});
  return unwrap(result);
}

export async function rejectRun(runId: string, reason?: string): Promise<LifecycleAck> {
  const result = await bffPost<LifecycleAck>(
    ENDPOINTS.RUNS.reject(runId),
    reason ? { reason } : {},
  );
  return unwrap(result);
}

export type ForkAck = {
  ok: boolean;
  run_id: string;
  forked_id: string;
  from_event_id: string | null;
};

/**
 * Stage 6.4 — conversation-state revert via SDK-native fork.
 *
 * ``from_event_id`` scopes the fork to the branch up to and including that
 * event.  Omit for a full fork of the source run.
 *
 * NOTE: the wire key MUST be exactly ``from_event_id``.  Agent-server
 * (openhands-agent-server 1.40.0) silently ignores unknown keys and
 * full-forks instead — a live probe on 2026-08-06 confirmed this trap
 * with ``at_event_id`` / ``from_event`` / ``event_id`` / ``leaf_event_id``.
 */
export async function forkRun(
  runId: string,
  opts?: { fromEventId?: string },
): Promise<ForkAck> {
  const body: Record<string, unknown> = {};
  if (opts?.fromEventId) {
    body.from_event_id = opts.fromEventId;
  }
  const result = await bffPost<ForkAck>(ENDPOINTS.RUNS.fork(runId), body);
  return unwrap(result);
}

// ---------------------------------------------------------------------------
// Stage 6.4c — restart-from-here (ADR-026, Decision item 1).
// POST /api/runs/{run_id}/restart with { from_event_id } → BFF composes
// worktree provision + agent-server conversation create + event seed and
// returns the shape below.
//
// NOTE: the wire key MUST be exactly ``from_event_id``.  Symmetric to
// forkRun above.  This is the SAME anchor semantics as fork-from-here
// (only user MessageEvents with a ledger-captured sha), but the endpoint
// ALSO resets the working tree.
// ---------------------------------------------------------------------------

export type RestartAck = {
  ok: boolean;
  restarted_run_id: string;
  source_run_id: string;
  from_event_id: string;
  reset_to_sha: string;
  worktree_path: string;
};

export async function restartRun(
  runId: string,
  opts: { fromEventId: string },
): Promise<RestartAck> {
  const body = { from_event_id: opts.fromEventId };
  const result = await bffPost<RestartAck>(ENDPOINTS.RUNS.restart(runId), body);
  return unwrap(result);
}

// ---------------------------------------------------------------------------
// Stage 1.6 (reconciliation-plan-v1) — send-message-while-running.
// POST /api/runs/{run_id}/message → agent-server
//   POST /api/conversations/{cid}/events with role='user'.
// ---------------------------------------------------------------------------

export type MessageAck = { ok: boolean; run_id: string; agent_server?: unknown };

export async function sendRunMessage(runId: string, message: string): Promise<MessageAck> {
  const result = await bffPost<MessageAck>(ENDPOINTS.RUNS.message(runId), { message });
  return unwrap(result);
}

// ---------------------------------------------------------------------------
// Stage 6.5.2 — runtime model switching (ADR-027).
// POST /api/runs/{run_id}/model with { agentPresetId }.
//
// The wire body is PRESET-ONLY.  Raw model strings and LLM-Input blobs are
// rejected at the BFF's Pydantic layer because credentials/model-source must
// never come from the browser — the BFF hydrates from the preset registry +
// inference-backends registry and forwards to agent-server switch_llm.
// See ADR-027 (Ratified 2026-08-06) and BUILD_LOG.md 2026-08-06 10:12 EDT.
// ---------------------------------------------------------------------------

export type SwitchModelAck = {
  ok: boolean;
  run_id: string;
  agentPresetId: string;
  resolved: {
    role: 'coder' | 'planner' | string;
    backend: 'vllm' | 'ollama' | string;
    model: string;
    base_url: string;
    max_tokens: number;
  };
  resolved_model_note: string | null;
  agent_server?: unknown;
};

export async function switchRunModel(
  runId: string,
  opts: { agentPresetId: string },
): Promise<SwitchModelAck> {
  const result = await bffPost<SwitchModelAck>(
    ENDPOINTS.RUNS.model(runId),
    { agentPresetId: opts.agentPresetId },
  );
  return unwrap(result);
}
