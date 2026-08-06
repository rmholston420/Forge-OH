# ADR-020 — Qwen3-Embedding as Forge-OH's default EmbeddingsPort model

**Status:** Accepted
**Lock-in phase:** Stage 5.2 (Kosmos EmbeddingsPort adapter)
**Supersedes:** — (departs from Kosmos upstream default; no prior Forge-OH ADR)
**Related:** ADR-008 (Trajectory memory — separate embedder), ADR-019 (DozerDB consolidation — Stage 5 predecessor), `docs/reconciliation-plan-v1-stage-5.md § 5.2`, `PORTING_LEDGER.md` (Stage 5.2 Kosmos adapters port)

## Context

Stage 5.2 vendors Kosmos's `OllamaEmbeddingsAdapter` (`OllamaEmbeddingsPort` implementation) into `openhands_tools_ext/memory/adapters/embeddings/ollama/`. The Kosmos upstream default is `nomic-embed-text` (768-dim, MTEB ~62 avg, MTEB Code untracked). Before running the live-tier smoke test against real Ollama + real Qdrant, the user asked whether Qwen3-Embedding — released after Kosmos froze on `nomic-embed-text` — is a better choice for Forge-OH's semantic-memory workload.

### Facts gathered (2026-08-06 01:50–01:54 EDT)

MTEB v2 (open-weight, 2026-Q2/Q3 snapshots cross-referenced against the Qwen3-Embedding arXiv paper `2506.05176v2` and the official [Ollama library entry](https://ollama.com/library/qwen3-embedding)):

| Model | Ollama tag | Native dim | Ctx | MTEB Mult. | MTEB EN v2 | MTEB Code | Steady-state VRAM |
|---|---|---|---|---|---|---|---|
| `nomic-embed-text` (Kosmos default) | `nomic-embed-text` | 768 | 8K | ~62 | 63.6 | untracked | ~350 MB |
| `qwen3-embedding:0.6b` | `qwen3-embedding:0.6b` | 1024 | 32K | 64.33 | 70.70 | ~73 | ~1.2 GB |
| `qwen3-embedding:4b` | `qwen3-embedding:4b` | 2560 | 40K | 69.45 | 74.60 | ~79 | ~5 GB |
| `qwen3-embedding:8b` | `qwen3-embedding:8b` | 4096 | 40K | **70.58 (#1)** | **75.22 (#1)** | **80.68 (#1)** | ~8 GB (Q4) / ~15 GB (FP16) |

Sources: Qwen3-Embedding arXiv paper, [`qwen-ai.com`](https://qwen-ai.com/qwen-embeddings/), [Ollama library](https://ollama.com/library/qwen3-embedding), [`morphllm.com` benchmarked Ollama embedders](https://www.morphllm.com/ollama-embedding-models), [`codesota.com` MTEB leaderboard](https://www.codesota.com/benchmarks/mteb), and [`thegtmdirectory.com` embeddings ranking](https://thegtmdirectory.com/models/category/embeddings).

### Colossus VRAM budget (RTX 5090, 32 GB, single-user with GPU-driven display)

Concurrent-resident models under normal Forge-OH operation:

- `qwen3.6:35b-a3b` (OLLAMA_PRIMARY_MODEL) — ~23 GB at Q4_K_M
- `qwen3-coder:30b` (OLLAMA_FAST_MODEL) — evicted/reloaded on demand
- Embedder — resident whenever memory-inspector or ACE curation is running
- **Display driver + WM + browser** — user reports flakiness when VRAM fills

Headroom above the 23 GB chat model = ~9 GB. Deducting a conservative ~2 GB for display/desktop leaves ~7 GB. The 8B embedder at ~8 GB pushes into that reserve and would cause eviction thrashing (chat model rolls to disk) or display instability.

## Decision

Forge-OH's EmbeddingsPort default is **`qwen3-embedding:0.6b`** (1024-dim). The **`qwen3-embedding:4b`** (2560-dim) tag is also pulled to Colossus and registered in the adapter's dimension table for opt-in A/B comparison via `OLLAMA_EMBED_MODEL=qwen3-embedding:4b`.

The Kosmos upstream default `nomic-embed-text` is **not** used in Forge-OH; it remains in the adapter's `_MODEL_DIMENSIONS` table for compatibility with any Kosmos code paths that hard-code it, but Forge-OH's `.env.example` and the adapter's ctor fallback both point at `qwen3-embedding:0.6b`.

The **8B variant is explicitly rejected** as a default — see Rationale.

## Rationale

**Why Qwen3-Embedding over `nomic-embed-text`:**
- ~+8 points MTEB average and ~+10 points MTEB Code even at the 0.6B tier — Forge-OH indexes task/symptom strings, error traces, and diff hunks (a mixed code + prose workload), where MTEB Code is the direct relevance signal.
- 32K native context vs Nomic's 8K — no truncation of long memory events or trajectory records.
- MRL-native dimension selection preserves the option to shrink Qdrant footprint later without switching models.
- Same Ollama runtime — no new inference dependency, one-line `.env` swap.

**Why 0.6B as default, not 4B:**
- Fits comfortably in the ~7 GB VRAM headroom above the 35B chat model with display driver reserve intact — the user reports display flakiness at full VRAM saturation.
- Still beats `nomic-embed-text` on every MTEB axis by a wide margin (+8 avg, ~+10 code, +24 max context).
- 4B is available for on-demand A/B; a config flip runs the comparison without redeploy.

**Why 4B is available but not default:**
- ~+5 MTEB Code points over 0.6B is real quality, but ~+3.8 GB VRAM cost puts total resident allocation (35B chat + 4B embed + display) at the edge of the safe budget. Acceptable for benchmark runs, not for continuous background embedding.

**Why 8B is rejected as default:**
- ~8 GB VRAM steady-state at Q4_K_M exceeds the 5090 headroom above the 35B chat model. Would force Ollama to evict the chat model on every embed call, tanking end-to-end latency and destabilizing display.
- The +1-2 MTEB points over 4B does not justify eviction thrashing for Forge-OH's workload.

**Alternatives considered and rejected:**
- `BAAI/bge-code-v1` (Stage 3 trajectory embedder, sentence-transformers, 1536-dim) — code-retrieval-specialized and already in the stack, but requires a second embedder pipeline (no Ollama runtime), doubles the memory subsystem's inference surface, and creates a divergence between semantic memory and trajectory embeddings that would need reconciliation before ACE curation can compare cross-tier.
- `NV-Embed-v2` (7 GB, MTEB 72.31) — NVIDIA license restricts commercial use; comparable quality to Qwen3-Embedding-4B at higher VRAM cost.
- `EmbeddingGemma-300M` — small, cheap, Apache 2.0, but MTEB score is 5+ points below `qwen3-embedding:0.6b` at similar VRAM.

## Consequences

**Files changed:**
- `openhands_tools_ext/memory/adapters/embeddings/ollama/adapter.py` — added `qwen3-embedding:{0.6b,4b,8b}` to `_MODEL_DIMENSIONS`; default fallback changed from `nomic-embed-text` to `qwen3-embedding:0.6b`; docstring updated.
- `.env.example` — `OLLAMA_EMBED_MODEL=qwen3-embedding:0.6b` (was `nomic-embed-text`); comment block documents the 4B A/B option.
- `PORTING_LEDGER.md` — note added under the Stage 5.2 entry recording the deviation from Kosmos's `nomic-embed-text` default with reference to this ADR.
- `SESSION_HANDOFF.md` — Stage 5.2 live-smoke commands updated to pull both `qwen3-embedding:0.6b` and `qwen3-embedding:4b` in place of `nomic-embed-text`.
- `BUILD_LOG.md` — this ADR filing + Stage 5.2 amendment appended.

**Kosmos re-sync implication:** any future re-vendor of Kosmos `adapters/embeddings/ollama/adapter.py` at a newer SHA must preserve the two Forge-OH changes (dim table entries + default fallback). PORTING_LEDGER's Stage 5.2 entry already lists these as modification notes.

**Test impact:** contract tests are dimension-agnostic (they use httpx mocks or the `InMemoryQdrantBackend`); no test changes required. Live-tier smoke (`FORGE_MEMORY_LIVE=1`) will exercise the new default.

**Downstream ADRs:** Stage 5.3 (DozerDB semantic memory path), 5.4 (zero-trust write enforcement), 5.5 (ACE curation), 5.6 (memory-inspector UI) all consume this EmbeddingsPort; none pin a specific model. Qdrant collections created in Stage 5.3 must be provisioned with `dim=1024` (or `dim=2560` for the 4B A/B) — the adapter's `dimension()` method returns the correct value automatically.

## Lock-in phase

Stage 5.2 exit gate. Locked in when Stage 5.2's live-tier smoke test passes end-to-end with `qwen3-embedding:0.6b` producing a 1024-dim vector via `OllamaEmbeddingsAdapter.embed()` against Colossus's Ollama daemon.

## References

- Qwen3-Embedding paper: `arXiv:2506.05176v2` — https://arxiv.org/pdf/2506.05176v2.pdf
- Ollama library: https://ollama.com/library/qwen3-embedding
- MTEB v2 leaderboard snapshot (2026-07-03): https://thegtmdirectory.com/models/category/embeddings
- Ollama-runtime embedder benchmark (2026-06-09): https://www.morphllm.com/ollama-embedding-models
- `docs/reconciliation-plan-v1-stage-5.md § 5.2`
- `PORTING_LEDGER.md` — Stage 5.2 entry (2026-08-06 01:44 EDT)
- ADR-008 (`docs/adr/008-trajectory-memory.md`) — trajectory embedder (`BAAI/bge-code-v1`, separate path)
- ADR-019 (`docs/adr/019-dozerdb-consolidation.md`) — Stage 5 storage predecessor
