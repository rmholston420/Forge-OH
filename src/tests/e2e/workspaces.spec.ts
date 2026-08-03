/**
 * workspaces.spec.ts — Workspaces page against real BFF.
 */
import { test, expect } from '@playwright/test';

test.describe('Workspaces', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/workspaces');
  });

  test('page loads without app error', async ({ page }) => {
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('new workspace button opens modal', async ({ page }) => {
    // Feature flag may be off; only run if button exists.
    const btn = page.getByRole('button', { name: /New Workspace/i });
    if (await btn.count() === 0) {
      test.skip(true, 'workspaces feature disabled or empty toolbar');
      return;
    }
    await btn.click();
    // The modal is a WorkspaceFormModal — assert some dialog appears.
    await expect(page.getByRole('dialog')).toBeVisible();
  });
});
