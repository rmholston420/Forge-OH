/**
 * condensation-timeline-marker.spec.ts — Stage 6.2 DoD screenshot.
 *
 * Verifies that a synthetic ``Condensation`` event injected through the
 * dev-only ``POST /api/_debug/inject-event`` endpoint (gated behind
 * ``FORGE_TIMELINE_DEBUG_INJECT=1``) surfaces on the run-detail timeline
 * as a 🗜️ EventCard, and captures a screenshot for §6.2 evidence.
 *
 * Design rationale (see conversation on 2026-08-06):
 *   * The SDK ``Condensation`` event only fires under real context-window
 *     pressure. Forcing a real compaction in an E2E is unreliable, so
 *     we exercise the frontend rendering path deterministically by
 *     injecting a raw event with the correct ``kind`` and letting the
 *     BFF normalize + relay it identically to a real event.
 *   * Uses the same run-id-then-navigate pattern as
 *     ``search-timeline-marker.spec.ts`` so the auto-push contract
 *     matches Stage 6.1.
 *
 * Preconditions (verified in beforeAll):
 *   * BFF up on :8081 with ``FORGE_TIMELINE_DEBUG_INJECT=1`` exported.
 *   * agent-server up on :8090 so /api/runs create returns a real run id.
 *   * prod frontend up on :3100 (``next start``, never ``next dev``).
 *
 * Screenshot output (auto-pushed when PLAYWRIGHT_GPU_STRIP_PUSH=1):
 *   screenshots/condensation-timeline-marker.png
 */
import { test, expect, type Page } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
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

// REPO_ROOT via __dirname (Playwright loads specs as CJS here — see Stage
// 6.1 DEBUG_LOG entry for why import.meta doesn't work).
const REPO_ROOT = resolve(__dirname, '..', '..', '..');
const APP_DIR = REPO_ROOT;
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const MARKER_PNG = join(SCREENSHOT_DIR, 'condensation-timeline-marker.png');
const SHOULD_PUSH = process.env.PLAYWRIGHT_GPU_STRIP_PUSH === '1';

// Injected event payload.  Uses the SDK v1.40.0 ``Condensation`` shape.
const FORGOTTEN_IDS = ['synthetic-a', 'synthetic-b', 'synthetic-c'];
const CONDENSATION_SUMMARY = 'Rolled up 3 planning steps into a single frame.';
const LLM_RESPONSE_ID = 'synthetic-llm-response-1';

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
    console.log('[cond-timeline] START_PROD=1 — building + starting next start on :' + PROD_PORT);
    execFileSync('npm', ['run', 'build'], { cwd: APP_DIR, stdio: 'inherit' });
    nextProc = spawn('npx', ['next', 'start', '-p', String(PROD_PORT)], {
      cwd: APP_DIR,
      stdio: 'inherit',
      env: { ...process.env, NEXT_PUBLIC_BFF_URL: BFF_URL },
      detached: false,
    });
    await waitForPort(PROD_PORT);
  }

  // Probe the debug endpoint to verify the flag is set. A disabled server
  // returns 404 (not 503), so we send an intentionally minimal payload and
  // treat 404 as "flag not set" rather than "route missing".
  const injectProbe = await request
    .post(`${BFF_URL}/api/_debug/inject-event`, {
      data: { runId: 'probe', kind: 'CondensationRequest', extra: {} },
    })
    .catch(() => null);
  const injectStatus = injectProbe ? injectProbe.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[cond-timeline] BFF inject-event probe status:', injectStatus);
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
  console.log('[cond-timeline] agent-server /api/tools status:', agentStatus);
  if (!agentProbe || agentStatus >= 500) missing.push(`agent-server ${AGENT_URL}`);

  const feProbe = await request.get(FRONTEND_URL).catch(() => null);
  // eslint-disable-next-line no-console
  console.log('[cond-timeline] FE status:', feProbe ? feProbe.status() : 'null', 'URL=', FRONTEND_URL);
  if (!feProbe || feProbe.status() >= 500) {
    missing.push(
      `frontend ${FRONTEND_URL} unreachable. Start prod frontend on :${PROD_PORT} (never next dev):\n` +
        `  cd ~/dev/forge-oh && npm run build && \\\n` +
        `    NEXT_PUBLIC_BFF_URL=http://127.0.0.1:8081 \\\n` +
        `    nohup npx next start -H 127.0.0.1 -p ${PROD_PORT} >~/.forge-oh/next-prod.log 2>&1 &\n` +
        `Or re-run with PLAYWRIGHT_START_PROD=1 to have the spec do it.`,
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

const OLLAMA_PRESET_ID = process.env.FORGE_TEST_OLLAMA_PRESET_ID || 'ap-3';

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
        console.log('[cond-timeline] reusing existing conversation id:', it.id);
        return it.id;
      }
    }
    // eslint-disable-next-line no-console
    console.log('[cond-timeline] no existing conversations; falling back to create-run.');
  }

  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title: 'Stage 6.2 condensation-timeline-marker',
      agentPresetId: OLLAMA_PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt: 'idle: this run only exists to receive a Condensation event.',
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
  if (!res.ok() || !id) {
    throw new Error(
      `Could not synthesize a conversation via preset ${OLLAMA_PRESET_ID}. ` +
        `HTTP ${res.status()} status=${status ?? 'n/a'} body=${text.slice(0, 400)}`,
    );
  }
  // eslint-disable-next-line no-console
  console.log(
    '[cond-timeline] created new conversation via preset',
    OLLAMA_PRESET_ID,
    'id:', id, 'status:', status,
  );
  return id;
}

async function injectCondensation(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
): Promise<void> {
  const res = await request.post(`${BFF_URL}/api/_debug/inject-event`, {
    data: {
      runId,
      kind: 'Condensation',
      extra: {
        forgotten_event_ids: FORGOTTEN_IDS,
        summary: CONDENSATION_SUMMARY,
        summary_offset: 0,
        llm_response_id: LLM_RESPONSE_ID,
      },
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  expect(body?.data?.type).toBe('condensation');
}

async function waitForCondensationCard(page: Page): Promise<void> {
  const expectedSummaryStart = `Context compressed — ${FORGOTTEN_IDS.length} turns forgotten`;
  await expect(page.getByText(new RegExp(expectedSummaryStart))).toBeVisible({
    timeout: 30_000,
  });
  const eventCard = page.getByRole('button', {
    name: new RegExp('^Context compressed'),
  });
  await expect(eventCard).toBeVisible({ timeout: 5_000 });
  await expect(eventCard.getByText('🗜️')).toBeVisible({ timeout: 5_000 });
}

test.describe('Condensation timeline marker — synthetic emit (Stage 6.2)', () => {
  test('injects Condensation and renders 🗜️ EventCard on run-detail', async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);

    const runId = await pickOrCreateConversation(request);
    // eslint-disable-next-line no-console
    console.log('[cond-timeline] runId:', runId);

    await page.goto(`${FRONTEND_URL}/runs/${runId}`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    await page.waitForTimeout(1_000);

    await injectCondensation(request, runId);

    await waitForCondensationCard(page);

    await page.screenshot({ path: MARKER_PNG, fullPage: true });
    expect(existsSync(MARKER_PNG), `${MARKER_PNG} missing`).toBeTruthy();

    if (!SHOULD_PUSH) {
      // eslint-disable-next-line no-console
      console.log(
        `[cond-timeline] screenshot saved to ${MARKER_PNG}. ` +
          `Set PLAYWRIGHT_GPU_STRIP_PUSH=1 to auto-commit + push.`,
      );
      return;
    }

    const rel = 'screenshots/condensation-timeline-marker.png';
    execFileSync('git', ['add', '-f', rel], { cwd: REPO_ROOT, stdio: 'inherit' });
    const status = execFileSync('git', ['status', '--porcelain', rel], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (!status.trim()) {
      // eslint-disable-next-line no-console
      console.log('[cond-timeline] no change vs HEAD — skipping commit + push');
      return;
    }
    execFileSync(
      'git',
      [
        '-c',
        'user.name=Perplexity Computer',
        '-c',
        'user.email=computer@perplexity.ai',
        'commit',
        '-m',
        'Stage 6.2 screenshot: condensation-timeline-marker (🗜️ icon on run-detail)',
      ],
      { cwd: REPO_ROOT, stdio: 'inherit' },
    );
    execFileSync('git', ['push', 'origin', 'main'], { cwd: REPO_ROOT, stdio: 'inherit' });
  });
});
