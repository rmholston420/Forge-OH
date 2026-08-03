# SESSION HANDOFF — 2026-08-03 20:00 EDT

## Current stage
**F.19 COMPLETE** except F.19.5 (native venv unification, deferred).

## Completed this session
- F.19.1a supervisor + swap-on-demand logic
- F.19.1b Docker smoke, launchers, VLLM_READY_TIMEOUT 300s -> 420s
- F.19.2a role API (`route_by_role`, `RoleRoute`)
- F.19.2b runs.py migration to role-based routing
- F.19.2c settings.py per-role probes (`roleProbes`, coder/planner
  URLs/models/maxTokens/vLLM health)
- F.19.3 removed `route_request`/`try_model`, expanded model_router
  tests (14/14 in sandbox, 30/30 including hook_config), settings
  probe except-widening hotfix (1ab3daf)
- F.19.4 live P1/P2/P3 smoke: Phase 1 direct probe green, Phase 2
  agent-server round-trip green. Router timeout fix 300s -> 480s
  to exceed supervisor's 420s READY_TIMEOUT.

## Colossus state
- vLLM coder :8501 (qwen3.6-35b-nvfp4) available on demand via
  supervisor
- vLLM planner :8511 (qwen3-thinking-2507-awq) available on demand
- Supervisor `ops/vllm_supervisor.sh ensure {coder|planner}` swaps
  in ~140-250s depending on direction
- BFF :8081 (uvicorn --reload) — restarted this session, running
  the new 480s supervisor timeout
- Agent-server :8090 up (no workspaces registered — smoke uses
  fallback `workspaceId="default"`)
- BUILD_LOG.md + SESSION_HANDOFF.md updated

## Next action
Awaiting user's call. Options:
1. **F.19.5** — native venv unification (deferred; migrate off
   Docker vLLM to native venv launch)
2. **F.20** — next stage per Forge-OH-Action-Plan-v4.md (agent
   presets? persistence layer? need to re-read the plan to
   restate scope)
3. **Register a proper workspace on the agent-server** so
   `/api/runs` picks a real `workspaceId` instead of the
   `"default"` fallback (small unblock for real end-to-end
   agent runs)

## Open questions
None outstanding. F.19.4 DoD met.

## Latest commits
  - bf3fe6c  F.19.4 smoke scripts
  - 9904e6c  F.19.4 curl timeout 900s
  - 485be66  F.19.4 supervisor timeout 300 -> 480
  - 4a70fb1  F.19.4 curl timeout 900 -> 1200
