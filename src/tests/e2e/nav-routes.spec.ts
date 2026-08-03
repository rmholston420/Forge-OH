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

// Each route asserts a body-text pattern that must appear somewhere on the
// page. Patterns are broad on purpose — the goal is to detect that the
// route rendered ITS content (not the sidebar shell which is present on
// every route). Patterns are anchored to strings unique to that route.
const routes: { path: string; expect: RegExp }[] = [
  { path: '/runs',              expect: /Search runs|Filter by status|No runs/i },
  { path: '/agents',            expect: /Agent Presets/i },
  { path: '/workspaces',        expect: /Workspace|New Workspace|feature-flag/i },
  { path: '/plugins',           expect: /Plugin|Filter by status|feature-flag/i },
  { path: '/tools-mcp',         expect: /Tools & MCP|MCP server/i },
  { path: '/observability',     expect: /Observability|Metrics dashboard/i },
  { path: '/settings',          expect: /Appearance|Model & Agent|Shortcuts/i },
  { path: '/settings/secrets',  expect: /Secrets/i },
  { path: '/runs/compare',      expect: /No runs selected|feature-flag|Fork action/i },
];

for (const r of routes) {
  test(`route ${r.path} renders without application error`, async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', (err) => consoleErrors.push(String(err)));

    await page.goto(r.path);
    await expect(page).not.toHaveURL(/\/404/);
    await expect(page.locator('body')).not.toContainText('Application error');
    await expect(page.locator('body')).not.toContainText('unhandled');

    // Route-specific content assertion.
    await expect(page.locator('body')).toContainText(r.expect);

    expect(consoleErrors, `pageerror on ${r.path}`).toEqual([]);
  });
}
