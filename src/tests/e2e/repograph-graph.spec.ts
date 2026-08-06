/**
 * repograph-graph.spec.ts
 *
 * Stage 4.3 E2E — standalone /repograph route renders the panel, the
 * List/Graph toggle switches modes, and the sidebar link is present.
 *
 * Skips gracefully if the feature flag is off or the BFF isn't reachable.
 */
import { test, expect } from '@playwright/test';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';

async function repographReachable(page: import('@playwright/test').Page): Promise<boolean> {
  try {
    const res = await page.request.get(`${BFF_URL}/api/repograph/health`);
    if (!res.ok()) return false;
    const body = await res.json();
    return Boolean(body?.enabled) && Boolean(body?.reachable);
  } catch {
    return false;
  }
}

test.describe('RepoGraph standalone /repograph route', () => {
  test('renders the panel and the sidebar entry', async ({ page }) => {
    if (!(await repographReachable(page))) test.skip();

    await page.goto('/repograph');
    await expect(page.getByTestId('repograph-page')).toBeVisible();
    // Panel is either enabled (mounted) or disabled — assert one of them
    // rather than requiring the feature flag be on in every env.
    const enabled = page.getByTestId('repograph-panel');
    const disabled = page.getByTestId('repograph-panel-disabled');
    await expect(enabled.or(disabled)).toBeVisible();

    // Sidebar link
    await expect(page.getByRole('link', { name: /RepoGraph/i })).toBeVisible();
  });

  test('List/Graph toggle appears after an index and switches views', async ({
    page,
  }) => {
    if (!(await repographReachable(page))) test.skip();
    // The flag needs to be on for the panel to mount its inner state.
    if (process.env.NEXT_PUBLIC_FEATURE_REPOGRAPH !== 'true') test.skip();

    await page.goto('/repograph');
    await expect(page.getByTestId('repograph-panel')).toBeVisible();

    // Kick an index using the default path prefill.
    await page.getByRole('button', { name: /^Index$/ }).click();
    await expect(page.getByTestId('repograph-stats')).toBeVisible({
      timeout: 30_000,
    });

    // Toggle to Graph.
    await page.getByTestId('repograph-toggle-graph').click();
    await expect(page.getByTestId('repograph-graph-container')).toBeVisible();
  });
});
