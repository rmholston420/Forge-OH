import { test, expect } from '@playwright/test';

test('run detail page loads for a run', async ({ page }) => {
  await page.goto('/runs/run-001');
  await expect(page.locator('h1')).toBeVisible();
});

test('run detail tabs are navigable', async ({ page }) => {
  await page.goto('/runs/run-001');
  const overviewTab = page.getByRole('tab', { name: 'Overview' });
  await expect(overviewTab).toBeVisible();
  await overviewTab.click();
  await expect(overviewTab).toHaveAttribute('aria-selected', 'true');
});
