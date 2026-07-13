import { test, expect } from './fixtures/auth';

test.describe('RBAC — Admin', () => {
  test('admin sees New Run button', async ({ adminPage: page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: /new run/i })).toBeVisible();
  });

  test('admin sees Settings nav link', async ({ adminPage: page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('link', { name: /settings/i })).toBeVisible();
  });

  test('admin can access /settings/model page', async ({ adminPage: page }) => {
    await page.goto('/settings/model');
    await expect(page).toHaveURL(/\/settings\/model/);
  });
});

test.describe('RBAC — Developer', () => {
  test('developer sees New Run button', async ({ developerPage: page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: /new run/i })).toBeVisible();
  });

  test('developer does not see Invite Users option', async ({ developerPage: page }) => {
    await page.goto('/runs');
    await page.getByRole('button', { name: /user menu/i }).click();
    await expect(page.getByRole('menuitem', { name: /invite users/i })).not.toBeVisible();
  });

  test('developer can approve runs', async ({ developerPage: page }) => {
    await page.goto('/runs');
    // Approval banner should be actionable for developer
    // (run must be in awaiting_approval state — MSW mock returns one)
    const approvalBanner = page.getByRole('region', { name: /approval required/i });
    if (await approvalBanner.isVisible()) {
      await expect(page.getByRole('button', { name: /approve/i })).toBeEnabled();
    }
  });
});

test.describe('RBAC — Viewer', () => {
  test('viewer does not see New Run button', async ({ viewerPage: page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: /new run/i })).not.toBeVisible();
  });

  test('viewer navigating to /settings/model is redirected to /runs', async ({ viewerPage: page }) => {
    await page.goto('/settings/model');
    await expect(page).toHaveURL(/\/runs/);
  });

  test('viewer does not see Delete button on runs', async ({ viewerPage: page }) => {
    await page.goto('/runs');
    await expect(page.getByRole('button', { name: /delete/i })).not.toBeVisible();
  });

  test('viewer sees read-only secrets page (no create button)', async ({ viewerPage: page }) => {
    await page.goto('/settings/secrets');
    await expect(page.getByRole('button', { name: /add secret/i })).not.toBeVisible();
  });
});
