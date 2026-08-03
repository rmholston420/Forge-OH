/**
 * secrets.spec.ts
 *
 * /settings/secrets is currently an EmptyState stub in the shipped app.
 * This spec asserts THAT ACTUAL BEHAVIOR (per user instruction:
 * "make the optimal choices. what is important is that the app actually
 *  works for real."). When secrets are implemented, this file should be
 * expanded with real CRUD flows.
 */
import { test, expect } from '@playwright/test';

test.describe('Secrets (stub)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings/secrets');
  });

  test('page loads with heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Secrets/i })).toBeVisible();
  });

  test('page never leaks secret values in DOM even in stub state', async ({ page }) => {
    const bodyText = await page.locator('body').innerText();
    // Guardrail: no obvious credential-looking substrings anywhere on this page.
    expect(bodyText).not.toMatch(/ghp_[A-Za-z0-9]{20,}/);
    expect(bodyText).not.toMatch(/sk-[A-Za-z0-9]{20,}/);
  });
});
