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
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const AGENT_URL = process.env.PLAYWRIGHT_AGENT_URL || 'http://127.0.0.1:8090';
const FRONTEND_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.PLAYWRIGHT_FRONTEND_URL ||
  'http://127.0.0.1:3100';
const WORKSPACE_ID =
  process.env.FORGE_TEST_WORKSPACE_ID || '18c99443b23c452899010095abd5f29b';
const PRESET_ID = process.env.FORGE_TEST_PRESET_ID || 'ap-1';

const REPO_ROOT = resolve(process.cwd(), '..');
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const MARKER_PNG = join(SCREENSHOT_DIR, 'memory-timeline-marker.png');
const SHOULD_PUSH = process.env.PLAYWRIGHT_GPU_STRIP_PUSH === '1';

const CONSULT_QUERY = 'stage-5.6b timeline marker probe';
const CONSULT_TIER = 'semantic';
const CONSULT_RESULT_COUNT = 2;

test.beforeAll(async ({ request }) => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const missing: string[] = [];

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
  console.log('[memory-timeline] FE status:', feProbe ? feProbe.status() : 'null');
  if (!feProbe || feProbe.status() >= 500) missing.push(`frontend ${FRONTEND_URL}`);

  test.skip(missing.length > 0, `preconditions unmet: ${missing.join(', ')}`);
});

async function createRun(
  request: import('@playwright/test').APIRequestContext,
): Promise<string> {
  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title: 'Stage 5.6b memory-timeline-marker',
      agentPresetId: PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt: 'idle: this run only exists to receive a memory_consultation event.',
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const id = body?.data?.id;
  expect(id, `create_run body missing data.id: ${JSON.stringify(body)}`).toBeTruthy();
  return id as string;
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
  await expect(page.getByText('🧠')).toBeVisible({ timeout: 5_000 });
}

test.describe('Memory timeline marker — live emit (Stage 5.6b)', () => {
  test('emits memory_consultation and renders 🧠 EventCard on run-detail', async ({
    page,
    request,
  }) => {
    test.setTimeout(120_000);

    // 1. Create a real run so the Socket.IO room and run-detail page exist.
    const runId = await createRun(request);
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
