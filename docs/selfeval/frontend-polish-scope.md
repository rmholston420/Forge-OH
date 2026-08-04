# Self-Eval Frontend Polish — Scope Doc

**Slice:** `slice/selfeval-frontend-polish`
**Author:** Perplexity Computer
**Date:** 2026-08-04 02:49 EDT
**Status:** DRAFT — awaiting operator approval before any code changes

## Current-state inventory (verified from source, `29ff23a` + `9a0e1d0`)

### Files backing the two routes

| Concern | Path |
|---|---|
| `/selfeval` route entry | `src/app/(dashboard)/selfeval/page.tsx` |
| `/selfeval/[date]` route entry | `src/app/(dashboard)/selfeval/[date]/page.tsx` |
| History + Run-now page | `src/features/selfeval/SelfEvalPage.tsx` |
| Cycle detail page | `src/features/selfeval/SelfEvalDatePage.tsx` |
| React-Query hooks | `src/features/selfeval/hooks.ts` |
| BFF client | `src/features/selfeval/api.ts` |
| BFF router | `bff/routers/selfeval.py` |
| Sidebar entry | `src/components/navigation/Sidebar.tsx` (line 15, `/selfeval` label `Self-Eval`, icon `⏰`) |
| Playwright smoke | `src/tests/e2e/selfeval.spec.ts` (3 tests, empty-state only) |

### BFF surface (unchanged this slice; polish is FE-only)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/selfeval/cycles` | `{cycles: CycleListItem[]}` newest-first |
| GET | `/api/selfeval/cycles/{filename}` | full `CycleSummary` |
| GET | `/api/selfeval/proposals?date=YYYY-MM-DD` | `{proposals: ProposalListItem[]}` |
| GET | `/api/selfeval/proposals/{filename}` | `{filename, body}` (Markdown) |
| POST | `/api/selfeval/run` | fires `systemctl --user start forge-oh-selfeval.service`; 409 if in-flight |
| GET | `/api/selfeval/status` | `{running, started_at, last_result}` |

`useStatus()` polls every 5s while `running=true`, every 30s otherwise. `useRunNow()` invalidates cycles + status on success.

## Findings from code inspection

Grep of every class name referenced by the two pages against `src/**/*.css`:

| Class | Defined? | Where |
|---|---|---|
| `selfeval-page` | ❌ MISS | — |
| `selfeval-date-page` | ❌ MISS | — |
| `page-header` | ✅ | `styles/legacy-globals.css:280` |
| `data-table` | ❌ MISS | — |
| `kpi-grid` | ✅ | `styles/legacy-globals.css:314` |
| `kpi` | ✅ (nested) | `styles/legacy-globals.css:314` |
| `kpi-label` | ❌ MISS | — |
| `kpi-value` | ❌ MISS | — |
| `badge`, `badge--success/error/warning` | ⚠️ CSS-Module only (`Badge.module.css`) — won't apply from raw string className |
| `card` | ⚠️ CSS-Module only (`PluginCard.module.css`) — won't apply from raw string className |
| `btn--primary`, `btn--disabled` | ⚠️ Module-scoped (`Button.module.css`); the "disabled" variant isn't defined at all |
| `text-muted`, `text-error`, `skeleton` | ✅ | legacy-globals / theme |
| `proposal-list` | ❌ MISS | — |

**Net effect on Colossus:** the pages render, layout is basically legible (thanks to `page-header`, `kpi-grid`, `data-table` browser defaults), but:
- Verdict badges probably render as unstyled inline text (module class strings are hashed at build time; passing the raw source name from a `Record<string,string>` produces no match).
- The primary "Run now" button is missing its filled-button treatment for the same reason.
- The `<details><summary>` proposal cards have no card chrome.
- KPI values inherit only the parent stack, no size/weight emphasis.

Additional behavior gaps (from source, not visual — visual to be verified via screenshots):
1. **No live cycle progress.** While `running=true`, the button shows "Running…" but the page has zero indication of which task is currently executing, elapsed time, or ETA. `_state.last_result` is populated at cycle end only; no per-task streaming.
2. **No "just finished" toast/notice.** When a cycle transitions running→false, the cycles table quietly refetches; the user has to look at the table to know it landed.
3. **Cycle history doesn't link elapsed duration or model tag.** The `CycleSummary` has `started_at`+`finished_at`; the list view drops both. Duration would be a useful sort/filter dimension.
4. **`/selfeval/[date]` "Trajectory status" column can be `null`** — displayed as `—`. When present it's raw enum text (`agent-finished`, `errored`, `timed_out`), no visual grouping.
5. **Proposals section is date-scoped correctly, but "No proposals for this date" appears even when the cycle itself hasn't landed proposals yet** — no distinction between "cycle produced zero proposals" and "cycle didn't run".
6. **Playwright spec covers empty-state only.** No populated-state assertions (the exact operator ask for step 4 of the queued sequence).

## Proposed polish scope (execution order — dependency-first)

**All items below are frontend-only. No BFF changes. No new routes. No new BFF endpoints.**

### 0. Baseline screenshots (BEFORE any code changes)
On Colossus, run a new small spec that captures:
- `/selfeval` empty state (already covered) — take a fresh screenshot too
- `/selfeval` populated state (Colossus has 1+ cycles as of `a698bd2` verification)
- `/selfeval/2026-08-04` populated state
- `/selfeval/9999-99-99` invalid-date error path

Purpose: reference for before/after diff. Screenshots go to `screenshots/selfeval-*.png`, `git add -f` + committed.

### 1. Fix CSS class hygiene (unblocks everything visual)
Two sub-options — I recommend **1a** for consistency with the rest of the codebase that IS using CSS Modules (Badge, Button, PluginCard):

- **1a.** Introduce `src/features/selfeval/SelfEval.module.css` with:
  `page`, `datePage`, `header`, `dataTable`, `kpiLabel`, `kpiValue`, `proposalList`, `verdictBadge`, `verdictBadgeSuccess/Error/Warning`, `runButton`, `runButtonRunning`, `emptyStateHint`, `cycleRowLink`, `proposalCardSummary`.
  Refactor both `SelfEvalPage.tsx` + `SelfEvalDatePage.tsx` to import + apply `styles.*`. Delete the string class references that never matched.
- **1b.** (Rejected in favor of 1a — but noting for the record.) Add the missing classes to `styles/legacy-globals.css`. Faster patch, but perpetuates the two-CSS-systems drift; the rest of Slice-C+ moved to modules.

### 2. Verdict badges & KPI value styling
- Verdict badges use `.verdictBadge` + `.verdictBadgeSuccess/Error/Warning` — thin colored pill matching `Badge.module.css` visual language (rgba(53,196,124,.15) etc.) so it reads consistent with the rest of the app.
- KPI values: 24px/600 weight, muted label. Matches the `KpiCard` treatment already used in `/metrics`.

### 3. Cycle history table additions
- Add "Started at" column (formatted `HH:mm`, cell has full ISO in `title` attr).
- Add "Duration" column (`finished_at - started_at` seconds → `Xm Ys` or `Xs`).
- Right-align numeric columns.

### 4. Live-cycle indicator
- While `status.running=true`, show a slim progress rail at the top of the page: cycle start time + elapsed time counter (client-side `setInterval` on cached start_at). No BFF change — this is a pure derived state.
- On running→false transition, show a one-shot inline notice: "Cycle finished at HH:mm — X passed, Y failed" derived from the freshest cycles-list refetch that `useRunNow.onSuccess` triggers.

### 5. Cycle detail polish
- "Trajectory status" column → colored dot (`agent-finished` green, `timed_out` yellow, `errored` red, other neutral).
- Duration cell right-aligned + monospaced.
- Task ID column renders as a `<code>` element (visually distinguish from prose).
- Proposal cards get real card chrome via `styles.proposalCardSummary` (uses existing `--surface-*` design tokens from `theme.css`).

### 6. Empty vs "cycle didn't run" copy
- If `useStatus().last_result` is null and `useCycles().cycles.length === 0` → "No cycles yet. Hit **Run now** to fire the first one."
- If cycles exist but this date has none → "No proposals recorded for {date}." (already close; wording tweak only)

### 7. Populated-state Playwright coverage (step 4 of queued sequence)
Extend `src/tests/e2e/selfeval.spec.ts`:
- Fixture: seed `docs/selfeval/2026-08-04-selfeval.json` with the fixture we already verified in `a698bd2`, OR skip when the BFF returns zero cycles.
- Assertions:
  - `getByRole('row').filter({ hasText: '2026-08-04' })` is visible (history row).
  - Clicking `Open →` navigates to `/selfeval/2026-08-04`.
  - KPI grid shows `3` passed, `0` failed.
  - Task-outcomes table has 3 rows.
  - Verdict badges have the `verdictBadgeSuccess` module class.
  - "Trace →" link on a passed task navigates to `/runs/<id>`.
- Workflow assertion:
  - `getByRole('button', {name: /run now/i})` click → 200 or 409. If 200, poll status endpoint until `running=false`, then assert cycle count went up by one.
  - Skip the "actually launch" test when `PLAYWRIGHT_SKIP_SELFEVAL_LAUNCH=1` (default on) so the spec doesn't burn a real cycle every CI/dev run.

### 8. Screenshot re-capture (AFTER polish)
Rerun the spec from step 0 to produce after-screenshots for the BUILD_LOG entry.

## Explicitly NOT in scope
- No BFF endpoint changes (add/rename/behavior).
- No cycle streaming (SSE / WebSocket). Poll-based is fine at MVP tier.
- No proposal accept/reject UI. Proposals stay read-only Markdown in this slice.
- No multi-cycle-per-day UX. That's the follow-up ADR called out in `SelfEvalDatePage.tsx`.
- No changes to `bff/routers/selfeval.py`, `bff/tests/test_selfeval_router.py`, or the systemd unit under `ops/systemd/`.
- No sidebar icon change (`⏰` stays until a proper icon-set slice).

## Definition of Done
1. All string-based classes on `SelfEvalPage` and `SelfEvalDatePage` either resolve or are replaced by module classes that do.
2. `pnpm exec playwright test src/tests/e2e/selfeval.spec.ts` **passes green** with the new populated-state assertions on Colossus.
3. Before/after screenshots committed under `screenshots/selfeval-*.png`.
4. Existing 3 empty-state tests still pass.
5. BUILD_LOG appended with file list, test counts, and screenshot references.

## Stop condition
Stop and ask if:
- Any polish item requires a BFF endpoint or shape change → out of scope, would need its own slice.
- Playwright can't run to green on Colossus after two attempts → stop, log DEBUG_LOG, ask.
- Any polish item forces a design-token change to `theme.css` beyond adding a new component-local class.

## Estimated size
Small-to-medium. Approx:
- 1 new `.module.css` file (~120 lines)
- 2 refactors (`SelfEvalPage.tsx`, `SelfEvalDatePage.tsx`) — mostly className churn plus 2 small feature adds (live-cycle rail + finished notice)
- 1 spec extension (~80 new lines, existing 3 tests kept)
- 0 new dependencies
