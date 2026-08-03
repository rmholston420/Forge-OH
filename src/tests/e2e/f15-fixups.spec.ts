/**
 * f15-fixups.spec.ts — post-F.14/F.15 verification (2026-08-03)
 *
 * Verifies end-to-end that the two fixup commits (1250c99, 1e9d623)
 * produce the correct trajectory row on Colossus:
 *
 * 1. Happy path — Create /workspace/hello.py + run it.
 *    Expect: final_status="success", non-empty diffs_json, empty
 *    symptom, empty plan (no TaskTrackerAction in ap-1),
 *    empty repograph_symbols_json.
 *
 * 2. Failing terminal — Force TerminalObservation.exit_code=1.
 *    Expect: final_status="success" (verify skipped, F.14 fixup),
 *    symptom containing "TerminalObservation exit=1".
 *
 * The DB row is read directly with sqlite3 via a short child-process
 * call, matching the pattern already used by
 * trajectory-memory-panel.spec.ts.
 *
 * Runs against the real BFF at PLAYWRIGHT_BFF_URL (default
 * http://127.0.0.1:8081). Requires:
 *
 *   * BFF up on :8081
 *   * agent-server up on :8090
 *   * a Colossus workspace with FORGE_TEST_WORKSPACE_ID set (defaults
 *     to the id captured in the F.14/F.15 verification session:
 *     18c99443b23c452899010095abd5f29b).
 *
 * Skip guard: if the BFF isn't reachable, the whole file skips
 * (rather than failing) — same policy as the other online specs.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { homedir } from 'node:os';
import { join } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const WORKSPACE_ID =
  process.env.FORGE_TEST_WORKSPACE_ID ||
  '18c99443b23c452899010095abd5f29b';
const PRESET_ID = process.env.FORGE_TEST_PRESET_ID || 'ap-1';
const TRAJECTORY_DB =
  process.env.FORGE_TRAJECTORY_DB ||
  join(homedir(), '.forge-oh', 'trajectories.db');
const RUN_POLL_INTERVAL_MS = 3_000;
const RUN_TIMEOUT_MS = 180_000;

/** Fire a new run and return the run/session id. */
async function createRun(
  request: import('@playwright/test').APIRequestContext,
  title: string,
  taskPrompt: string,
): Promise<string> {
  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title,
      agentPresetId: PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const id = body?.data?.id;
  expect(id, `create_run body missing data.id: ${JSON.stringify(body)}`).toBeTruthy();
  return id as string;
}

/** Poll GET /api/runs/{id} until terminal, or throw on timeout. */
async function waitForTerminal(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
): Promise<string> {
  const deadline = Date.now() + RUN_TIMEOUT_MS;
  let last = '';
  while (Date.now() < deadline) {
    const res = await request.get(`${BFF_URL}/api/runs/${runId}`);
    if (res.ok()) {
      const body = await res.json();
      last = body?.data?.status ?? '';
      if (['succeeded', 'failed', 'blocked'].includes(last)) return last;
    }
    await new Promise((r) => setTimeout(r, RUN_POLL_INTERVAL_MS));
  }
  throw new Error(`run ${runId} did not reach terminal status (last=${last})`);
}

/** Trigger the trajectory drain endpoint so the row is in SQLite. */
async function drainTrajectories(
  request: import('@playwright/test').APIRequestContext,
): Promise<void> {
  const res = await request.post(`${BFF_URL}/api/trajectories/drain`);
  expect(res.ok(), await res.text()).toBeTruthy();
}

/** Read the trajectory row for a session id as JSON. */
function readTrajectoryRow(sessionId: string): {
  session_id: string;
  final_status: string;
  task_description: string;
  symptom: string;
  plan: string;
  diffs_json: string;
  repograph_symbols_json: string;
} {
  const sql = `
    SELECT json_object(
      'session_id', session_id,
      'final_status', final_status,
      'task_description', task_description,
      'symptom', symptom,
      'plan', plan,
      'diffs_json', diffs_json,
      'repograph_symbols_json', repograph_symbols_json
    ) FROM trajectories WHERE session_id = '${sessionId}';
  `;
  const out = execFileSync('sqlite3', [TRAJECTORY_DB, sql], {
    encoding: 'utf8',
  }).trim();
  expect(out, `no trajectory row for ${sessionId}`).toBeTruthy();
  return JSON.parse(out);
}

test.beforeAll(async ({ request }) => {
  // Skip the whole file if the BFF isn't reachable.
  const res = await request.get(`${BFF_URL}/api/runs`).catch(() => null);
  test.skip(!res || !res.ok(), `BFF at ${BFF_URL} not reachable — skipping`);
});

test.describe('F.14 / F.15 fixup verification', () => {
  test('happy path: fresh file create + run populates diffs, no symptom', async ({
    request,
  }) => {
    test.setTimeout(RUN_TIMEOUT_MS + 60_000);
    // Use a per-run unique filename so a prior verification run's
    // artifact can't make `create` legitimately error out. That is
    // exactly what happened on the first Colossus run of this spec
    // (F.15 producer correctly surfaced the FileEditorObservation
    // error — the assertion was the bug, not the producer).
    const stamp = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const relPath = `hello_${stamp}.py`;
    const absPath = `/workspace/${relPath}`;
    const cid = await createRun(
      request,
      `F.15 fixup — happy path (${relPath})`,
      `Create ${absPath} that prints hello world, then run it.`,
    );
    const status = await waitForTerminal(request, cid);
    expect(status).toBe('succeeded');

    await drainTrajectories(request);
    const row = readTrajectoryRow(cid);

    expect(row.final_status).toBe('success');
    expect(row.task_description).toContain(relPath);
    expect(row.symptom).toBe(''); // no observation errored on a fresh path
    expect(row.plan).toBe(''); // ap-1 has no TaskTrackerAction — expected

    const diffs = JSON.parse(row.diffs_json) as Array<{
      path: string;
      lines_added: number;
      lines_removed: number;
      summary: string;
    }>;
    expect(diffs.length).toBeGreaterThan(0);
    const created = diffs.find((d) => d.path.endsWith(relPath));
    expect(
      created,
      `${relPath} missing from diffs: ${row.diffs_json}`,
    ).toBeTruthy();
    expect(created!.lines_added).toBeGreaterThanOrEqual(1);
    expect(created!.summary).toBe('added');

    const symbols = JSON.parse(row.repograph_symbols_json) as string[];
    expect(symbols).toEqual([]);
  });

  test('failing terminal: exit=1 becomes structured symptom', async ({
    request,
  }) => {
    test.setTimeout(RUN_TIMEOUT_MS + 60_000);
    const cid = await createRun(
      request,
      'F.15 fixup — symptom path',
      'Run exactly this shell command and then stop: false',
    );
    const status = await waitForTerminal(request, cid);
    // The run itself still "succeeds" from the BFF's perspective — the
    // failing command is an in-turn observation, not an agent-level
    // failure. F.14 verdict map maps verify's "skipped" → "success".
    expect(status).toBe('succeeded');

    await drainTrajectories(request);
    const row = readTrajectoryRow(cid);

    expect(row.final_status).toBe('success');
    expect(row.symptom).toContain('TerminalObservation exit=1');
    // Symptom is capped at 500 chars by _truncate().
    expect(row.symptom.length).toBeLessThanOrEqual(500);
  });
});
