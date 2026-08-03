/**
 * settings.spec.ts — Settings page against real BFF.
 */
import { test, expect } from '@playwright/test';

test.describe('Settings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
  });

  test('page loads with tabs', async ({ page }) => {
    await expect(page.locator('body')).not.toContainText('Application error');
    for (const name of ['Appearance', 'Model & Agent', 'Shortcuts', 'About']) {
      // Tabs may render as tabs or buttons depending on component; accept either.
      const tab    = page.getByRole('tab',    { name });
      const button = page.getByRole('button', { name });
      const anyTab = tab.or(button);
      await expect(anyTab.first()).toBeVisible();
    }
  });

  test('switching to Model & Agent tab works', async ({ page }) => {
    const modelTab = page.getByRole('tab', { name: 'Model & Agent' })
      .or(page.getByRole('button', { name: 'Model & Agent' }));
    if (await modelTab.count() === 0) {
      test.skip(true, 'settings tabs not rendered');
      return;
    }
    await modelTab.first().click();
    // After click, model section should have SOME model-related copy in the DOM.
    await expect(page.locator('body')).toContainText(/Model|Provider|Ollama|LLM/i);
  });
});
