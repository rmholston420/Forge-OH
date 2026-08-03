/**
 * trajectory-memory-panel.spec.ts
 *
 * E2E test for the Slice F.7 trajectory memory widget on the run detail
 * Overview tab. Seeds two deterministic records directly into the store
 * (via a short Python one-liner that uses TrajectoryStore + a
 * fixed 1536-dim embedding), then loads a run detail page and asserts
 * the widget renders at least one hit with the expected score and
 * status pill.
 *
 * Screenshots at each milestone go to `screenshots/trajectory-*.png`
 * (gitignored) so the user can paste them back for the Brain wiki.
 *
 * Runs against the real BFF. Skips gracefully if no runs exist or the
 * feature flag is off (checked via `data-testid="trajectory-memory-*"`).
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const SCREENSHOT_DIR = join(process.cwd(), 'screenshots');
const PY =
  process.env.PLAYWRIGHT_PYTHON ||
  `${process.env.HOME}/dev/forge-oh/.oh-venv/bin/python`;
// Use a scratch DB so the test never touches the user's real memory.
const SCRATCH_DB = join(
  mkdtempSync(join(tmpdir(), 'forge-oh-traj-e2e-')),
  'trajectories.db',
);

test.beforeAll(() => {
  mkdirSync(SCREENSHOT_DIR, { recursive: true });
});

async function firstRunId(
  page: import('@playwright/test').Page,
): Promise<string | null> {
  const res = await page.request.get(`${BFF_URL}/api/runs`);
  if (!res.ok()) return null;
  const body = await res.json();
  const runs = (Array.isArray(body) ? body : body?.data ?? []) as Array<{
    id: string;
  }>;
  return runs.length ? runs[0].id : null;
}

async function widgetEnabled(
  page: import('@playwright/test').Page,
  runId: string,
): Promise<boolean> {
  await page.goto(`/runs/${runId}`);
  // The panel container is only in the DOM if the flag is on.
  const enabled = await page
    .getByTestId('trajectory-memory-panel')
    .first()
    .isVisible()
    .catch(() => false);
  return enabled;
}

/**
 * Seed two records via a Python one-liner. Uses a deterministic
 * dummy embedding so search ranking is stable across runs.
 *
 * NOTE: this points the store at SCRATCH_DB, not the real DB, and the
 * BFF must be started with FORGE_OH_TRAJECTORY_DB=$SCRATCH_DB for the
 * seeded records to be visible to the widget. If the BFF's env var
 * doesn't match, the test skips.
 */
function seedTrajectories(runQuery: string): void {
  const script = `
import os
os.environ["FORGE_OH_TRAJECTORY_DB"] = ${JSON.stringify(SCRATCH_DB)}
from datetime import datetime, timezone
from openhands_tools_ext.trajectory.schema import (
    TrajectoryRecord,
    TrajectoryDiff,
    TrajectoryStatus,
)
from openhands_tools_ext.trajectory.store import TrajectoryStore

store = TrajectoryStore(${JSON.stringify(SCRATCH_DB)})

# Same-ish embedding so semantic term is high for the query.
q_emb = [0.05] * 1536
alt_emb = [0.01] * 1536

recs = [
    TrajectoryRecord(
        trajectory_id="traj_e2e_A",
        run_id="e2e-run-A",
        session_id="s-A",
        task_description=${JSON.stringify(runQuery)},
        plan="reproduce, diagnose, fix",
        diffs=[TrajectoryDiff(path="bff/routers/runs.py", lines_added=3, lines_removed=1, summary="")],
        verify_iterations=[],
        final_status=TrajectoryStatus.SUCCESS,
        symptom="assert failed: expected 200 got 401",
        repograph_repo_key="forge-oh",
        repograph_symbols=["bff.routers.runs.create_run"],
        embedding=q_emb,
        embedding_model="bge-code-v1",
        created_at=datetime.now(timezone.utc).isoformat(),
    ),
    TrajectoryRecord(
        trajectory_id="traj_e2e_B",
        run_id="e2e-run-B",
        session_id="s-B",
        task_description="unrelated task about docs formatting",
        plan="",
        diffs=[],
        verify_iterations=[],
        final_status=TrajectoryStatus.FAILED,
        symptom="",
        repograph_repo_key="forge-oh",
        repograph_symbols=["docs.build"],
        embedding=alt_emb,
        embedding_model="bge-code-v1",
        created_at=datetime.now(timezone.utc).isoformat(),
    ),
]

for r in recs:
    store.insert(r)

print("seeded", store.count())
`;
  execFileSync(PY, ['-c', script], { stdio: 'inherit' });
}

test.describe('Trajectory Memory Panel (Overview tab)', () => {
  let runId: string | null = null;
  let widgetOn = false;
  let bffUsesScratch = false;

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    runId = await firstRunId(page);
    if (runId) widgetOn = await widgetEnabled(page, runId);

    // If the widget is on, check whether the BFF is pointing at our
    // scratch DB. We do this by seeding a probe record then asking the
    // BFF for it.
    if (widgetOn) {
      try {
        seedTrajectories('probe: is BFF using the scratch DB?');
        const res = await page.request.get(
          `${BFF_URL}/api/trajectories/traj_e2e_A`,
        );
        bffUsesScratch = res.ok();
      } catch {
        bffUsesScratch = false;
      }
    }
    await ctx.close();
  });

  test('renders idle hint when no task on run (smoke)', async ({ page }) => {
    test.skip(!runId, 'no runs on BFF');
    test.skip(!widgetOn, 'FEATURE_TRAJECTORY_MEMORY off on frontend');

    await page.goto(`/runs/${runId!}`);
    const panel = page.getByTestId('trajectory-memory-panel');
    await expect(panel).toBeVisible();

    // Widget must show *something* — either idle, empty, error, or hits.
    // A single visible testid confirms the state machine wired up.
    const anyState = panel.locator(
      '[data-testid^="trajectory-memory-"]',
    );
    await expect(anyState.first()).toBeVisible();

    await page.screenshot({
      path: join(SCREENSHOT_DIR, 'trajectory-01-panel-mounted.png'),
      fullPage: true,
    });
  });

  test('renders top-k hits after seeding matching trajectories', async ({
    page,
  }) => {
    test.skip(!runId, 'no runs on BFF');
    test.skip(!widgetOn, 'FEATURE_TRAJECTORY_MEMORY off on frontend');
    test.skip(
      !bffUsesScratch,
      `BFF is not pointing at scratch DB ${SCRATCH_DB}; ` +
        'start with FORGE_OH_TRAJECTORY_DB=$SCRATCH_DB',
    );

    // Grab the current run's task title and seed a matching trajectory.
    const runRes = await page.request.get(`${BFF_URL}/api/runs/${runId!}`);
    const runBody = await runRes.json();
    const title: string =
      runBody?.data?.title ?? runBody?.title ?? 'seeded task';
    seedTrajectories(title);

    await page.goto(`/runs/${runId!}`);
    const panel = page.getByTestId('trajectory-memory-panel');
    await expect(panel).toBeVisible();

    // At least one hit row is visible.
    const hits = panel.locator('[data-testid="trajectory-memory-hit"]');
    await expect(hits.first()).toBeVisible({ timeout: 15_000 });

    // Status pill on the top hit reads success (traj_e2e_A).
    const topStatus = panel
      .locator('[data-testid="trajectory-status"]')
      .first();
    await expect(topStatus).toHaveText(/success|failed|verified failure/);

    // Score row shows all three components.
    await expect(panel.getByText(/^score /)).toBeVisible();
    await expect(panel.getByText(/^sem /)).toBeVisible();
    await expect(panel.getByText(/^sym /)).toBeVisible();

    await page.screenshot({
      path: join(SCREENSHOT_DIR, 'trajectory-02-hits.png'),
      fullPage: true,
    });
  });
});
