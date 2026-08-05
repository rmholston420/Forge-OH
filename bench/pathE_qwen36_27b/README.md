# Path E — Qwen3.6-27B rebench vs ADR-009 baseline

**Purpose:** validate that `Qwen3.6-27B` beats the ADR-009 baseline (`qwen3.6-35b-a3b-nvfp4` coder, `qwen3-thinking-2507-awq` planner) on Forge-OH's own coder + planner prompts before flipping the canonical model in `MODEL_ROUTER_CATALOG`.

**Methodology:** [`forge-oh-bench-methodology`](../../.claude/skills/space/forge-oh-bench-methodology.md) — Path D v2 shape. Quality-first, speed-second tiebreak within 3 points. Perplexity Max (Claude Sonnet 4.6) is the gold-standard baseline.

**Research report:** `/home/user/workspace/coder_llm_research.md` + `/home/user/workspace/planner_llm_research.md` (deep-research subagents, 2026-08-04).

## Cells

| Cell | Role | Runtime | Model | Purpose |
|---|---|---|---|---|
| c01 | coder | vLLM | `Lorbus/Qwen3.6-27B-int4-AutoRound` | **PROPOSED coder pick** |
| c02 | coder | vLLM | `qwen3.6-35b-a3b-nvfp4` | ADR-009 baseline |
| c03 | coder | Ollama | `qwen3-coder:32k` | Current fallback (floor) |
| c04 | planner | vLLM | `nvidia/Qwen3.6-27B-NVFP4` | **PROPOSED planner pick** |
| c05 | planner | vLLM | `qwen3-thinking-2507-awq` | ADR-009 baseline |

Ordering rule (Ollama first, then vLLM to minimize container restarts): `c03 → c01 → c02 → c04 → c05`.

## Execution (Colossus)

Run all commands from `~/dev/forge-oh` on Colossus.

### 0. Pull new models (~40 GB total download)

```bash
bash bench/pathE_qwen36_27b/pull_models.sh
```

Verify:
```bash
ls -la ~/models/ | grep qwen3.6-27b
```

### 1. c03 — Ollama coder fallback (no vLLM needed)

```bash
# Ensure Ollama is up
sudo systemctl start ollama 2>/dev/null || (ollama serve >/tmp/ollama.log 2>&1 &) ; sleep 3
ollama list | grep qwen3-coder:32k   # confirm present

python3 bench/pathE_qwen36_27b/bench_pathE.py --cells c03 --runs 3
```

### 2. c01 — Qwen3.6-27B-int4-AutoRound (coder pick)

```bash
bash bench/pathE_qwen36_27b/vllm_launch.sh c01
python3 bench/pathE_qwen36_27b/bench_pathE.py --cells c01 --runs 3
bash bench/pathE_qwen36_27b/vllm_down.sh
```

### 3. c02 — Qwen3.6-35B-A3B-NVFP4 (coder baseline)

```bash
bash bench/pathE_qwen36_27b/vllm_launch.sh c02
python3 bench/pathE_qwen36_27b/bench_pathE.py --cells c02 --runs 3
bash bench/pathE_qwen36_27b/vllm_down.sh
```

### 4. c04 — Qwen3.6-27B-NVFP4 (planner pick)

```bash
bash bench/pathE_qwen36_27b/vllm_launch.sh c04
python3 bench/pathE_qwen36_27b/bench_pathE.py --cells c04 --runs 3
bash bench/pathE_qwen36_27b/vllm_down.sh
```

### 5. c05 — Qwen3-Thinking-2507 AWQ (planner baseline)

```bash
bash bench/pathE_qwen36_27b/vllm_launch.sh c05
python3 bench/pathE_qwen36_27b/bench_pathE.py --cells c05 --runs 3
bash bench/pathE_qwen36_27b/vllm_down.sh
```

### 6. Dump results for gold-standard scoring

```bash
LATEST=$(ls -td ~/.forge-oh/bench_pathE/*_run | head -1)
echo "run: $LATEST"

python3 - <<PY | tee "$LATEST/dump_$(date +%Y%m%d_%H%M).txt"
import json, glob, os
run = "$LATEST"
for f in sorted(glob.glob(f"{run}/*.json")):
    if os.path.basename(f) == "manifest.json": continue
    d = json.load(open(f))
    print(f"=== {os.path.basename(f)} ===")
    if "error" in d:
        print(f"[ERROR] {d['error']}")
        print()
        continue
    tok_s = d.get("tokens_per_s_med", 0)
    comp = d.get("completion_tokens", 0)
    wall = d.get("latency_med_s", 0)
    print(f"tok/s={tok_s} completion_tokens={comp} wall_med={wall}s")
    print("--- content_stripped ---")
    print((d.get("content_stripped") or "")[:8000])
    print()
PY
```

### 7. Gold-standard scoring

Paste the dump into Perplexity Max (a fresh chat) with the following rubric:

```
For each cell × prompt, score 0-100 on:
- exact-answer match (relative to a Perplexity Max gold answer generated
  from the same prompt files at bench/prompts/{debug,arch,plan}.txt)
- key-fact coverage
- absence of hallucinations
- code correctness where applicable

Rank cells by average quality DESC. Ties within 3 points → higher tok/s wins.
Never rank on speed alone.
```

Record the verdict in `docs/adr/013-qwen36-27b-canonical-coder-planner.md`.

## Success criteria (for flipping the canonical)

- **c01 quality ≥ c02 quality** (within 3 points is acceptable; tiebreak on speed then goes to the winner)
- **c04 quality > c05 quality** (planner is quality-first, no speed tiebreak — this is the user's stated preference)
- **Zero c01/c04 errors** across the 3-run × 3-prompt matrix
- **c01 VRAM peak < 28 GB** measured via `nvidia-smi` during bench
- **c04 VRAM peak < 28 GB** measured via `nvidia-smi` during bench

If all criteria met: proceed to author ADR-013 and update `LLM_CODER_MODEL` + `LLM_PLANNER_MODEL` defaults + `MODEL_ROUTER_CATALOG`.

If any criterion fails: keep the ADR-009 baseline; ADR-013 documents the negative result and closes the loop.

## Bench artifacts (gitignored)

- Raw results: `~/.forge-oh/bench_pathE/<TS>_run/`
- Dump for scoring: `~/.forge-oh/bench_pathE/<TS>_run/dump_<TS>.txt`

Only the ADR verdict is committed to the repo.
