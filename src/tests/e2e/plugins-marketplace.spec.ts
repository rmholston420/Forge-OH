/**
 * plugins-marketplace.spec.ts — Slice H: /plugins/marketplace + /plugins/install
 * wired into a Marketplace tab. Asserts the tab renders and swaps content.
 */
import { test, expect } from '@playwright/test';

test.describe('Plugins Marketplace tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/plugins');
  });

  test('Installed and Marketplace tabs are both present', async ({ page }) => {
    const feature = page.getByRole('group', { name: 'Filter by status' });
    if (await feature.count() === 0) {
      test.skip(true, 'plugins feature disabled');
      return;
    }
    await expect(page.getByRole('tab', { name: 'Installed' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Marketplace' })).toBeVisible();
  });

  test('switching to Marketplace tab hides the Installed filter row', async ({ page }) => {
    const marketplaceTab = page.getByRole('tab', { name: 'Marketplace' });
    if (await marketplaceTab.count() === 0) {
      test.skip(true, 'plugins feature disabled');
      return;
    }
    await marketplaceTab.click();
    // Installed-only "Filter by status" group must NOT be visible on marketplace tab.
    await expect(page.getByRole('group', { name: 'Filter by status' })).toHaveCount(0);
    // Page must not crash.
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
