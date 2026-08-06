# ADR 013: Code-execution-with-MCP invocation mode via BashCommand + SDK tools

**Status:** Accepted
**Date:** 2026-08-06
**Stage:** 6.7 (Harness engineering maturity)

## Context

Stage 6.7 of `Forge-OH-reconciliation-plan-v1-stage-6.md` calls for a
"code-execution-with-MCP" invocation mode: the agent authors Python that calls
tool functions programmatically, rather than the model emitting per-call
tool-invocation JSON, so intermediate results and unused tool schemas stay out
of the model's context. Complementary progressive-disclosure step: expose only
tool name + one-line description at session start, load full schemas on demand.

The spec sketches four wire points as illustrative snippets:

1. `invoke_via_code_execution(code, stubs)` in `openhands_tools_ext/tool_invocation/code_exec_mode.py`
2. Sandbox invocation path (`run_in_sandbox`, `docker exec`, `gVisor`, `runsc`)
3. `build_context` / `assemble_prompt` in Forge-OH for progressive-disclosure wiring
4. Dispatch interception for `should_use_code_execution(...)` routing

Grep pass on Colossus at commit `d6476be` confirmed that **none of the four
wire points exist in Forge-OH**:

- **(1)** No `invoke_tool` / `dispatch_tool` in `bff/services/*.py` or
  `openhands_tools_ext/*.py`. Tools are registered globally via
  `openhands.sdk.tool.registry.register_tool(name, ToolDefinition)` at module
  import; dispatch happens inside the pinned OpenHands SDK v1.40.0 during the
  agent loop, not in Forge-OH.
- **(2)** No sandbox boundary (`run_in_sandbox`, `docker exec`, `gVisor`,
  `runsc`) in the repo. Agent-authored code runs today via the SDK's own
  `BashCommand` action → agent-server subprocess. There is no separate
  "sandboxed workspace execution boundary" per the spec's wording.
- **(3)** `context_loader.py::build_context_preamble` builds skill/memory
  context, not tool schemas. Tool schemas are assembled by the SDK's own
  `Agent`/`Conversation` classes from the tool registry.
- **(4)** No dispatch call site in Forge-OH.

Building the four illustrative snippets verbatim would either ship dead code
(the SDK never calls them) or require forking / monkey-patching
`openhands.sdk.Agent` — a large architectural change nowhere flagged in the
spec.

## Decision

Ship Stage 6.7 as **three SDK-registered tools** the model calls explicitly,
plus a routing helper the system prompt references. Route the code-execution
sandbox through the agent-server's existing `BashCommand` action, rather than
introducing a separate sandbox tier.

Concretely:

1. **`code_execute` SDK tool** (`openhands_tools_ext/tool_invocation/code_exec_mode.py`).
   Model calls it with a Python program that itself calls other registered
   tools by name. The executor emits a `BashCommand`-equivalent invocation via
   `python3 -c '<program>'` on the agent-server runtime, inheriting the same
   sandbox tier already used by every `bash` action. **No bare `exec()` in the
   BFF process.**

2. **`list_tool_stubs` and `get_tool_schema` SDK tools**
   (`openhands_tools_ext/tool_invocation/progressive_disclosure.py`). Both read
   `openhands.sdk.tool.registry` at call time and return either `(name,
   description)` pairs or the full JSON schema for a single tool. The model
   calls `list_tool_stubs` at session start and `get_tool_schema` only when it
   needs the full schema for a specific tool.

3. **`should_use_code_execution(task_phase, estimated_tool_call_count) → bool`**
   (`openhands_tools_ext/tool_invocation/router.py`). Pure function: returns
   True for `{multi_file_edit, verification, refactor}` phases or when
   `estimated_tool_call_count > 3`. Exposed as a Python helper and referenced
   from the agent's system-prompt hint. **Not enforced dispatch** — the model
   decides whether to call `code_execute` based on the hint.

4. **Token-usage verification** uses the existing tracking already flowing
   through `bff/services/trace_reconstruction.py` (`inputTokens` /
   `outputTokens` per span, aggregated in the run summary) and displayed in
   `RunDetailHeader.tsx`. Measurement is deferred to the next
   `local-llm-bench` pass; no new instrumentation.

## Rationale

Alternatives considered:

- **A: Ship the illustrative snippets verbatim, no wiring.** Dead code. Fails
  the Stage 6 exit-gate line 882 ("confirmed reducing token usage").
- **B: Fork `openhands.sdk.Agent` to intercept dispatch.** Large architectural
  change; the spec explicitly does not authorize this scope. Would also
  couple Forge-OH to a specific SDK internal.
- **C: Defer §6.7 with a DEBUG_LOG entry** (same pattern §6.5 used). Honest
  but Stage 6 was designed to *deliver* code-execution mode; a second deferral
  card on the last sub-stage weakens the whole stage.

Path B (this decision) matches the actual architecture: the SDK owns dispatch;
we author tools it can call. `BashCommand` is already the sandbox tier for
agent-authored code — reusing it is the honest way to satisfy the "not bare
`exec()` in the BFF" clause without inventing a new tier.

Progressive disclosure via two explicit tools (`list_tool_stubs`,
`get_tool_schema`) is a more honest read of the spec than intercepting
context-assembly: the model actually decides when to load a full schema,
which is the point of "progressive disclosure."

## Consequences

- Adds three tool modules under `openhands_tools_ext/tool_invocation/` +
  one `router.py` helper.
- Agent-server launch line must add
  `--import-modules openhands_tools_ext.tool_invocation.code_exec_mode,openhands_tools_ext.tool_invocation.progressive_disclosure`
  so the tools register at import time (mirrors the pattern
  `write_note`, `consult_memory`, and `search_web` already use).
- System prompt gains a short hint referencing `should_use_code_execution`
  (out of scope for this ADR — will be threaded through the existing
  prompt-assembly path in a follow-up).
- No BFF, FE, or agent-server code changes required.
- Token-usage measurement uses existing tracking; no new metrics port.
- Reversible in one commit: unregister the three tools; delete the
  four modules; remove the ADR reference from BUILD_LOG.

## References

- Spec: `Forge-OH-reconciliation-plan-v1-stage-6.md` §6.7 (lines 758–861)
- Related: ADR 002 (BFF-mediated OpenHands access)
- BUILD_LOG entry: 2026-08-06 Stage 6.7 shipped
- Discovery grep pass: commit `d6476be`
