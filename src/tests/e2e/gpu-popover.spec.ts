/**
 * gpu-popover.spec.ts — visual capture of the GPU chip sparkline
 * popover. Clicks the temperature chip and screenshots the resulting
 * 300 s trend chart.
 *
 * Same env flags as gpu-strip.spec.ts:
 *   PLAYWRIGHT_FRONTEND_URL     — where to browse (default 3000)
 *   PLAYWRIGHT_BFF_URL          — BFF probe target (default 8081)
 *   PLAYWRIGHT_GPU_STRIP_PUSH=1 — auto-commit + push screenshot
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const FRONTEND_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  process.env.PLAYWRIGHT_FRONTEND_URL ||
  'http://127.0.0.1:3000';
const REPO_ROOT = resolve(process.cwd(), '..');
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const POPOVER_PNG = join(SCREENSHOT_DIR, 'gpu-popover-temperature.png');
const SHOULD_PUSH = process.env.PLAYWRIGHT_GPU_STRIP_PUSH === '1';

test.beforeAll(async ({ request }) => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
  const missing: string[] = [];
  const bffRes = await request.get(`${BFF_URL}/api/gpu`).catch(() => null);
  if (!bffRes || !bffRes.ok()) missing.push(`BFF ${BFF_URL}/api/gpu`);
  const feRes = await request.get(FRONTEND_URL).catch(() => null);
  if (!feRes || feRes.status() >= 500) missing.push(`frontend ${FRONTEND_URL}`);
  test.skip(missing.length > 0, `preconditions unmet: ${missing.join(', ')}`);
});

test('GPU chip popover — click T chip, screenshot sparkline', async ({ page }) => {
  test.setTimeout(60_000);

  // Wait for first snapshot so chips are hydrated with values.
  const snapshot = page.waitForResponse(
    (r) => r.url().includes('/api/gpu') && !r.url().includes('/history') && r.ok(),
    { timeout: 20_000 },
  );

  await page.goto(`${FRONTEND_URL}/runs`, { waitUntil: 'domcontentloaded' });
  await snapshot;

  // Click the temperature chip.
  const tempChip = page.getByRole('button', { name: /Open temperature_c history/ });
  await expect(tempChip).toBeVisible({ timeout: 10_000 });

  // Prime the history endpoint before click so the popover renders
  // a chart on open instead of "loading…".
  const history = page.waitForResponse(
    (r) => r.url().includes('/api/gpu/history') && r.ok(),
    { timeout: 15_000 },
  );
  await tempChip.click();
  await history;

  const popover = page.getByRole('dialog', { name: /Temperature/ });
  await expect(popover).toBeVisible({ timeout: 5_000 });

  // Give recharts one render frame + a poll cycle so the line
  // has more than one point.
  await page.waitForTimeout(2500);

  await popover.screenshot({ path: POPOVER_PNG });
  expect(existsSync(POPOVER_PNG), `${POPOVER_PNG} missing`).toBeTruthy();

  if (!SHOULD_PUSH) {
    // eslint-disable-next-line no-console
    console.log(
      `[gpu-popover] saved ${POPOVER_PNG}. Set PLAYWRIGHT_GPU_STRIP_PUSH=1 to auto-push.`,
    );
    return;
  }

  const rel = 'screenshots/gpu-popover-temperature.png';
  execFileSync('git', ['add', '-f', rel], { cwd: REPO_ROOT, stdio: 'inherit' });
  const status = execFileSync('git', ['status', '--porcelain', rel], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
  });
  if (!status.trim()) {
    // eslint-disable-next-line no-console
    console.log('[gpu-popover] no changes vs HEAD — skipping commit + push');
    return;
  }
  execFileSync(
    'git',
    [
      '-c',
      'user.name=Perplexity Computer',
      '-c',
      'user.email=computer@perplexity.ai',
      'commit',
      '-m',
      'F.16-UI screenshots: GPU popover — temperature sparkline',
    ],
    { cwd: REPO_ROOT, stdio: 'inherit' },
  );
  execFileSync('git', ['push', 'origin', 'main'], { cwd: REPO_ROOT, stdio: 'inherit' });
});
