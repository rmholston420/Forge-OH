
# Forge-OH Reconciliation Plan v1 — Stage 4 (Detailed)

Standalone implementation plan for Perplexity Computer. Target: Colossus (128GB RAM, RTX 5090, 32GB VRAM, Blackwell SM_120). Single-user, local-first, no cloud control planes.

**Prerequisite:** Stage 3 must be complete and its exit gate verified (see `Forge-OH-reconciliation-plan-v1-stage-3.md`). Read `SESSION_HANDOFF.md` before starting — it should point here.

**Governing rule (non-negotiable):** backend and frontend ship together in the same commit/session. A backend endpoint with no reachable UI path, or a UI control wired to a stub, is not "done."

**Stage 4 goal:** enable the existing-but-disabled RepoGraph knowledge-graph feature end to end (DozerDB-backed, currently text/list-only), add a graph-shaped visualization, and add a new `LSPClient` port (Serena-wrapped language servers) for symbol-precise operations that neither grep nor embeddings can provide. This stage also requires resolving a real architectural decision: whether RepoGraph's symbol graph and Stage 5's semantic-memory graph share one DozerDB instance.

```bash
cd ~/dev/forge-oh
cat SESSION_HANDOFF.md
```

Confirm it names Stage 4 as the next action before proceeding.

---

## 4.0 Baseline inspection

```bash
grep -rn "repograph_enabled\|REPOGRAPH_ENABLED" bff/ openhands_tools_ext/ docker-compose.yml .env* 2>/dev/null
find openhands_tools_ext -iname "*repograph*"
cat openhands_tools_ext/repograph/neo4j_driver.py 2>/dev/null || find . -iname "*neo4j_driver*"
grep -rn "dozerdb\|DozerDB\|DOZERDB" . --include="*.py" --include="*.yml" --include="*.env*" 2>/dev/null
docker ps -a | grep -i "dozerdb\|neo4j"
grep -n "GET /api/repograph" bff/routers/repograph.py 2>/dev/null
find src -iname "*RepoGraph*"
```

Record the exact current state: is `neo4j_driver.py` actually pointed at a DozerDB connection string, or does it assume stock Neo4j? DozerDB is a Neo4j fork and is largely protocol-compatible via the Bolt driver, but confirm the connection URI scheme and any DozerDB-specific extensions actually in use before assuming a drop-in swap.

---

## 4.1 Enable RepoGraph for real (ops)

### 4.1.1 Confirm DozerDB is running and reachable

```bash
docker ps | grep dozerdb
```

If not running, start it (adjust image/tag to your actual pinned DozerDB image):

```bash
docker run -d --name dozerdb \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/CHANGE_ME_REAL_PASSWORD \
  -v dozerdb_data:/data \
  graphfoundation/dozerdb:latest
```

Confirm the exact DozerDB image name/tag from your existing infra docs before running this — do not guess an image name blindly:

```bash
grep -rn "dozerdb" docker-compose.yml Software_stack_versions.md 2>/dev/null
```

Verify connectivity:

```bash
curl http://localhost:7474
```

### 4.1.2 Populate real credentials

```bash
cat ~/dev/forge-oh/.env.neo4j 2>/dev/null
```

If this file has placeholder/missing credentials (per the warning log referenced in `neo4j_driver.py`), set real ones:

```bash
cat > ~/dev/forge-oh/.env.neo4j << 'EOF'
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=CHANGE_ME_REAL_PASSWORD
EOF
chmod 600 ~/dev/forge-oh/.env.neo4j
```

Confirm this file is in `.gitignore`:

```bash
grep -n ".env.neo4j" .gitignore || echo ".env.neo4j" >> .gitignore
```

### 4.1.3 Flip the enablement flag to env-driven

```bash
grep -n "repograph_enabled" bff/config.py openhands_tools_ext/repograph/*.py 2>/dev/null
```

Locate the hardcoded `False` and replace it:

```python
# before
repograph_enabled = False

# after
import os
repograph_enabled = os.getenv("REPOGRAPH_ENABLED", "false").lower() == "true"
```

Add to `.env.example` and your local `.env`:

```bash
echo "REPOGRAPH_ENABLED=true" >> .env
grep -n "REPOGRAPH_ENABLED" .env.example || echo "REPOGRAPH_ENABLED=false" >> .env.example
```

### 4.1.4 Verify

```bash
curl http://localhost:8000/api/repograph/health
```

Must return `{"available": true, ...}` instead of a 503. If still 503, check the driver's actual connection attempt:

```bash
grep -n "def get_driver\|GraphDatabase.driver" openhands_tools_ext/repograph/neo4j_driver.py
python3 -c "
from openhands_tools_ext.repograph.neo4j_driver import get_driver
d = get_driver()
d.verify_connectivity()
print('OK')
"
```

### 4.1.5 Index the current repo to confirm end-to-end data flow

```bash
grep -n "def index_repo\|POST /api/repograph/index" bff/routers/repograph.py
curl -X POST http://localhost:8000/api/repograph/index -H "Content-Type: application/json" -d '{"repo_key":"forge-oh"}'
```

Confirm symbols and edges are actually written — query directly:

```bash
docker exec -it dozerdb cypher-shell -u neo4j -p CHANGE_ME_REAL_PASSWORD "MATCH (n) RETURN count(n)"
```

Must return a non-zero count.

### 4.1.6 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 4.1: RepoGraph enabled on DozerDB
- Started DozerDB container, confirmed Bolt connectivity
- Populated .env.neo4j with real credentials, confirmed .gitignore coverage
- Flipped repograph_enabled to env-driven (REPOGRAPH_ENABLED)
- Indexed forge-oh repo itself as first real data, confirmed non-zero node count in DozerDB
- Files touched: bff/config.py (or wherever the flag lived), .env, .env.example, .env.neo4j, .gitignore
- Verification: GET /api/repograph/health returns available:true, direct cypher-shell query confirms real data
EOF
```

---

## 4.2 Graph-shaped aggregation endpoint (backend)

### 4.2.1 Inspect existing query patterns

```bash
grep -n "def.*pagerank\|def get_callers\|def get_callees" openhands_tools_ext/repograph/store.py
cat openhands_tools_ext/repograph/store.py | head -100
```

Confirm the existing Cypher query style and the `SymbolOut`/`CallerOut`/`CalleeOut` Pydantic models already defined — the new endpoint must reuse these types, not invent new ones.

### 4.2.2 Implement `full_graph()`

```python
# openhands_tools_ext/repograph/store.py — add
from pydantic import BaseModel

class GraphNode(BaseModel):
    id: str
    label: str
    pagerank: float
    category: str
    rel_path: str

class GraphEdge(BaseModel):
    source: str
    target: str
    type: str  # "CALLS" | "DEFINES"

class FullGraphResult(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphEdge]

def full_graph(repo_key: str, limit: int = 500) -> FullGraphResult:
    driver = get_driver()
    query = """
    MATCH (s:Symbol {repo_key: $repo_key})
    WITH s ORDER BY s.pagerank DESC LIMIT $limit
    WITH collect(s) AS symbols
    UNWIND symbols AS s1
    OPTIONAL MATCH (s1)-[r:CALLS|DEFINES]->(s2:Symbol)
    WHERE s2 IN symbols
    RETURN
        [x IN symbols | {id: x.id, label: x.name, pagerank: x.pagerank, category: x.category, rel_path: x.rel_path}] AS nodes,
        collect(DISTINCT {source: s1.id, target: s2.id, type: type(r)}) AS edges
    """
    with driver.session() as session:
        result = session.run(query, repo_key=repo_key, limit=limit)
        record = result.single()
        nodes = [GraphNode(**n) for n in record["nodes"]]
        links = [GraphEdge(**e) for e in record["edges"] if e["target"] is not None]
    return FullGraphResult(nodes=nodes, links=links)
```

Confirm this Cypher query's exact node/relationship label names (`Symbol`, `CALLS`, `DEFINES`) match what the existing indexing code actually writes — grep the indexer:

```bash
grep -n "CREATE.*Symbol\|MERGE.*Symbol\|:CALLS\|:DEFINES" openhands_tools_ext/repograph/indexer.py
```

Adjust label/relationship names in the query above if they differ from what's found here.

### 4.2.3 New endpoint

```python
# bff/routers/repograph.py — add
from openhands_tools_ext.repograph.store import full_graph

@router.get("/api/repograph/graph")
async def get_full_graph(repo_key: str, limit: int = 500):
    result = full_graph(repo_key=repo_key, limit=limit)
    return {"nodes": [n.model_dump() for n in result.nodes], "links": [l.model_dump() for l in result.links]}
```

### 4.2.4 Verify

```bash
curl "http://localhost:8000/api/repograph/graph?repo_key=forge-oh&limit=500" | python3 -m json.tool | head -50
```

Confirm `nodes` and `links` are both non-empty and match the exact shape `ForceGraph2D` expects (`{id, label, ...}` for nodes; `{source, target, type}` for links — `react-force-graph` specifically needs `source`/`target` keys, confirm no renaming is needed before frontend work begins).

### 4.2.5 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 4.2: Graph aggregation endpoint shipped (backend half — ships with 4.3 frontend in same pass)
- Added full_graph() Cypher aggregation in store.py, reusing existing SymbolOut/CallerOut/CalleeOut type conventions
- New GET /api/repograph/graph returning {nodes, links} shape
- Files touched: openhands_tools_ext/repograph/store.py, bff/routers/repograph.py
- Verification: confirmed non-empty response shape matches react-force-graph's expected {id,...}/{source,target,type}
EOF
```

---

## 4.3 Visualization component (frontend — ships in same pass as 4.2, not deferred)

### 4.3.1 Vendor `react-force-graph-2d`

```bash
pnpm add react-force-graph-2d
```

```bash
cat >> PORTING_LEDGER.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — react-force-graph-2d
- Source: https://github.com/vasturiano/react-force-graph
- Pinned version: $(pnpm list react-force-graph-2d | grep react-force-graph-2d)
- SPDX license: MIT
- Modification notes: none, vendored as-is via pnpm
EOF
```

### 4.3.2 Inspect the existing RepoGraph panel to extend, not replace

```bash
find src -iname "*RepoGraphPanel*"
cat src/features/repograph/RepoGraphPanel.tsx
grep -n "useCallers\|useCallees" src/features/repograph/hooks.ts
```

### 4.3.3 Build the graph view component

```typescript
// src/features/repograph/RepoGraphGraphView.tsx
import ForceGraph2D from "react-force-graph-2d";
import { useState } from "react";
import { useCallers, useCallees } from "./hooks";

interface GraphNode {
  id: string;
  label: string;
  pagerank: number;
  category: string;
  rel_path: string;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
}

export function RepoGraphGraphView({ repoKey }: { repoKey: string }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });

  useEffect(() => {
    fetch(`${BASE}/api/repograph/graph?repo_key=${repoKey}&limit=500`)
      .then((res) => res.json())
      .then(setGraphData);
  }, [repoKey]);

  const { data: callers } = useCallers(selectedNode ?? "", { enabled: !!selectedNode });
  const { data: callees } = useCallees(selectedNode ?? "", { enabled: !!selectedNode });

  return (
    <div style={{ height: "600px", position: "relative" }}>
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="label"
        nodeVal={(n: GraphNode) => Math.max(2, n.pagerank * 50)}
        nodeColor={(n: GraphNode) => (n.category === "function" ? "#4f9cf9" : "#f97316")}
        onNodeClick={(n: GraphNode) => setSelectedNode(n.id)}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
      />
      {selectedNode && (
        <div style={{ position: "absolute", top: 0, right: 0, width: "300px" }}>
          <h4>Callers/Callees for {selectedNode}</h4>
          <ul>{callers?.map((c) => <li key={c.id}>{c.name}</li>)}</ul>
          <ul>{callees?.map((c) => <li key={c.id}>{c.name}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
```

Confirm `useCallers`/`useCallees` hook signatures match exactly — adapt the call shape above to whatever they actually return, do not assume.

### 4.3.4 Add List/Graph toggle to the existing panel

```typescript
// src/features/repograph/RepoGraphPanel.tsx — extend, do not replace existing list view
import { useState } from "react";
import { RepoGraphGraphView } from "./RepoGraphGraphView";

export function RepoGraphPanel({ repoKey }: { repoKey: string }) {
  const [view, setView] = useState<"list" | "graph">("list");

  return (
    <div>
      <div className="flex gap-2 mb-2">
        <button onClick={() => setView("list")} className={view === "list" ? "font-bold" : ""}>List</button>
        <button onClick={() => setView("graph")} className={view === "graph" ? "font-bold" : ""}>Graph</button>
      </div>
      {view === "list" ? <ExistingListView repoKey={repoKey} /> : <RepoGraphGraphView repoKey={repoKey} />}
    </div>
  );
}
```

Confirm the actual name of the existing list-rendering component before referencing `ExistingListView` — grep the current file's JSX to find it.

### 4.3.5 Standalone `/repograph` route

```bash
find src/app -maxdepth 2 -type d
```

```typescript
// src/app/(dashboard)/repograph/page.tsx
import { RepoGraphPanel } from "@/features/repograph/RepoGraphPanel";

export default function RepoGraphPage() {
  return <RepoGraphPanel repoKey="forge-oh" />;
  // TODO: make repoKey selectable once multi-repo workspace support exists
}
```

Add a sidebar entry:

```bash
grep -n "href=\"/tools-mcp\"" src/components/Sidebar.tsx
```

Add a matching entry for `/repograph` in the same list.

### 4.3.6 Verify

```bash
pnpm dev
```

- Navigate to a run-detail Trace tab, confirm the per-run RepoGraph panel now has a working List/Graph toggle, and the graph renders nodes sized/colored by pagerank.
- Click a node, confirm the caller/callee side panel populates using the existing hooks (no new fetch logic for drill-down).
- Navigate to the standalone `/repograph` route via the new sidebar entry, confirm the whole-codebase graph renders.

### 4.3.7 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 4.3: RepoGraph visualization shipped (frontend half of 4.2's endpoint)
- Vendored react-force-graph-2d (logged in PORTING_LEDGER.md)
- New RepoGraphGraphView.tsx, List/Graph toggle added to existing RepoGraphPanel.tsx
- New standalone /repograph route + sidebar entry
- Files touched: src/features/repograph/RepoGraphGraphView.tsx, RepoGraphPanel.tsx, src/app/(dashboard)/repograph/page.tsx, Sidebar.tsx
- Verification: per-run Trace-tab graph confirmed rendering with working drill-down; standalone route confirmed reachable
- Both halves shipped together: yes (4.2 backend + 4.3 frontend landed in the same pass)
EOF
```

---

## 4.4 `LSPClient` port (Serena-wrapped language servers)

This closes an ACA-v8 gap: embeddings alone can't do symbol-precise renames, references, or type-aware diagnostics. Add this as Tier 3 of a grep → embeddings → LSP retrieval cascade.

### 4.4.1 Inspect Serena and confirm MCP exposure

```bash
pip show serena-agent 2>/dev/null || echo "not installed"
```

```bash
pip install serena-agent
```

Confirm Serena's MCP server entrypoint:

```bash
python3 -m serena --help
```

Identify which language servers it wraps by default and confirm at least Python and TypeScript/JavaScript are covered (Forge-OH's own stack), since your active worktrees will primarily be Python (bff) and TypeScript (frontend):

```bash
python3 -m serena list-languages 2>/dev/null || python3 -c "import serena; print(serena.SUPPORTED_LANGUAGES)"
```

### 4.4.2 Backend: register as an MCP tool

```bash
grep -n "def register_mcp_server\|mcp.*register" bff/services/*.py openhands_tools_ext/*.py
```

Confirm the existing MCP-server registration pattern (used for other MCP tools already in Forge-OH), then register Serena the same way:

```python
# openhands_tools_ext/lsp/serena_registration.py
import subprocess

def start_serena_mcp_server(workspace_path: str, port: int = 9100):
    return subprocess.Popen([
        "python3", "-m", "serena", "start-mcp-server",
        "--workspace", workspace_path,
        "--port", str(port),
    ])
```

Wire lazy-start logic: only start Serena's language server for a given language when the active worktree actually contains files of that language, not eagerly on session start (per the progressive-disclosure principle):

```python
# openhands_tools_ext/lsp/lazy_start.py
import os

def detect_languages_in_worktree(worktree_path: str) -> set[str]:
    languages = set()
    for root, _, files in os.walk(worktree_path):
        for f in files:
            if f.endswith(".py"):
                languages.add("python")
            elif f.endswith((".ts", ".tsx")):
                languages.add("typescript")
    return languages
```

Add an entry to the existing MCP servers registry/config (same pattern as any other registered MCP server, e.g. SearXNG later, GitHub tools, etc.):

```bash
grep -n "MCP_SERVERS\s*=" bff/config.py 2>/dev/null
```

```python
# bff/config.py — extend the existing MCP servers list/dict
MCP_SERVERS["serena"] = {
    "command": "python3",
    "args": ["-m", "serena", "start-mcp-server", "--workspace", "${WORKTREE_PATH}"],
    "lazy": True,
}
```

### 4.4.3 Frontend: distinct event-card type for LSP tool calls

```bash
grep -n "type ToolAction\|type Observation\|type BrowserAction" src/features/run-detail/types.ts
```

Add a new variant matching the existing discriminated-union pattern:

```typescript
// src/features/run-detail/types.ts
export type EventCardType =
  | { kind: "ToolAction"; /* ...existing fields */ }
  | { kind: "Observation"; /* ...existing fields */ }
  | { kind: "BrowserAction"; /* ...existing fields */ }
  | { kind: "LSPAction"; operation: "goto_definition" | "find_references" | "rename"; symbol: string; result: unknown };
```

```bash
grep -n "case \"ToolAction\"\|case \"Observation\"" src/features/run-detail/EventCard.tsx
```

Add a rendering branch:

```typescript
// src/features/run-detail/EventCard.tsx
case "LSPAction":
  return (
    <div className="border-l-2 border-purple-500 pl-2">
      <span className="font-mono text-sm">{event.operation}</span>: {event.symbol}
      <pre className="text-xs">{JSON.stringify(event.result, null, 2)}</pre>
    </div>
  );
```

Confirm the backend's `event_normalize.py` actually emits this `kind: "LSPAction"` shape for Serena tool-call events — grep how other MCP tool calls are currently normalized and mirror that exactly:

```bash
grep -n "def normalize_tool_call\|mcp.*tool" bff/services/event_normalize.py
```

### 4.4.4 Enforce the three-tier retrieval cascade as a documented convention

This is not new code but a documented policy for how/when the agent should reach for LSP vs. grep vs. embeddings. Add this to `AGENTS.md` (or the project's constitution doc) so the agent's own tool-selection behavior reflects it:

```bash
grep -n "retrieval\|grep\|embeddings\|LSP" AGENTS.md 2>/dev/null
```

```markdown
<!-- append to AGENTS.md -->

## Code Retrieval Tiering

Use the cheapest tool that answers the question:
1. grep/ripgrep — broad textual search, literal matches. Default first choice.
2. Tree-sitter + embeddings (RepoGraph semantic search) — fuzzy/semantic recall across unfamiliar code.
3. LSP (Serena) — symbol-precise operations only: go-to-definition, find-all-references, safe renames, type-aware diagnostics. Use only when the task genuinely requires symbolic guarantees, not for general exploration.
```

### 4.4.5 Verify

```bash
pnpm dev
```

Issue a real coding task requiring a precise rename across files (e.g., "rename function `foo` to `bar` everywhere it's used"). Confirm:
- The agent invokes the Serena MCP tool for the rename rather than attempting a manual grep-and-replace.
- The LSP tool call renders as a distinct `LSPAction` card in the run-detail timeline, not folded into generic `ToolAction`.
- The rename is correct and complete across all call sites (verify manually against the actual codebase state).

```bash
# Confirm Serena only started for languages actually present
ps aux | grep serena
```

Confirm no language server started for a language absent from the active worktree.

### 4.4.6 Log

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 4.4: LSPClient port (Serena) shipped
- Backend: Serena registered as a lazy-started MCP server, language detection scoped to active worktree
- Frontend: new LSPAction event-card type, distinct rendering in run-detail timeline
- Documentation: added three-tier retrieval cascade (grep -> embeddings -> LSP) to AGENTS.md
- Files touched (backend): openhands_tools_ext/lsp/{serena_registration.py,lazy_start.py}, bff/config.py, bff/services/event_normalize.py
- Files touched (frontend): src/features/run-detail/{types.ts,EventCard.tsx}
- Files touched (docs): AGENTS.md
- Verification: real rename task confirmed using Serena via LSPAction card, not manual grep-replace; lazy-start confirmed via process inspection
- Both halves shipped together: yes
EOF
```

---

## 4.5 Decision point: DozerDB consolidation (resolve before Stage 5)

This is a real architectural decision, not a mechanical task — flag it explicitly and get sign-off before proceeding to Stage 5's memory-port work.

### 4.5.1 Gather the facts needed to decide

```bash
docker exec -it dozerdb cypher-shell -u neo4j -p CHANGE_ME_REAL_PASSWORD "CALL dbms.components() YIELD name, versions RETURN name, versions"
grep -rn "DozerDB\|Graphiti" ideal-ACA-v8.md forge-oh-improvement-plan-v2.md
```

Confirm whether Stage 5's Kosmos-ported `semantic_memory_path.py` requires any DozerDB-fork-specific feature (e.g., specific procedure extensions) that stock community Neo4j lacks, or whether it works against the Bolt protocol generically.

```bash
grep -n "CALL dozer\.\|dozerdb\." $(find . -path "*/kosmos/*semantic_memory*" 2>/dev/null) 2>/dev/null
```

If you have access to the Kosmos source referenced in the improvement plan, grep it directly for DozerDB-specific Cypher procedure calls (`CALL dozer.*`) versus stock Cypher.

### 4.5.2 Present the decision explicitly — do not proceed silently

State clearly in your own words to the project owner (this is a stop-and-ask point per project convention, not a task to auto-resolve):

- **Option A — single shared DozerDB instance:** RepoGraph's symbol graph and Stage 5's semantic-memory temporal graph (Graphiti-based) coexist in one DozerDB container, distinguished by node labels/namespaces (e.g., `Symbol` vs. `MemoryEvent`). Lower ops overhead, one database to run/back up.
- **Option B — two separate graph instances:** keep them isolated if Graphiti's temporal indexing or RepoGraph's PageRank computation show any sign of resource contention or query-pattern conflict under real load.

Recommendation based on facts gathered in 4.5.1: default to Option A unless 4.5.1 reveals a genuine DozerDB-fork-specific incompatibility or a concrete performance conflict — running two graph databases on one workstation adds operational surface area the single-user Colossus mandate explicitly tries to avoid.

**Do not proceed to Stage 5 until this is confirmed by the project owner.** Log the decision once made:

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 4.5: DozerDB consolidation decision
- Decision: [Option A: single shared instance / Option B: separate instances] — filled in after owner confirmation
- Rationale: [summarize findings from 4.5.1]
- Affects: Stage 5's semantic_memory_path.py port target connection config
EOF
```

---

## Stage 4 exit gate — do not proceed to Stage 5 until all pass AND 4.5 is explicitly resolved

```bash
cd ~/dev/forge-oh
pytest bff/tests/ -q
pnpm typecheck
pnpm test:unit
pnpm build
```

Manual verification checklist:
- [ ] `GET /api/repograph/health` returns `available: true` against live DozerDB.
- [ ] Real repo indexing confirmed via direct Cypher query showing non-zero nodes.
- [ ] Per-run Trace-tab RepoGraph panel has a working List/Graph toggle; graph renders pagerank-sized/colored nodes with working click-to-drill-down.
- [ ] Standalone `/repograph` route is reachable via sidebar and renders the whole-codebase graph.
- [ ] `react-force-graph-2d` vendoring logged in `PORTING_LEDGER.md`.
- [ ] Serena LSP tool confirmed invoked for a real precise-rename task, rendering as a distinct `LSPAction` card, lazy-started only for languages present in the worktree.
- [ ] AGENTS.md updated with the three-tier retrieval cascade convention.
- [ ] **DozerDB consolidation decision (4.5) explicitly confirmed by the project owner and logged** — this is a hard blocker for Stage 5, not optional.

## Final Stage 4 log entry

```bash
cat >> BUILD_LOG.md << 'EOF'

## $(date '+%Y-%m-%d %H:%M %Z') — Stage 4 COMPLETE
- All Stage 4 exit-gate checks passed
- RepoGraph enabled end-to-end on DozerDB with working graph visualization (per-run + standalone)
- LSPClient port (Serena) live, three-tier retrieval cascade documented in AGENTS.md
- DozerDB consolidation decision resolved: [fill in from 4.5]
- Next action: begin Stage 5.1 (port Kosmos ports/memory.py, ports/vector.py, ports/embeddings.py verbatim)
EOF

cat > SESSION_HANDOFF.md << 'EOF'
# Session Handoff

**Current stage:** Stage 4 complete, ready to begin Stage 5 (Four-Tier Memory Port from Kosmos, on DozerDB).

**Completed this session:**
- Stage 4.1 through 4.5, all verified per exit-gate checklist above.

**Remaining before Stage 4 Definition of Done:** none — Stage 4 is fully complete.

**Open questions awaiting review:** none outstanding — DozerDB consolidation decision (4.5) was resolved as [Option A/B] before this handoff was written.

**Exact next action:** Begin Stage 5.1 — port Kosmos's ports/memory.py, ports/vector.py, ports/embeddings.py verbatim into openhands_tools_ext/, using the DozerDB connection config confirmed in Stage 4.5.
EOF
```
