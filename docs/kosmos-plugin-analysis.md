# Kosmos Plugin Analysis — Should Forge-OH Become a Tektos-Adjacent Plugin Now?

**Date:** 2026-08-03
**Author:** Perplexity Computer (audit branch `audit/frontend-backend-parity`)
**Status:** RECOMMENDATION — **NOT NOW.** Revisit at Forge-OH Phase 5, or when Kosmos plugins that Forge-OH would want to consume (Gnosis-as-plugin, Koinonia A2A) exist as `PluginDescriptor`-registering modules — Gnosis exists today only as a kernel-side retrieval surrogate at `/api/gnosis/*`, not as a plugin.

**Evidence discipline:** all claims about Kosmos in this doc are derived from source code in `plugins/`, `ports/`, `kernel/`, and `ui/` at commit `c455165`. Docs (`SESSION_HANDOFF.md`, `Kosmos-Build-Sequence-v25.md`, ADR index) are treated as un-verified narrative and not cited for state claims. This matters — the docs describe some stages as "NOT STARTED" that actually have substantial code, and describe some stages as "LANDED" whose behavior on Colossus we did not exercise.

**Related:** `docs/decisions/2026-08-03-improvement-slate.md` (already surveys reusable Tektos components without requiring plugin conversion).

---

## Executive Summary

The user asked: "determine if it would be of value to make Forge-OH a plugin under Kosmos's Tektos now."

**Answer: no, not now.** Three converging reasons based on Tektos + Kosmos source code:

1. **The Tektos slot is already occupied by a fully-formed sibling.** `plugins/tektos/` in Kosmos main is real code, not spec — one `TektosAgent` importing five kernel ports (`LLMPort`, `MemoryPort`, `MCPPort`, `ApprovalGatewayPort`, `TraceFeedPort`), an OpenSpec parser + plan producer, an aider-style RepoMap indexer, a Pier subprocess-invoked eval harness with a DeepSWE-manifest loader, a docling ingest harness, a FastAPI/HTMX UI, and a registered `PluginDescriptor` with a `/tektos` Route and an `APPROVALS_QUEUE` Panel at priority 90. Forge-OH is an OpenHands runtime host with a Next.js BFF, wired to real vLLM backends on Colossus — not a superset of Tektos and not shaped like a Kosmos plugin.
2. **Conversion cost is a full BFF+UI rewrite.** Kosmos plugins do not expose HTTP; they expose a `PluginDescriptor` whose lazy React modules the Kosmos Next.js dashboard imports. Forge-OH's 16 BFF routers + Next.js App Router are the wrong shape for that surface. Every runtime path (LLM call, tool call, plan approval, memory write, trace emission) would be re-routed through Kosmos ports with zero-trust provenance/confidence invariants Forge-OH does not currently enforce.
3. **Reuse without conversion is already the plan of record.** The improvement-slate doc committed to Forge-OH's `docs/decisions/` on 2026-08-03 already identified four Tektos components that could be pattern-vendored INTO Forge-OH (Pier eval harness, DeepSWE corpus subset, OpenSpec plan producer, RepoMap indexer) without requiring Forge-OH to adopt Kosmos's kernel, ports layer, or ADR ceremony.

Becoming a plugin means adopting an architecture optimized for a system that does not yet exist in a form Forge-OH can plug into. Recommendation is to keep Forge-OH standalone through Phase 4 completion, borrow Tektos code where clean, and reassess plugin conversion once Kosmos hits Stage 4 (Gnosis) or later.

---

## Section 1 — What "Being a Kosmos Plugin" Concretely Means

Extracted from `ports/frontend_contract.py`, `plugins/tektos/plugin.py`, and `docs/Kosmos-Build-Spec-v25.md` §17 in Kosmos main @ `c455165`:

### 1.1 Mandatory descriptor shape

Every plugin must construct a frozen `PluginDescriptor` with:

- `name` — kebab-case identifier
- `state_namespace` — reserved key in the kernel state store
- `version` — semver string
- `kernel_compat` — semver-range against the kernel version
- `design_tokens` — dict of CSS custom properties (must merge cleanly with kernel-owned tokens; violations rejected at `register_plugin()`)
- `routes` — tuple of `Route(path, label, icon, lazy_module)` (each route must lazy-load a React module the kernel dashboard imports at runtime)
- `panels` — tuple of `Panel(id, slot, priority, lazy_module, plugin_name)` where `slot` is one of nine enumerated `PanelSlot` values (`APPROVALS_QUEUE`, `ALGEDONIC`, `GOVERNANCE`, `MEMORY_INTEGRITY`, `MODEL_SWAP_SLO`, `STUB_DEGRADATION`, `CONTEXT_PRESSURE`, `HARDWARE_RESILIENCE`, `AGENT_TRACE`)

### 1.2 Mandatory port consumption discipline (ADR-007)

A plugin **may only import from `ports/*`** — never from another plugin's module tree. AST-verified per-plugin by tests like `plugins/tektos/tests/test_tektos_agent.py::test_tektos_agent_imports_no_other_plugins_adr_007`. Cross-plugin coupling is events-only through `MemoryPort.write_event` + `MemoryPort.query_temporal`.

Tektos consumes six ports:

- `LLMPort` (verb: `generate_text`)
- `MemoryPort` (verbs: `write_event`, `query_temporal`, `search_semantic`)
- `MCPPort` (verbs: `initialize`, `list_tools`, `call_tool`, `close`)
- `ApprovalGatewayPort` (verb: `propose`)
- `ApprovalResolverPort` (verb: `list_pending` — added at Stage 3.11)
- `TraceFeedPort` (verb: `publish`)
- `FrontendContractPort` (verb: `register_plugin` — for the descriptor above)

### 1.3 Mandatory zero-trust memory-write invariants (ADR-008)

Every `MemoryPort.write_event` call must carry `provenance` + `confidence` in `(0, 1]`. Confidence formulas are locked per predicate (e.g., RepoMap uses linear-decay over a 30-day freshness window with `min_confidence=0.01`; DeepSWE corpus uses `n_pass/n_total`; Pier eval uses `1.0` on PASS / `0.0` on FAIL). Non-conformance rejected at the port level.

### 1.4 UI Parity Rule (ADR-014)

Every plugin descriptor carries a `ui_parity_status` in `{NOT_STARTED, IN_PROGRESS, COMPLIANT, GRANDFATHERED}`. `COMPLIANT` requires at least one `Route` AND at least one `Panel` at kernel-dashboard registration time. Enforced on every phase after Tektos Phase 2.

### 1.5 What this means for Forge-OH

To convert Forge-OH into a Kosmos plugin, we would need to:

1. **Delete or radically refactor the BFF.** BFF endpoints do not map to Kosmos ports — Kosmos plugins do not expose HTTP; they expose `PluginDescriptor` + lazy React modules the kernel loads. The 16 BFF routers (Conversations, Runs, Files, Terminal, RepoGraph, Plugins, Governance, Metrics, Notifications, Trajectories, Verify, Secrets, Skills, MCP-Servers, Tools-MCP, Health) collapse into memory-event predicates + one route + zero or more panels.
2. **Rewrite frontend as lazy React modules keyed off `Route.lazy_module`.** The Next.js App Router at `web/app/(dashboard)/` becomes obsolete — the kernel dashboard is the shell, not Forge-OH.
3. **Refactor every OpenHands SDK integration point through Kosmos ports.** OpenHands `LLM` calls → `LLMPort.generate_text`. Every tool call → `MCPPort.call_tool` gated through `ApprovalGatewayPort.propose`. Every event → `MemoryPort.write_event` with locked provenance/confidence. Every trace → `TraceFeedPort.publish`.
4. **Adopt Kosmos ADR ceremony.** Every non-reversible decision requires a formal ADR under `docs/adrs/` following the Kosmos template (Context / Decision / Rationale / Consequences / Lock-in phase / References). Kosmos currently sits at ADR-045 with numbering reserved through ~ADR-076.
5. **Adopt Kosmos build-log discipline for the Tektos plugin slot.** Every slice appends to Kosmos's `BUILD_LOG.md`, not Forge-OH's. Stage-gate DoD literals must be defined and green before any slice is considered landed.

None of this is impossible — Tektos itself follows exactly this discipline and has landed 815 tests over 11 phases in ~5 weeks. But it is expensive, and the payoff depends entirely on Kosmos being close enough to production to make plugin membership a delivery accelerator rather than a delivery tax.

---

## Section 2 — Kosmos Readiness Assessment (from code, not logs)

**Method:** inventoried `plugins/`, `ports/`, `kernel/`, `ui/`, and `adapters/` in Kosmos main @ `c455165`. Ignored `SESSION_HANDOFF.md`, `BUILD_LOG.md`, `docs/Kosmos-Build-Sequence-v25.md`, and the ADR index for status claims. What is a `.py` file with imports and definitions counts as landed; what is only in docs does not.

### 2.1 What exists as code today

| Subsystem | Path | Evidence | Verdict |
|---|---|---|---|
| Kernel dispatcher | `kernel/app.py` | 2746 lines, FastAPI, health + memory + praxis + gnosis-graph + zetesis endpoints | LANDED |
| Ports layer | `ports/*.py` | 17 port modules: approval, data, embeddings, event_bus, event_envelope, frontend_contract, llm, mcp, memory, notification, observability, resource, search, secrets, trace_feed, vector | LANDED |
| Next.js dashboard | `ui/` | Next 16.2.11 + React 19, cytoscape, force-graph, Sidebar, AlgedonicBanner, PersistentShell, CommandPalette, NotificationTray, kernel-client | LANDED |
| Praxis (governance) | `plugins/praxis/` | 18 .py files; `build_praxis_descriptor()` registers governance + approvals Panels; `apex/` + `constitution/` submodules | LANDED AS PLUGIN |
| Phrouros (observability) | `plugins/phrouros/` | 12 .py files; `build_phrouros_descriptor()` registers trace Panel; `detectors/` + `engine.py` | LANDED AS PLUGIN |
| Tektos (coding) | `plugins/tektos/` | 12,935 LOC across `agent`, `openspec`, `repomap`, `eval` (Pier + DeepSWE), `ingest` (docling), `mcp`, `renderer`, `ui`; descriptor with Route `/tektos` + Panel `APPROVALS_QUEUE@90` | LANDED AS PLUGIN |
| Zetesis (research) | `plugins/zetesis/` | 28 .py files; descriptor consumes 12 ports (data, event_bus, llm, memory, notification, observability, resource, search, secrets, vector, embeddings, frontend_contract) | LANDED AS PLUGIN |
| Gnosis (knowledge) | kernel surrogate, NOT `plugins/gnosis/` | `kernel/app.py` exposes 9 `/api/gnosis/*` endpoints (query, corpora, stats, event/{id}, plus graph routes) backed by DozerDB corpora seeded at boot (`gnosis_seed` in `_BootRegistry`); 5 corpora committed under `adapters/memory/dozerdb/corpora/` (humanities_bilara, humanities_cidoc, superpowers, synthetic_lifeline, rigpa_export); Next.js UI at `ui/app/gnosis/{page,detail,graph}.tsx` with 3 Playwright specs; kernel comment at line 1293 verbatim: *"The Gnosis plugin does not exist yet (Phase 3 territory); ADR-051 blessed the surrogate pattern at the adapter layer and ADR-064 extends it to an HTTP surface so the GUI Gnosis tab can render corpus facts + provenance + timestamps against real data ahead of `plugins/gnosis/` landing."* | SUBSTANTIALLY BUILT, NOT YET A PLUGIN |
| Oikos (household admin) | `plugins/oikos/` | absent | NOT LANDED |
| Koinonia (A2A transport) | `plugins/koinonia/` | absent | NOT LANDED |

### 2.2 What this means

- **Kosmos is more than a spec.** The kernel + Next.js dashboard + four plugins are real code. `FrontendContractPort` is not aspirational — Praxis, Phrouros, Tektos, and Zetesis all construct `PluginDescriptor` instances and would register at kernel boot.
- **We did not exercise Kosmos on Colossus.** The audit read the tree; it did not run `make stage1-gate`, boot the kernel, or verify the plugins register cleanly against a live Praxis approval flow. Docs claim green pytest counts; that claim is not verified here.
- **Gnosis is substantially built but not yet a plugin.** DozerDB corpora + 9 kernel-side `/api/gnosis/*` routes + a real Next.js `/gnosis` tab work today, but there is no `plugins/gnosis/` with a `PluginDescriptor`. A hypothetical Forge-OH plugin could consume Gnosis retrieval via HTTP (like the UI does) — but that same access is available to a standalone Forge-OH BFF just by calling the kernel's HTTP surface. Plugin membership adds nothing for consuming Gnosis.
- **Koinonia and Oikos do not exist as code.** No transport, no descriptor, no adapters. The multi-agent story Forge-OH would benefit from is unimplemented.
- **Forge-OH already has its own conversation/run persistence via OpenHands** and does not require Praxis + Phrouros to function.

**Implication for Forge-OH:** Kosmos being further along than the logs' "Stage 1.6" summary made it look does NOT strengthen the plugin-conversion case. It weakens it. If Forge-OH became a plugin today, it would compete for the `APPROVALS_QUEUE` panel slot with Tektos (priority 90) and Praxis (priority 100), duplicate Tektos's coding-agent role, and gain access to no Kosmos-side capability Forge-OH lacks. Gnosis retrieval is already reachable via HTTP without plugin membership; Koinonia + Oikos + `plugins/gnosis/` — the surfaces where plugin membership would matter — do not exist as code.

---

## Section 3 — Where Tektos and Forge-OH Overlap and Diverge

### 3.1 Overlap (both systems solve these problems)

- **Coding agent execution loop.** Tektos has `TektosAgent.run()`; Forge-OH has OpenHands runtime + agent server @ `openhands-agent-server==1.40.0`.
- **Plan approval UX.** Tektos has `PlanApprovalPanel` (priority 90 in `APPROVALS_QUEUE`) + HTMX dashboard on `:8765`. Forge-OH has `/runs/[runId]` page with governance/plan tabs backed by BFF `runs`, `plans`, `governance` routers.
- **Tool-call gating.** Tektos has `TEKTOS_TOOL_TIER_MAP` gating tools through `ApprovalGatewayPort.propose`. Forge-OH has BFF `governance` router with tier-based approval endpoints and the `/governance` sidebar page.
- **Memory persistence.** Tektos writes every meaningful event to `MemoryPort` with zero-trust invariants; Forge-OH persists conversations/runs to SQLite through OpenHands storage layer.
- **Eval / regression signal.** Tektos runs Pier trials + DeepSWE corpus subset via `run_pier_trial` + `record_corpus_run`. Forge-OH has the improvement-slate proposal to vendor exactly this into `docs/decisions/2026-08-03-improvement-slate.md` but has not landed it.
- **Document ingestion.** Tektos has docling ingest (`plugins/tektos/ingest/`). Forge-OH has no equivalent — but the audit did not surface this as a user-visible gap.

### 3.2 Divergence (only one system solves this)

**Only Forge-OH has:**

- Live OpenHands SDK runtime with real tool execution on Colossus (not test doubles).
- vLLM router with backend selection (Ollama, vLLM coder qwen3.6-35b-nvfp4 at :8501, vLLM planner at :8511).
- Multi-workspace concept (Runs are keyed by workspaceId — `18c99443…` etc.).
- BFF layer that can proxy MCP servers, expose file operations, and stream terminal output.
- Trajectory viewer + replay (planned).
- Real user data on Colossus — sessions, runs, plans, approvals from actual coding work.

**Only Tektos has:**

- OpenSpec plan producer (deterministic, tested).
- Repomap indexer with locked freshness policy.
- Pier eval harness + DeepSWE corpus subset (both env-gated but production-ready).
- HTMX UI at `:8765` (though this is simpler than Forge-OH's Next.js UI).
- Zero-trust memory-event discipline enforced by port-level guards.
- Formal ADR ceremony for every decision.

The overlap is significant but each system is optimized differently: Tektos is optimized for pattern-purity and eventual embedding into Kosmos; Forge-OH is optimized for direct end-user coding sessions with real OpenHands runtime on real hardware.

---

## Section 4 — The Two Realistic Paths Forward

### Path A — Convert Forge-OH into a Kosmos plugin (rejected)

**What it means:** Deprecate the BFF and Next.js UI. Rewrite Forge-OH functionality as a Kosmos plugin `plugins/forgeoh/` registering a `PluginDescriptor` through `FrontendContractPort`. Every user-visible feature runs through Kosmos kernel dashboard. Every persistence write goes through `MemoryPort` with locked provenance/confidence.

**Effort estimate:** 6–10 weeks of full-time refactor work. Comparable to Tektos Stages 3.1–3.11 which took ~5 weeks with a spec already in hand. Forge-OH does not have that spec. Effort would include:

- Writing a `Forge-OH-Build-Sequence.md` under Kosmos ceremony.
- Authoring ~15 ADRs equivalent to ADR-036 through ADR-045.
- Rewriting every BFF endpoint as a memory-event predicate.
- Deleting the Next.js app; rewriting UI as React lazy modules keyed off `Route.lazy_module`.
- Refactoring OpenHands SDK integration to run through Kosmos ports (LLM, MCP, Approval, Trace, Memory).
- Landing plugin tests to Kosmos gate discipline.

**Cost / benefit:**

- Costs 6–10 weeks of pure refactor with zero user-visible feature gain during the refactor.
- User loses working Colossus system during transition.
- Benefit is realized ONLY if Kosmos reaches production and adds features Forge-OH would want (Praxis governance, Gnosis knowledge, Koinonia A2A) — none of which currently exists.
- If Tektos stays inside Kosmos as the "coding plugin" slot, Forge-OH-as-plugin would collide with Tektos and either force a merge or force Forge-OH to occupy a different slot name.

**Verdict:** REJECTED. High cost, deferred benefit, active downside during transition.

### Path B — Keep Forge-OH standalone, vendor Tektos components à la carte (recommended)

**What it means:** Forge-OH continues under its current architecture (BFF + Next.js + OpenHands runtime). Vendor specific Tektos modules as improvement-slate deliverables — but into Forge-OH's tree at `openhands_tools_ext/` rather than adopting Kosmos ports discipline.

**Concrete backlog items** (already surveyed by the improvement-slate doc):

1. **Pier eval harness** — `plugins/tektos/eval/harness.py` is Apache-2.0 compatible after license verification. Pattern-vendor as `openhands_tools_ext/eval/pier_harness.py`. Wire to a new BFF `/eval` router.
2. **DeepSWE corpus subset** — `plugins/tektos/eval/corpora/deepswe/` is manifest-only. Vendor manifest + loader into `openhands_tools_ext/eval/deepswe/`.
3. **OpenSpec plan producer** — `plugins/tektos/openspec/` is MIT (Fission-AI). Vendor into `openhands_tools_ext/plan/openspec/` and expose through BFF `plans` router.
4. **RepoMap indexer** — `plugins/tektos/repomap/` is Apache-2.0 (aider). Vendor into `openhands_tools_ext/repomap/` and wire to BFF `repograph` router.

**Effort estimate:** 3–5 days per vendored component. Total 2–4 weeks if all four ship. Every component maps cleanly to an existing (currently stubbed) BFF router.

**Cost / benefit:**

- Costs are contained; user keeps working system throughout.
- Every component delivers a user-visible feature the audit identified as needed (RepoMap fills the `/tools-mcp` context-integrity story; Pier fills the `/verify` real-eval story; OpenSpec fills the plan-quality story).
- No coupling to Kosmos kernel readiness.
- If Kosmos hits Stage 4+ later, Forge-OH can revisit plugin conversion having already integrated the Tektos primitives — the refactor cost drops because the integration points are already proven.

**Verdict:** RECOMMENDED.

---

## Section 5 — Explicit Non-Recommendations

1. **Do not merge Forge-OH into `plugins/tektos/`.** Tektos has its own DoD trajectory ratified via ADR-036 through ADR-045. Merging Forge-OH would require re-opening every one of those ADRs.
2. **Do not fork Kosmos and add `plugins/forgeoh/` on the fork.** The `rmholston420/kosmos` main branch is user-owned. A fork creates the maintenance overhead of tracking Kosmos changes without any of the delivery benefits.
3. **Do not adopt Kosmos ports without adopting the kernel.** Kosmos ports are only meaningful within the kernel's registration + dispatch flow. Bolting `ports/*.py` onto Forge-OH without the kernel adds import ceremony with zero enforcement.
4. **Do not defer the frontend-parity audit work** (documented separately in `docs/frontend-backend-gap.md` and slices F.20–F.31) waiting for a Kosmos decision. The parity work is independently valuable and unblocks Forge-OH user-visible correctness regardless of plugin status.

---

## Section 6 — Revisit Criteria

Reassess plugin conversion when ALL of the following are true. Each is checked by looking at code, not logs.

1. `plugins/gnosis/` exists in Kosmos main as a `PluginDescriptor`-registering plugin (not just the current kernel-side surrogate at `/api/gnosis/*`) and Forge-OH would benefit from richer integration than plain HTTP retrieval — verified by inspecting the tree, not by reading a build-sequence claim.
2. `plugins/koinonia/` exists in Kosmos main with a working transport adapter — verified same way.
3. The user is actively running `kernel/app.py` + `ui/` on Colossus for a non-Forge-OH workflow and wants Forge-OH to appear inside that dashboard.
4. Forge-OH has hit Phase 5 (Approvals) completion and Phase 6 (release readiness) is next on the Definitive Plan.
5. The improvement-slate Tektos-component vendoring is complete — meaning Forge-OH already has Pier, DeepSWE, OpenSpec, and RepoMap integrated at `openhands_tools_ext/*`, so plugin conversion is a re-packaging exercise rather than a functionality rewrite.

Until then: Forge-OH stays standalone; Tektos components get vendored as needed; Kosmos stays as an aspirational eventual host, not an immediate one.

---

## References

**Code sources (trusted):**
- Kosmos `ports/*.py` @ `c455165` — 17 port modules including `frontend_contract.py` (`PluginDescriptor`, `Panel`, `Route`, `PanelSlot`), `approval.py`, `memory.py`, `llm.py`, `mcp.py`, `trace_feed.py`
- Kosmos `kernel/app.py` @ `c455165` — 2746-line FastAPI kernel
- Kosmos `ui/` @ `c455165` — Next.js 16 + React 19 dashboard
- Kosmos `plugins/tektos/` @ `c455165` — coding plugin (agent, openspec, repomap, eval, ingest, mcp, ui, plugin.py)
- Kosmos `plugins/praxis/` @ `c455165` — governance plugin (apex, constitution)
- Kosmos `plugins/phrouros/` @ `c455165` — observability plugin (detector, engine, detectors)
- Kosmos `plugins/zetesis/` @ `c455165` — research plugin (adapters, research)

**Forge-OH sources:**
- Forge-OH `docs/decisions/2026-08-03-improvement-slate.md` — reusable Tektos component survey
- Forge-OH `docs/frontend-backend-gap.md` (this audit) — parity gap enumeration
- Forge-OH `docs/adr/010-frontend-parity-scope.md` — ADR-010 (Proposed)

**Kosmos additional code sources (trusted):**
- Kosmos `adapters/memory/dozerdb/corpora/` — five landed corpora (humanities_bilara, humanities_cidoc, superpowers, synthetic_lifeline, rigpa_export)
- Kosmos `ui/app/gnosis/{page,detail,graph}.tsx` — Next.js Gnosis tab consuming `/api/gnosis/*`
- Kosmos `kernel/app.py` lines 1288–1305 + `_BootRegistry.gnosis_corpus_counts` seeder — surrogate rationale documented inline

**Kosmos docs (not trusted for status claims; used only for names/paths/mapping):**
- Kosmos `docs/Kosmos-Build-Sequence-v25.md`
- Kosmos `docs/adrs/README.md`
- Kosmos `SESSION_HANDOFF.md`

Contradictions found between docs and code:
- Docs implied Stage 2 (Praxis + Phrouros) was NOT STARTED; code shows both plugins landed with descriptors.
- Docs implied Stage 6.1 Zetesis was minimally landed; code shows 28-file Zetesis plugin consuming 12 ports.
- Docs implied kernel dashboard was future-scoped; code shows real `kernel/app.py` + Next.js `ui/`.
- Docs did not clearly distinguish "Gnosis substantially built" (true, as kernel surrogate + DozerDB corpora + UI tab) from "Gnosis is a plugin" (false — `plugins/gnosis/` does not exist).
