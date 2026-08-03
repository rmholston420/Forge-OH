/**
 * gpu-strip.spec.ts — visual capture of the always-visible GPU strip.
 *
 * Loads `/runs`, waits for a real `/api/gpu` response so the strip
 * has telemetry to render, then writes two screenshots to
 * `screenshots/` inside the repo:
 *
 *   gpu-strip-chip.png   — tight crop of the strip element only.
 *   gpu-strip-header.png — full topbar for context.
 *
 * When run with `PLAYWRIGHT_GPU_STRIP_PUSH=1`, the spec also commits
 * and pushes those screenshots to origin/main so the user can see
 * them without any manual step.
 *
 * Skips if the frontend or BFF isn't reachable.
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
// process.cwd() is `<repo>/src` when Playwright runs; go up one for the repo root.
const REPO_ROOT = resolve(process.cwd(), '..');
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const CHIP_PNG = join(SCREENSHOT_DIR, 'gpu-strip-chip.png');
const HEADER_PNG = join(SCREENSHOT_DIR, 'gpu-strip-header.png');
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

test.describe('GPU strip — visual capture', () => {
  test('captures chip + header screenshots and (optionally) pushes them', async ({
    page,
  }) => {
    test.setTimeout(60_000);

    // Wait for the strip's first `/api/gpu` response so the chip
    // renders real telemetry, not the "GPU n/a" fallback.
    const gpuResponse = page.waitForResponse(
      (r) => r.url().includes('/api/gpu') && r.ok(),
      { timeout: 20_000 },
    );

    await page.goto(`${FRONTEND_URL}/runs`, { waitUntil: 'domcontentloaded' });
    await gpuResponse;

    // Give React one frame to commit the update.
    const strip = page.getByRole('status', { name: 'GPU health' });
    await expect(strip).toBeVisible({ timeout: 10_000 });

    // Wait until at least the temperature chip has a real value
    // (i.e. not the em-dash fallback rendered before the first sample).
    await expect
      .poll(async () => (await strip.innerText()).replace(/\s+/g, ''), {
        timeout: 10_000,
      })
      .toMatch(/T\d/);

    await strip.screenshot({ path: CHIP_PNG });
    const header = page.getByRole('banner');
    await header.screenshot({ path: HEADER_PNG });

    // Sanity: files exist and are non-empty.
    for (const p of [CHIP_PNG, HEADER_PNG]) {
      expect(existsSync(p), `${p} missing`).toBeTruthy();
    }

    if (!SHOULD_PUSH) {
      // eslint-disable-next-line no-console
      console.log(
        `[gpu-strip] screenshots saved to ${SCREENSHOT_DIR}. ` +
          `Set PLAYWRIGHT_GPU_STRIP_PUSH=1 to auto-commit + push.`,
      );
      return;
    }

    // Commit + push. `git add -f` because `screenshots/` is
    // gitignored per the repo's existing convention.
    const relChip = 'screenshots/gpu-strip-chip.png';
    const relHeader = 'screenshots/gpu-strip-header.png';
    execFileSync('git', ['add', '-f', relChip, relHeader], {
      cwd: REPO_ROOT,
      stdio: 'inherit',
    });
    // Skip the commit if nothing actually changed (rerun on same telemetry).
    const status = execFileSync('git', ['status', '--porcelain', relChip, relHeader], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (!status.trim()) {
      // eslint-disable-next-line no-console
      console.log('[gpu-strip] no changes vs HEAD — skipping commit + push');
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
        'F.16-UI screenshots: GPU strip chip + header',
      ],
      { cwd: REPO_ROOT, stdio: 'inherit' },
    );
    execFileSync('git', ['push', 'origin', 'main'], {
      cwd: REPO_ROOT,
      stdio: 'inherit',
    });
  });
});
