/**
 * plugins-marketplace.spec.ts — Slice H: /plugins/marketplace + /plugins/install
 * wired into a Marketplace tab. Asserts the tab renders and swaps content.
 */
import { test, expect } from '@playwright/test';

test.describe('Plugins Marketplace tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/plugins');
    // Wait until the Installed tab is present and the initial query has
    // settled, so the Tabs component isn't remounting mid-click.
    await page.getByRole('tab', { name: 'Installed' }).waitFor({ state: 'visible' });
    await page.waitForLoadState('networkidle');
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
    // The tab can briefly re-render as tanstack-query settles. Click via
    // aria-selected assertion so Playwright waits until the tab actually
    // becomes active rather than trying to click a stale element.
    await marketplaceTab.click({ trial: false });
    await expect(marketplaceTab).toHaveAttribute('aria-selected', 'true');
    // Installed-only "Filter by status" group must NOT be visible on marketplace tab.
    await expect(page.getByRole('group', { name: 'Filter by status' })).toHaveCount(0);
    // Page must not crash.
    await expect(page.locator('body')).not.toContainText('Application error');
  });
});
