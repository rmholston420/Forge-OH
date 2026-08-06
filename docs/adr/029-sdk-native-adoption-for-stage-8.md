# ADR-029: SDK-Native Adoption for Stage 8 — Adopt Skills + Condenser + Workspace, Hand-Build the Rest

- **Status:** Ratified (2026-08-06)
- **Date:** 2026-08-06
- **Slice:** Stage 8 initialization (pre-slicing SDK-native investigation spike, per [ADR-028](./028-stage-7-deviation-topology-first-capability-slices-renumbered.md) §4)
- **Amends:** none — reduces scope of Stage 8 slices as scheduled by Council-Synthesis.
- **Supersedes:** —
- **Related:**
  - [ADR-028 (Stage 7 deviation)](./028-stage-7-deviation-topology-first-capability-slices-renumbered.md) — mandated this pre-slice investigation.
  - `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (Perplexity project files repo, commit `8e093bc`) — slice contracts under review.
  - OpenHands SDK v1.40.0 source: [`OpenHands/software-agent-sdk` at `v1.40.0`](https://github.com/OpenHands/software-agent-sdk/tree/v1.40.0).
  - `bff/routers/skills.py:83` — existing Forge-OH consumer of `openhands.sdk.skills.skill.Skill`.

## Context

Council-Synthesis (Gemini 3.1 Pro's angle) claimed that OpenHands SDK 1.40+ already ships three primitives that would make half the Stage 8 custom scaffolding unnecessary:

1. **Microagents** — natively cover Council-Synthesis **§8.6** (ACE-style skill playbook with token budget cap).
2. **Context Condensation** — natively cover a distinct but adjacent concern (context-window management overlaps with §8.6 memory hygiene).
3. **Pluggable Runtime** — natively cover Council-Synthesis **§8.1** (hermetic verification primitive) and **§8.2** (bounded execution-grounded repair loop).

Per ADR-028 §4, this claim was flagged for a 1-hour investigation before any Stage 8 slice is written. This ADR is the deliverable.

Investigation method: direct read of the SDK monorepo at the pinned tag `v1.40.0` (source of truth, not release-notes claims), plus check of what Forge-OH's own `bff/` and `openhands_tools_ext/` already import from the SDK.

## Investigation findings

### F1 — There is no "Microagents" module in SDK v1.40.0

`git grep -i microagent` against `OpenHands/software-agent-sdk@v1.40.0` returns zero matches. The term "Microagents" from Gemini's council output is a colloquial name for two distinct SDK v1 primitives that were renamed and separated in the V1 SDK split:

- **`openhands.sdk.skills`** (module at `openhands-sdk/openhands/sdk/skills/`) — a first-class SKILL.md ingestion + activation system with `Skill`, `SkillResources`, `KeywordTrigger`, `TaskTrigger`, `PathTrigger`, `load_skills_from_dir`, `install_skill`, `enable_skill`, and marketplace-standalone loading. This IS the primitive that replaces "microagents-as-knowledge" in the V0 codebase.
- **`openhands.tools.delegate`** + `openhands-tools/openhands/tools/preset/subagents/*.md` — the subagent registry with `DelegateAction(command="spawn"|"delegate")`, `agent_types` per delegated ID, and per-subagent SKILL-style markdown descriptors (e.g. `bash_runner.md`). This IS the primitive that replaces "microagents-as-sub-agents" in the V0 codebase.

Forge-OH already imports `openhands.sdk.skills.skill.Skill` at `bff/routers/skills.py:83`, so the skills primitive is a live integration point — not a new SDK we would be adopting for the first time.

### F2 — Context Condensation is a full first-class primitive in SDK v1.40.0

`openhands-sdk/openhands/sdk/context/condenser/` ships:

- **`CondenserBase`** — abstract interface with `condense(view, agent_llm)` and `acondense(view, agent_llm)`.
- **`RollingCondenser`** (from `pipeline_condenser.py`) — subclass with `should_condense`, `get_condensation`, `handles_condensation_requests`.
- **`LLMSummarizingCondenser`** — a working production strategy with:
  - `max_size` (event count trigger).
  - `max_tokens` (optional token-count trigger).
  - `keep_first` (minimum events preserved at start — critical for APC alignment with vLLM Automatic Prefix Caching).
  - `minimum_progress` (safeguard against ineffective condensations).
- **`NoCondensationAvailableException`**, **`CondensationRequirement.HARD` / `.SOFT`** — well-modeled failure and priority semantics.
- **Condensation event type** in `openhands.sdk.event.condenser` — condensations are recorded on the append-only event log as tombstone-style markers, so agent history stays fully auditable across condensation cycles.
- **`View`** — projection that applies condensation events on read, used by agents to fetch "current LLM-visible history" without mutating the log.

Council-Synthesis §8.0 explicitly calls for aligning OpenHands condenser `keep_first` with vLLM APC prefix boundaries. That knob is a first-class `Field` on `LLMSummarizingCondenser`; no SDK modification is needed.

### F3 — "Pluggable Runtime" is `openhands.sdk.workspace` in v1.40.0

`openhands-sdk/openhands/sdk/workspace/` ships:

- **`BaseWorkspace`** (`workspace/base.py`) — abstract class with `execute_command(command, cwd, timeout) -> CommandResult`, `file_upload`, `file_download`, `read_file`, and context-manager protocol. `CommandResult` carries `stdout`, `stderr`, `exit_code`, `timeout_occurred`.
- **`LocalWorkspace`** (`workspace/local.py`) — host-filesystem implementation.
- **`RemoteWorkspace`** (`workspace/remote/base.py`) — HTTP-client implementation talking to an `openhands-agent-server` over a REST/WebSocket API; wraps httpx with tenacity retry on transient 5xx / connect / timeout.
- **`RemoteWorkspaceMixin`** — the reusable async surface for remote workspaces.
- Git integration via `openhands.sdk.git.git_diff`, `git_changes`, `RepoSource`, `clone_repos` — workspace understands repository state natively.

This is exactly the primitive Council-Synthesis §8.1 called "Sandboxed pytest runner via OpenHands Pluggable Runtime." `RemoteWorkspace` already gives us the sandbox boundary (agent-server on `:8090` is the isolation domain); `execute_command` gives us the pytest invocation surface; `CommandResult` gives us `exit_code + stdout + stderr + timeout_occurred` which is 4 of the 5 fields §8.1's deterministic outcome schema needs.

**Missing from `CommandResult` for §8.1's outcome schema:** structured pytest report parsing (pass/fail/skipped/errored counts, per-failure `test_id + reason + file:line`). SDK gives us the runner surface; it does not give us the schema. See D1 below.

### F4 — SDK v1.40.0 ships adjacent primitives that also affect Stage 8 scope

Discovered incidentally during the read:

- **`openhands.sdk.agent.critic_mixin`** — a Critic mixin used to layer self-critique on any agent, directly relevant to Council-Synthesis §8.8 (Self-Refine plan critique A/B).
- **`openhands.sdk.agent.parallel_executor`** — parallel agent step execution, relevant to Council-Synthesis §8.3 (Selection layer with N=2 adaptive) and §8.5 (SBFL fusion on-demand).
- **`openhands.tools.planning_file_editor` + `openhands.tools.task_tracker` + `openhands.tools.workflow`** — planning tool suite (PLAN.md-restricted editor, task tracker, workflow orchestration). Directly relevant to §8.8.
- **`openhands.tools.delegate` (DelegateAction/DelegateObservation)** — subagent spawn+task-dispatch surface. Directly relevant if any Stage 8 slice wants role-differentiated sub-agents (e.g. planner vs coder as distinct system prompts, per Council-Synthesis "activate Microagents when planner and executor need distinct system prompts").
- **`openhands.tools.terminal`** with `tmux_terminal`, `subprocess_terminal`, and Windows/Unix variants — persistent-session terminal that `RemoteWorkspace.execute_command` mounts. This is where a §8.1 hermetic pytest runner would actually invoke pytest.

None of these existed as first-class exports in the pre-V1 OpenHands architecture that the Council-Synthesis authors were most familiar with. The correct default for Stage 8 is not "hand-build against `openhands_tools_ext`" — it is "start from the SDK's shipped surface and wrap where the SDK is silent."

## Decision

Adopt SDK-native primitives for the three specifically-flagged slices where the SDK covers the primitive and hand-build the thin schema layer that the SDK is silent on. Concretely:

### D1 — Slice 8.1 (Hermetic verification primitive) — HYBRID: adopt Workspace + hand-build the outcome schema

**Adopt:**
- `openhands.sdk.workspace.RemoteWorkspace` as the sandbox surface. The agent-server on `:8090` is the isolation domain; no separate Docker-in-Docker or Firecracker MicroVM primitive is warranted.
- `openhands.sdk.workspace.models.CommandResult` as the raw pytest-invocation return type.
- `openhands.tools.terminal` (already used by `RemoteWorkspace.execute_command`) as the underlying persistent session.

**Hand-build (in `openhands_tools_ext/verification/` — new subpackage):**
- The **deterministic outcome schema** Council-Synthesis §8.1 requires:
  ```
  { patch_applies: bool, syntax_ok: bool, imports_ok: bool,
    focused_tests: {passed:int, failed:int, skipped:int, errored:int,
                    failures: [{test_id, reason, file, line}]},
    regression_subset: {…same shape…},
    outcome: "verified" | "regressed" | "unrelated_fail" | "syntax_error" | "import_error" | "timeout" }
  ```
- A thin `VerifyPort` protocol wrapping `RemoteWorkspace.execute_command` that parses pytest's `--tb=short --no-header -q` or `--json-report` output into that schema.
- A `PatchDryRunAdapter` that runs `git apply --check` as the dry-run step.

**Rationale:** SDK gives us the runner and the sandbox boundary; SDK does not (and should not) give us the pytest-outcome vocabulary Council-Synthesis needs for §8.3's selection layer. Wrapping is cheap and the wrapper lives at the port layer (formal `VerifyPort` in `ports/verify.py`, adapter in `openhands_tools_ext/verification/`), following the [Kosmos porting workflow](https://github.com/rmholston420/Forge-OH/blob/main/PORTING_LEDGER.md).

Slice 8.1 estimated size **reduces** from the Council-Synthesis "1 slice with full sandbox stand-up" to "1 slice, thinner: schema + parser + `VerifyPort` + contract tests." No infrastructure work.

### D2 — Slice 8.2 (Bounded execution-grounded repair loop) — HYBRID: adopt Workspace, hand-build the loop controller

**Adopt:**
- `openhands.sdk.workspace.RemoteWorkspace` for the per-iteration test invocation (via the §8.1 wrapper from D1).
- `openhands.sdk.agent.base.Agent` step model as the substrate — agents step against an `AgentContext` and produce actions; the SDK does not lock the step count to 1, and it does not lock the retry policy to `n=1`.
- `openhands.sdk.event` as the observability trail — every repair iteration is already recorded on the append-only log; a bounded repair loop gets checkpointing and audit for free.

**Hand-build (in `bff/services/repair_loop.py` — new):**
- The **loop controller**: N=1 generate → verify via §8.1 → diagnose from `focused_tests.failures[]` → 1-2 patch retries → stop-on-no-progress rule (Council-Synthesis §8.2 wording).
- Progress signal: minimum-diff between the previous patch and the current patch, plus a monotone failure-count decrease requirement across iterations.
- Prompt-injection surface: the diagnose step must feed the failing test's `test_id + reason + file + line` (from D1's schema) into the next agent turn — hand-built because Council-Synthesis §8.2 explicitly requires this and no SDK primitive currently formats a pytest failure into an agent-prompt attachment.

**Rationale:** SDK provides no "N-bounded repair loop" primitive — it provides an unbounded agent loop with a condenser. The SDK's Critic mixin (`openhands.sdk.agent.critic_mixin`) is a closer analog than "Pluggable Runtime" for §8.2, but it is a general critique layer, not a bounded execution-grounded repair loop with a §8.1-schema-typed feedback channel. Hand-building the loop controller is the right level of custom code; adopting the SDK Workspace and event log is cheap.

Slice 8.2 estimated size **stays at "1 slice"** but the slice scope narrows to loop-controller code plus prompt-injection wiring.

### D3 — Slice 8.6 (ACE-style skill playbook with token budget cap) — ADOPT SDK Skills wholesale, add only the token-budget gate

**Adopt:**
- `openhands.sdk.skills.Skill` — data model with frontmatter, resources, MCP config, triggers.
- `openhands.sdk.skills.KeywordTrigger` — activate skill by prompt keywords (Council-Synthesis §8.6 "routing gate on task signature" is a strict subset of this).
- `openhands.sdk.skills.TaskTrigger` — activate skill by task type.
- `openhands.sdk.skills.PathTrigger` — activate skill by touched file paths.
- `openhands.sdk.skills.installed.*` — `install_skill`, `enable_skill`, `disable_skill`, `list_installed_skills`, `update_skill`.
- `openhands.sdk.skills.fetch.fetch_skill_with_resolution` — marketplace / standalone / repo loading.
- SDK's `to_prompt` — XML prompt block generator for available skills (Council-Synthesis §8.6's "prompt-injection surface for active skills" IS this function).

**Hand-build (thin, in `bff/services/skill_budget.py` — new):**
- **Token budget cap** — Council-Synthesis §8.6 explicitly rejects a skill-count cap in favor of a hard token budget. The SDK does not enforce a token cap; it activates all matching-trigger skills. The gate is a filter that runs AFTER SDK trigger matching and BEFORE `to_prompt` rendering. Uses `openhands.sdk.llm.LLM.token_count` (already available via the LLM abstraction) to count expected skill-prompt-block tokens per activated skill, greedy-drops lowest-priority skills until the budget holds.
- **Priority signal** — skills are ranked by (a) explicit `priority` field on `Skill` (added to Forge-OH's SKILL.md schema, backward-compatible), (b) recency of last successful activation (from the SDK's own installed-skills state), (c) declaration order.

**Rationale:** SDK's skills system covers 90% of §8.6. The 10% gap — a hard token budget instead of a skill-count cap — is a single function, not a subsystem. Hand-building an ACE-style playbook substrate from scratch when the SDK ships one is exactly the "fights the framework" anti-pattern Gemini's council output warned against.

Slice 8.6 estimated size **reduces** from the Council-Synthesis "2 slices" to "1 slice" — the SKILL.md ingestion, trigger matching, activation, and prompt rendering are already done.

### D4 — Slice 8.6 subquestion — SDK Condenser is a separate primitive and Forge-OH should adopt it too (out of §8.6 scope but noted here)

The Council-Synthesis document conflates "Context Condensation" with §8.6 (ACE playbook). They are distinct concerns:

- ACE playbook (§8.6) = skill-library prompt injection with a token cap on the *skill block*.
- Context Condensation = event-log summarization with a token cap on the *conversation history*.

Both are needed; they gate different tokens. Recommendation: adopt `LLMSummarizingCondenser` for the conversation-history side with two Forge-OH-specific configuration choices:

- **`keep_first` alignment with vLLM APC** — Council-Synthesis §8.0 requires alignment. `LLMSummarizingCondenser.keep_first` is a `Field(default=2, ge=0)`. Forge-OH sets this equal to the vLLM APC prefix token count (or the nearest event boundary at or below that count).
- **`max_tokens`** — Set to `model_context_window - agent_reserve - skill_budget` (from D3). Guarantees the condenser fires before the LLM's context window is exhausted.

**No new slice for this.** It rides on §8.0 (vLLM infra config bundle) as a configuration tweak in whatever module composes the agent. The condenser adoption is a compose-time choice, not a slice.

### D5 — Slices 8.0, 8.0.5, 8.3, 8.4, 8.5, 8.7, 8.8, 8.9 — hand-build with SDK affordances where they help

Per-slice, the SDK either does not cover the primitive or covers it in a way that materially differs from Council-Synthesis's contract:

| Slice | SDK affordance available | SDK covers the slice? | Decision |
|---|---|---|---|
| **8.0** (vLLM config bundle) | `LLMSummarizingCondenser.keep_first` (see D4) | No — it's vLLM config, not SDK code | Hand-build in `scripts/vllm_start.sh` and `docs/deployment-topology.md`. Adopt D4 condenser tweak at compose time. |
| **8.0.5** (Measurement hardening) | None | No | Hand-build in `bench/`. |
| **8.3** (Selection layer w/ LLM judge) | `openhands.sdk.agent.critic_mixin`, `openhands.sdk.agent.parallel_executor` | Partial — critic gives us the judge primitive; SDK doesn't ship a rank-aggregation function | HYBRID: adopt `critic_mixin` for the judge, hand-build the rank aggregator (trusted-tests > compiles > minimal-diff > judge tie-break with swapped-order). |
| **8.4** (Path B tree-sitter localization) | None (RepoGraph is in Forge-OH's own ext package) | No | Hand-build; vendor tree-sitter via PORTING_LEDGER. |
| **8.5** (SBFL fusion on-demand) | None | No | Hand-build. |
| **8.7** (Task-conditioned memory re-query) | Event log surface (`openhands.sdk.event.base.LLMConvertibleEvent`) — the retrieval trigger can subscribe to specific event subtypes | Partial — SDK gives event surface; Forge-OH's Kosmos MemoryPort is the retrieval engine | HYBRID: subscribe to `openhands.sdk.event.base` on failure events; call existing MemoryPort. Hand-build the trigger. |
| **8.8** (Self-Refine plan critique) | `openhands.sdk.agent.critic_mixin` + `openhands.tools.planning_file_editor` (PLAN.md-restricted editor) + `openhands.tools.task_tracker` + `openhands.tools.workflow` | Substantial — SDK ships the planning tool stack that Council-Synthesis §8.8's A/B experiment sits on top of | ADOPT SDK planning tools; hand-build only the A/B experiment control arm (retry-without-feedback baseline). |
| **8.9** (Tool-call memoization TVCACHE-style) | None (cache is orthogonal to SDK) | No | Hand-build. |

## Consequences

**Positive**

- Slice 8.1 gains a well-tested sandbox surface (`RemoteWorkspace` + agent-server) for free; the only new code is a pytest outcome schema (~200 LoC).
- Slice 8.6 shrinks from 2 slices to 1; the token-budget gate is a single function against SDK's already-shipped skill activation pipeline.
- Slice 8.8 gains PLAN.md tooling, task tracker, and workflow orchestration for free — Council-Synthesis's A/B experiment sits on top of proven SDK primitives instead of a hand-built planner scaffold.
- The condenser adoption (D4) aligns Council-Synthesis §8.0's APC-alignment requirement with an SDK field that already exists — no config-plumbing slice needed.
- Every adopted primitive is on the version pinned in `bff/requirements.txt` (`openhands-sdk==1.40.0`) — no dependency bump, no PORTING_LEDGER entry, no upstream tracking overhead.

**Negative**

- Forge-OH takes on a dependency on SDK 1.40 stability across Stage 8. Any SDK API break in a follow-up bump requires re-verification. Mitigated by: (a) the SDK primitives adopted (Skills, Condenser, Workspace, DelegateAction) are all core surfaces the SDK is unlikely to break without deprecation, (b) `bff/requirements.txt` pins SDK versions exactly.
- The pytest outcome schema in D1 is Forge-OH-owned code. If a future SDK release ships a first-class "structured pytest runner" tool (there is no indication yet), the D1 wrapper becomes dead code. Cost of that migration: one adapter file. Acceptable.
- Council-Synthesis §8.6's original 2-slice sizing is now 1 slice; slice 8.6.5 (formerly "SKILL.md ingestion") disappears. This changes the Stage 8 total slice count from 12 to 11. No downstream slice ordering breaks (dependencies in the Council-Synthesis table are on §8.2 and the new §8.6 satisfies all of them).

**Neutral**

- The Council-Synthesis document at `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` (project files repo commit `8e093bc`) is factually accurate as of its writing; this ADR does not amend it. It supersedes only the specific slice sizings and the specific claim that Slices 8.1 / 8.2 / 8.6 are pure hand-build.
- Existing Forge-OH SDK-skill integration at `bff/routers/skills.py:83` remains the model for D3 wiring — no re-architecting.

## Alternatives considered

- **Alt-A: Adopt everything SDK-native, defer all hand-build work.** Rejected because (i) the pytest outcome schema in D1 has no SDK equivalent and Council-Synthesis §8.3's selection layer strictly requires it, (ii) the bounded-N repair loop in D2 has no SDK equivalent, (iii) the token-budget gate in D3 has no SDK equivalent.
- **Alt-B: Hand-build everything, treat SDK as event/tool substrate only (ignore Skills, Condenser, Workspace).** Rejected — this is the "fights the framework" pattern the Gemini council output specifically flagged, and it would re-implement three tested SDK subsystems for no benefit.
- **Alt-C: Adopt SDK Skills and Condenser but hand-build a separate sandbox for §8.1 (not `RemoteWorkspace`).** Rejected because `RemoteWorkspace` is already how Forge-OH's `bff/routers/runs.py` talks to the agent-server; a second sandbox would be a parallel isolation domain with no clear boundary.
- **Alt-D: Wait for SDK 1.41+ and defer this decision.** Rejected because ADR-028 §4 sequences this investigation before any Stage 8 slice; SDK v1.41.0 exists (see tag list) but the pinned version is 1.40.0 and Council-Synthesis's baseline is measured against the current pinned stack.

## Rollout

The following file changes land in one PR ("Stage 8 initialization · ADR-029") against `main`:

1. **New file**: `docs/adr/029-sdk-native-adoption-for-stage-8.md` (this ADR).
2. **Edit**: `docs/adr/README.md` — add ADR-029 index row.

Immediately after ratification (in a follow-up commit on the same branch or the merge commit itself):

3. **Append** to `BUILD_LOG.md` — one timestamped entry recording the ADR-029 filing and its decisions per slice.
4. **Overwrite** `SESSION_HANDOFF.md` — Stage 8 in progress · Slice 8.0 (vLLM infra config bundle) as exact next action · ADR-029 decisions inlined per subsequent slice.

## Verification (already satisfied at ratification time)

- [x] SDK v1.40.0 tag exists on `OpenHands/software-agent-sdk` and pinned in `bff/requirements.txt` (`openhands-sdk==1.40.0`).
- [x] No `microagent` string anywhere in v1.40.0 tree — confirmed by full-tree recursive search (F1).
- [x] `openhands.sdk.skills` module read directly at v1.40.0 — Skill / triggers / installed-skills API surface verified (F1, D3).
- [x] `openhands.sdk.context.condenser` module read directly at v1.40.0 — CondenserBase / LLMSummarizingCondenser / keep_first field / hard-context-reset semantics verified (F2, D4).
- [x] `openhands.sdk.workspace` module read directly at v1.40.0 — BaseWorkspace / LocalWorkspace / RemoteWorkspace / CommandResult verified (F3, D1, D2).
- [x] Forge-OH's own SDK-skill integration point confirmed at `bff/routers/skills.py:83` (existing consumer).
- [x] Adjacent primitives (critic_mixin, parallel_executor, planning_file_editor, task_tracker, workflow, delegate) confirmed present at v1.40.0 (F4, D5).
