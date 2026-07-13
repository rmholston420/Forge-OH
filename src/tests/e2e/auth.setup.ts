import { test as setup, expect } from '@playwright/test';

const authFile = '.auth/user.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'domcontentloaded' });

  await page.locator('input[type="email"], input[name="email"]').first().fill('admin@forge.dev');
  await page.locator('input[type="password"], input[name="password"]').first().fill('password123');
  await page.locator('button[type="submit"]').first().click();

  await page.waitForURL(/\/runs/, { timeout: 10000 });
  await expect(page).toHaveURL(/\/runs/);

  await page.context().storageState({ path: authFile });
});
