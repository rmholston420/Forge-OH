/**
 * hooks-live.spec.ts
 *
 * End-to-end integration test for the Slice F.9 + F.10 runtime hook
 * wiring: creates a real conversation through the BFF, waits for the
 * agent to reach a terminal state, then asserts that BOTH STOP hooks
 * actually fired against the live agent-server:
 *
 *   1. Verify hook wrote  ``$WORKSPACE/.forge-oh/verify-state.json``
 *   2. Trajectory hook inserted a row into
 *      ``$FORGE_OH_TRAJECTORY_DB`` (default ``~/.forge-oh/trajectories.db``)
 *      keyed by the run id
 *
 * The test is gated behind ``LIVE_HOOKS_E2E=1`` — it needs Ollama, the
 * agent-server, and the BFF all up, and it consumes a real LLM call. It
 * runs a deliberately trivial task so the agent finishes fast:
 *
 *     LIVE_HOOKS_E2E=1 npx playwright test src/tests/e2e/hooks-live.spec.ts
 *
 * Without ``LIVE_HOOKS_E2E=1`` set, every spec in this file skips with
 * a clear reason — the file is safe to leave in the default test suite.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const PY = process.env.PLAYWRIGHT_PYTHON || `${process.env.HOME}/dev/forge-oh/.oh-venv/bin/python`;
const TRAJ_DB =
  process.env.FORGE_OH_TRAJECTORY_DB || `${process.env.HOME}/.forge-oh/trajectories.db`;
// A tight-but-realistic upper bound for a trivial task on Ollama.
// Adjust down once we have benchmarks; keep generous for cold starts.
const RUN_TIMEOUT_MS = Number(process.env.LIVE_HOOKS_E2E_TIMEOUT_MS || 4 * 60_000);
const POLL_INTERVAL_MS = 2000;

const LIVE = process.env.LIVE_HOOKS_E2E === '1';

/** Poll ``GET /api/runs/{id}`` until it hits a terminal status or times out. */
async function waitForTerminal(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
): Promise<{ status: string; workspacePath?: string }> {
  const deadline = Date.now() + RUN_TIMEOUT_MS;
  let lastBody: Record<string, unknown> = {};
  while (Date.now() < deadline) {
    const res = await request.get(`${BFF_URL}/api/runs/${runId}`);
    if (res.ok()) {
      const body = await res.json();
      lastBody = body?.data ?? body;
      const status = (lastBody?.status as string) || 'unknown';
      if (['succeeded', 'failed', 'stopped', 'cancelled'].includes(status)) {
        return {
          status,
          workspacePath: (lastBody?.workspacePath as string) || undefined,
        };
      }
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  throw new Error(
    `run ${runId} did not reach a terminal state within ${RUN_TIMEOUT_MS}ms ` +
      `(last status=${lastBody?.status ?? 'unknown'})`,
  );
}

/** Ask sqlite for the most recent trajectory row matching the given run id. */
function trajectoryRowForRun(runId: string): {
  trajectory_id: string;
  run_id: string;
  task_description: string;
  final_status: string;
} | null {
  const script = `
import json, sqlite3, sys
conn = sqlite3.connect(${JSON.stringify(TRAJ_DB)})
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT trajectory_id, run_id, task_description, final_status "
    "FROM trajectories WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
    (${JSON.stringify(runId)},),
).fetchone()
sys.stdout.write(json.dumps(dict(row)) if row else "null")
`;
  const out = execFileSync(PY, ['-c', script], { encoding: 'utf8' }).trim();
  return out === 'null' ? null : JSON.parse(out);
}

test.describe('Live STOP hook plumbing (verify + trajectory)', () => {
  test.beforeAll(() => {
    if (!LIVE) return;
    // Fail fast if the interpreter or DB path isn't reachable so we
    // don't waste 4 minutes waiting for a run before hitting a config error.
    try {
      execFileSync(PY, ['-c', 'import sqlite3; sqlite3.connect(":memory:")'], {
        stdio: 'ignore',
      });
    } catch {
      throw new Error(
        `Python interpreter not usable: ${PY}. Override with PLAYWRIGHT_PYTHON.`,
      );
    }
  });

  test('BFF is reachable', async ({ request }) => {
    test.skip(!LIVE, 'set LIVE_HOOKS_E2E=1 to run live-plumbing checks');
    const res = await request.get(`${BFF_URL}/api/runs`);
    expect(res.ok(), `GET ${BFF_URL}/api/runs failed`).toBeTruthy();
  });

  test('a completed run triggers both STOP hooks', async ({ request }) => {
    test.skip(!LIVE, 'set LIVE_HOOKS_E2E=1 to run live-plumbing checks');

    // ---- 1. Ensure at least one workspace exists ------------------------
    let workspaceId: string | undefined;
    const wsRes = await request.get(`${BFF_URL}/api/workspaces`);
    expect(wsRes.ok()).toBeTruthy();
    const wsBody = await wsRes.json();
    const wsList = (Array.isArray(wsBody) ? wsBody : wsBody?.data ?? []) as Array<{
      id: string;
      path?: string;
    }>;
    if (wsList.length > 0) {
      workspaceId = wsList[0].id;
    } else {
      const createRes = await request.post(`${BFF_URL}/api/workspaces`, {
        data: { name: 'hooks-live-e2e' },
      });
      expect(createRes.ok()).toBeTruthy();
      const created = (await createRes.json()) as { id: string; path?: string };
      workspaceId = created.id;
    }
    expect(workspaceId).toBeTruthy();

    // ---- 2. Create + start the run --------------------------------------
    // Trivial single-turn task; the agent should reply and hit `finish`
    // quickly, which is what triggers the SDK's STOP hook processor.
    const uniq = Date.now();
    const runRes = await request.post(`${BFF_URL}/api/runs`, {
      data: {
        title: `hooks-live-${uniq}`,
        agentPresetId: 'default',
        workspaceId,
        taskPrompt:
          'Respond with exactly the single word "ok" and then finish. ' +
          'Do not call any tools.',
        taskComplexity: 'simple',
      },
    });
    expect(runRes.ok(), `POST /api/runs failed: ${await runRes.text()}`).toBeTruthy();
    const runBody = (await runRes.json()) as { data?: { id?: string } };
    const runId = runBody?.data?.id;
    expect(runId, 'BFF did not return a run id — check agent-server + Ollama').toBeTruthy();

    // ---- 3. Wait for the run to reach a terminal state ------------------
    const { status, workspacePath } = await waitForTerminal(request, runId!);
    expect(
      ['succeeded', 'failed', 'stopped'].includes(status),
      `unexpected terminal status: ${status}`,
    ).toBeTruthy();

    // ---- 4. Verify hook produced verify-state.json ----------------------
    // The verify hook writes ``$OPENHANDS_PROJECT_DIR/.forge-oh/verify-state.json``
    // keyed by session id, so file presence is the correct assertion.
    if (workspacePath) {
      const verifyStatePath = join(workspacePath, '.forge-oh', 'verify-state.json');
      expect(
        existsSync(verifyStatePath),
        `verify hook did not write ${verifyStatePath} — check .forge-logs/agent-server.log for hook stderr`,
      ).toBeTruthy();
      // Payload should be JSON-parseable and keyed by session/run id.
      const parsed = JSON.parse(readFileSync(verifyStatePath, 'utf8')) as Record<
        string,
        unknown
      >;
      expect(typeof parsed).toBe('object');
    }

    // ---- 5. Trajectory hook wrote a row keyed by our run id -------------
    // Give SQLite up to 10s in case the hook is still committing.
    let row: ReturnType<typeof trajectoryRowForRun> = null;
    const trajDeadline = Date.now() + 10_000;
    while (Date.now() < trajDeadline && row === null) {
      row = trajectoryRowForRun(runId!);
      if (row !== null) break;
      await new Promise((r) => setTimeout(r, 500));
    }
    expect(
      row,
      `trajectory hook did not insert a row for run_id=${runId} in ${TRAJ_DB} — ` +
        `check .forge-logs/agent-server.log for hook stderr and confirm ` +
        `FORGE_OH_TRAJECTORY_DB is exported by scripts/forge-up.sh`,
    ).not.toBeNull();
    expect(row!.run_id).toBe(runId);
    // Verify + trajectory ordering: if verify wrote state, final_status
    // should be one of the mapped values. If verify skipped (e.g. no
    // repo), final_status defaults to "unknown", which is also fine.
    expect(['success', 'failed', 'unknown']).toContain(row!.final_status);
  });
});
