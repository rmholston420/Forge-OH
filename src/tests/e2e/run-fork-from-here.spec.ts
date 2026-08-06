/**
 * run-fork-from-here.spec.ts — Stage 6.4 DoD screenshot.
 *
 * Verifies that the Stage 6.4 "Fork from here" button:
 *   1. only renders for user-message events (spec D2);
 *   2. wires ``from_event_id`` all the way to agent-server (defends
 *      against the silent-full-fork trap discovered in the 2026-08-06
 *      live probe);
 *   3. navigates to /runs/${forked_id} on success.
 *
 * Method:
 *   1. Reuse or create a run via BFF.
 *   2. Inject a synthetic ``MessageEvent`` with ``source=user`` through
 *      ``POST /api/_debug/inject-event`` (gated behind
 *      ``FORGE_TIMELINE_DEBUG_INJECT=1``). This produces a real,
 *      normalized user-message row on the timeline whose event id we
 *      capture from the response.
 *   3. Navigate to /runs/{runId}, click the injected event card so the
 *      inspector opens, assert the fork-from-here button is visible.
 *   4. Also inject an assistant-source MessageEvent and assert the
 *      button is HIDDEN when that event is selected (D2 negative case).
 *   5. Intercept POST /api/runs/{id}/fork to prove the wire body is
 *      ``{from_event_id: "<injected event id>"}`` with the exact key.
 *      Stub the response so we don't actually spawn a fork run against
 *      agent-server (which would require the workspace to be idle).
 *   6. Assert navigation to /runs/${stubbed forked_id}.
 *   7. Capture screenshot for §6.4 evidence.
 *
 * Preconditions (verified in beforeAll):
 *   * BFF up on :8081 with FORGE_TIMELINE_DEBUG_INJECT=1 exported.
 *   * agent-server up on :8090.
 *   * prod frontend up on :3100 (next start, never next dev).
 */
import { test, expect, type Page } from '@playwright/test';
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
const SCREENSHOT_PATH = join(SCREENSHOT_DIR, 'run-fork-from-here.png');

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
    console.log('[fork-from-here] START_PROD=1 — building + next start on :' + PROD_PORT);
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
  console.log('[fork-from-here] BFF inject-event probe status:', injectStatus);
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
  console.log('[fork-from-here] agent-server /api/tools status:', agentStatus);
  if (!agentProbe || agentStatus >= 500) missing.push(`agent-server ${AGENT_URL}`);

  const feProbe = await request.get(FRONTEND_URL).catch(() => null);
  // eslint-disable-next-line no-console
  console.log(
    '[fork-from-here] FE status:',
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
  const listResp = await request.get(`${AGENT_URL}/api/conversations`).catch(() => null);
  if (listResp && listResp.ok()) {
    const body = await listResp.json();
    const items: Array<{ id?: string }> = Array.isArray(body)
      ? body
      : (body?.items ?? body?.data ?? []);
    for (const it of items) {
      if (it && typeof it.id === 'string' && it.id.length > 0) {
        // eslint-disable-next-line no-console
        console.log('[fork-from-here] reusing existing conversation id:', it.id);
        return it.id;
      }
    }
  }

  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title: 'Stage 6.4 fork-from-here DoD',
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
  if (!res.ok() || !id) {
    throw new Error(
      `Could not synthesize a conversation via preset ${OLLAMA_PRESET_ID}. ` +
        `HTTP ${res.status()} body=${text.slice(0, 400)}`,
    );
  }
  return id;
}

async function injectMessageEvent(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
  source: 'user' | 'agent',
  content: string,
): Promise<{ id: string; summary: string }> {
  const res = await request.post(`${BFF_URL}/api/_debug/inject-event`, {
    data: {
      runId,
      kind: 'MessageEvent',
      extra: {
        source,
        llm_message: { role: source === 'user' ? 'user' : 'assistant', content },
      },
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  expect(body?.data?.type).toBe('message');
  expect(body?.data?.source).toBe(source);
  return { id: String(body.data.id), summary: String(body.data.summary ?? content) };
}

test('Stage 6.4: fork-from-here appears on user messages only + wires from_event_id verbatim', async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);

  const runId = await pickOrCreateConversation(request);
  // eslint-disable-next-line no-console
  console.log('[fork-from-here] runId:', runId);

  // Stub POST /api/runs/{runId}/fork FIRST so the route is intercepted from
  // the moment the page loads. Captures the request body to prove
  // exact-wire-key forwarding.
  let capturedBody: any = null;
  const stubbedForkedId = 'stub-forked-id-6-4-dod';
  await page.route(`**/api/runs/${runId}/fork`, async (route) => {
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
        run_id: runId,
        forked_id: stubbedForkedId,
        from_event_id: capturedBody?.from_event_id ?? null,
      }),
    });
  });

  // Navigate to the run detail page FIRST and wait for it to be fully
  // mounted + Socket.IO-connected. The debug-inject endpoint emits into
  // the run's socket room only (no persistence), so if we inject before
  // the client joins the room the event is lost. See reference:
  // src/tests/e2e/condensation-timeline-marker.spec.ts.
  await page.goto(`${FRONTEND_URL}/runs/${runId}`, { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({
    timeout: 15_000,
  });
  // Give the Socket.IO client time to join the conversation room.
  await page.waitForTimeout(1_500);

  // NOW inject one user + one assistant message. The user one is the
  // fork target; the assistant one is the D2 negative case.
  const userEvt = await injectMessageEvent(
    request,
    runId,
    'user',
    'STAGE-6.4-DOD user checkpoint — fork from here should be visible for this event.',
  );
  const agentEvt = await injectMessageEvent(
    request,
    runId,
    'agent',
    'STAGE-6.4-DOD assistant reply — fork from here MUST NOT appear for this event.',
  );
  // eslint-disable-next-line no-console
  console.log('[fork-from-here] injected user evt:', userEvt.id, 'agent evt:', agentEvt.id);

  // Wait for the timeline to render our injected user event card.
  // Target the EventCard specifically via its role=button (see EventCard.tsx),
  // not raw text — the inspector aside will re-render the same summary
  // text as a <dd> and would otherwise collide.
  const userCard = page.getByRole('button', {
    name: new RegExp('STAGE-6.4-DOD user checkpoint'),
  }).first();
  const agentCard = page.getByRole('button', {
    name: new RegExp('STAGE-6.4-DOD assistant reply'),
  }).first();
  await expect(userCard).toBeVisible({ timeout: 30_000 });
  await expect(agentCard).toBeVisible({ timeout: 30_000 });

  // D2 negative case: click the assistant event, confirm the button is HIDDEN.
  await agentCard.click();
  await expect(page.getByTestId('fork-from-here-button')).toHaveCount(0);

  // D2 positive case: click the user event, confirm the button IS visible.
  await userCard.click();
  const forkBtn = page.getByTestId('fork-from-here-button');
  await expect(forkBtn).toBeVisible();

  // Trigger the confirm dialog and confirm.
  await forkBtn.click();
  const confirmBtn = page.getByTestId('fork-from-here-confirm');
  await expect(confirmBtn).toBeVisible();

  // Capture the screenshot BEFORE confirming — this shows the dialog
  // open with the user-message event highlighted underneath.
  await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true });

  await confirmBtn.click();

  // Assert navigation to /runs/${forked_id} — this is the D1 sibling-fork
  // stop condition rendered end-to-end.
  await page.waitForURL(new RegExp(`/runs/${stubbedForkedId}$`), { timeout: 15_000 });

  // Finally, prove the wire body. This is THE regression assertion against
  // the silent-full-fork trap discovered in the 2026-08-06 05:53 EDT probe.
  expect(capturedBody).toEqual({ from_event_id: userEvt.id });

  // Sanity: prove we did NOT accidentally use one of the alias keys that
  // agent-server silently ignores.
  expect(capturedBody).not.toHaveProperty('at_event_id');
  expect(capturedBody).not.toHaveProperty('from_event');
  expect(capturedBody).not.toHaveProperty('event_id');
  expect(capturedBody).not.toHaveProperty('leaf_event_id');
});
