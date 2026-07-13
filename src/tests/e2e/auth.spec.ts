import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('shows validation errors on empty submit', async ({ page }) => {
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByText(/valid email/i)).toBeVisible();
  });

  test('shows validation error for invalid email format', async ({ page }) => {
    await page.getByLabel('Email').fill('not-an-email');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByText(/valid email/i)).toBeVisible();
  });

  test('shows validation error for short password', async ({ page }) => {
    await page.getByLabel('Email').fill('admin@forge.dev');
    await page.getByLabel('Password').fill('short');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByText(/at least 8 characters/i)).toBeVisible();
  });

  test('successful login redirects to /runs', async ({ page }) => {
    await page.getByLabel('Email').fill('admin@forge.dev');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/runs/);
  });

  test('wrong credentials shows error banner', async ({ page }) => {
    await page.getByLabel('Email').fill('admin@forge.dev');
    await page.getByLabel('Password').fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByRole('alert')).toContainText(/invalid email or password/i);
  });

  test('logout clears session and redirects to /login', async ({ page }) => {
    // First log in
    await page.getByLabel('Email').fill('admin@forge.dev');
    await page.getByLabel('Password').fill('password123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL(/\/runs/);
    // Sign out via user menu
    await page.getByRole('button', { name: /user menu/i }).click();
    await page.getByRole('menuitem', { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test('unauthenticated user is redirected to /login with callbackUrl', async ({ page }) => {
    await page.goto('/runs');
    await expect(page).toHaveURL(/\/login.*callbackUrl/);
  });
});
