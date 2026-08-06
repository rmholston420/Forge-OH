/**
 * memory-inspector.spec.ts — Stage 5.6a / ADR-024 visual capture.
 *
 * Screenshots the /memory-inspector page against the LIVE BFF composed
 * with a real MemoryPort singleton (K1). The spec seeds one canonical
 * MemoryEvent via the BFF's actual MemoryPort — no route mocking, no
 * fixtures. This matches the user's directive: "Inspector page against
 * LIVE DozerDB (seed real data)".
 *
 * Preconditions (verified in beforeAll):
 *   - BFF up on :8081
 *   - /api/memory/recent-writes returns 200 (i.e. NEO4J_PASSWORD was in
 *     the BFF env at boot; if it returns 503 the spec skips with an
 *     actionable message rather than screenshotting the unavailable
 *     banner as if it were success)
 *   - prod frontend up on :3100 (`next start`, never `next dev`)
 *
 * Screenshot outputs (auto-pushed when PLAYWRIGHT_GPU_STRIP_PUSH=1):
 *   screenshots/memory-inspector-page.png     full page (data table)
 *   screenshots/memory-inspector-sidebar.png  sidebar with 🧠 Memory row
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
    'http://127.0.0.1:3100';
const REPO_ROOT = resolve(process.cwd(), '..');
const APP_DIR = process.cwd(); // <repo>/src
const SCREENSHOT_DIR = join(REPO_ROOT, 'screenshots');
const PAGE_PNG = join(SCREENSHOT_DIR, 'memory-inspector-page.png');
const SIDEBAR_PNG = join(SCREENSHOT_DIR, 'memory-inspector-sidebar.png');
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
    execFileSync('npm', ['run', 'build'], { cwd: APP_DIR, stdio: 'inherit' });
    nextProc = spawn('npx', ['next', 'start', '-p', String(PROD_PORT)], {
      cwd: APP_DIR,
      stdio: 'inherit',
      env: { ...process.env, NEXT_PUBLIC_BFF_URL: BFF_URL },
      detached: false,
    });
    await waitForPort(PROD_PORT);
  }

  // Fail-fast probes.
  const missing: string[] = [];

  const bffRoot = await request.get(`${BFF_URL}/api/memory/recent-writes?limit=1`).catch((e) => {
    // eslint-disable-next-line no-console
    console.log('[memory-inspector] BFF probe threw:', e instanceof Error ? e.message : String(e));
    return null;
  });
  const bffStatus = bffRoot ? bffRoot.status() : 0;
  // eslint-disable-next-line no-console
  console.log('[memory-inspector] BFF /api/memory/recent-writes status:', bffStatus);

  if (!bffRoot) missing.push(`BFF ${BFF_URL}`);
  else if (bffStatus === 503) {
    missing.push(
      `BFF MemoryPort unavailable (503). Restart BFF with NEO4J_PASSWORD in env ` +
      `(source ~/dev/forge-oh/.env.neo4j) so the composed singleton binds to DozerDB.`,
    );
  } else if (bffStatus !== 200) {
    missing.push(`BFF /api/memory/recent-writes returned ${bffStatus}`);
  }

  const feRes = await request.get(FRONTEND_URL).catch(() => null);
  // eslint-disable-next-line no-console
  console.log('[memory-inspector] FE status:', feRes ? feRes.status() : 'null', 'URL=', FRONTEND_URL);
  if (!feRes || feRes.status() >= 500) missing.push(`frontend ${FRONTEND_URL}`);

  test.skip(missing.length > 0, `preconditions unmet: ${missing.join(', ')}`);
});

test.afterAll(() => {
  if (nextProc && !nextProc.killed) {
    nextProc.kill('SIGTERM');
    nextProc = null;
  }
});

test.describe('Memory inspector — visual capture (live DozerDB)', () => {
  test('renders sidebar entry and recent-writes table', async ({ page, request }) => {
    test.setTimeout(120_000);

    // Seed one MemoryEvent via a tiny scripted BFF call so the table has
    // at least one row. We use the well-known Colossus seed helper
    // (scripts/seed_memory_event.py); on Colossus it POSTs directly
    // through the composed MemoryPort. Failure is non-fatal for the
    // screenshot but flagged in the console.
    try {
      execFileSync(
        'python',
        ['scripts/seed_memory_event.py'],
        { cwd: REPO_ROOT, stdio: 'inherit', env: { ...process.env } },
      );
    } catch (e) {
      // eslint-disable-next-line no-console
      console.log('[memory-inspector] seed step warning:', e instanceof Error ? e.message : String(e));
    }

    // Confirm the row landed via the same BFF endpoint the UI will hit.
    const listResp = await request.get(`${BFF_URL}/api/memory/recent-writes?limit=5`);
    expect(listResp.status()).toBe(200);
    const body = await listResp.json();
    // eslint-disable-next-line no-console
    console.log('[memory-inspector] recent-writes rows:', (body?.data ?? []).length);
    expect(Array.isArray(body?.data)).toBe(true);
    expect(body.data.length).toBeGreaterThan(0);

    // Visual: sidebar first — the 🧠 Memory entry must be present.
    await page.goto(`${FRONTEND_URL}/runs`, { waitUntil: 'domcontentloaded' });
    const sidebar = page.getByRole('navigation', { name: /main navigation/i });
    await expect(sidebar).toBeVisible({ timeout: 10_000 });
    await expect(sidebar.getByRole('link', { name: /memory/i })).toBeVisible();
    await sidebar.screenshot({ path: SIDEBAR_PNG });

    // Visual: memory-inspector page.
    const recentResp = page.waitForResponse(
      (r) => r.url().includes('/api/memory/recent-writes') && r.ok(),
      { timeout: 30_000 },
    );
    await page.goto(`${FRONTEND_URL}/memory-inspector`, { waitUntil: 'domcontentloaded' });
    await recentResp;

    await expect(
      page.getByRole('heading', { name: /^memory$/i, level: 1 }),
    ).toBeVisible();

    const table = page.getByRole('table', { name: /recent memory writes/i });
    await expect(table).toBeVisible({ timeout: 10_000 });
    await expect(table.getByRole('row')).toHaveCount(
      (body.data.length as number) + 1, // +1 for header
      { timeout: 10_000 },
    );

    await page.screenshot({ path: PAGE_PNG, fullPage: true });

    for (const p of [PAGE_PNG, SIDEBAR_PNG]) {
      expect(existsSync(p), `${p} missing`).toBeTruthy();
    }

    if (!SHOULD_PUSH) {
      // eslint-disable-next-line no-console
      console.log(
        `[memory-inspector] screenshots saved to ${SCREENSHOT_DIR}. ` +
          `Set PLAYWRIGHT_GPU_STRIP_PUSH=1 to auto-commit + push.`,
      );
      return;
    }

    const rels = ['screenshots/memory-inspector-page.png', 'screenshots/memory-inspector-sidebar.png'];
    execFileSync('git', ['add', '-f', ...rels], { cwd: REPO_ROOT, stdio: 'inherit' });
    const status = execFileSync('git', ['status', '--porcelain', ...rels], {
      cwd: REPO_ROOT,
      encoding: 'utf8',
    });
    if (!status.trim()) {
      // eslint-disable-next-line no-console
      console.log('[memory-inspector] no changes vs HEAD — skipping commit + push');
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
        'Stage 5.6a screenshots: memory-inspector page + sidebar entry',
      ],
      { cwd: REPO_ROOT, stdio: 'inherit' },
    );
    execFileSync('git', ['push', 'origin', 'main'], { cwd: REPO_ROOT, stdio: 'inherit' });
  });
});
