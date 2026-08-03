/**
 * g1-self-testing.spec.ts — Forge-OH grows its own test suite (2026-08-03)
 *
 * Slice G.1: proves that Forge-OH can extend one of its own tests and
 * that the new test passes. This is the concrete "does the app
 * actually work" bar for the coding assistant — beyond "the run
 * succeeded", it demonstrates a real, verifiable code change landed
 * on disk.
 *
 * Flow:
 *   1. Baseline: count `pytest --collect-only` cases inside
 *      `bff/tests/test_sidecar_producers.py::TestSymptomProducer` in
 *      the Colossus workspace repo.
 *   2. Fire a Forge-OH run whose taskPrompt asks the agent to add
 *      one new test case named
 *      `test_g1_marker_terminal_exit_2_becomes_symptom` to that same
 *      class. The case content is fully specified inside the
 *      prompt so the spec's assertions are deterministic.
 *   3. Wait for terminal, drain trajectories.
 *   4. Recount pytest cases: expect exactly baseline + 1.
 *   5. Run the newly added test in isolation: expect 1 passed.
 *
 * Runs against the real BFF at PLAYWRIGHT_BFF_URL (default
 * http://127.0.0.1:8081). Requires:
 *
 *   * BFF up on :8081
 *   * agent-server up on :8090
 *   * FORGE_TEST_WORKSPACE_ID set to the Colossus repo checkout id
 *     (defaults to the id used by the other F.* specs).
 *   * FORGE_TEST_WORKSPACE_PATH set to the absolute path of that
 *     checkout on disk (default: $HOME/forge-oh).
 *   * FORGE_TEST_PYTEST set to the pytest command in that repo
 *     (default: .oh-venv/bin/pytest — the Colossus venv).
 *
 * Skip guard: if the BFF isn't reachable OR the target test file /
 * pytest binary isn't found, the whole file skips.
 */
import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const BFF_URL = process.env.PLAYWRIGHT_BFF_URL || 'http://127.0.0.1:8081';
const WORKSPACE_ID =
  process.env.FORGE_TEST_WORKSPACE_ID ||
  '18c99443b23c452899010095abd5f29b';
const WORKSPACE_PATH =
  process.env.FORGE_TEST_WORKSPACE_PATH || join(homedir(), 'forge-oh');
const PYTEST_BIN =
  process.env.FORGE_TEST_PYTEST || join(WORKSPACE_PATH, '.oh-venv', 'bin', 'pytest');
const TEST_FILE_REL = 'bff/tests/test_sidecar_producers.py';
const TEST_CLASS = 'TestSymptomProducer';
const NEW_TEST_NAME = 'test_g1_marker_terminal_exit_127_becomes_symptom';
const NODE_ID = `${TEST_FILE_REL}::${TEST_CLASS}::${NEW_TEST_NAME}`;
const PRESET_ID = process.env.FORGE_TEST_PRESET_ID || 'ap-1';
const RUN_POLL_INTERVAL_MS = 3_000;
const RUN_TIMEOUT_MS = 300_000;

/** Fully-specified new test case body — deterministic assertions.
 *
 * Event shape mirrors the existing passing sibling
 * `test_terminal_observation_with_nonzero_exit_becomes_symptom`
 * (top-level `kind: "ObservationEvent"`, `content` as a list of typed
 * parts) so the producer's real code path is exercised. Uses
 * `exit_code=127` as an unambiguous marker (distinct from the 2 that
 * the sibling case uses) so a `grep 'exit=127'` audit finds only this
 * self-test.
 */
const NEW_TEST_BODY = `    def ${NEW_TEST_NAME}(
        self, workspace: Path, cid: str
    ) -> None:
        """G.1 marker: TerminalObservation exit=127 becomes structured symptom.

        Added by Forge-OH self-testing spec
        (src/tests/e2e/g1-self-testing.spec.ts). Mirrors
        test_terminal_observation_with_nonzero_exit_becomes_symptom
        but uses exit_code=127 as an unambiguous G.1 marker.
        """
        _feed(
            workspace,
            cid,
            {
                "kind": "ObservationEvent",
                "observation": {
                    "kind": "TerminalObservation",
                    "is_error": False,
                    "exit_code": 127,
                    "content": [
                        {"type": "text", "text": "bash: command not found"}
                    ],
                },
            },
        )
        sym = _read_slot(workspace, cid).get("symptom", "")
        assert "TerminalObservation" in sym
        assert "exit=127" in sym
        assert "bash: command not found" in sym
`;

async function createRun(
  request: import('@playwright/test').APIRequestContext,
  title: string,
  taskPrompt: string,
): Promise<string> {
  const res = await request.post(`${BFF_URL}/api/runs`, {
    data: {
      title,
      agentPresetId: PRESET_ID,
      workspaceId: WORKSPACE_ID,
      taskPrompt,
    },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = await res.json();
  const id = body?.data?.id;
  expect(id, `create_run body missing data.id: ${JSON.stringify(body)}`).toBeTruthy();
  return id as string;
}

async function waitForTerminal(
  request: import('@playwright/test').APIRequestContext,
  runId: string,
): Promise<string> {
  const deadline = Date.now() + RUN_TIMEOUT_MS;
  let last = '';
  while (Date.now() < deadline) {
    const res = await request.get(`${BFF_URL}/api/runs/${runId}`);
    if (res.ok()) {
      const body = await res.json();
      last = body?.data?.status ?? '';
      if (['succeeded', 'failed', 'blocked'].includes(last)) return last;
    }
    await new Promise((r) => setTimeout(r, RUN_POLL_INTERVAL_MS));
  }
  throw new Error(`run ${runId} did not reach terminal status (last=${last})`);
}

async function drainTrajectories(
  request: import('@playwright/test').APIRequestContext,
): Promise<void> {
  const res = await request.post(`${BFF_URL}/api/trajectories/drain`);
  expect(res.ok(), await res.text()).toBeTruthy();
}

/** Return the number of pytest test-case ids inside a class. */
function countCasesInClass(): number {
  const out = execFileSync(
    PYTEST_BIN,
    [
      `${TEST_FILE_REL}::${TEST_CLASS}`,
      '--collect-only',
      '-q',
      '--no-header',
      '--disable-warnings',
    ],
    { cwd: WORKSPACE_PATH, encoding: 'utf8' },
  );
  // `pytest -q --collect-only` prints one node-id per line, then a
  // blank line and a summary. Count only lines that look like node
  // ids (contain `::`).
  return out
    .split('\n')
    .filter((line) => line.includes('::') && line.includes(TEST_CLASS))
    .length;
}

test.beforeAll(async ({ request }) => {
  const res = await request.get(`${BFF_URL}/api/runs`).catch(() => null);
  const testFileAbs = join(WORKSPACE_PATH, TEST_FILE_REL);
  const missing: string[] = [];
  if (!res || !res.ok()) missing.push(`BFF ${BFF_URL}`);
  if (!existsSync(testFileAbs)) missing.push(`test file ${testFileAbs}`);
  if (!existsSync(PYTEST_BIN)) missing.push(`pytest ${PYTEST_BIN}`);
  test.skip(missing.length > 0, `G.1 preconditions unmet: ${missing.join(', ')}`);
});

test.describe('G.1 — Forge-OH self-testing', () => {
  test('agent adds one new passing test case to TestSymptomProducer', async ({
    request,
  }) => {
    // Playwright's default per-test timeout is 30s. The agent run
    // itself can take multiple minutes on a local model; give
    // Playwright headroom over our own poll deadline.
    test.setTimeout(RUN_TIMEOUT_MS + 60_000);

    const testFileAbs = join(WORKSPACE_PATH, TEST_FILE_REL);

    // Guard: don't run this spec if the marker case already exists
    // (e.g. left behind by a prior run). Reset before proceeding so
    // baseline math stays honest.
    const preContent = readFileSync(testFileAbs, 'utf8');
    expect(
      preContent.includes(NEW_TEST_NAME),
      `marker test ${NEW_TEST_NAME} already present in ${testFileAbs} — ` +
        'remove it before rerunning this spec so the +1 assertion is valid',
    ).toBeFalsy();

    const baseline = countCasesInClass();
    expect(baseline, 'baseline case count must be > 0').toBeGreaterThan(0);

    const taskPrompt = [
      `In the file ${TEST_FILE_REL}, inside the existing class \`${TEST_CLASS}\`,`,
      'append EXACTLY the following new test method (do not modify any other',
      'code in the repository, and do not rename existing methods):',
      '',
      '```python',
      NEW_TEST_BODY,
      '```',
      '',
      'Preserve the existing indentation style (4 spaces). Place the new',
      'method after the last existing method in the class. Do not run',
      'pytest, do not commit anything, just save the file. Confirm the',
      'file was written by reading the last 30 lines back.',
    ].join('\n');

    const cid = await createRun(
      request,
      'G.1 — self-testing add case',
      taskPrompt,
    );
    const status = await waitForTerminal(request, cid);
    expect(status).toBe('succeeded');

    await drainTrajectories(request);

    // File on disk should now contain the marker.
    const postContent = readFileSync(testFileAbs, 'utf8');
    expect(
      postContent.includes(NEW_TEST_NAME),
      `marker test ${NEW_TEST_NAME} not found in ${testFileAbs} after run — ` +
        'agent did not persist the edit',
    ).toBeTruthy();

    // Pytest collection must now count exactly baseline + 1 cases.
    const post = countCasesInClass();
    expect(post).toBe(baseline + 1);

    // The new case must actually pass in isolation.
    const runOut = execFileSync(
      PYTEST_BIN,
      [NODE_ID, '-q', '--no-header', '--disable-warnings'],
      { cwd: WORKSPACE_PATH, encoding: 'utf8' },
    );
    expect(runOut).toMatch(/1 passed/);
  });
});
