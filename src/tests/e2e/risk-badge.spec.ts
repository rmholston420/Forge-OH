/**
 * risk-badge.spec.ts — Stage 3.1 visual verification.
 *
 * Verifies:
 *   1. RiskBadge renders on ActionEvents when securityRisk is LOW/MEDIUM/HIGH.
 *   2. RiskBadge hides on securityRisk=UNKNOWN or absent.
 *   3. Auto-collapse toggle hides UNKNOWN/absent action events from the timeline.
 *
 * Uses route-mocking to inject deterministic events; does NOT require a
 * live agent-server session. Runs against the prod frontend.
 */
import { test, expect, Page } from '@playwright/test';

const FRONTEND_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.PLAYWRIGHT_FRONTEND_URL ||
  'http://127.0.0.1:3000';
const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';

const FAKE_RUN_ID = 'stage3-risk-badge-fixture';

const FAKE_RUN = {
  data: {
    id: FAKE_RUN_ID,
    title: 'Stage 3.1 risk-badge fixture',
    status: 'succeeded',
    createdAt: '2026-08-05T22:00:00Z',
    updatedAt: '2026-08-05T22:05:00Z',
    workspaceId: 'ws-fixture',
    agentPresetId: 'ap-1',
  },
};

const FAKE_EVENTS = {
  events: [
    {
      id: 'evt-msg-1',
      type: 'message',
      timestamp: '2026-08-05T22:00:01Z',
      source: 'user',
      summary: 'Please clean up /tmp',
    },
    {
      id: 'evt-act-high',
      type: 'action',
      timestamp: '2026-08-05T22:00:02Z',
      source: 'agent',
      summary: 'terminal: rm -rf /tmp/*',
      securityRisk: 'HIGH',
    },
    {
      id: 'evt-act-medium',
      type: 'action',
      timestamp: '2026-08-05T22:00:03Z',
      source: 'agent',
      summary: 'terminal: chmod -R 777 /var',
      securityRisk: 'MEDIUM',
    },
    {
      id: 'evt-act-low',
      type: 'action',
      timestamp: '2026-08-05T22:00:04Z',
      source: 'agent',
      summary: 'terminal: ls -la',
      securityRisk: 'LOW',
    },
    {
      id: 'evt-act-unknown',
      type: 'action',
      timestamp: '2026-08-05T22:00:05Z',
      source: 'agent',
      summary: 'terminal: echo hi',
      securityRisk: 'UNKNOWN',
    },
    {
      id: 'evt-act-nofield',
      type: 'action',
      timestamp: '2026-08-05T22:00:06Z',
      source: 'agent',
      summary: 'terminal: pwd',
    },
  ],
  total: 6,
  latestEventId: 6,
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

test.describe('Stage 3.1 RiskBadge + auto-collapse', () => {
  test.beforeAll(async () => {
    const ok = await bffReachable();
    test.skip(!ok, `BFF unreachable at ${BFF_URL}/api/inference-backends`);
  });

  test.beforeEach(async ({ page }) => {
    // Intercept the run-detail + events fetches for the fixture run id.
    await page.route(`**/api/runs/${FAKE_RUN_ID}`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(FAKE_RUN) }),
    );
    await page.route(`**/api/runs/${FAKE_RUN_ID}/events**`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(FAKE_EVENTS) }),
    );
  });

  test('renders LOW/MEDIUM/HIGH badges and hides UNKNOWN/absent', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/runs/${FAKE_RUN_ID}`);

    // Wait for timeline to render at least one event card.
    await expect(page.getByText('terminal: rm -rf /tmp/*')).toBeVisible({ timeout: 15_000 });

    // Three risk chips must render (LOW/MEDIUM/HIGH).
    await expect(page.getByLabel('Security risk: high risk')).toBeVisible();
    await expect(page.getByLabel('Security risk: medium risk')).toBeVisible();
    await expect(page.getByLabel('Security risk: low risk')).toBeVisible();

    // UNKNOWN + absent must NOT render any risk chip.
    await expect(page.getByLabel('Security risk: unknown risk')).toHaveCount(0);
    // Total risk chips == 3.
    await expect(page.locator('[role="status"][aria-label^="Security risk:"]')).toHaveCount(3);

    await pushScreenshot(page, 'stage3-1-risk-badges');
  });

  test('auto-collapse toggle hides UNKNOWN/absent action events', async ({ page }) => {
    await page.goto(`${FRONTEND_URL}/runs/${FAKE_RUN_ID}`);

    await expect(page.getByText('terminal: rm -rf /tmp/*')).toBeVisible({ timeout: 15_000 });

    // Before toggle: unknown/no-field actions are visible.
    await expect(page.getByText('terminal: echo hi')).toBeVisible();
    await expect(page.getByText('terminal: pwd')).toBeVisible();

    // Flip the toggle on.
    await page.getByLabel('Auto-collapse low-risk actions').check();

    // After toggle: LOW/MEDIUM/HIGH still visible; UNKNOWN + absent hidden.
    await expect(page.getByText('terminal: rm -rf /tmp/*')).toBeVisible();
    await expect(page.getByText('terminal: chmod -R 777 /var')).toBeVisible();
    await expect(page.getByText('terminal: ls -la')).toBeVisible();
    await expect(page.getByText('terminal: echo hi')).toHaveCount(0);
    await expect(page.getByText('terminal: pwd')).toHaveCount(0);

    // Message events (non-action) still visible.
    await expect(page.getByText('Please clean up /tmp')).toBeVisible();

    // "2 hidden" badge.
    await expect(page.getByText(/2 hidden/i)).toBeVisible();

    await pushScreenshot(page, 'stage3-1-auto-collapse');
  });
});
