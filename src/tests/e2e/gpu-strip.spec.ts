/**
 * gpu-strip.spec.ts — visual capture of the always-visible GPU strip.
 *
 * The Turbopack dev server's HMR websocket handshake fails against a
 * fresh headless Chromium and blocks client hydration, so we can't
 * screenshot the strip via `next dev`. Instead we build once, serve
 * with `next start` on a dedicated port, take the shots, and shut down.
 *
 * Runs the build+start dance only when PLAYWRIGHT_START_PROD=1 is set
 * (otherwise falls back to whatever PLAYWRIGHT_FRONTEND_URL points at).
 * When PLAYWRIGHT_GPU_STRIP_PUSH=1, auto-commits + pushes screenshots.
 */
import { test, expect } from '@playwright/test';
import { execFileSync, spawn, type ChildProcess } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { join, resolve } from 'node:path';
import net from 'node:net';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const START_PROD = process.env.PLAYWRIGHT_START_PROD === '1';
const PROD_PORT = Number(process.env.PLAYWRIGHT_PROD_PORT || 3100);
const FRONTEND_URL = START_PROD
  ? `http://127.0.0.1:${PROD_PORT}`
  : process.env.PLAYWRIGHT_BASE_URL ||
    process.env.PLAYWRIGHT_FRONTEND_URL ||
    'http://127.0.0.1:3000';
const REPO_ROOT = resolve(process.cwd(), '..');
const APP_DIR = process.cwd(); // <repo>/src
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const CHIP_PNG = join(SCREENSHOT_DIR, 'gpu-strip-chip.png');
const HEADER_PNG = join(SCREENSHOT_DIR, 'gpu-strip-header.png');
const SHOULD_PUSH = process.env.PLAYWRIGHT_GPU_STRIP_PUSH === '1';

let nextProc: ChildProcess | null = null;

function waitForPort(port: number, host = '127.0.0.1', timeoutMs = 60_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolveP, reject) => {
    const tryOnce = () => {
      const socket = net.createConnection({ port, host });
      socket.once('connect', () => {
        socket.end();
        resolveP();
      });
      socket.once('error', () => {
        socket.destroy();
        if (Date.now() > deadline) {
          reject(new Error(`port ${host}:${port} not ready after ${timeoutMs}ms`));
        } else {
          setTimeout(tryOnce, 500);
        }
      });
    };
    tryOnce();
  });
}

test.beforeAll(async ({ request }) => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });

  if (START_PROD) {
    // Build once (Next caches, so reruns are fast).
    execFileSync('npm', ['run', 'build'], { cwd: APP_DIR, stdio: 'inherit' });
    // Start the production server on a dedicated port.
    nextProc = spawn('npx', ['next', 'start', '-p', String(PROD_PORT)], {
      cwd: APP_DIR,
      stdio: 'inherit',
      env: { ...process.env, NEXT_PUBLIC_BFF_URL: BFF_URL },
      detached: false,
    });
    await waitForPort(PROD_PORT);
  }

  const missing: string[] = [];
  const bffRes = await request.get(`${BFF_URL}/api/gpu`).catch(() => null);
  if (!bffRes || !bffRes.ok()) missing.push(`BFF ${BFF_URL}/api/gpu`);
  const feRes = await request.get(FRONTEND_URL).catch(() => null);
  if (!feRes || feRes.status() >= 500) missing.push(`frontend ${FRONTEND_URL}`);
  test.skip(missing.length > 0, `preconditions unmet: ${missing.join(', ')}`);
});

test.afterAll(() => {
  if (nextProc && !nextProc.killed) {
    nextProc.kill('SIGTERM');
    nextProc = null;
  }
});

test.describe('GPU strip — visual capture', () => {
  test('captures chip + header screenshots and (optionally) pushes them', async ({ page }) => {
    test.setTimeout(120_000);

    const gpuResponse = page.waitForResponse(
      (r) => r.url().includes('/api/gpu') && r.ok(),
      { timeout: 30_000 },
    );

    await page.goto(`${FRONTEND_URL}/runs`, { waitUntil: 'domcontentloaded' });
    await gpuResponse;

    const strip = page.getByRole('status', { name: 'GPU status' });
    await expect(strip).toBeVisible({ timeout: 10_000 });
    await expect
      .poll(async () => (await strip.innerText()).replace(/\s+/g, ''), { timeout: 10_000 })
      .toMatch(/T\d/);

    await strip.screenshot({ path: CHIP_PNG });
    const header = page.getByRole('banner');
    await header.screenshot({ path: HEADER_PNG });

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

    const relChip = 'screenshots/gpu-strip-chip.png';
    const relHeader = 'screenshots/gpu-strip-header.png';
    execFileSync('git', ['add', '-f', relChip, relHeader], {
      cwd: REPO_ROOT,
      stdio: 'inherit',
    });
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
