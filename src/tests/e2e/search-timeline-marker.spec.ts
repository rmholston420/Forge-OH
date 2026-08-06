/**
 * search-timeline-marker.spec.ts — Stage 6.1 live-task DoD screenshot.
 *
 * Verifies that the ``search_web`` tool's bridge endpoint
 * (``POST /api/search/emit``) causes a ``web_search`` event with the 🔍
 * icon to appear on the run-detail timeline, then captures a screenshot
 * for the plan §6.1 evidence.
 *
 * Design mirrors memory-timeline-marker.spec.ts:
 *   * We deterministically POST the same bridge endpoint the tool calls,
 *     using a real run id returned by the BFF. This isolates the frontend
 *     contract without depending on the agent's own decision to call the
 *     tool.
 *
 * Preconditions (verified in beforeAll):
 *   * BFF up on :8081 with search emit enabled (FORGE_SEARCH_EMIT_ENABLED=1
 *     or FORGE_SEARXNG_BASE_URL set).
 *   * agent-server up on :8090 so /api/runs create returns a real run id.
 *   * prod frontend up on :3100 (``next start``, never ``next dev``).
 *
 * Screenshot output (auto-pushed when PLAYWRIGHT_GPU_STRIP_PUSH=1):
 *   screenshots/search-timeline-marker.png  run-detail with 🔍 event card
 */
import { test, expect, type Page } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
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
const PRESET_ID = process.env.FORGE_TEST_PRESET_ID || 'ap-1';

// Derive REPO_ROOT from this spec file's absolute location so the value is
// stable no matter what cwd Playwright is invoked from.
// This file lives at <repo>/src/tests/e2e/ so REPO_ROOT is three levels up.
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const REPO_ROOT = resolve(__dirname, '..', '..', '..');
const APP_DIR = REPO_ROOT; // Next.js app root (package.json lives at repo root)
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const MARKER_PNG = join(SCREENSHOT_DIR, 'search-timeline-marker.png');
const SHOULD_PUSH = process.env.PLAYWRIGHT_GPU_STRIP_PUSH === '1';

const SEARCH_QUERY = 'stage-6.1 timeline marker probe';
const SEARCH_PROVENANCE = 'searxng:http://127.0.0.1:18888';
const SEARCH_RESULT_COUNT = 2;
const SEARCH_LATENCY_MS = 37;

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
    console.log('[search-timeline] START_PROD=1 — building + starting next start on :' + PROD_PORT);
    execFileSync('npm', ['run', 'build'], { cwd: APP_DIR, stdio: 'inherit' });
    nextProc = spawn('npx', ['next', 'start', '-p', String(PROD_PORT)], {
      cwd: APP_DIR,
      stdio: 'inherit',
      env: { ...process.env, NEXT_PUBLIC_BFF_URL: BFF_URL },
      detached: false,
    });
    await waitForPort(PROD_PORT);
  }

  const emitProbe = await request
    .post(`${BFF_URL}/api/search/emit`, {
      data: {
        runId: 'probe',
        query: 'probe',
        resultCount: 0,
        provenance: 'searxng:probe',
        latencyMs: 0,
      },
    })
    .catch(() => null);
  const emitStatus = emitProbe ? emitProbe.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[search-timeline] BFF emit probe status:', emitStatus);
  if (!emitProbe) missing.push(`BFF ${BFF_URL}`);
  else if (emitStatus === 503) {
    missing.push(
      `BFF search emit disabled (503). Restart with FORGE_SEARCH_EMIT_ENABLED=1 ` +
      `or FORGE_SEARXNG_BASE_URL set.`,
    );
  } else if (emitStatus >= 500) {
    missing.push(`BFF emit endpoint returned ${emitStatus}`);
  }

  const agentProbe = await request.get(`${AGENT_URL}/api/tools/`).catch(() => null);
  const agentStatus = agentProbe ? agentProbe.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[search-timeline] agent-server /api/tools status:', agentStatus);
  if (!agentProbe || agentStatus >= 500) missing.push(`agent-server ${AGENT_URL}`);

  const feProbe = await request.get(FRONTEND_URL).catch(() => null);
  // eslint-disable-next-line no-console
  console.log('[search-timeline] FE status:', feProbe ? feProbe.status() : 'null', 'URL=', FRONTEND_URL);
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
        console.log('[search-timeline] reusing existing conversation id:', it.id);
        return it.id;
      }
    }
    // eslint-disable-next-line no-console
    console.log('[search-timeline] no existing conversations; falling back to create-run.');
  }

  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title: 'Stage 6.1 search-timeline-marker',
      agentPresetId: OLLAMA_PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt: 'idle: this run only exists to receive a web_search event.',
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
    '[search-timeline] created new conversation via preset',
    OLLAMA_PRESET_ID,
    'id:', id, 'status:', status,
  );
  return id;
}

async function emitSearch(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
): Promise<void> {
  const res = await request.post(`${BFF_URL}/api/search/emit`, {
    data: {
      runId,
      query: SEARCH_QUERY,
      resultCount: SEARCH_RESULT_COUNT,
      provenance: SEARCH_PROVENANCE,
      latencyMs: SEARCH_LATENCY_MS,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  expect(body?.data?.type).toBe('web_search');
}

async function waitForSearchCard(page: Page): Promise<void> {
  const expectedSummary = `Web searched: "${SEARCH_QUERY}" — ${SEARCH_RESULT_COUNT} result(s)`;
  await expect(page.getByText(expectedSummary)).toBeVisible({ timeout: 30_000 });
  const eventCard = page.getByRole('button', { name: new RegExp('^Web searched:') });
  await expect(eventCard).toBeVisible({ timeout: 5_000 });
  await expect(eventCard.getByText('🔍')).toBeVisible({ timeout: 5_000 });
}

test.describe('Web-search timeline marker — live emit (Stage 6.1)', () => {
  test('emits web_search and renders 🔍 EventCard on run-detail', async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);

    const runId = await pickOrCreateConversation(request);
    // eslint-disable-next-line no-console
    console.log('[search-timeline] runId:', runId);

    await page.goto(`${FRONTEND_URL}/runs/${runId}`, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    await page.waitForTimeout(1_000);

    await emitSearch(request, runId);

    await waitForSearchCard(page);

    await page.screenshot({ path: MARKER_PNG, fullPage: true });
    expect(existsSync(MARKER_PNG), `${MARKER_PNG} missing`).toBeTruthy();

    if (!SHOULD_PUSH) {
      // eslint-disable-next-line no-console
      console.log(
        `[search-timeline] screenshot saved to ${MARKER_PNG}. ` +
          `Set PLAYWRIGHT_GPU_STRIP_PUSH=1 to auto-commit + push.`,
      );
      return;
    }

    const rel = 'screenshots/search-timeline-marker.png';
    execFileSync('git', ['add', '-f', rel], { cwd: REPO_ROOT, stdio: 'inherit' });
    const status = execFileSync('git', ['status', '--porcelain', rel], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (!status.trim()) {
      // eslint-disable-next-line no-console
      console.log('[search-timeline] no change vs HEAD — skipping commit + push');
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
        'Stage 6.1 screenshot: search-timeline-marker (magnifier icon on run-detail)',
      ],
      { cwd: REPO_ROOT, stdio: 'inherit' },
    );
    execFileSync('git', ['push', 'origin', 'main'], { cwd: REPO_ROOT, stdio: 'inherit' });
  });
});
