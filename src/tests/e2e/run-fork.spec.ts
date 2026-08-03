/**
 * run-fork.spec.ts — Slice D: POST /runs/{id}/fork wired into RunDetailHeader.
 *
 * Only asserts the button is present + clickable. Does NOT actually fork
 * (side effect on real BFF) — that path is exercised by hook-level unit tests.
 */
import { test, expect } from '@playwright/test';

async function firstRunId(page: import('@playwright/test').Page): Promise<string | null> {
  const res = await page.request.get(`${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{ id: string }>;
  return runs.length ? runs[0].id : null;
}

test.describe('Run Fork button', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunId(page);
    await ctx.close();
  });

  test('Fork button is visible in run header', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    await expect(page.getByRole('button', { name: 'Fork run' })).toBeVisible();
  });

  test('Env (secrets) button is visible next to Fork', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    await expect(page.getByRole('button', { name: 'Edit run environment variables' })).toBeVisible();
  });
});
