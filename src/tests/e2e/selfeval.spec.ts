/**
 * selfeval.spec.ts — Slice G.1 + `selfeval-frontend-polish`.
 *
 * Three tiers of assertions:
 *  1. Sidebar + empty state (original G.1 smoke — always runs).
 *  2. Populated state (skipped if BFF returns zero cycles).
 *  3. Run-now launch (skipped by default; opt-in via
 *     PLAYWRIGHT_SKIP_SELFEVAL_LAUNCH=0). Costs one real cycle.
 *
 * Deep integration is tested via bff/tests/test_selfeval_router.py against
 * a mocked systemctl subprocess.
 *
 * Env:
 *   PLAYWRIGHT_BFF_URL              — default http://127.0.0.1:8081
 *   PLAYWRIGHT_SKIP_SELFEVAL_LAUNCH — default 1 (skip). Set to 0 to run.
 */
import { test, expect, type Page } from '@playwright/test';

const BFF = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const SKIP_LAUNCH = (process.env.PLAYWRIGHT_SKIP_SELFEVAL_LAUNCH ?? '1') !== '0';

interface CycleListItem {
  filename: string;
  tasks_selected: number;
  tasks_passed: number;
  tasks_failed: number;
  tasks_timed_out: number;
  tasks_errored: number;
}

async function fetchCycles(page: Page): Promise<CycleListItem[]> {
  const res = await page.request.get(`${BFF}/api/selfeval/cycles`);
  if (!res.ok()) return [];
  const body = await res.json();
  return (body?.cycles ?? []) as CycleListItem[];
}

async function fetchStatus(page: Page): Promise<{ running: boolean } | null> {
  const res = await page.request.get(`${BFF}/api/selfeval/status`);
  if (!res.ok()) return null;
  return (await res.json()) as { running: boolean };
}

test.describe('Self-Eval page smoke', () => {

  /* ── Tier 1: original G.1 smoke ─────────────────────────── */

  test('sidebar exposes Self-Eval link', async ({ page }) => {
    await page.goto('/');
    await expect(
      page.getByRole('link', { name: /self-eval/i }),
    ).toBeVisible();
  });

  test('/selfeval page loads with heading + Run now button', async ({ page }) => {
    await page.goto('/selfeval');
    await expect(page.getByRole('heading', { name: 'Self-Eval' })).toBeVisible();
    // Button text is either "Run now", "Running…" (cycle in-flight), or the
    // loading spinner treatment during POST. Accept any.
    const btn = page.getByRole('button', { name: /run|launching/i });
    await expect(btn).toBeVisible();
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  test('empty cycle state renders a hint OR cycle history table', async ({ page }) => {
    await page.goto('/selfeval');
    const emptyHint = page.getByText(/no cycles yet/i);
    const historyHeading = page.getByRole('heading', { name: /cycle history/i });
    await Promise.race([
      emptyHint.waitFor({ state: 'visible', timeout: 5000 }),
      historyHeading.waitFor({ state: 'visible', timeout: 5000 }),
    ]);
  });

  /* ── Tier 2: populated state (skip when no cycles) ──────── */

  test('populated cycle history shows a row + Open link navigates to detail', async ({ page }) => {
    const cycles = await fetchCycles(page);
    test.skip(cycles.length === 0, 'BFF has zero cycles on disk');

    const first = cycles[0];
    const date = first.filename.slice(0, 10);

    await page.goto('/selfeval');
    // The row containing today's date should be visible.
    const row = page.getByRole('row').filter({ hasText: date }).first();
    await expect(row).toBeVisible();

    // "Open →" link on that row navigates to /selfeval/[date]. Use
    // Promise.all to race the click and the navigation — Next.js's client
    // router uses history.pushState, which page.waitForURL sometimes misses
    // when the assertion is set up after the click has already resolved.
    await Promise.all([
      page.waitForURL(new RegExp(`/selfeval/${date}(?:\?|$)`), { timeout: 10_000 }),
      row.getByRole('link', { name: /Open/i }).click(),
    ]);
    await expect(
      page.getByRole('heading', { name: new RegExp(`Cycle: ${date}`) }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('cycle detail page renders KPIs + task outcomes table', async ({ page }) => {
    const cycles = await fetchCycles(page);
    test.skip(cycles.length === 0, 'BFF has zero cycles on disk');

    const first = cycles[0];
    const date = first.filename.slice(0, 10);
    await page.goto(`/selfeval/${date}`);

    // KPI grid — DOM text is title-case ("Passed", "Failed", ...); the
    // uppercase appearance comes from CSS text-transform which Playwright
    // does NOT normalize into hasText matches. Assert the DOM text.
    await expect(page.getByText('Passed', { exact: true })).toBeVisible();
    await expect(page.getByText('Failed', { exact: true })).toBeVisible();
    await expect(page.getByText('Timed out', { exact: true })).toBeVisible();
    await expect(page.getByText('Errored', { exact: true })).toBeVisible();

    // Task outcomes heading present.
    const outcomesHeading = page.getByRole('heading', { name: /task outcomes/i });
    await expect(outcomesHeading).toBeVisible();

    if (first.tasks_selected > 0) {
      // At least one row in the outcomes tbody (skip strict count — the
      // list endpoint's tasks_selected can differ from stored outcomes
      // when the harness aborted early).
      const outcomeRows = page.locator('tbody tr');
      const count = await outcomeRows.count();
      expect(count).toBeGreaterThan(0);
    }
  });

  test('cycle detail: passed verdict renders a Badge component', async ({ page }) => {
    const cycles = await fetchCycles(page);
    test.skip(cycles.length === 0, 'BFF has zero cycles on disk');
    const first = cycles[0];
    test.skip(first.tasks_passed === 0, 'Latest cycle has zero passed tasks');

    const date = first.filename.slice(0, 10);
    await page.goto(`/selfeval/${date}`);

    // The core Badge component emits a <span> whose accessible text is
    // exactly the verdict string. Search across ALL tbody spans (not just
    // the first row's first span) since the first row's verdict may not
    // be 'passed'.
    const passedBadges = page.locator('tbody span').filter({ hasText: /^passed$/ });
    const count = await passedBadges.count();
    expect(count).toBeGreaterThan(0);
    await expect(passedBadges.first()).toBeVisible();
  });

  test('/selfeval/{invalid-date} surfaces an error banner (not a crash)', async ({ page }) => {
    await page.goto('/selfeval/9999-99-99');
    // Wait for either the error banner OR the empty-state (a very forgiving
    // BFF could return 200 with empty outcomes — but our BFF returns 400).
    const banner = page.getByRole('alert');
    await expect(banner).toBeVisible({ timeout: 5000 });
    await expect(page.locator('body')).not.toContainText('Application error');
  });

  /* ── Tier 3: Run-now launch (opt-in, off by default) ────── */

  test('Run-now actually launches a cycle end-to-end', async ({ page }) => {
    test.skip(
      SKIP_LAUNCH,
      'PLAYWRIGHT_SKIP_SELFEVAL_LAUNCH default-on; set to 0 to run',
    );
    test.setTimeout(600_000); // 10 min — a full cycle on vLLM primary is ~90s

    const statusBefore = await fetchStatus(page);
    test.skip(statusBefore?.running === true, 'A cycle is already running');
    const cyclesBefore = await fetchCycles(page);
    const countBefore = cyclesBefore.length;

    await page.goto('/selfeval');
    await page.getByRole('button', { name: /^run now$/i }).click();

    // Live-cycle rail should appear.
    await expect(page.getByText(/cycle in progress/i)).toBeVisible({ timeout: 15_000 });

    // Poll status until it drops back to running=false.
    let elapsed = 0;
    while (elapsed < 550_000) {
      const s = await fetchStatus(page);
      if (s && s.running === false && s.last_result != null) break;
      await page.waitForTimeout(5_000);
      elapsed += 5_000;
    }

    // A new cycle summary should be on disk.
    const cyclesAfter = await fetchCycles(page);
    expect(cyclesAfter.length).toBeGreaterThanOrEqual(countBefore + 1);
  });
});
