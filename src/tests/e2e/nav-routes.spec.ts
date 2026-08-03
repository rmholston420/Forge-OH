/**
 * nav-routes.spec.ts
 *
 * Route-smoke coverage for every dashboard route the app currently ships.
 * Real BFF at 127.0.0.1:8081 provides responses; each test asserts the
 * route renders (h1/heading present) and does NOT throw an application
 * error boundary. Tests are resilient to empty data — they only assert
 * shells, not seeded content.
 */
import { test, expect } from '@playwright/test';

const routes: { path: string; heading?: RegExp; empty?: RegExp; feature?: string }[] = [
  { path: '/runs',                       heading: /^Runs$/ },
  { path: '/agents',                     heading: /Agent Presets/i },
  { path: '/workspaces',                 empty: /workspace/i, feature: 'FEATURE_WORKSPACES_ENABLED' },
  { path: '/plugins',                    empty: /plugin/i,    feature: 'FEATURE_PLUGINS_ENABLED' },
  { path: '/tools-mcp',                  heading: /Tools & MCP/i },
  { path: '/observability',              heading: /Observability/i },
  { path: '/settings',                   heading: /Settings|Appearance/i },
  { path: '/settings/secrets',           heading: /Secrets/i },
  { path: '/runs/compare',               empty: /No runs selected/i, feature: 'FEATURE_RUN_COMPARE_ENABLED' },
];

for (const r of routes) {
  test(`route ${r.path} renders without application error`, async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (err) => consoleErrors.push(String(err)));

    await page.goto(r.path);
    // Never bounce to /404 unless intentional
    await expect(page).not.toHaveURL(/\/404/);
    // Body must not contain a raw error boundary crash string
    await expect(page.locator('body')).not.toContainText('Application error');
    await expect(page.locator('body')).not.toContainText('unhandled');

    // Either the heading (real page) or the empty-state text (stub / no data)
    // must appear — allowing for feature-flag stubs.
    const bodyText = await page.locator('body').innerText();
    const matched = (r.heading && r.heading.test(bodyText)) || (r.empty && r.empty.test(bodyText));
    expect(matched, `route ${r.path} should show heading/empty state`).toBeTruthy();

    expect(consoleErrors, `pageerror on ${r.path}`).toEqual([]);
  });
}
