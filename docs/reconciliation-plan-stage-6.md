
# Forge-OH Reconciliation Plan v1 — Stage 6 (Detailed)

> **STATUS NOTE (2026-08-06):** §6.4 ("Checkpoint-to-disk revert") ships in two split slices whose design layer is superseded by **[ADR-025 — Restore via fork](adr/025-restore-via-fork.md)**:
>
> - **Stage 6.4 (SHIPPED · 2026-08-06):** fork-from-here on user-message events. Non-destructive branching. See BUILD_LOG.md 2026-08-06.
> - **Stage 6.4b (OPEN):** per-run worktrees under `WORKTREE_ROOT`. Foundation for both revert and §2.4 concurrent worktree-agents.
> - **Stage 6.4c (DEFERRED, opens after 6.4b lands):** restore-via-fork — `POST /api/runs/{run_id}/restore` composes `Conversation.fork()` + `git reset --hard` inside the new fork's isolated worktree. Original run untouched.
>
> Codebase inspection (DEBUG_LOG.md 2026-08-06) found that the in-place destructive design in §6.4.1–§6.4.5 below assumes prerequisites that do not exist: no `Checkpoint` entity, no per-run worktrees, no `get_run_workdir`, and `openhands-sdk==1.40.0` exposes no in-place conversation-state rewind API. See ADR-025 for the full evidence and the design that supersedes §6.4.1–§6.4.5. The prose below is retained verbatim as historical context.

Standalone implementation plan for Perplexity Computer. Target: Colossus (128GB RAM, RTX 5090, 32GB VRAM, Blackwell SM_120). Single-user, local-first, no cloud control planes.

**Prerequisite:** Stage 5 must be complete and its exit gate verified (see `Forge-OH-reconciliation-plan-v1-stage-5.md`). Read `SESSION_HANDOFF.md` before starting — it should point here.

**Governing rule (non-negotiable):** backend and frontend ship together in the same commit/session. A backend endpoint with no reachable UI path, or a UI control wired to a stub, is not "done."

**Stage 6 goal:** harness-engineering maturity — a ported web-research tool, context-compaction visibility, an exactly-once idempotency ledger, checkpoint-to-disk revert, runtime model switching, a skills/microagents page, and code-execution-based MCP invocation for token efficiency. Each sub-stage is independent except where noted; sequence per the recommended order at the end.

```bash
cd ~/dev/forge-oh
cat SESSION_HANDOFF.md
```

Confirm it names Stage 6 as the next action before proceeding.

---

## 6.0 Baseline inspection

```bash
ls ~/dev/kosmos-reference/ports/search.py ~/dev/kosmos-reference/adapters/search/searxng/adapter.py 2>/dev/null
grep -n "CondensationEvent\|CondensationSummaryEvent" bff/services/event_normalize.py
find . -iname "*idempot*"
grep -n "def fork\|Conversation.fork" bff/services/*.py openhands_tools_ext/*.py 2>/dev/null
grep -n "switch_model" $(python3 -c "import openhands.sdk, os; print(os.path.dirname(openhands.sdk.__file__))") -r 2>/dev/null
grep -rn "activated_skills" bff/services/event_normalize.py
find src -iname "*skills*"
```

Record what's already present before writing new code — several of these sub-stages depend on fields (`activated_skills`) or methods (`Conversation.fork()`) that Stage 2/3/4 work may have already touched incidentally.

---

## 6.1 Ported SearXNG web-research tool (Kosmos `SearchPort`)

### 6.1.1 Confirm Kosmos reference is current

```bash
cd ~/dev/kosmos-reference
git pull
git rev-parse HEAD
cat ports/search.py
cat adapters/search/searxng/adapter.py
find adapters/search/searxng -iname "test_contract*"
```

Confirm the `SearchPort` Protocol (`SearchResult`/`SearchResponse` dataclasses, mandatory `provenance` field, keyword-only `search(query, *, num_results, language, engines)`), the JSON-first/HTML-fallback adapter, and the contract test all exist as described.

### 6.1.2 Port verbatim

```bash
mkdir -p openhands_tools_ext/websearch/ports
mkdir -p openhands_tools_ext/websearch/adapters/searxng
cp ~/dev/kosmos-reference/ports/search.py openhands_tools_ext/websearch/ports/search.py
cp ~/dev/kosmos-reference/adapters/search/searxng/adapter.py openhands_tools_ext/websearch/adapters/searxng/adapter.py
cp ~/dev/kosmos-reference/adapters/search/searxng/test_contract.py openhands_tools_ext/websearch/adapters/searxng/test_contract.py
touch openhands_tools_ext/websearch/__init__.py openhands_tools_ext/websearch/ports/__init__.py openhands_tools_ext/websearch/adapters/__init__.py openhands_tools_ext/websearch/adapters/searxng/__init__.py
```

Fix imports:

```bash
grep -rln "from kosmos" openhands_tools_ext/websearch/
```

Replace `kosmos.ports.search` → `openhands_tools_ext.websearch.ports.search` throughout.

### 6.1.3 Deploy local SearXNG

```bash
grep -n "searxng" docker-compose.yml
```

If absent, add:

```yaml
# docker-compose.yml — add under services:
  searxng:
    image: searxng/searxng:latest
    ports:
      - "8888:8080"
    volumes:
      - searxng_data:/etc/searxng
    restart: unless-stopped
    environment:
      - SEARXNG_BASE_URL=http://localhost:8888/
```

Merge `searxng_data` into the existing top-level `volumes:` block (do not duplicate the key — check what Stage 5.2 already added for `qdrant_data`).

```bash
docker compose up -d searxng
sleep 5
curl "http://localhost:8888/search?q=test&format=json"
```

If the JSON format request is rejected (some SearXNG instances disable `format=json` by default), enable it:

```bash
docker exec -it $(docker ps -qf "name=searxng") cat /etc/searxng/settings.yml | grep -A3 "search:"
```

Edit `settings.yml` to add `formats: [html, json]` under the `search:` section, then restart:

```bash
docker compose restart searxng
```

### 6.1.4 Run the ported contract test against the live instance

```bash
cd ~/dev/forge-oh
pytest openhands_tools_ext/websearch/adapters/searxng/test_contract.py -v
```

Confirm the contract test passes against your actual local SearXNG instance, not a mock — this is the point of porting the test alongside the adapter.

### 6.1.5 Backend: wrap as an `openhands_tools_ext` tool

```bash
grep -n "def register_tool\|@tool" openhands_tools_ext/*.py | head -5
```

Confirm the existing tool-registration pattern (same one used for the GPU hook, verify runner, RepoGraph tools), then mirror it exactly:

```python
# openhands_tools_ext/websearch/tool.py
from openhands_tools_ext.websearch.adapters.searxng.adapter import SearXNGAdapter
import os

_adapter = SearXNGAdapter(base_url=os.getenv("SEARXNG_BASE_URL", "http://localhost:8888"))

async def web_search_tool(query: str, num_results: int = 10, language: str = "en", engines: list[str] | None = None):
    """Search the web for current information. Returns ranked results with provenance."""
    response = await _adapter.search(query, num_results=num_results, language=language, engines=engines)
    return {
        "query": query,
        "results": [
            {"title": r.title, "url": r.url, "snippet": r.snippet, "provenance": r.provenance}
            for r in response.results
        ],
    }
```

Register following the exact pattern found in 6.0's grep — adapt the decorator/registration call to match, do not invent a new registration mechanism.

### 6.1.6 Frontend: distinct event type in run-detail timeline

```bash
grep -n "case \"LSPAction\"\|case \"MemoryConsultation\"" src/features/run-detail/EventCard.tsx
```

Add alongside the existing variants (from Stage 4.4 and Stage 5.6):

```typescript
// src/features/run-detail/types.ts — extend the discriminated union
| { kind: "WebSearch"; query: string; results: { title: string; url: string; snippet: string; provenance: string }[] }
```

```typescript
// src/features/run-detail/EventCard.tsx
case "WebSearch":
  return (
    <div className="border-l-2 border-teal-500 pl-2">
      <div className="text-sm font-medium">Web search: "{event.query}"</div>
      <ul className="text-xs">
        {event.results.map((r, i) => (
          <li key={i}>
            <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> — {r.snippet}
            <span className="text-gray-400"> ({r.provenance})</span>
          </li>
        ))}
      </ul>
    </div>
  );
```

Confirm `event_normalize.py` emits this shape at the tool-call site:

```bash
grep -n "def normalize_tool_call" bff/services/event_normalize.py
```

Add a branch mapping the web-search tool's result shape to `kind: "WebSearch"`, mirroring how other tool results are already normalized.

### 6.1.7 Verify

```bash
pnpm dev
```

Issue a real coding task requiring current external information (e.g., "check the latest FastAPI release notes for breaking changes"). Confirm:
- The agent calls the web-search tool.
- SearXNG returns real results via the ported adapter.
- Results and provenance render as a distinct `WebSearch` event in the timeline, with clickable source links.

### 6.1.8 Log

```bash
cat >> PORTING_LEDGER.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Kosmos SearchPort + SearXNG adapter
- Source: rmholston420/kosmos, commit $(cd ~/dev/kosmos-reference && git rev-parse HEAD)
- Source paths: ports/search.py, adapters/search/searxng/adapter.py, adapters/search/searxng/test_contract.py
- Destination: openhands_tools_ext/websearch/
- License/ownership: same-owner internal port
- Modification notes: import paths only
EOF
```

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.1: SearXNG web-research tool shipped
- Backend: ported SearchPort + SearXNG adapter, deployed local SearXNG via docker-compose, wrapped as an openhands_tools_ext tool, ported contract test passing against live instance
- Frontend: new WebSearch event-card type in run-detail timeline with clickable sources and provenance
- Files touched (backend): openhands_tools_ext/websearch/**, docker-compose.yml, bff/services/event_normalize.py
- Files touched (frontend): src/features/run-detail/{types.ts,EventCard.tsx}
- Verification: real task confirmed triggering the tool, results visible with provenance in the UI
- Both halves shipped together: yes
- Note: Zetesis research-loop sub-agent upgrade (synthesis/critique) explicitly deferred as a later follow-up per project sequencing
EOF
```

---

## 6.2 Condensation visibility

### 6.2.1 Inspect current status-noise fallthrough

```bash
grep -n "def normalize_status\|CondensationEvent\|CondensationSummaryEvent\|\"status\"" bff/services/event_normalize.py
```

Confirm condensation events currently fall through to the generic `"status"` kind rather than having their own normalized type.

### 6.2.2 Backend: dedicated normalized type

```python
# bff/services/event_normalize.py
def normalize_event(event) -> dict:
    if isinstance(event, CondensationEvent):
        return {
            "kind": "Condensation",
            "turnsSummarized": event.turns_summarized,
            "summary": event.summary,
        }
    if isinstance(event, CondensationSummaryEvent):
        return {
            "kind": "CondensationSummary",
            "artifactManifest": event.artifact_manifest,
        }
    # ... existing fallthrough logic for other event types, unchanged
```

Confirm the exact class names and field names from the SDK (`CondensationEvent`/`CondensationSummaryEvent`) match what's actually importable:

```bash
python3 -c "
from openhands.sdk.event import CondensationEvent, CondensationSummaryEvent
print(CondensationEvent.model_fields.keys())
print(CondensationSummaryEvent.model_fields.keys())
"
```

Adjust field access in the normalizer to match whatever's actually confirmed here.

### 6.2.3 Frontend: collapsible marker

```typescript
// src/features/run-detail/EventCard.tsx
case "Condensation":
  return (
    <details className="text-xs text-gray-400 border rounded px-2 py-1">
      <summary>Context compressed — {event.turnsSummarized} turns summarized</summary>
      <p className="mt-1">{event.summary}</p>
    </details>
  );
```

### 6.2.4 Verify

Trigger a long-running task that hits a context-compaction threshold (or artificially lower the threshold temporarily to force one for testing):

```bash
grep -n "COMPACTION_THRESHOLD\|condenser.*trigger" bff/config.py openhands_tools_ext/*.py 2>/dev/null
```

Confirm a `Condensation` marker appears in the timeline at the moment compaction fires, distinct from generic status noise, and that it's collapsed by default with expandable detail.

### 6.2.5 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.2: Condensation visibility shipped
- Backend: dedicated Condensation/CondensationSummary normalized event types, replacing generic status fallthrough
- Frontend: collapsible "context compressed — N turns summarized" marker in timeline
- Files touched (backend): bff/services/event_normalize.py
- Files touched (frontend): src/features/run-detail/EventCard.tsx
- Verification: confirmed marker appears distinctly at a real compaction trigger, collapsed by default
EOF
```

---

## 6.3 Idempotency ledger (exactly-once gap)

### 6.3.1 Inspect existing SQLite patterns to match

```bash
cat bff/db/episodic_memory.py | head -30
cat bff/db/agent_presets.py 2>/dev/null | head -30  # from Stage 1.5
```

### 6.3.2 Backend: ledger table and check function

```python
# bff/db/idempotency_ledger.py
import sqlite3
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("data/idempotency_ledger.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS completed_side_effects (
            idempotency_key TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            argument_hash TEXT NOT NULL,
            result_summary TEXT,
            completed_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def compute_idempotency_key(task_id: str, step_index: int, arguments: dict) -> str:
    arg_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()
    return f"{task_id}:{step_index}:{arg_hash}"

def has_completed(idempotency_key: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT 1 FROM completed_side_effects WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    conn.close()
    return row is not None

def mark_completed(idempotency_key: str, task_id: str, step_index: int, arguments: dict, result_summary: str = ""):
    arg_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO completed_side_effects (idempotency_key, task_id, step_index, argument_hash, result_summary) VALUES (?, ?, ?, ?, ?)",
        (idempotency_key, task_id, step_index, arg_hash, result_summary),
    )
    conn.commit()
    conn.close()
```

```bash
mkdir -p data
python3 -c "from bff.db.idempotency_ledger import init_db; init_db()"
```

### 6.3.3 Wire into the tool-execution envelope

```bash
grep -n "def execute_tool\|class ToolExecutionEnvelope" bff/services/*.py openhands_tools_ext/*.py 2>/dev/null
```

Confirm the exact point where state-changing tool calls are dispatched, then wrap:

```python
# wherever tool execution is dispatched, e.g. bff/services/tool_dispatcher.py
from bff.db.idempotency_ledger import compute_idempotency_key, has_completed, mark_completed

async def execute_state_changing_tool(task_id: str, step_index: int, tool_name: str, arguments: dict):
    key = compute_idempotency_key(task_id, step_index, arguments)
    if has_completed(key):
        return {"skipped": True, "reason": "Already completed (idempotency key match)", "key": key}
    result = await actually_invoke_tool(tool_name, arguments)
    mark_completed(key, task_id, step_index, arguments, result_summary=str(result)[:500])
    return {"skipped": False, "result": result}
```

Confirm this wraps every write-tool call path identified in Stage 3.3.1's install-path grep, plus any file-write/notification-send tool paths — grep broadly:

```bash
grep -rln "def.*write\|def.*send\|def.*notify\|def.*install\|def.*delete" openhands_tools_ext/ bff/services/ | grep -v test
```

### 6.3.4 Verify replay safety

```bash
python3 -c "
import asyncio
from bff.services.tool_dispatcher import execute_state_changing_tool

async def main():
    r1 = await execute_state_changing_tool('task-1', 0, 'write_file', {'path': '/tmp/test.txt', 'content': 'hello'})
    print('First call:', r1)
    r2 = await execute_state_changing_tool('task-1', 0, 'write_file', {'path': '/tmp/test.txt', 'content': 'hello'})
    print('Replay:', r2)
    assert r2['skipped'] is True

asyncio.run(main())
"
```

Confirm the second identical call is skipped, not re-executed.

Test a genuine crash-and-resume scenario if feasible: kill the BFF process mid-task, restart, confirm the ledger (SQLite-backed, durable across restarts) correctly prevents re-running the already-completed step.

### 6.3.5 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.3: Idempotency ledger shipped
- SQLite-backed completed_side_effects table keyed by task_id+step_index+argument_hash
- Wired into tool-execution envelope for all identified state-changing tool paths (write, send, notify, install, delete)
- Files touched: bff/db/idempotency_ledger.py, bff/services/tool_dispatcher.py (or actual dispatch location)
- Verification: replay of an identical call confirmed skipped; crash-and-resume scenario confirmed not re-executing a completed step
EOF
```

---

## 6.4 Checkpoint-to-disk revert

### 6.4.1 Inspect existing checkpoint/fork mechanism

```bash
grep -n "def fork\|Conversation.fork\|checkpoint" bff/services/*.py openhands_tools_ext/*.py 2>/dev/null
find src -iname "*checkpoint*" -o -iname "*history*"
```

Confirm what checkpoint metadata already exists (commit SHA association, conversation-state snapshot) before building the revert action on top of it.

### 6.4.2 Backend: revert endpoint

```python
# bff/routers/checkpoints.py
from fastapi import APIRouter, HTTPException
import subprocess

router = APIRouter()

@router.post("/api/runs/{run_id}/checkpoints/{checkpoint_id}/revert")
async def revert_to_checkpoint(run_id: str, checkpoint_id: str):
    checkpoint = get_checkpoint_metadata(run_id, checkpoint_id)  # confirm actual lookup function name
    if checkpoint is None:
        raise HTTPException(404, "Checkpoint not found")
    workdir = get_run_workdir(run_id)  # confirm actual lookup function name
    result = subprocess.run(
        ["git", "-C", workdir, "reset", "--hard", checkpoint.commit_sha],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise HTTPException(500, f"git reset failed: {result.stderr}")
    await restore_conversation_state(run_id, checkpoint_id)  # confirm actual state-restore function name
    return {"status": "reverted", "commitSha": checkpoint.commit_sha}
```

Confirm the exact function names for checkpoint lookup, workdir resolution, and conversation-state restore from 6.4.1's inspection — do not invent function names that don't exist in the real codebase.

**Safety guard:** confirm `workdir` is genuinely the run's isolated worktree/sandbox path, not a shared or host-critical directory, before running `git reset --hard` — a hardcoded or misresolved path here is destructive.

```bash
grep -n "def get_run_workdir" bff/services/*.py
```

Add an assertion before the reset:

```python
if not workdir.startswith(str(WORKTREE_ROOT)):
    raise HTTPException(500, f"Refusing to revert outside worktree root: {workdir}")
```

### 6.4.3 Frontend: revert control on checkpoint/history view

```bash
find src -iname "*CheckpointList*" -o -iname "*HistoryPanel*"
```

Add a revert button per checkpoint entry, with a confirmation dialog since this is destructive:

```typescript
// src/features/run-detail/CheckpointRevertButton.tsx
export function CheckpointRevertButton({ runId, checkpointId }: { runId: string; checkpointId: string }) {
  const [confirming, setConfirming] = useState(false);

  async function handleRevert() {
    const res = await fetch(`${BASE}/api/runs/${runId}/checkpoints/${checkpointId}/revert`, { method: "POST" });
    if (!res.ok) {
      alert(`Revert failed: ${res.status}`);
      return;
    }
    window.location.reload(); // or trigger a proper state refetch, confirm the codebase's preferred pattern
  }

  if (!confirming) {
    return <button onClick={() => setConfirming(true)}>Revert to here</button>;
  }
  return (
    <div>
      <p>This will discard all working-directory changes and conversation state after this checkpoint. Continue?</p>
      <button onClick={handleRevert}>Confirm revert</button>
      <button onClick={() => setConfirming(false)}>Cancel</button>
    </div>
  );
}
```

Wire into the existing checkpoint list/history panel component found in 6.4.1.

### 6.4.4 Verify

```bash
pnpm dev
```

Run a task with at least two checkpoints, make a working-directory change after the first checkpoint, revert to it via the UI, confirm:
- The confirmation dialog appears before any destructive action.
- The working directory's file contents match the state at that checkpoint (`git log` / `git status` in the worktree).
- The conversation state (message history, plan state) is also restored, not just the files.

### 6.4.5 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.4: Checkpoint-to-disk revert shipped
- Backend: POST /api/runs/{run_id}/checkpoints/{checkpoint_id}/revert, git reset --hard scoped to confirmed worktree root, conversation-state restore
- Frontend: CheckpointRevertButton with destructive-action confirmation dialog, wired into existing checkpoint/history panel
- Files touched (backend): bff/routers/checkpoints.py
- Files touched (frontend): src/features/run-detail/CheckpointRevertButton.tsx, checkpoint/history panel file
- Verification: confirmed both working-directory files and conversation state correctly restored on real revert; worktree-root safety guard confirmed rejecting out-of-bounds paths
EOF
```

---

## 6.5 Runtime model switching

### 6.5.1 Confirm the REST surface exists at pinned SDK version — do not assume

```bash
python3 -c "
import openhands.sdk
import inspect
print([m for m in dir(openhands.sdk) if 'model' in m.lower() or 'switch' in m.lower()])
"
grep -rn "switch_model" $(python3 -c "import openhands.sdk, os; print(os.path.dirname(openhands.sdk.__file__))")
```

**Decision gate:** if this is only an SDK-level method with no exposed REST endpoint on the agent-server, log this as an SDK gap in `DEBUG_LOG.md` and stop here — do not build a frontend control for a capability with no real backend path, per the governing rule in reverse (a UI control with no real backend effect is exactly as forbidden as a backend-only dead end).

```bash
cat >> DEBUG_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — SDK gap check: runtime model switching REST surface
- Symptom: confirming whether openhands-sdk==1.40.0 exposes switch_model via agent-server REST, not just SDK-internal method
- Affected stage: Stage 6.5
- Finding: [PRESENT as REST endpoint / SDK-internal only, no REST surface — fill in from inspection]
- If absent: Stage 6.5 deferred until agent-server exposes this over REST; do not fabricate a frontend control against a nonexistent endpoint
EOF
```

If confirmed present as a real REST surface, continue to 6.5.2.

### 6.5.2 Backend: forwarding endpoint

```python
# bff/routers/runs.py — add
@router.post("/runs/{run_id}/model")
async def switch_run_model(run_id: str, payload: ModelSwitchPayload):
    conversation_id = get_conversation_id_for_run(run_id)
    result = await agent_server_client.post(
        f"/api/conversations/{conversation_id}/switch-model",  # confirm exact path from SDK inspection
        json={"model": payload.model, "backendId": payload.backendId},
    )
    return result
```

### 6.5.3 Frontend: model-switch control in run-detail header

```bash
cat src/features/settings/ModelSection.tsx
```

Reuse its model-picker pattern:

```typescript
// src/features/run-detail/ModelSwitchControl.tsx
import { useInferenceBackends } from "@/features/agent-presets/hooks"; // from Stage 2.2

export function ModelSwitchControl({ runId, currentModel }: { runId: string; currentModel: string }) {
  const { data: backends } = useInferenceBackends();

  async function handleSwitch(model: string, backendId: string) {
    const res = await fetch(`${BASE}/api/runs/${runId}/model`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, backendId }),
    });
    if (!res.ok) alert(`Model switch failed: ${res.status}`);
  }

  // render a picker matching ModelSection.tsx's existing UI pattern, calling handleSwitch on selection
}
```

### 6.5.4 Verify

Start a run on a fast/small model, mid-task switch to a heavier model via the new control, confirm the agent's subsequent responses reflect the new model (check response metadata or latency profile as a signal) without restarting the run.

### 6.5.5 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.5: Runtime model switching shipped
- Confirmed agent-server REST surface for switch_model at pinned SDK version: [confirmed present]
- Backend: POST /runs/{run_id}/model forwarding to agent-server
- Frontend: ModelSwitchControl in run-detail header, reusing ModelSection.tsx's picker pattern
- Files touched (backend): bff/routers/runs.py
- Files touched (frontend): src/features/run-detail/ModelSwitchControl.tsx
- Verification: mid-task model switch confirmed without run restart
EOF
```

(If the decision gate in 6.5.1 found the capability absent, skip 6.5.2-6.5.5 and log only the DEBUG_LOG.md entry, then proceed to 6.6.)

---

## 6.6 Skills/Microagents management page

### 6.6.1 Inspect existing skills usage

```bash
grep -rn "activated_skills" bff/services/event_normalize.py
find . -iname "*.skills" -o -iname "skills" -type d
grep -rn "GET.*skills" $(python3 -c "import openhands.sdk, os; print(os.path.dirname(openhands.sdk.__file__))") 2>/dev/null
```

### 6.6.2 Backend: skills listing

If the agent-server exposes a skills-listing endpoint at the pinned SDK version, proxy it:

```python
# bff/routers/skills.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/skills")
async def list_skills():
    result = await agent_server_client.get("/api/skills")  # confirm exact path exists first
    return result
```

If no such endpoint exists, read skill definitions from disk directly:

```python
@router.get("/api/skills")
async def list_skills():
    skills_dir = Path(".skills")  # confirm actual directory name/location from 6.6.1
    skills = []
    for f in skills_dir.glob("*.md"):
        content = f.read_text()
        skills.append({"name": f.stem, "path": str(f), "content": content[:500]})
    return {"skills": skills}
```

Register in `bff/main.py`.

### 6.6.3 Frontend: skills page

```typescript
// src/app/(dashboard)/skills/page.tsx
import { useQuery } from "@tanstack/react-query";

export default function SkillsPage() {
  const { data } = useQuery({
    queryKey: ["skills"],
    queryFn: async () => (await fetch(`${BASE}/api/skills`)).json(),
  });

  return (
    <div>
      <h2>Skills / Microagents</h2>
      <ul>
        {data?.skills?.map((s: any) => (
          <li key={s.name}>
            <strong>{s.name}</strong>
            <p className="text-sm text-gray-500">{s.content}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

Add sidebar entry matching the existing nav pattern.

### 6.6.4 Surface which skills fired on a given run's Trace tab

```bash
grep -n "activated_skills" bff/services/event_normalize.py
```

Confirm this field already flows through normalized events (per the baseline inspection); add a rendering branch:

```typescript
// src/features/run-detail/TraceTab.tsx (or wherever the Trace tab renders)
{run.activatedSkills?.length > 0 && (
  <div className="text-xs">
    Skills fired: {run.activatedSkills.join(", ")}
  </div>
)}
```

### 6.6.5 Verify

```bash
pnpm dev
```

Confirm `/skills` lists real skill definitions and trigger conditions. Run a task known to fire a specific skill, confirm it's listed in that run's Trace tab.

### 6.6.6 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.6: Skills/Microagents page shipped
- Backend: GET /api/skills (proxy or disk-read, per 6.6.1 finding)
- Frontend: new /skills page + sidebar entry, activated_skills surfaced in run-detail Trace tab
- Files touched (backend): bff/routers/skills.py, bff/main.py
- Files touched (frontend): src/app/(dashboard)/skills/page.tsx, src/features/run-detail/TraceTab.tsx, Sidebar.tsx
- Verification: real skills listed, activated_skills confirmed visible on a run known to trigger one
EOF
```

---

## 6.7 Code-execution-with-MCP invocation mode

### 6.7.1 Inspect current tool-invocation pattern

```bash
grep -n "def invoke_tool\|direct.*mcp.*call" bff/services/*.py openhands_tools_ext/*.py 2>/dev/null
```

Confirm whether tool calls currently always load full schemas into context, or whether any progressive-disclosure already exists from Stage 4.4's LSP lazy-start work.

### 6.7.2 Backend: code-execution invocation path

```python
# openhands_tools_ext/tool_invocation/code_exec_mode.py
import subprocess
import json

async def invoke_via_code_execution(python_code: str, available_tool_stubs: dict) -> dict:
    """
    Execute agent-authored Python that calls tool functions programmatically,
    rather than the model directly emitting per-call tool-invocation JSON.
    Intermediate results and unused tool schemas stay out of the model's context.
    """
    namespace = {**available_tool_stubs}
    exec_globals = {"__builtins__": __builtins__, **namespace}
    try:
        exec(python_code, exec_globals)
        result = exec_globals.get("result")
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**Security note:** this executes agent-authored code, which must run inside the existing sandboxed workspace execution boundary (per the sandboxing tier already established for all agent-generated code), never in the BFF process directly. Confirm the actual sandbox invocation path:

```bash
grep -n "def run_in_sandbox\|docker.*exec\|gVisor\|runsc" bff/services/*.py openhands_tools_ext/*.py 2>/dev/null
```

Route `invoke_via_code_execution`'s actual `exec()` call through that sandbox boundary, not as a bare Python `exec()` in the BFF process as shown above — the snippet above is illustrative of the invocation contract only, not the final security posture.

### 6.7.3 Progressive disclosure: tool/skill metadata gating

```python
# openhands_tools_ext/tool_invocation/progressive_disclosure.py
def get_tool_stub_metadata() -> list[dict]:
    """Return only name + one-line description for every registered tool, not full schemas."""
    return [{"name": t.name, "description": t.one_line_description} for t in ALL_REGISTERED_TOOLS]

def get_full_tool_schema(tool_name: str) -> dict:
    """Load full schema/instructions only once a task is identified as needing this specific tool."""
    tool = next(t for t in ALL_REGISTERED_TOOLS if t.name == tool_name)
    return tool.full_schema()
```

Wire the agent's context-assembly step to call `get_tool_stub_metadata()` at session start (cheap), and `get_full_tool_schema()` only when the planning step identifies a specific tool as needed — confirm the actual context-assembly call site:

```bash
grep -n "def build_context\|def assemble_prompt" bff/services/*.py openhands_tools_ext/*.py 2>/dev/null
```

### 6.7.4 Default routing: code-execution for tool-heavy phases, direct calls otherwise

```python
# openhands_tools_ext/tool_invocation/router.py
def should_use_code_execution(task_phase: str, estimated_tool_call_count: int) -> bool:
    TOOL_HEAVY_PHASES = {"multi_file_edit", "verification", "refactor"}
    return task_phase in TOOL_HEAVY_PHASES or estimated_tool_call_count > 3
```

Wire this decision into whichever orchestration point currently dispatches tool calls, defaulting to direct MCP calls for anything not flagged tool-heavy.

### 6.7.5 Verify token-usage improvement

```bash
grep -n "token.*count\|usage.*track" bff/services/event_normalize.py bff/services/*.py 2>/dev/null
```

Run the same multi-file-edit task twice — once forcing direct MCP calls, once via code-execution mode — and compare token usage from whatever tracking mechanism already exists:

```bash
curl "http://localhost:8000/api/runs/{run_id}/token-usage" 2>/dev/null || grep -n "token" bff/routers/runs.py
```

Confirm a measurable reduction in tool-schema-related token overhead for the code-execution path on the tool-heavy task. This does not require a frontend change on its own — token usage should already be visible wherever the existing run-detail page shows cost/usage metrics; confirm this is the case rather than building a new display.

```bash
grep -rn "tokenUsage\|token_count" src/features/run-detail/
```

If no such display exists yet, this is out of scope for Stage 6.7 to add net-new — flag it as a possible Stage 7 addition rather than scope-creeping this sub-stage.

### 6.7.6 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6.7: Code-execution-with-MCP invocation mode shipped
- Backend: invoke_via_code_execution() routed through existing sandbox boundary (not bare exec in BFF process), progressive-disclosure tool-stub/full-schema split, should_use_code_execution() routing heuristic (tool-heavy phases or >3 estimated calls)
- Verification: measurable token-usage reduction confirmed on a tool-heavy multi-file-edit task comparing direct-call vs. code-execution paths
- Files touched: openhands_tools_ext/tool_invocation/{code_exec_mode.py,progressive_disclosure.py,router.py}
- Frontend: no new UI required — confirmed existing token-usage display (if present) already reflects the improvement; flagged for Stage 7 if no such display currently exists
EOF
```

---

## Stage 6 exit gate — do not proceed to Stage 7 until all pass

```bash
cd ~/dev/forge-oh
pytest bff/tests/ -q
pnpm typecheck
pnpm test:unit
pnpm build
```

Manual verification checklist:
- [ ] SearXNG web-research tool confirmed triggering on a real task, results visible with provenance in the timeline.
- [ ] Condensation events render distinctly, collapsed by default, not blended into generic status noise.
- [ ] Idempotency ledger confirmed preventing a replayed identical tool call from re-executing, including across a real crash-and-resume test.
- [ ] Checkpoint revert confirmed restoring both working-directory files and conversation state, with the worktree-root safety guard confirmed rejecting out-of-bounds paths.
- [ ] Runtime model switching confirmed working (or correctly deferred with a `DEBUG_LOG.md` entry if the REST surface doesn't exist at this SDK version).
- [ ] Skills page lists real skills and trigger conditions; a run's Trace tab shows which skills fired.
- [ ] Code-execution invocation mode confirmed reducing token usage on a tool-heavy task, routed through the existing sandbox boundary (not bare `exec()` in the BFF).

## Final Stage 6 log entry

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 6 COMPLETE
- All Stage 6 exit-gate checks passed
- Harness engineering maturity raised: web-research tool, condensation visibility, idempotency ledger, checkpoint revert, model switching (or documented gap), skills page, code-execution invocation mode
- Next action: begin Stage 7.1 (docker-compose.yml single-host topology reconciliation)
EOF

cat > SESSION_HANDOFF.md << 'EOF'
# Session Handoff

**Current stage:** Stage 6 complete, ready to begin Stage 7 (Infra Cleanup and Deferred Items — final stage).

**Completed this session:**
- Stage 6.1 through 6.7, all verified per exit-gate checklist above.

**Remaining before Stage 6 Definition of Done:** none — Stage 6 is fully complete.

**Open questions awaiting review:**
- [If 6.5 found no REST surface for switch_model]: deferred pending future SDK version; no action needed now.
- [If 6.7.5 found no existing token-usage display]: flagged as a possible Stage 7 addition, not yet scheduled.

**Exact next action:** Begin Stage 7.1 — rewrite docker-compose.yml for the real single-host topology (bff + frontend + DozerDB + Qdrant + SearXNG containerized, agent-server as host process).
EOF
```
