# ADR-010 — Frontend Parity Scope: F.20–F.31

**Status:** Proposed
**Lock-in phase:** Pre-F.20 (this ADR must ratify before F.20 executes)
**Supersedes:** —

## Context

An audit conducted 2026-08-03 (`docs/frontend-backend-gap.md`) identified twelve gaps between the Forge-OH BFF surface and its Next.js frontend. Three sidebar entries (Agents, Tools & MCP, Metrics) route to `<EmptyState/>` placeholder pages despite fully implemented backend endpoints. Three feature modules (Notifications, Trajectories, Secrets) have working data layers and, in Secrets' case, a full page — but no sidebar entry. Two per-run routes (terminal, files) are 7-line stubs even though their components exist. Three named slices from the Definitive Build Plan (Browser Session View 4A, Trace Explorer 4C, Approvals inbox 5A) have never been built.

The audit proposed twelve F.20-series slices (`docs/decisions/2026-08-03-frontend-parity-plan.md`). Before executing any of them, three load-bearing choices must be locked:

**Q1 — Do parity slices (F.20–F.28) block on Definitive-Plan slices (F.29–F.31), or vice versa?** F.29–F.31 are canonical Phase-4/5 work already in the plan; F.20–F.28 are corrective. Sequencing implications differ.

**Q2 — Does an EmptyState-with-live-sidebar-link count as a bug or as an accepted "coming soon"?** The Definition of Done says "no `EmptyState` unless the resource is genuinely empty" — Agents/Tools&MCP/Metrics stubs violate this, but they've been in the tree since Slice 1A landed and no prior slice was cancelled to fix them.

**Q3 — Is "everything the BFF exposes must have a frontend consumer" a hard invariant going forward?** Some backend resources (e.g. `/api/plugins/*`) are passthroughs to the OpenHands agent-server and may not warrant Forge-OH-native UI.

## Decision

**Q1 = A** — Parity work (F.20–F.28) executes before net-new Definitive-Plan slices (F.29–F.31). Rationale: a user cannot discover new features when three sidebar entries are dead. Fixing what already claims to work is prerequisite to shipping more.

**Q2 = A** — Live sidebar link pointing at `<EmptyState/>` is a **bug** and counts against the current-slice DoD. The three stubs (Agents, Tools & MCP, Metrics) are treated as legacy DoD violations from Slice 1A that F.21–F.23 discharge. No new slice may introduce a sidebar link whose page is stub-only.

**Q3 = B** — A new invariant is adopted: **every wired BFF router must have a documented consumer surface — either a Next.js page, a Topbar/sidebar affordance, or an explicit "internal API only" tag in the router docstring.** F.24–F.26 discharge the current-state violations. Going forward, `bff/main.py` review must confirm the consumer path for any newly-included router.

## Rationale

**Q1 rejects B (interleave parity and net-new) and C (defer parity)**. Interleaving loses focus per single-slice-at-a-time discipline. Deferring parity ships more features on top of a broken navigation surface — worse UX every slice.

**Q2 rejects B (accept as "coming soon")**. Accepting `<EmptyState/>` as valid means the DoD phrase "no `EmptyState` unless the resource is genuinely empty" is toothless. If the pattern is acceptable, the DoD needs an amendment; if not, the current tree has DoD-violating slices. This ADR chooses the latter interpretation.

**Q3 rejects A (no invariant needed)** and **C (frontend must match backend 1:1 with a page)**. A is the status quo that let the current gaps accumulate. C over-constrains — internal-only routers (health checks, admin endpoints) shouldn't require pages. B allows the pragmatic middle: every router has a documented consumer, but the consumer can be a page, a component embed, a Topbar element, or an explicit backend-only tag.

## Consequences

- `docs/DEFINITION_OF_DONE.md` amended to add: **"Any new sidebar entry must route to a real page; adding a sidebar link that points at an `<EmptyState/>` fails DoD."** Filed as a separate amendment PR alongside F.20.
- `docs/adr/README.md` (if it exists) or the ADR list in `docs/adr/` — index entry for ADR-010 added.
- `docs/decisions/2026-08-03-frontend-parity-plan.md` is the sequencing document for F.20–F.31. F.20–F.28 execute before F.29–F.31 per Q1.
- `bff/main.py` review checklist adds: for each newly-included router, note the consumer surface (page path, component embed, Topbar element, or `# internal-only` tag).
- No `PORTING_LEDGER.md` entry — this is a scoping decision, not a vendor.
- No spec edit required — no Definitive Build Plan section changes; F.29–F.31 already exist there and their sequencing is not re-numbered.
- `BUILD_LOG.md` gets an entry when this ADR is committed.

## Lock-in phase

Pre-F.20. This ADR ratifies before F.20 executes. Every F.20-series slice references this ADR by number.

## References

- `docs/frontend-backend-gap.md` — the audit
- `docs/decisions/2026-08-03-frontend-parity-plan.md` — the slice plan
- `docs/DEFINITION_OF_DONE.md` — the DoD this ADR enforces
- `docs/Forge-OH-Build-Plan-Definitive.md` §Phase 4–5 — the source of F.29–F.31
