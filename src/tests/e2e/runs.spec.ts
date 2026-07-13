import { test, expect } from '@playwright/test';

test('runs page loads with run list or empty state', async ({ page }) => {
  await page.goto('/runs');
  const list = page.getByRole('list', { name: 'Runs' });
  const empty = page.getByRole('status');
  await expect(list.or(empty)).toBeVisible();
});

test('new run button opens modal', async ({ page }) => {
  await page.goto('/runs');
  const btn = page.getByRole('button', { name: 'New Run' });
  await btn.click();
  await expect(page.getByRole('dialog', { name: 'New Run' })).toBeVisible();
});

test('status filter renders options', async ({ page }) => {
  await page.goto('/runs');
  const filterSelect = page.getByRole('combobox', { name: 'Filter by status' });
  await expect(filterSelect).toBeVisible();
});
