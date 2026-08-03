/**
 * run-secrets-modal.spec.ts — Slice E: POST /runs/{id}/secrets wired into
 * RunSecretsModal (per-run env vars UI). Asserts the modal opens with the
 * expected fields; does NOT submit (would mutate BFF state).
 */
import { test, expect } from '@playwright/test';

async function firstRunId(page: import('@playwright/test').Page): Promise<string | null> {
  const res = await page.request.get(`${process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081'}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{ id: string }>;
  return runs.length ? runs[0].id : null;
}

test.describe('Run Secrets modal', () => {
  let runId: string | null = null;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunId(page);
    await ctx.close();
  });

  test('clicking Env opens the run environment variables modal', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    await page.getByRole('button', { name: 'Edit run environment variables' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText(/environment variables/i);
  });

  test('modal exposes a first key/value input pair', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    await page.goto(`/runs/${runId!}`);
    await page.getByRole('button', { name: 'Edit run environment variables' }).click();
    await expect(page.getByLabel('Secret 1 key')).toBeVisible();
    await expect(page.getByLabel('Secret 1 value')).toBeVisible();
  });
});
