/**
 * run-model-switch.spec.ts — Stage 6.5.2 (ADR-027)
 *
 * Verifies the model-switch modal is wired into the run-detail header.
 * We do NOT trigger an actual model switch here — that has real side
 * effects on the running agent-server conversation. Unit tests exercise
 * the 200/404/422/503 branches via MSW.
 *
 * The button only renders when the run is running or paused (see
 * RunDetailHeader logic), so if no eligible run is present we skip
 * cleanly instead of failing.
 */
import { test, expect } from '@playwright/test';

async function firstRunningOrPausedRunId(
  page: import('@playwright/test').Page,
): Promise<string | null> {
  const res = await page.request.get(
    `${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`,
  );
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{
    id: string;
    status: string;
  }>;
  const eligible = runs.find(
    (r) =>
      r.status === 'running' || r.status === 'streaming' || r.status === 'paused',
  );
  return eligible ? eligible.id : null;
}

test.describe('Run model-switch button (Stage 6.5.2 · ADR-027)', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunningOrPausedRunId(page);
    await ctx.close();
  });

  test('Switch model button is visible on a running or paused run', async ({
    page,
  }) => {
    test.skip(!runId, 'no running or paused run on BFF');
    await page.goto(`/runs/${runId!}`);
    await expect(page.getByRole('button', { name: 'Switch model' })).toBeVisible();
  });

  test('Clicking the button opens the modal with the preset picker', async ({
    page,
  }) => {
    test.skip(!runId, 'no running or paused run on BFF');
    await page.goto(`/runs/${runId!}`);
    await page.getByRole('button', { name: 'Switch model' }).click();
    // Modal heading and the picker <select> should both be present.
    await expect(
      page.getByRole('heading', { name: /switch model/i }),
    ).toBeVisible();
    await expect(page.getByLabel(/target agent preset/i)).toBeVisible();
    // Cancel dismisses without side effects.
    await page.getByRole('button', { name: /cancel/i }).click();
    await expect(
      page.getByRole('heading', { name: /switch model/i }),
    ).toHaveCount(0);
  });
});
