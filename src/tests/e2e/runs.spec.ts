/**
 * runs.spec.ts
 *
 * Runs Home flows against real BFF.  Assertions kept tolerant of empty
 * lists (BFF may have zero runs) — the runs list container is either
 * populated or replaced by an empty-state.
 */
import { test, expect } from '@playwright/test';

test.describe('Runs Home', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/runs');
  });

  test('page loads with heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible();
  });

  test('search input is present and focusable', async ({ page }) => {
    const search = page.getByRole('searchbox', { name: 'Search runs' });
    await expect(search).toBeVisible();
    await search.fill('nonexistent-run-xyz');
    // Filter is client-side; assertion is only that fill did not throw.
    await expect(search).toHaveValue('nonexistent-run-xyz');
  });

  test('status and workspace filters render', async ({ page }) => {
    await expect(page.getByRole('combobox', { name: 'Filter by status' })).toBeVisible();
    await expect(page.getByRole('combobox', { name: 'Filter by workspace type' })).toBeVisible();
  });

  test('list container or empty state is visible', async ({ page }) => {
    const list  = page.getByRole('list',   { name: 'Runs' });
    const empty = page.getByRole('status'); // EmptyState uses role=status
    await expect(list.or(empty)).toBeVisible();
  });

  test('new run button opens composer modal', async ({ page }) => {
    const btn = page.getByRole('button', { name: /New Run/i });
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page.getByRole('dialog', { name: /New Run/i })).toBeVisible();
    // Close via Escape.
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: /New Run/i })).not.toBeVisible();
  });
});
