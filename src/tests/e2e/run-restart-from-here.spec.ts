/**
 * run-restart-from-here.spec.ts — Stage 6.4c DoD screenshot.
 *
 * Verifies that the Stage 6.4c "Restart from here" button (per ADR-026):
 *   1. only renders for user-message events that carry a captured
 *      ``commit_sha_at_time_of_event`` (ADR-026 §Frontend contract);
 *   2. renders the NORMATIVE ADR-026 confirmation copy verbatim
 *      (three user-outcomes: files reset, prompt replayed, source
 *      preserved);
 *   3. wires ``from_event_id`` verbatim to POST /api/runs/{id}/restart;
 *   4. navigates to /runs/${restarted_run_id} on success.
 *
 * Also negatively asserts:
 *   * an assistant-source MessageEvent does NOT get the button;
 *   * a user MessageEvent WITHOUT a captured sha does NOT get the button
 *     (ADR-026 §Frontend contract sha-gate — the failure mode this test
 *     exists to defend against is silent ledger drift, where the BFF
 *     stops stamping shas and the UI keeps offering a button that would
 *     404 with anchor_not_found).
 *
 * Method:
 *   1. Reuse or create a run via BFF or agent-server.
 *   2. Inject three synthetic events via
 *      ``POST /api/_debug/inject-event`` (gated behind
 *      ``FORGE_TIMELINE_DEBUG_INJECT=1``):
 *        (a) a user MessageEvent WITH ``commit_sha_at_time_of_event``
 *            (the restart-eligible target),
 *        (b) an assistant MessageEvent (D2 negative case),
 *        (c) a user MessageEvent WITHOUT a captured sha
 *            (sha-gate negative case).
 *   3. Navigate to /runs/{runId}, click each event card in turn.
 *   4. Assert the restart button is visible only for (a).
 *   5. Intercept POST /api/runs/{id}/restart to prove the wire body is
 *      ``{from_event_id: "<a's event id>"}`` and stub the 200 response
 *      so we don't actually spawn a new run against agent-server.
 *   6. Assert navigation to /runs/${stubbed restarted_run_id}.
 *   7. Capture screenshot for §6.4c evidence.
 *
 * Preconditions (verified in beforeAll):
 *   * BFF up on :8081 with FORGE_TIMELINE_DEBUG_INJECT=1 exported.
 *   * agent-server up on :8090.
 *   * prod frontend up on :3100 (next start, never next dev).
 */
import { test, expect } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import net from 'node:net';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const AGENT_URL = process.env.PLAYWRIGHT_AGENT_URL || 'http://127.0.0.1:8090';
const START_PROD = process.env.PLAYWRIGHT_START_PROD === '1';
const PROD_PORT = Number(process.env.PLAYWRIGHT_PROD_PORT || 3100);
const FRONTEND_URL = START_PROD
  ? `http://127.0.0.1:${PROD_PORT}`
  : process.env.PLAYWRIGHT_BASE_URL ||
    process.env.PLAYWRIGHT_FRONTEND_URL ||
    `http://127.0.0.1:${PROD_PORT}`;
const WORKSPACE_ID =
  process.env.FORGE_TEST_WORKSPACE_ID || '18c99443b23c452899010095abd5f29b';
const OLLAMA_PRESET_ID = process.env.FORGE_TEST_OLLAMA_PRESET_ID || 'ap-3';

const REPO_ROOT = resolve(__dirname, '..', '..', '..');
const APP_DIR = REPO_ROOT;
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const SCREENSHOT_PATH = join(SCREENSHOT_DIR, 'run-restart-from-here.png');

// A canonical 40-char hex sha used by the E2E injector to feed the
// ADR-026 §Storage sha_lookup path.  The value is arbitrary — the
// endpoint stub captures it back into the request body for the wire
// assertion; agent-server never sees this sha because we stub the
// restart endpoint response.
const SYNTHETIC_SHA = 'a'.repeat(40);

let nextProc: ChildProcess | null = null;

function waitForPort(port: number, host = '127.0.0.1', timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolveP, reject) => {
    const tryOnce = () => {
      const socket = net.createConnection({ port, host });
      socket.once('connect', () => {
        socket.end();
        resolveP();
      });
      socket.once('error', () => {
        socket.destroy();
        if (Date.now() > deadline) {
          reject(new Error(`port ${host}:${port} not ready after ${timeoutMs}ms`));
        } else {
          setTimeout(tryOnce, 500);
        }
      });
    };
    tryOnce();
  });
}

test.beforeAll(async ({ request }) => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const missing: string[] = [];

  if (START_PROD) {
    // eslint-disable-next-line no-console
    console.log('[restart-from-here] START_PROD=1 — building + next start on :' + PROD_PORT);
    execFileSync('npm', ['run', 'build'], { cwd: APP_DIR, stdio: 'inherit' });
    nextProc = spawn('npx', ['next', 'start', '-p', String(PROD_PORT)], {
      cwd: APP_DIR,
      stdio: 'inherit',
      env: { ...process.env, NEXT_PUBLIC_BFF_URL: BFF_URL },
      detached: false,
    });
    await waitForPort(PROD_PORT);
  }

  const injectProbe = await request
    .post(`${BFF_URL}/api/_debug/inject-event`, {
      data: { runId: 'probe', kind: 'MessageEvent', extra: {} },
    })
    .catch(() => null);
  const injectStatus = injectProbe ? injectProbe.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[restart-from-here] BFF inject-event probe status:', injectStatus);
  if (!injectProbe) missing.push(`BFF ${BFF_URL}`);
  else if (injectStatus === 404) {
    missing.push(
      `BFF debug inject disabled (404). Restart BFF with ` +
        `FORGE_TIMELINE_DEBUG_INJECT=1 exported.`,
    );
  } else if (injectStatus >= 500) {
    missing.push(`BFF inject-event endpoint returned ${injectStatus}`);
  }

  const agentProbe = await request.get(`${AGENT_URL}/api/tools/`).catch(() => null);
  const agentStatus = agentProbe ? agentProbe.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[restart-from-here] agent-server /api/tools status:', agentStatus);
  if (!agentProbe || agentStatus >= 500) missing.push(`agent-server ${AGENT_URL}`);

  const feProbe = await request.get(FRONTEND_URL).catch(() => null);
  // eslint-disable-next-line no-console
  console.log(
    '[restart-from-here] FE status:',
    feProbe ? feProbe.status() : 'null',
    'URL=', FRONTEND_URL,
  );
  if (!feProbe || feProbe.status() >= 500) {
    missing.push(
      `frontend ${FRONTEND_URL} unreachable. Start prod frontend on :${PROD_PORT} (never next dev)`,
    );
  }

  test.skip(missing.length > 0, `preconditions unmet: ${missing.join(', ')}`);
});

test.afterAll(() => {
  if (nextProc && !nextProc.killed) {
    nextProc.kill('SIGTERM');
    nextProc = null;
  }
});

async function pickOrCreateConversation(
  request: import('@playwright/test').APIRequestContext,
): Promise<string> {
  // 1. Try to reuse any existing conversation on agent-server.
  const listResp = await request.get(`${AGENT_URL}/api/conversations/search?limit=25`).catch(() => null);
  if (listResp && listResp.ok()) {
    const body = await listResp.json();
    const items: Array<{ id?: string }> = Array.isArray(body)
      ? body
      : (body?.results ?? body?.items ?? body?.data ?? []);
    // eslint-disable-next-line no-console
    console.log('[restart-from-here] agent /api/conversations/search items=', items.length);
    for (const it of items) {
      if (it && typeof it.id === 'string' && it.id.length > 0) {
        // eslint-disable-next-line no-console
        console.log('[restart-from-here] reusing existing conversation id:', it.id);
        return it.id;
      }
    }
  } else {
    // eslint-disable-next-line no-console
    console.log(
      '[restart-from-here] agent /api/conversations/search failed status=',
      listResp?.status(),
    );
  }

  // 2. Create a bare conversation directly on agent-server.
  const workingDir = process.env.FORGE_TEST_WORKING_DIR || process.cwd();
  const agentCreate = await request.post(`${AGENT_URL}/api/conversations`, {
    data: {
      workspace: {
        working_dir: workingDir,
        kind: 'LocalWorkspace',
      },
    },
  }).catch(() => null);
  if (agentCreate && agentCreate.ok()) {
    const body = await agentCreate.json().catch(() => null);
    const id: string | undefined = body?.id || body?.data?.id || body?.conversation_id;
    if (id) {
      // eslint-disable-next-line no-console
      console.log('[restart-from-here] created bare conversation on agent-server id:', id);
      return id;
    }
  } else if (agentCreate) {
    // eslint-disable-next-line no-console
    console.log(
      '[restart-from-here] agent POST /api/conversations status=',
      agentCreate.status(),
      'body=',
      (await agentCreate.text().catch(() => '')).slice(0, 200),
    );
  }

  // 3. Last-resort fallback — BFF's /api/runs.
  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title: 'Stage 6.4c restart-from-here DoD',
      agentPresetId: OLLAMA_PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt: 'idle: this run only exists to receive synthetic MessageEvents.',
    },
  });
  const text = await res.text();
  let body: any = null;
  try {
    body = JSON.parse(text);
  } catch {
    /* non-JSON body */
  }
  const id: string | undefined = body?.data?.id;
  const status: string | undefined = body?.data?.status;
  if (!res.ok() || !id || status === 'blocked') {
    throw new Error(
      `Could not synthesize a conversation. All three paths failed:\n` +
        `  1. agent-server list returned no conversations\n` +
        `  2. agent-server POST /api/conversations rejected the create\n` +
        `  3. BFF POST /api/runs returned HTTP ${res.status()} status=${status ?? 'n/a'}\n` +
        `  body=${text.slice(0, 400)}`,
    );
  }
  return id;
}

async function injectMessageEvent(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
  source: 'user' | 'agent',
  content: string,
  opts: { commitSha?: string } = {},
): Promise<{ id: string; summary: string; commitSha: string | null }> {
  const extra: Record<string, unknown> = {
    source,
    llm_message: { role: source === 'user' ? 'user' : 'assistant', content },
  };
  if (opts.commitSha) {
    extra.commit_sha_at_time_of_event = opts.commitSha;
  }
  const res = await request.post(`${BFF_URL}/api/_debug/inject-event`, {
    data: {
      runId,
      kind: 'MessageEvent',
      extra,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  expect(body?.data?.type).toBe('message');
  expect(body?.data?.source).toBe(source);
  // Wire-shape guard: ADR-026 §Storage — the stamped key is
  // `commit_sha_at_time_of_event` on the normalized wire event.  If this
  // ever regresses (e.g. someone renames it camelCase), the frontend gate
  // silently starts hiding buttons even on eligible events.
  if (opts.commitSha) {
    expect(body?.data?.commit_sha_at_time_of_event).toBe(opts.commitSha);
  } else {
    expect(body?.data?.commit_sha_at_time_of_event).toBeUndefined();
  }
  return {
    id: String(body.data.id),
    summary: String(body.data.summary ?? content),
    commitSha: (body.data.commit_sha_at_time_of_event as string | undefined) ?? null,
  };
}

test('Stage 6.4c: restart-from-here appears on user messages with a captured sha + wires from_event_id verbatim', async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);

  const runId = await pickOrCreateConversation(request);
  // eslint-disable-next-line no-console
  console.log('[restart-from-here] runId:', runId);

  // Stub POST /api/runs/{runId}/restart FIRST so the route is intercepted
  // from the moment the page loads.  Captures the request body to prove
  // exact-wire-key forwarding.
  let capturedBody: any = null;
  const stubbedRestartedId = 'stub-restarted-id-6-4c-dod';
  await page.route(`**/api/runs/${runId}/restart`, async (route) => {
    try {
      capturedBody = route.request().postDataJSON();
    } catch {
      capturedBody = route.request().postData();
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        source_run_id: runId,
        restarted_run_id: stubbedRestartedId,
        from_event_id: capturedBody?.from_event_id ?? null,
        reset_to_sha: SYNTHETIC_SHA,
        worktree_path: '/tmp/stub-worktree',
      }),
    });
  });

  page.on('console', (msg) => {
    const t = msg.text();
    if (t.includes('socket') || t.includes('stream') || t.includes('error') || t.includes('Error')) {
      // eslint-disable-next-line no-console
      console.log('[browser]', msg.type(), t.slice(0, 400));
    }
  });
  page.on('pageerror', (err) => {
    // eslint-disable-next-line no-console
    console.log('[browser pageerror]', err.message);
  });

  await page.goto(`${FRONTEND_URL}/runs/${runId}`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({
    timeout: 15_000,
  });

  // Wait for Socket.IO to connect before injecting; otherwise the
  // best-effort emit into the room is lost.
  const disconnectedBanner = page.getByText('Disconnected from run stream');
  await expect(disconnectedBanner).toHaveCount(0, { timeout: 20_000 });
  // eslint-disable-next-line no-console
  console.log('[restart-from-here] stream connected (Disconnected banner absent)');
  await page.waitForTimeout(500);

  // Inject three events:
  //   (a) user + sha  -> restart button MUST be visible.
  //   (b) assistant  -> restart button MUST be hidden (D2 negative).
  //   (c) user, no sha -> restart button MUST be hidden (sha-gate).
  const userWithSha = await injectMessageEvent(
    request,
    runId,
    'user',
    'STAGE-6.4c-DOD user checkpoint WITH sha — restart-from-here must be visible.',
    { commitSha: SYNTHETIC_SHA },
  );
  const agentEvt = await injectMessageEvent(
    request,
    runId,
    'agent',
    'STAGE-6.4c-DOD assistant reply — restart-from-here MUST NOT appear here.',
  );
  const userNoSha = await injectMessageEvent(
    request,
    runId,
    'user',
    'STAGE-6.4c-DOD user checkpoint WITHOUT sha — restart-from-here MUST NOT appear here.',
  );
  // eslint-disable-next-line no-console
  console.log(
    '[restart-from-here] injected user+sha:', userWithSha.id,
    ' agent:', agentEvt.id,
    ' user-nosha:', userNoSha.id,
  );

  const userWithShaCard = page.getByRole('button', {
    name: /STAGE-6.4c-DOD user checkpoint WITH sha/,
  }).first();
  const agentCard = page.getByRole('button', {
    name: /STAGE-6.4c-DOD assistant reply/,
  }).first();
  const userNoShaCard = page.getByRole('button', {
    name: /STAGE-6.4c-DOD user checkpoint WITHOUT sha/,
  }).first();
  await expect(userWithShaCard).toBeVisible({ timeout: 30_000 });
  await expect(agentCard).toBeVisible({ timeout: 30_000 });
  await expect(userNoShaCard).toBeVisible({ timeout: 30_000 });

  // Negative 1: assistant event -> restart button hidden.
  await agentCard.click();
  await expect(page.getByTestId('restart-from-here-button')).toHaveCount(0);

  // Negative 2: user event without a captured sha -> restart button hidden.
  // This is the ADR-026 §Frontend contract sha-gate rendered end-to-end.
  await userNoShaCard.click();
  await expect(page.getByTestId('restart-from-here-button')).toHaveCount(0);

  // Positive: user event with a captured sha -> restart button visible.
  await userWithShaCard.click();
  const restartBtn = page.getByTestId('restart-from-here-button');
  await expect(restartBtn).toBeVisible();

  // Open the confirmation dialog and assert the ADR-026 §Frontend
  // contract normative copy is present verbatim.
  await restartBtn.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/files reset to that state/i)).toBeVisible();
  await expect(dialog.getByText(/re-send your original message/i)).toBeVisible();
  await expect(dialog.getByText(/your current run is preserved/i)).toBeVisible();
  await expect(
    dialog.getByText(/assistant's prior replies won't carry over/i),
  ).toBeVisible();

  const confirmBtn = page.getByTestId('restart-from-here-confirm');
  await expect(confirmBtn).toBeVisible();

  // Capture screenshot with dialog open — this is the §6.4c evidence.
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

  await confirmBtn.click();

  // Assert navigation to /runs/${restarted_run_id} — the D1 stop
  // condition for Stage 6.4c rendered end-to-end.
  await page.waitForURL(new RegExp(`/runs/${stubbedRestartedId}$`), { timeout: 15_000 });

  // Finally, prove the wire body.  This is THE regression assertion
  // against ledger drift and against the fork/restart mix-up (if the
  // hook ever wires POST /fork instead of /restart the route interceptor
  // above never fires, capturedBody stays null, and this fails).
  expect(capturedBody).toEqual({ from_event_id: userWithSha.id });

  // Sanity: prove we did NOT accidentally use one of the alias keys.
  expect(capturedBody).not.toHaveProperty('at_event_id');
  expect(capturedBody).not.toHaveProperty('from_event');
  expect(capturedBody).not.toHaveProperty('event_id');
  expect(capturedBody).not.toHaveProperty('leaf_event_id');
});
