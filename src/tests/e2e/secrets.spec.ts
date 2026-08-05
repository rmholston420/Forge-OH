/**
 * secrets.spec.ts
 *
 * Real Secrets page at /secrets (Stage 1.3 reconciliation-plan-v1 wired
 * the sidebar entry and removed the redundant /settings/secrets stub).
 * The page renders the real SecretsPage feature component; values
 * remain masked in the DOM.
 */
import { test, expect } from '@playwright/test';

test.describe('Secrets', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/secrets');
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
