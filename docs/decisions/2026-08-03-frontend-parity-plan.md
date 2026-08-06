# Frontend Parity Plan — F.20 through F.31

**Author:** Perplexity Computer
**Date:** 2026-08-03 21:14 EDT
**Status:** Decision doc (not a locked ADR — promote to slices individually)
**Parent audit:** `docs/frontend-backend-gap.md`

Twelve build slices closing the frontend-backend parity gap identified in the audit. Sequenced in dependency order.

Each slice inherits the standard Forge-OH DoD (see `docs/DEFINITION_OF_DONE.md`): tests, Playwright visual, no `EmptyState` unless the resource is genuinely empty, keyboard shortcuts, dark-first design tokens.

---

## F.20 — Dead-stub cleanup

**Category:** D (dead code)
**Scope:** delete `bff/routers/agents.py` and `src/app/(dashboard)/settings/secrets/page.tsx`. Grep for stale imports.
**DoD:** `pytest bff/`, `pnpm build`, and `pnpm test` all green. No route or page references the deleted files.
**Stop condition:** commit pushed; nothing else touched.
**Effort:** ~15 min.

## F.21 — Agent Presets page (Category A)

**Scope:** real `/agents` page consuming `/api/agent-presets/*`. List presets, view, create, duplicate, edit, delete, set-default.
**Ports touched:** none on backend (already complete). Frontend `src/features/agent-presets/`.
**DoD:** all 7 backend endpoints exercised via the UI; Playwright spec verifies list + create + set-default; empty-state only when list is truly empty.
**Stop condition:** page replaces the current 6-line `EmptyState` stub.
**Effort:** ~1 slice.

## F.22 — Tools & MCP page (Category A)

**Scope:** real `/tools-mcp` page consuming `/api/mcp/*`. List MCP servers, add/remove, enable/disable, ping.
**Design ambiguity to flag:** page name says "Tools & MCP" but backend exposes MCP only. Either (a) rename page to "MCP Servers", or (b) add a Tools sub-tab that documents the OpenHands tool inventory. **Ask user before starting.**
**DoD:** all 5 backend endpoints exercised via UI; Playwright spec verifies add + toggle + ping.
**Stop condition:** page replaces the current 6-line `EmptyState` stub.
**Effort:** ~1 slice.

## F.23 — Metrics dashboard (Category A)

**Scope:** real `/metrics` page consuming `/api/metrics/*`. Overview cards (summary), daily runs chart, models breakdown, workspaces breakdown, cost trend.
**DoD:** all 8 backend endpoints exercised; recharts or equivalent renders; Playwright verifies chart presence.
**Stop condition:** page replaces the current 6-line `EmptyState` stub.
**Effort:** ~1 slice.

## F.24 — Notifications (Category B)

**Scope:** Topbar bell dropdown showing unread count + list. Mark-read + mark-all-read + delete.
**DoD:** 4 backend endpoints exercised; Topbar shows unread badge; keyboard-accessible.
**Design ambiguity:** need to decide if there's ALSO a full `/notifications` page or only the bell. **Ask user.**
**Stop condition:** bell wired end-to-end.
**Effort:** ~1 slice.

## F.25 — Link Secrets into Sidebar (Category B)

**Scope:** add sidebar entry pointing at the existing 99-line `/secrets` page. Feature-flag currently gates it (`NEXT_PUBLIC_FEATURE_SECRETS_ENABLED`); decide if flag stays.
**DoD:** sidebar entry appears; page loads and functions as before.
**Stop condition:** nav entry added, dead `settings/secrets` stub removed (already covered by F.20).
**Effort:** ~0.5 slice.

## F.26 — Trajectories (Category B)

**Scope:** either a top-level `/trajectories` page OR a Settings sub-tab "Trajectory Memory". **Ask user which.**
**Uses:** `/api/trajectories/*` (list, detail, search, drain).
**DoD:** search + browse works; drain button gated by confirmation.
**Effort:** ~1 slice.

## F.27 — Terminal per-run (Category C)

**Scope:** replace `runs/[runId]/terminal/page.tsx` 7-line stub with the real xterm/bash streaming shell. Components in `src/features/terminal/` already built.
**Uses:** `/api/runs/{id}/bash/*`.
**DoD:** terminal opens, streams events via `/stream`, supports execute + kill.
**Effort:** ~0.5 slice.

## F.28 — Files per-run (Category C)

**Scope:** replace `runs/[runId]/files/page.tsx` 7-line stub. Or delete the route if `FilesTab` inside `runs/[runId]` suffices. **Ask user.**
**Uses:** `/api/runs/{id}/files*`, `/api/runs/{id}/git/*`.
**DoD:** browse + diff working per DoD-standard.
**Effort:** ~0.5 slice.

## F.29 — Browser Session View (Slice 4A from Definitive Plan)

**Scope:** real UI for `/api/runs/{id}/browser`. Live session viewer with playback.
**Category:** E (net-new).
**Effort:** ~1 slice.

## F.30 — Trace Explorer top-level (Slice 4C from Definitive Plan)

**Scope:** a `/trace` (or `/observability/traces`) explorer deeper than the current Observability dashboard.
**Category:** E (net-new).
**Effort:** ~1 slice.

## F.31 — Approvals inbox (Slice 5A support UI)

**Scope:** page listing runs blocked awaiting approval; approve/reject inline.
**Uses:** `/api/runs`, `/api/runs/{id}/approve|reject`.
**Category:** E (net-new).
**Effort:** ~1 slice.

---

## Sequencing recommendation

**Wave 1 — Cleanup + Category A (visible sidebar stubs):** F.20 → F.21 → F.22 → F.23. Highest user-visible impact per unit effort. F.20 first because it removes noise; F.21–F.23 are independent and can be scheduled in any order.

**Wave 2 — Category B (features that work but are unreachable):** F.25 (Secrets nav) → F.24 (Notifications bell) → F.26 (Trajectories). F.25 first because it's the smallest and unblocks Secrets discovery.

**Wave 3 — Category C (per-run stubs):** F.27 → F.28. Improves the run-detail experience.

**Wave 4 — Category E (net-new slices from Definitive Plan):** F.29 → F.30 → F.31. Scheduled after parity is achieved.

---

## Ambiguities requiring user decision before F.22, F.24, F.26, F.28

Flag list — do not start these slices without answers:

1. **F.22:** rename `/tools-mcp` to `/mcp`, or keep name and add a Tools sub-tab? What does "Tools" mean here — OpenHands built-in tools, or something else?
2. **F.24:** notifications = Topbar bell only, or bell + full page?
3. **F.26:** trajectories = top-level page or Settings sub-tab?
4. **F.28:** keep `runs/{id}/files/page.tsx` route or delete in favor of the existing FilesTab?

## Non-goals

- Does not commit to executing any of these slices in this session.
- Does not touch backend routes.
- Does not decide sequencing against non-parity work (Kosmos plugin migration, F.19.5 native venv, etc.).
