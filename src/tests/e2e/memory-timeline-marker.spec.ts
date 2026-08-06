/**
 * memory-timeline-marker.spec.ts — Stage 5.6b live-task DoD screenshot.
 *
 * Verifies that the ``consult_memory`` tool's bridge endpoint
 * (``POST /api/memory/emit-consultation``) causes a ``memory_consultation``
 * event with the 🧠 icon to appear on the run-detail timeline, then
 * captures a screenshot for the plan §5.6.4 evidence.
 *
 * Design (why this shape, not driving the tool from inside the agent):
 *   * The tool is registered inside the agent-server process (:8090) via
 *     ``--import-modules openhands_tools_ext.memory.tools.consult_memory``
 *     (see scripts/forge-up.sh) and is exercised by the unit test suite.
 *   * For the visual DoD we deterministically POST the same bridge
 *     endpoint the tool calls, using a real run id returned by the BFF.
 *     This isolates the frontend contract without depending on the
 *     agent's own decision to call the tool.
 *
 * Preconditions (verified in beforeAll):
 *   * BFF up on :8081 with memory emit enabled (env-gated OR MemoryPort
 *     composed via NEO4J_PASSWORD).
 *   * agent-server up on :8090 so /api/runs create returns a real run id.
 *   * prod frontend up on :3100 (``next start``, never ``next dev``).
 *
 * Screenshot output (auto-pushed when PLAYWRIGHT_GPU_STRIP_PUSH=1):
 *   screenshots/memory-timeline-marker.png  run-detail with 🧠 event card
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
const PRESET_ID = process.env.FORGE_TEST_PRESET_ID || 'ap-1';

const REPO_ROOT = resolve(process.cwd(), '..');
const APP_DIR = process.cwd(); // <repo>/src
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const MARKER_PNG = join(SCREENSHOT_DIR, 'memory-timeline-marker.png');
const SHOULD_PUSH = process.env.PLAYWRIGHT_GPU_STRIP_PUSH === '1';

const CONSULT_QUERY = 'stage-5.6b timeline marker probe';
const CONSULT_TIER = 'semantic';
const CONSULT_RESULT_COUNT = 2;

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
    console.log('[memory-timeline] START_PROD=1 — building + starting next start on :' + PROD_PORT);
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
    .post(`${BFF_URL}/api/memory/emit-consultation`, {
      data: { runId: 'probe', tier: 'semantic', query: 'probe', resultCount: 0 },
    })
    .catch(() => null);
  const emitStatus = emitProbe ? emitProbe.status() : 0;
  // 200 = enabled and reachable; 503 = feature-gated off, actionable message.
  // eslint-disable-next-line no-console
  console.log('[memory-timeline] BFF emit probe status:', emitStatus);
  if (!emitProbe) missing.push(`BFF ${BFF_URL}`);
  else if (emitStatus === 503) {
    missing.push(
      `BFF memory emit disabled (503). Restart with FORGE_MEMORY_EMIT_ENABLED=1 ` +
      `or NEO4J_PASSWORD set so the MemoryPort composes.`,
    );
  } else if (emitStatus >= 500) {
    missing.push(`BFF emit endpoint returned ${emitStatus}`);
  }

  const agentProbe = await request.get(`${AGENT_URL}/api/tools/`).catch(() => null);
  const agentStatus = agentProbe ? agentProbe.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[memory-timeline] agent-server /api/tools status:', agentStatus);
  if (!agentProbe || agentStatus >= 500) missing.push(`agent-server ${AGENT_URL}`);

  const feProbe = await request.get(FRONTEND_URL).catch(() => null);
  // eslint-disable-next-line no-console
  console.log('[memory-timeline] FE status:', feProbe ? feProbe.status() : 'null', 'URL=', FRONTEND_URL);
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

/**
 * Resolve a real agent-server conversation id to use as the ``runId``.
 *
 * Strategy:
 *  1. Prefer reusing an existing agent-server conversation — fastest
 *     and free of side effects.
 *  2. Otherwise, create a fresh run through the BFF using the Ollama
 *     fallback preset (``ap-3``). Ollama runs on :11434 and is always
 *     up on Colossus; this decouples the DoD from vLLM state without
 *     requiring an extra debug endpoint on the BFF.
 */
const OLLAMA_PRESET_ID = process.env.FORGE_TEST_OLLAMA_PRESET_ID || 'ap-3';

async function pickOrCreateConversation(
  request: import('@playwright/test').APIRequestContext,
): Promise<string> {
  // 1. Try to reuse.
  const listResp = await request.get(`${AGENT_URL}/api/conversations`).catch(() => null);
  if (listResp && listResp.ok()) {
    const body = await listResp.json();
    const items: Array<{ id?: string }> = Array.isArray(body)
      ? body
      : (body?.items ?? body?.data ?? []);
    for (const it of items) {
      if (it && typeof it.id === 'string' && it.id.length > 0) {
        // eslint-disable-next-line no-console
        console.log('[memory-timeline] reusing existing conversation id:', it.id);
        return it.id;
      }
    }
    // eslint-disable-next-line no-console
    console.log('[memory-timeline] no existing conversations; falling back to create-run.');
  }

  // 2. Create via BFF using the Ollama fallback preset (ap-3).
  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title: 'Stage 5.6b memory-timeline-marker',
      agentPresetId: OLLAMA_PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt: 'idle: this run only exists to receive a memory_consultation event.',
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
    '[memory-timeline] created new conversation via preset',
    OLLAMA_PRESET_ID,
    'id:', id, 'status:', status,
  );
  return id;
}

async function emitConsultation(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
): Promise<void> {
  const res = await request.post(`${BFF_URL}/api/memory/emit-consultation`, {
    data: {
      runId,
      tier: CONSULT_TIER,
      query: CONSULT_QUERY,
      resultCount: CONSULT_RESULT_COUNT,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  expect(body?.data?.type).toBe('memory_consultation');
}

async function waitForBrainCard(page: Page): Promise<void> {
  // The EventCard renders `summary` verbatim; the 🧠 icon is applied via
  // EVENT_ICONS[event.type]. Wait for the exact summary text so we don't
  // race the socket handshake.
  const expectedSummary = `Memory consulted (semantic): "${CONSULT_QUERY}" — ${CONSULT_RESULT_COUNT} result(s)`;
  await expect(page.getByText(expectedSummary)).toBeVisible({ timeout: 30_000 });
  // Scope the 🧠 assertion to the EventCard button (accessible name is
  // the summary text). Bare getByText('🧠') would match the sidebar
  // Memory nav icon and other decorative uses.
  const eventCard = page.getByRole('button', { name: new RegExp('^Memory consulted \\(semantic\\)') });
  await expect(eventCard).toBeVisible({ timeout: 5_000 });
  await expect(eventCard.getByText('🧠')).toBeVisible({ timeout: 5_000 });
}

test.describe('Memory timeline marker — live emit (Stage 5.6b)', () => {
  test('emits memory_consultation and renders 🧠 EventCard on run-detail', async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);

    // 1. Resolve a real conversation id so the Socket.IO room and
    //    run-detail page exist. We reuse any existing agent-server
    //    conversation — creating a NEW one through BFF /api/runs
    //    requires vLLM/Ollama routing to be up, which is outside the
    //    scope of this memory-marker DoD.
    const runId = await pickOrCreateConversation(request);
    // eslint-disable-next-line no-console
    console.log('[memory-timeline] runId:', runId);

    // 2. Navigate to run-detail BEFORE emitting so the socket is joined
    //    and the client is listening on the conversationId=<runId> room.
    await page.goto(`${FRONTEND_URL}/runs/${runId}`, { waitUntil: 'domcontentloaded' });
    // Wait for the run-detail heading so we know the page has hydrated
    // and useRunStream has had a chance to open its socket.
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    // Give socket.io-client one round-trip to complete its connect handshake.
    await page.waitForTimeout(1_000);

    // 3. Emit the consultation via the same bridge endpoint the tool uses.
    await emitConsultation(request, runId);

    // 4. Assert the 🧠 EventCard shows up with the expected summary.
    await waitForBrainCard(page);

    // 5. Screenshot the timeline pane (full page is fine — the card is
    //    the newest entry, so it will be visible near the top).
    await page.screenshot({ path: MARKER_PNG, fullPage: true });
    expect(existsSync(MARKER_PNG), `${MARKER_PNG} missing`).toBeTruthy();

    if (!SHOULD_PUSH) {
      // eslint-disable-next-line no-console
      console.log(
        `[memory-timeline] screenshot saved to ${MARKER_PNG}. ` +
          `Set PLAYWRIGHT_GPU_STRIP_PUSH=1 to auto-commit + push.`,
      );
      return;
    }

    const rel = 'screenshots/memory-timeline-marker.png';
    execFileSync('git', ['add', '-f', rel], { cwd: REPO_ROOT, stdio: 'inherit' });
    const status = execFileSync('git', ['status', '--porcelain', rel], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (!status.trim()) {
      // eslint-disable-next-line no-console
      console.log('[memory-timeline] no change vs HEAD — skipping commit + push');
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
        'Stage 5.6b screenshot: memory-timeline-marker (brain icon on run-detail)',
      ],
      { cwd: REPO_ROOT, stdio: 'inherit' },
    );
    execFileSync('git', ['push', 'origin', 'main'], { cwd: REPO_ROOT, stdio: 'inherit' });
  });
});
