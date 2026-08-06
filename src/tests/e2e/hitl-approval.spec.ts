/**
 * hitl-approval.spec.ts — Stage 3.2 visual verification.
 *
 * Verifies:
 *   1. ApprovalBanner renders when the run status is `awaiting_approval`
 *      (canonical form used everywhere post-hygiene-unification).
 *   2. Approve button POSTs /api/runs/:id/approve.
 *   3. Reject button POSTs /api/runs/:id/reject.
 *
 * Uses route-mocking to inject deterministic run + events + intercept the
 * resume/reject POSTs. Does NOT require a live agent-server session.
 * Runs against the prod frontend.
 */
import { test, expect, Page, Request } from '@playwright/test';

const FRONTEND_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.PLAYWRIGHT_FRONTEND_URL ||
  'http://127.0.0.1:3000';
const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';

const FAKE_RUN_ID = 'stage3-hitl-fixture';

// Envelope MUST match fetchRun: json.data is unwrapped. Fields mirror
// RunSummarySchema (src/lib/schemas/run.ts). Status is `awaiting_approval`
// (underscore) — the canonical form emitted by the BFF _STATUS_MAP and
// declared in RunStatusSchema after post-Stage-3 hygiene unification.
const FAKE_RUN_AWAITING = {
  data: {
    id: FAKE_RUN_ID,
    title: 'Stage 3.2 HITL fixture',
    status: 'awaiting_approval',
    agentPresetName: 'default',
    workspaceId: 'ws-fixture',
    workspaceType: 'local',
    activeTool: 'terminal',
    createdAt: '2026-08-05T22:00:00Z',
    updatedAt: '2026-08-05T22:05:00Z',
    elapsedMs: 42_000,
    estimatedCostUsd: 0,
  },
};

const FAKE_EVENTS_PAUSED = {
  data: [
    {
      id: 'evt-msg-1',
      type: 'message',
      timestamp: '2026-08-05T22:00:01Z',
      source: 'user',
      summary: 'delete the temp files',
    },
    {
      id: 'evt-act-medium',
      type: 'action',
      timestamp: '2026-08-05T22:00:02Z',
      source: 'agent',
      summary: 'terminal: rm -rf /tmp/scratch',
      securityRisk: 'MEDIUM',
    },
  ],
};

async function bffReachable(): Promise<boolean> {
  try {
    const r = await fetch(`${BFF_URL}/api/inference-backends`);
    return r.ok;
  } catch {
    return false;
  }
}

async function pushScreenshot(page: Page, name: string): Promise<void> {
  if (process.env.PLAYWRIGHT_GPU_STRIP_PUSH !== '1') return;
  await page.screenshot({ path: `screenshots/${name}.png`, fullPage: false });
}

test.describe('Stage 3.2 HITL ApprovalBanner', () => {
  test.beforeAll(async () => {
    const ok = await bffReachable();
    test.skip(!ok, `BFF unreachable at ${BFF_URL}/api/inference-backends`);
  });

  test.beforeEach(async ({ page }) => {
    await page.route(`**/api/runs/${FAKE_RUN_ID}/events**`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(FAKE_EVENTS_PAUSED),
      }),
    );
    await page.route(`**/api/runs/${FAKE_RUN_ID}`, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(FAKE_RUN_AWAITING),
      }),
    );
    // Stub Socket.IO handshake so useRunStream can't 404 loudly.
    await page.route('**/socket.io/**', (route) =>
      route.fulfill({ status: 200, contentType: 'text/plain', body: '' }),
    );
  });

  test('renders ApprovalBanner when run status is awaiting_approval', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        console.log(`[browser ${msg.type()}]`, msg.text());
      }
    });
    page.on('pageerror', (err) => console.log('[pageerror]', err.message));

    await page.goto(`${FRONTEND_URL}/runs/${FAKE_RUN_ID}`);

    // Timeline must load first.
    await expect(page.getByText('terminal: rm -rf /tmp/scratch')).toBeVisible({ timeout: 15_000 });

    // ApprovalBanner announces via role=alert + aria-live=assertive.
    // Scope by hasText to avoid strict-mode collision with Next.js's
    // built-in `__next-route-announcer__` (also role=alert, aria-live).
    const banner = page.getByRole('alert').filter({ hasText: /awaiting your approval/i });
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('Agent is awaiting your approval');

    // Both Approve + Reject buttons render.
    await expect(page.getByLabel('Approve agent action')).toBeVisible();
    await expect(page.getByLabel('Reject agent action')).toBeVisible();

    await pushScreenshot(page, 'stage3-2-approval-banner');
  });

  test('Approve button POSTs /api/runs/:id/approve', async ({ page }) => {
    const approveCalls: Request[] = [];
    await page.route(`**/api/runs/${FAKE_RUN_ID}/approve`, (route) => {
      approveCalls.push(route.request());
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { ok: true } }),
      });
    });

    await page.goto(`${FRONTEND_URL}/runs/${FAKE_RUN_ID}`);
    // Wait for the ApprovalBanner Approve button rather than role=alert
    // (Next.js route announcer also uses role=alert).
    await expect(page.getByLabel('Approve agent action')).toBeVisible({ timeout: 15_000 });

    await page.getByLabel('Approve agent action').click();

    // Wait one tick for the mutation to fire.
    await expect(async () => {
      expect(approveCalls.length).toBeGreaterThanOrEqual(1);
    }).toPass({ timeout: 5_000 });

    expect(approveCalls[0].method()).toBe('POST');
  });

  test('Reject button POSTs /api/runs/:id/reject', async ({ page }) => {
    const rejectCalls: Request[] = [];
    await page.route(`**/api/runs/${FAKE_RUN_ID}/reject`, (route) => {
      rejectCalls.push(route.request());
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { ok: true } }),
      });
    });

    await page.goto(`${FRONTEND_URL}/runs/${FAKE_RUN_ID}`);
    await expect(page.getByLabel('Reject agent action')).toBeVisible({ timeout: 15_000 });

    await page.getByLabel('Reject agent action').click();

    await expect(async () => {
      expect(rejectCalls.length).toBeGreaterThanOrEqual(1);
    }).toPass({ timeout: 5_000 });

    expect(rejectCalls[0].method()).toBe('POST');
  });
});
