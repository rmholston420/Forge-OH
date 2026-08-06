# Path F — F.3 SWE-bench Verified (Path A: oracle-retrieval, raw c01)

**Status:** Shakeout stage. Dry-run gates the full 500-task run.
**Owner:** ADR-013 amendment #2 (coder validation on real-world benchmark).
**Model under test:** `c01_coder_vllm_qwen36_27b_int4` (ratified coder from F.1b).
**Bench mode:** oracle-retrieval (ground-truth files provided in context).
**Bench methodology:** carries forward Path E/F conventions — prompts loaded from disk (task JSON here, not a `.txt`), one JSON per task, `<think>` stripped before dump, wall-time + tokens captured. See `forge-oh-bench-methodology` project skill.

## Why oracle-retrieval and not BM25

Decided 2026-08-05 06:27 EDT (user confirmed).
- Isolates code-editing skill from retrieval variance → ADR-013 amendment #2 is defensible.
- BUILD_LOG 2026-08-05 05:14 EDT specifies "oracle mode".
- Path B (Stage-1H sandbox) will inherit the oracle-retrieval shape naturally when the Forge-OH agent's file-read tools pass ground-truth files. Apples-to-apples with Path A.
- Faster wall time (~15% of full-issue mode).

## Not this slice

- Production BFF sandbox (`bff/services/swe_bench_sandbox.py`) — that's Stage-1H Track 2 (§1H.2).
- UI integration — Stage-1H §1H.3.
- Path B rerun through full Forge-OH — Stage-1H §1H.5.
- LiveCodeBench-v6 — cancelled 2026-08-05 05:14 EDT (post-cutoff bias + domain mismatch).

## Contents

| File | Purpose |
|---|---|
| `bench_pathF_swebench.py` | harness runner (single-task or full 500) |
| `load_verified.py` | loader for `princeton-nlp/SWE-bench_Verified` (HF datasets) |
| `oracle_prompt.py` | oracle-retrieval prompt builder (ground-truth files in context) |
| `apply_and_test.py` | patch application + `docker exec` FAIL_TO_PASS / PASS_TO_PASS runner |
| `sweb_prompts/` | (optional) per-task frozen prompts for reproducibility |
| `README.md` | this file |

## Prerequisites (Colossus, once)

```bash
cd ~/dev/forge-oh
source .oh-venv/bin/activate

# Verify HF datasets is present:
python -c "import datasets; print(datasets.__version__)"

# If missing:
pip install datasets

# Verify Docker is available and rootless is not blocking:
docker version | head -6

# Verify vLLM c01 is up (or launch it):
bash bench/pathE_qwen36_27b/vllm_launch.sh c01
curl -s http://localhost:8000/v1/models | jq '.data[].id'
# Expect: "c01_coder_vllm_qwen36_27b_int4"
```

## F.3.0 — Dry-run (one known-tractable task)

**Goal:** get end-to-end pass on `django__django-10914` (canonical easy Verified task) + accurate wall-time estimate.

```bash
cd ~/dev/forge-oh
source .oh-venv/bin/activate

# Pull the sandbox image once (cached forever):
docker pull swebench/sweb.eval.x86_64.django__django-10914:latest

# Run the dry-run:
python -m bench.pathF_swebench.bench_pathF_swebench \
    --tasks django__django-10914 \
    --model c01 \
    --keep-sandbox   # keep container for post-mortem on failure

ls ~/.forge-oh/bench_pathF_swebench/*_run/
```

Success criteria:
- Task JSON exists and `result.resolved == true`
- Wall time recorded (used to estimate full 500-task run)
- `<think>` blocks stripped from `content_stripped`
- No harness-level tracebacks

## F.3.1 — Full 500 Verified

Only after F.3.0 passes. This is the ADR-013-amendment-#2 evidence.

```bash
python -m bench.pathF_swebench.bench_pathF_swebench \
    --tasks all \
    --model c01 \
    --concurrency 1
```

Wall time estimate populated from the dry-run × 500. Concurrency stays at 1 because the sandbox images are already CPU-heavy and vLLM saturates the GPU.

## Output layout

```
~/.forge-oh/bench_pathF_swebench/<TS>_run/
├── manifest.json               # cell, mode, dataset version, git SHA, start/end
├── django__django-10914.json   # one file per task
├── ...
└── summary.json                # pass@1, wall totals, resolved/error/timeout counts
```

Each task JSON:

```json
{
  "instance_id": "django__django-10914",
  "model_id": "c01_coder_vllm_qwen36_27b_int4",
  "mode": "oracle-retrieval",
  "wall_seconds": 42.7,
  "prompt_tokens": 8123,
  "completion_tokens": 512,
  "tok_per_s": 12.0,
  "content_raw_chars": 3210,
  "content_stripped_chars": 3120,
  "patch": "...",
  "fail_to_pass": ["tests.test_x::test_y"],
  "pass_to_pass": ["tests.test_z::test_w"],
  "resolved": true,
  "test_output_tail": "..."
}
```

## Path B — through the Forge-OH stack

`bench_pathB.py` runs the same 30-task calibrated smoke set through the full Forge-OH BFF → agent-server → c01 vLLM path. Purpose: attribute the score / token / wall / tool-call delta caused by Stage 3-6 middleware (approval gates, RepoGraph/Serena LSP, four-tier memory, SearXNG, idempotency ledger, skills, code_execute + progressive disclosure).

Per task: creates a fresh agent-server workspace via `POST /api/workspaces`, creates a run via `POST /api/runs` pinned to `role=coder` + `backendId=vllm-coder`, polls `GET /api/runs/{id}` to terminal (or 3600s wall cap / 30 tool-call cap), reconstructs the patch from `GET /api/runs/{id}/files/*` diffs, runs the same `apply_and_test` docker path.

```bash
cd ~/dev/forge-oh
source .oh-venv/bin/activate

# Prerequisites: BFF up on :8081, agent-server up on :8090, vLLM c01 on :8000.
# forge-status.sh should show all three green.

# Dry-run (one task, no docker):
python -m bench.pathF_swebench.bench_pathB \
    --tasks django__django-11099 --dry-plan-only

# Full 30-task smoke through the Forge-OH stack:
nohup python -m bench.pathF_swebench.bench_pathB --smoke \
    > ~/.forge-oh/pathB_smoke_$(date +%Y%m%d_%H%M).log 2>&1 &
```

Outputs land under `~/.forge-oh/bench_pathB_swebench/<TS>_run/` mirroring the Path A layout, with these extra per-task fields:

- `run_id`, `workspace_id`, `workspace_path`
- `poll_count`, `terminal_status`, `terminal_reason` (`terminal` / `tool_cap` / `wall_cap`)
- `tool_call_count`
- `metrics` — full per-run metrics blob from `GET /api/runs/{id}/metrics`
- `patch_diagnostics` — which files were touched by the agent, per-file pull status codes

Env knobs:

- `PATHB_BFF_URL` (default `http://127.0.0.1:8081`)
- `PATHB_WALL_CAP_S` (default 3600)
- `PATHB_TOOL_CALL_CAP` (default 30)
- `PATHB_POLL_INTERVAL_S` (default 3.0)

## Path A vs Path B — token & cost comparison

`compare_tokens.py` reads two run directories and emits a markdown table + optional JSON of per-task deltas and aggregate stats.

```bash
python -m bench.pathF_swebench.compare_tokens \
    --path-a ~/.forge-oh/bench_pathF_swebench/<pathA_run> \
    --path-b ~/.forge-oh/bench_pathB_swebench/<pathB_run> \
    --out ~/.forge-oh/bench_compare/compare_$(date +%Y%m%d_%H%M).md \
    --json ~/.forge-oh/bench_compare/compare_$(date +%Y%m%d_%H%M).json
```

Comparison intentionally treats:

- Path A wall = single vLLM completion time
- Path B wall = full agent trajectory (all tool calls + all LLM calls)
- Path A tokens = single completion prompt+completion
- Path B tokens = sum across every LLM call in the trajectory

The B/A ratio is the raw cost multiplier of the Forge-OH stack for equal work.

## Scope reminder

F.3 Path A = raw c01 vs SWE-bench Verified in oracle-retrieval mode. Path B = same task set, same c01 backend, run through the Forge-OH stack for stack-cost attribution. NOT the production sandbox. NOT the UI. Those come later (Stage-1H Track 2/3).
