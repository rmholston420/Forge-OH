import { test, expect } from '@playwright/test';

test.describe('Secrets vault', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/settings/secrets');
  });

  test('page loads with correct heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Secrets' })).toBeVisible();
  });

  test('Add Secret button opens modal', async ({ page }) => {
    await page.getByRole('button', { name: '+ Add Secret' }).click();
    await expect(page.getByRole('dialog', { name: 'Add Secret' })).toBeVisible();
  });

  test('modal form validates required fields', async ({ page }) => {
    await page.getByRole('button', { name: '+ Add Secret' }).click();
    await page.getByRole('button', { name: 'Add Secret' }).click();
    // Name and value are required
    await expect(page.getByRole('alert').first()).toBeVisible();
  });

  test('secret value field type is password (never reveals raw input)', async ({ page }) => {
    await page.getByRole('button', { name: '+ Add Secret' }).click();
    const valueInput = page.getByLabel('Value');
    await expect(valueInput).toHaveAttribute('type', 'password');
  });

  test('search filter narrows visible rows', async ({ page }) => {
    // With MSW mocks active this tests client-side filtering
    const searchInput = page.getByLabel('Search secrets by name');
    await searchInput.fill('NONEXISTENT_SECRET_XYZ');
    await expect(page.getByText('No secrets match your search')).toBeVisible();
  });
});
