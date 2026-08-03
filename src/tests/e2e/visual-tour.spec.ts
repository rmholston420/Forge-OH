/**
 * visual-tour.spec.ts — full-page screenshot sweep of every route, run-detail
 * tab, and every wired modal from Slices C-I. NOT ASSERTIONS. Purpose is to
 * generate PNGs under ./screenshots/ so the agent can visually inspect the UI.
 *
 * Run:
 *   pnpm exec playwright test src/tests/e2e/visual-tour.spec.ts
 *
 * Screenshots land in: <repo>/screenshots/<slug>.png
 * The test file uses fullPage:true so wrapped/broken text is visible.
 */
import { test, type Page } from '@playwright/test';
import * as path from 'path';

const OUT = path.resolve(process.cwd(), 'screenshots');
const BFF = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';

test.describe.configure({ mode: 'serial' });

async function shot(page: Page, name: string) {
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {});
  // Give any late-mounting components (charts, react-query results) a beat.
  // Larger delay = tolerates one full react-query settle after a tab switch;
  // the previous 400ms often captured a Skeleton mid-flight (Metrics, Browser).
  await page.waitForTimeout(1200);
  await page.waitForLoadState('networkidle', { timeout: 2_000 }).catch(() => {});
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
}

async function firstRunId(page: Page): Promise<string | null> {
  const res = await page.request.get(`${BFF}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{ id: string }>;
  return runs.length ? runs[0].id : null;
}

async function runCount(page: Page): Promise<number> {
  const res = await page.request.get(`${BFF}/api/runs`);
  if (!res.ok()) return 0;
  const body = await res.json();
  const list = (Array.isArray(body) ? body : body?.data ?? []) as unknown[];
  return list.length;
}

async function hasWorkspaces(page: Page): Promise<boolean> {
  const res = await page.request.get(`${BFF}/api/workspaces`);
  if (!res.ok()) return false;
  const body = await res.json();
  const list = (Array.isArray(body) ? body : body?.data ?? []) as unknown[];
  return list.length > 0;
}

// ────────────────────────────────────────────────────────────────
// Top-level routes
// ────────────────────────────────────────────────────────────────
const ROUTES: Array<{ path: string; slug: string }> = [
  { path: '/',             slug: '01-root-redirect' },
  { path: '/runs',         slug: '02-runs-list' },
  { path: '/workspaces',   slug: '03-workspaces' },
  { path: '/plugins',      slug: '04-plugins-installed' },
  { path: '/agents',       slug: '05-agents' },
  { path: '/tools-mcp',    slug: '06-tools-mcp' },
  { path: '/observability',slug: '07-observability-empty' },
  { path: '/secrets',      slug: '08-secrets' },
  { path: '/settings',     slug: '09-settings' },
  { path: '/settings/secrets', slug: '10-settings-secrets' },
];

for (const r of ROUTES) {
  test(`route: ${r.path}`, async ({ page }) => {
    await page.goto(r.path, { waitUntil: 'domcontentloaded' });
    await shot(page, r.slug);
  });
}

// ────────────────────────────────────────────────────────────────
// Plugins — Marketplace tab (Slice H)
// ────────────────────────────────────────────────────────────────
test('plugins: marketplace tab', async ({ page }) => {
  await page.goto('/plugins');
  const marketplaceTab = page.getByRole('tab', { name: 'Marketplace' });
  if (await marketplaceTab.count() === 0) {
    await shot(page, '11-plugins-marketplace-DISABLED');
    return;
  }
  await marketplaceTab.click();
  await shot(page, '11-plugins-marketplace');
});

// ────────────────────────────────────────────────────────────────
// Runs Compare modal (Slice G)
// ────────────────────────────────────────────────────────────────
test('runs: compare modal (if ≥2 runs)', async ({ page }) => {
  await page.goto('/runs');
  const count = await runCount(page);
  const btn = page.getByRole('button', { name: 'Compare' });
  if (count < 2) {
    await shot(page, '12-runs-compare-button-DISABLED');
    return;
  }
  await btn.click();
  await shot(page, '12-runs-compare-modal');
});

// ────────────────────────────────────────────────────────────────
// Run detail tabs (Slice C is one of them) + fork + secrets modals
// ────────────────────────────────────────────────────────────────
test('run detail: every tab + fork/secrets modal', async ({ page }) => {
  const runId = await firstRunId(page);
  if (!runId) {
    await page.goto('/runs');
    await shot(page, '13-run-detail-NO-RUNS');
    return;
  }
  const tabs = ['Overview', 'Plan', 'Files', 'Terminal', 'Browser', 'Metrics', 'Security', 'Trace'];
  for (const t of tabs) {
    await page.goto(`/runs/${runId}`);
    await page.getByRole('tab', { name: t }).click();
    await shot(page, `13-run-tab-${t.toLowerCase()}`);
  }

  // Secrets modal (Slice E)
  await page.goto(`/runs/${runId}`);
  await page.getByRole('button', { name: 'Edit run environment variables' }).click();
  await shot(page, '14-run-secrets-modal');
  await page.keyboard.press('Escape');

  // Sub-routes with their own pages
  await page.goto(`/runs/${runId}/files`);      await shot(page, '15-run-files-subroute');
  await page.goto(`/runs/${runId}/artifacts`);  await shot(page, '16-run-artifacts-subroute');
  await page.goto(`/runs/${runId}/terminal`);   await shot(page, '17-run-terminal-subroute');
});

// ────────────────────────────────────────────────────────────────
// Observability drill-down (Slice I)
// ────────────────────────────────────────────────────────────────
test('observability: drill-down into first run', async ({ page }) => {
  await page.goto('/observability');
  const runButtons = page.locator('aside button');
  if (await runButtons.count() === 0) {
    await shot(page, '18-observability-empty-selected');
    return;
  }
  await runButtons.first().click();
  await shot(page, '18-observability-trace-detail');
});

// ────────────────────────────────────────────────────────────────
// Workspace card w/ Test button hover state (Slice F)
// ────────────────────────────────────────────────────────────────
test('workspaces: card + test button visible', async ({ page }) => {
  await page.goto('/workspaces');
  const has = await hasWorkspaces(page);
  if (!has) {
    await shot(page, '19-workspaces-empty');
    return;
  }
  // Just captures the list — the Test button lives on each card and is
  // already inside the full-page shot.
  await shot(page, '19-workspaces-with-cards');
});
