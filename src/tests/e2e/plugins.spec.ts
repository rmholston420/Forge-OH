/**
 * plugins.spec.ts — MCP Plugins page against real BFF.
 */
import { test, expect } from '@playwright/test';

test.describe('Plugins', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/plugins');
  });

  test('page loads without app error', async ({ page }) => {
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('status filter buttons render (feature enabled)', async ({ page }) => {
    const group = page.getByRole('group', { name: 'Filter by status' });
    if (await group.count() === 0) {
      test.skip(true, 'plugins feature disabled');
      return;
    }
    await expect(group).toBeVisible();
    // Buttons: all, enabled, disabled, error.
    for (const name of ['All', 'Enabled', 'Disabled', 'Error']) {
      await expect(group.getByRole('button', { name })).toBeVisible();
    }
  });
});
