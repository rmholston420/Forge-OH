import { test, expect } from '@playwright/test';

test('shell renders and redirects to /runs', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/runs/);
});

test('sidebar is visible', async ({ page }) => {
  await page.goto('/runs');
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
});

test('all nav routes resolve without errors', async ({ page }) => {
  const routes = ['/runs', '/agents', '/workspaces', '/tools-mcp', '/plugins', '/observability', '/settings'];
  for (const route of routes) {
    await page.goto(route);
    await expect(page).not.toHaveURL('/404');
    await expect(page.locator('body')).not.toContainText('Application error');
  }
});

test('command palette opens with Cmd+K', async ({ page }) => {
  await page.goto('/runs');
  await page.keyboard.press('Meta+k');
  await expect(page.getByRole('dialog', { name: 'Command palette' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Command palette' })).not.toBeVisible();
});

test('sidebar collapse toggle works', async ({ page }) => {
  await page.goto('/runs');
  const toggle = page.getByRole('button', { name: /collapse sidebar/i });
  await toggle.click();
  const expandToggle = page.getByRole('button', { name: /expand sidebar/i });
  await expect(expandToggle).toBeVisible();
});
