
# Forge-OH Reconciliation Plan v1 — Stage 7 (Detailed, Final Stage)

Standalone implementation plan for Perplexity Computer. Target: Colossus (128GB RAM, RTX 5090, 32GB VRAM, Blackwell SM_120). Single-user, local-first, no cloud control planes.

**Prerequisite:** Stage 6 must be complete and its exit gate verified (see `Forge-OH-reconciliation-plan-v1-stage-6.md`). Read `SESSION_HANDOFF.md` before starting — it should point here.

**Governing rule (non-negotiable):** backend and frontend ship together in the same commit/session. A backend endpoint with no reachable UI path, or a UI control wired to a stub, is not "done."

**Stage 7 goal:** close out the reconciliation plan — reconcile `docker-compose.yml` for the real single-host topology accumulated across Stages 1-6, resolve every deferred/flagged item logged along the way (SDK gaps, token-usage display, Zetesis upgrade, any open `DEBUG_LOG.md`/`SESSION_HANDOFF.md` items), run a full-system regression pass, and produce a final reconciliation closeout report. This is the last stage — there is no Stage 8 to hand off to.

```bash
cd ~/dev/forge-oh
cat SESSION_HANDOFF.md
```

Confirm it names Stage 7 as the next action before proceeding.

---

## 7.0 Baseline inspection — full accounting of what Stages 1-6 left open

```bash
cat docker-compose.yml
grep -n "^## " BUILD_LOG.md | tail -40
grep -n "deferred\|flagged\|not yet scheduled\|open question" SESSION_HANDOFF.md
grep -n "^## " DEBUG_LOG.md
cat PORTING_LEDGER.md | grep -c "^## "
```

Build an explicit list from this output of every open item before starting sub-stages. Do not rely on memory of what prior stages deferred — the logs are the source of truth.

```bash
grep -B2 -A8 "SDK gap" DEBUG_LOG.md
```

This surfaces every place a capability was found absent (Stage 3.1 risk scoring, Stage 6.5 model switching, etc.) — each needs a decision in 7.3.

---

## 7.1 `docker-compose.yml` single-host topology reconciliation

### 7.1.1 Inventory every service added across Stages 1-6

```bash
grep -n "^\s*[a-z_-]*:\s*$" docker-compose.yml
```

Expected accumulated services by this point: `bff` (or host process), frontend (or host process), `dozerdb` (Stage 4.1), `qdrant` (Stage 5.2), `searxng` (Stage 6.1), plus whatever agent-server topology already existed pre-Stage-1. Confirm which of these actually run containerized vs. as host processes — Stage 4.1 and 5.2's `docker run` commands may not have been folded into `docker-compose.yml` yet if they were started standalone.

```bash
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Ports}}"
```

Cross-reference running containers against `docker-compose.yml` service definitions — flag any container that's running standalone (via bare `docker run` from an earlier stage) but missing from compose.

### 7.1.2 Fold any standalone containers into compose

For each service found running standalone but absent from `docker-compose.yml` (likely `dozerdb` from Stage 4.1, since its setup command was a bare `docker run`):

```bash
docker inspect dozerdb --format '{{json .Config}}' | python3 -m json.tool
```

Use this to reconstruct the exact image, env vars, port mappings, and volumes into a proper compose service block:

```yaml
# docker-compose.yml — add/reconcile
  dozerdb:
    image: graphfoundation/dozerdb:latest  # confirm exact tag from docker inspect output
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
    volumes:
      - dozerdb_data:/data
    restart: unless-stopped
```

Reference `${NEO4J_PASSWORD}` from the `.env.neo4j` file established in Stage 4.1 rather than hardcoding the credential into the compose file itself:

```bash
grep -n "env_file" docker-compose.yml
```

Add `env_file: .env.neo4j` to the `dozerdb` service if not already using a shared top-level `env_file` directive.

### 7.1.3 Confirm the `volumes:` top-level block has no duplicate keys

```bash
grep -A20 "^volumes:" docker-compose.yml
```

Stages 4, 5, and 6 each may have appended to this block independently — confirm `dozerdb_data`, `qdrant_data`, and `searxng_data` are each declared exactly once.

### 7.1.4 Decide and document host-process vs. containerized split

Per the single-user, local-first mandate, GPU-bound inference engines (Ollama, vLLM, llama.cpp, SGLang from Stage 2) and the agent-server itself are expected to remain host processes for direct GPU passthrough simplicity on Colossus, while stateful auxiliary services (DozerDB, Qdrant, SearXNG) are containerized. Confirm this split matches reality:

```bash
ps aux | grep -E "ollama|vllm|llama-server|sglang|agent.server" | grep -v grep
docker ps --format "{{.Names}}"
```

Document this explicitly:

```bash
cat > docs/deployment-topology.md << 'EOF'
# Forge-OH Deployment Topology (Colossus, single-host)

## Host processes (direct GPU passthrough)
- Ollama (Stage 2)
- vLLM (Stage 2, on-demand)
- llama.cpp server (Stage 2, on-demand)
- SGLang (Stage 2, on-demand)
- OpenHands agent-server

## Containerized (docker-compose.yml)
- DozerDB (Stage 4/5 — RepoGraph symbol graph + [semantic memory graph, per Stage 4.5 decision])
- Qdrant (Stage 5 — vector store)
- SearXNG (Stage 6 — web research)
- bff / frontend: [confirm actual current deployment mode]

## Rationale
GPU-bound engines stay host-side for direct CUDA/driver access without container GPU-passthrough overhead on a single-user workstation. Stateful auxiliary services containerize cleanly since they don't need GPU access.
EOF
```

### 7.1.5 Full-stack up/down verification

```bash
docker compose down
docker compose up -d
docker compose ps
```

Confirm every containerized service reports healthy/running. Then confirm every host-process dependency (Ollama etc.) is separately documented as needing manual start, or scripted:

```bash
cat > scripts/start-host-services.sh << 'EOF'
#!/usr/bin/env bash
set -e
ollama serve &
echo "Ollama started. Start vLLM/llama.cpp/SGLang on demand per docs/colossus-inference-setup.md."
EOF
chmod +x scripts/start-host-services.sh
```

### 7.1.6 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7.1: docker-compose topology reconciled
- Folded standalone dozerdb container into docker-compose.yml, sourced config from live docker inspect
- Confirmed no duplicate volume keys across qdrant_data/dozerdb_data/searxng_data
- Documented host-process vs. containerized split in docs/deployment-topology.md
- Added scripts/start-host-services.sh for host-side GPU inference engines
- Files touched: docker-compose.yml, docs/deployment-topology.md, scripts/start-host-services.sh
- Verification: full docker compose down/up cycle confirmed all containerized services healthy
EOF
```

---

## 7.2 Full-system regression pass

### 7.2.1 Automated suite, full run

```bash
cd ~/dev/forge-oh
pytest bff/tests/ -v
pnpm typecheck
pnpm test:unit
pnpm build
pytest openhands_tools_ext/ -v
```

Fix any failures before proceeding — do not carry known-broken tests into the closeout. If a failure is pre-existing and out of scope, log it explicitly in `DEBUG_LOG.md` rather than silently ignoring it.

### 7.2.2 End-to-end smoke test across every stage's deliverable

Run through this checklist against the live running system, in order, noting pass/fail for each:

```bash
curl http://localhost:8000/api/inference-backends | python3 -m json.tool  # Stage 2
curl http://localhost:8000/api/repograph/health  # Stage 4
curl "http://localhost:8000/api/repograph/graph?repo_key=forge-oh&limit=50" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['nodes']), 'nodes')"  # Stage 4
curl http://localhost:6333/collections  # Stage 5
curl "http://localhost:8888/search?q=test&format=json" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['results']))"  # Stage 6
curl http://localhost:8000/api/memory/recent-writes  # Stage 5
curl http://localhost:8000/api/skills  # Stage 6
```

```bash
pnpm dev
```

Manually walk through, one pass each:
- Create an Agent Preset with a non-Ollama backend selected (Stage 2).
- Trigger a run with `mode: manual` confirmation policy, confirm approval prompts (Stage 3).
- Attempt an install of a nonexistent package mid-task, confirm it's blocked (Stage 3).
- Open `/repograph`, confirm the graph view renders (Stage 4).
- Trigger a memory write and search, confirm both appear in `/memory-inspector` and the timeline (Stage 5).
- Trigger a web search, confirm it renders as a `WebSearch` event (Stage 6).
- Revert to an earlier checkpoint, confirm both files and conversation state restore (Stage 6).
- Open `/skills`, confirm real skill entries render (Stage 6).

Any failure here at this late stage indicates either a regression introduced by a later stage's changes or an integration gap between stages that unit tests didn't catch — treat every such failure as a blocking bug, not a footnote.

### 7.2.3 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7.2: Full-system regression pass complete
- All automated suites (bff, frontend typecheck/unit/build, openhands_tools_ext) passing
- End-to-end smoke test walked through every Stage 1-6 deliverable against the live system: [PASS/FAIL per item — fill in from actual run]
- Any regressions found and fixed: [list, or "none found"]
EOF
```

---

## 7.3 Resolve every deferred/flagged item from Stages 1-6

### 7.3.1 Build the definitive list

```bash
grep -B2 -A8 "SDK gap\|deferred\|flagged" DEBUG_LOG.md BUILD_LOG.md SESSION_HANDOFF.md
```

Cross-reference against what this plan tracked explicitly:
- Stage 3.1 — security-analyzer risk scoring (if absent at SDK 1.40.0).
- Stage 6.5 — runtime model switching REST surface (if absent).
- Stage 6.7.5 — token-usage display (if absent, flagged as possible Stage 7 addition).
- Stage 6.1 — Zetesis research-loop sub-agent upgrade, explicitly deferred.

### 7.3.2 Re-check SDK-gap items against the current pinned version

```bash
pip show openhands-sdk | grep Version
```

If the pinned version has changed since Stages 3/6 (e.g., you upgraded mid-project), re-run the exact inspection commands from those stages now:

```bash
python3 -c "
from openhands.sdk.event import ActionEvent
print(ActionEvent.model_fields.keys())
"
grep -rn "switch_model" $(python3 -c "import openhands.sdk, os; print(os.path.dirname(openhands.sdk.__file__))")
```

If still absent, these remain legitimately deferred — do not force a workaround. Document the final status:

```bash
cat >> DEBUG_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7.3: Final status of deferred SDK-gap items
- Security-analyzer risk scoring: [confirmed still absent at v1.40.0 / now available, ported in this stage]
- Runtime model switching REST surface: [confirmed still absent / now available, ported in this stage]
- Both remain candidates for future work once openhands-sdk ships these capabilities; no local workaround attempted
EOF
```

If either capability is now present because of an SDK upgrade, implement it now following the exact patterns already written in Stage 3.1/6.5's plans (they were written defensively for exactly this situation) rather than re-designing from scratch.

### 7.3.3 Token-usage display (Stage 6.7.5 flag)

```bash
grep -rn "tokenUsage\|token_count\|cost.*display" src/features/run-detail/
```

If genuinely absent, decide now whether this is in scope for Stage 7 closeout or explicitly out of scope for this reconciliation plan (a reasonable call, since it's cosmetic and the underlying token-efficiency work from 6.7 is already functionally complete without it). Recommendation: implement a minimal display now since the data almost certainly already exists somewhere in agent-server response metadata, and this is cheap to close out cleanly rather than leave dangling:

```bash
grep -rn "usage\|prompt_tokens\|completion_tokens" bff/services/event_normalize.py
```

```python
# bff/services/event_normalize.py — add if usage data exists in raw events but isn't surfaced
def normalize_usage(event) -> dict | None:
    usage = getattr(event, "usage", None)
    if usage is None:
        return None
    return {"promptTokens": usage.prompt_tokens, "completionTokens": usage.completion_tokens}
```

```typescript
// src/features/run-detail/TokenUsageDisplay.tsx
export function TokenUsageDisplay({ promptTokens, completionTokens }: { promptTokens: number; completionTokens: number }) {
  return <div className="text-xs text-gray-500">Tokens: {promptTokens} prompt / {completionTokens} completion</div>;
}
```

Wire into the run-detail header. If the underlying usage data doesn't exist anywhere in agent-server responses at all (not just unsurfaced), log this as genuinely out of scope rather than fabricating numbers.

### 7.3.4 Zetesis research-loop upgrade (Stage 6.1 deferral)

```bash
grep -n "Zetesis\|synthesis.*critique" ideal-ACA-v8.md forge-oh-improvement-plan-v2.md
```

Confirm the exact scope of this deferred item from the source docs. This is a genuine feature addition (a synthesis/critique loop layered on top of Stage 6.1's basic web-search tool), not a bug fix — treat it as an explicit go/no-go decision for this closeout stage rather than silently completing or silently dropping it:

**Decision point — do not proceed past this without a call:** implementing the full Zetesis synthesis/critique loop is a nontrivial net-new feature. Given this is the final stage of the reconciliation plan (closing gaps against the existing spec, not adding new scope), the recommended default is to explicitly mark this out of scope for v1 and log it as a named candidate for a future v2 reconciliation pass, rather than scope-creep the closeout stage. Confirm this call before finalizing:

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7.3: Zetesis research-loop upgrade — scope decision
- Decision: explicitly deferred to a future v2 reconciliation pass, not implemented in Stage 7
- Rationale: net-new feature scope beyond v1's gap-closing mandate; basic SearXNG web-search tool from Stage 6.1 remains the shipped capability
EOF
```

### 7.3.5 Log overall resolution status

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7.3: All deferred items resolved or explicitly closed out
- Security-analyzer risk scoring: [status]
- Runtime model switching: [status]
- Token-usage display: [implemented / genuinely out of scope]
- Zetesis research-loop upgrade: explicitly deferred to future v2 pass
EOF
```

---

## 7.4 Documentation and ledger completeness audit

### 7.4.1 Confirm every port has a ledger entry

```bash
grep -c "^## " PORTING_LEDGER.md
```

Cross-reference against every port referenced across Stages 4-6: `react-force-graph-2d`, Kosmos `ports/memory.py`/`vector.py`/`embeddings.py`, Qdrant adapter, Ollama embeddings adapter, DozerDB semantic memory path, `ports/search.py`/SearXNG adapter. Confirm none are missing:

```bash
grep -n "^## " PORTING_LEDGER.md
```

### 7.4.2 Confirm every commit-hash reference in the ledger is still resolvable

```bash
cd ~/dev/kosmos-reference
for hash in $(grep -oP "commit \K[a-f0-9]{40}" ~/dev/forge-oh/PORTING_LEDGER.md | sort -u); do
  git cat-file -t "$hash" 2>/dev/null && echo "$hash: OK" || echo "$hash: MISSING"
done
```

Flag any `MISSING` result — it means the reference commit is unreachable, which breaks traceability. If found, re-verify the correct hash and correct the ledger entry.

### 7.4.3 Confirm `.gitignore` coverage for every secret/credential file introduced

```bash
grep -n "\.env\.neo4j\|\.env$" .gitignore
git status --porcelain | grep -i "\.env"
```

Confirm no credential file is staged or tracked.

### 7.4.4 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7.4: Documentation and ledger completeness audit complete
- Confirmed all Stage 4-6 ports have PORTING_LEDGER.md entries with resolvable commit hashes
- Confirmed no credential files tracked in git
- Files touched: PORTING_LEDGER.md (corrections if any were needed)
EOF
```

---

## 7.5 Final reconciliation closeout report

### 7.5.1 Generate the closeout document

```bash
cat > docs/reconciliation-closeout-v1.md << 'EOF'
# Forge-OH Reconciliation Plan v1 — Closeout Report

## Summary
Stages 1 through 7 complete. This document is the final record of what v1 of the reconciliation plan delivered, what was explicitly deferred, and what should seed a future v2 pass.

## Delivered
- Stage 1: install-blocker fixes, MCP Tools/Secrets nav wiring, Agent Presets persistence, send-while-running, approval_required socket fix
- Stage 2: InferenceBackend port (Ollama/vLLM/llama.cpp/SGLang), Colossus SM_120 tuning, VRAM-aware concurrency ceiling
- Stage 3: security/approval maturity (risk indicators or documented gap), policy-based confirmation, DependencyGuard slopsquatting defense, GPU staleness visibility, compare-endpoint fix
- Stage 4: RepoGraph enabled on DozerDB with graph visualization, LSPClient port (Serena)
- Stage 5: four-tier memory port from Kosmos (episodic/DozerDB, semantic/Qdrant+Ollama), zero-trust write enforcement, ACE curation cycle, memory-inspector UI
- Stage 6: SearXNG web-research tool, condensation visibility, idempotency ledger, checkpoint revert, model switching (or documented gap), skills page, code-execution invocation mode
- Stage 7: infra topology reconciliation, full-system regression, deferred-item resolution

## Explicitly deferred to future work
- [Fill in from 7.3: security-analyzer risk scoring if still absent]
- [Fill in from 7.3: runtime model switching if still absent]
- Zetesis research-loop synthesis/critique upgrade (net-new scope, not a v1 gap)

## Architectural decisions made during this plan
- Stage 4.5: DozerDB consolidation — [Option A/B, fill in]

## Ported components (see PORTING_LEDGER.md for full detail)
- react-force-graph-2d (MIT, vendored)
- Kosmos ports/adapters: memory, vector, embeddings, search — internal same-owner ports, commit-hash tracked

## System state at closeout
- All automated test suites passing
- Full end-to-end smoke test across every stage's deliverable passing
- docker-compose.yml reconciled to real single-host topology, documented in docs/deployment-topology.md
EOF
```

### 7.5.2 Final logs

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 7 COMPLETE — RECONCILIATION PLAN v1 COMPLETE
- All Stage 7 exit-gate checks passed
- docs/reconciliation-closeout-v1.md generated as the definitive closeout record
- Forge-OH reconciliation plan v1 (Stages 1-7) fully complete
- Next action: none scheduled under v1; future work seeds a v2 reconciliation pass per docs/reconciliation-closeout-v1.md's deferred-items list
EOF

cat > SESSION_HANDOFF.md << 'EOF'
# Session Handoff

**Current stage:** Reconciliation Plan v1 COMPLETE (Stages 1-7). No stage currently in progress.

**Completed this session:**
- Stage 7.1 through 7.5, all verified.

**Remaining before v1 Definition of Done:** none — v1 is fully complete.

**Open questions awaiting review:** none — all deferred items from Stages 1-6 were explicitly resolved or closed out with documented rationale in docs/reconciliation-closeout-v1.md.

**Exact next action:** None scheduled. Await direction on whether to begin a v2 reconciliation pass (candidates: security-analyzer risk scoring / model switching once SDK supports them, Zetesis research-loop upgrade) or move to net-new feature work outside this plan's scope.
EOF
```

---

## Stage 7 exit gate — final gate for the entire v1 plan

```bash
cd ~/dev/forge-oh
pytest bff/tests/ -q
pnpm typecheck
pnpm test:unit
pnpm build
pytest openhands_tools_ext/ -v
docker compose up -d
docker compose ps
```

Manual verification checklist:
- [ ] `docker-compose.yml` contains every accumulated containerized service (DozerDB, Qdrant, SearXNG at minimum) with no duplicate volume keys, and `docs/deployment-topology.md` accurately documents the host-process/containerized split.
- [ ] Full automated suite passes with zero known-broken tests carried forward silently.
- [ ] End-to-end smoke test across every Stage 1-6 deliverable passes on the live running system.
- [ ] Every deferred/flagged item from Stages 1-6 has an explicit final resolution (implemented, or documented as still absent/genuinely out of scope) — none left ambiguous.
- [ ] Every ported component has a `PORTING_LEDGER.md` entry with a resolvable commit hash.
- [ ] No credential files tracked in git.
- [ ] `docs/reconciliation-closeout-v1.md` exists and accurately reflects final system state.
- [ ] `SESSION_HANDOFF.md` reflects plan completion, not a pending stage.

This is the final gate. Once all boxes are checked, Forge-OH Reconciliation Plan v1 is complete.
