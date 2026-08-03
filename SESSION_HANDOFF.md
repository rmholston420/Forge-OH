# Forge-OH — Session Handoff

Overwrite this file at the end of every session. Reflects current state only.

---

## Current stage
**F.18 COMPLETE.** vLLM is primary, Ollama is fallback. Router honors
`LLM_PRIMARY_BACKEND=vllm` in `.env`, verified end-to-end via
`/api/settings/model-routing`. Bench data archived at
`~/.forge-oh/bench/20260803_1419/` — see BUILD_LOG 2026-08-03 14:32 EDT for
the full 8×-18× vLLM speedup table.

## Ambient
- vLLM: RUNNING at :8500 (qwen3-coder-30b GGUF, 29 GB VRAM).
- Ollama: STOPPED + systemd unit `disabled` (must be started manually now).
- Agent-server: RUNNING at :8090 (pid 4168753).
- BFF: RUNNING at :8081 (with F.18c dotenv fix in place).
- Frontend: RUNNING at :3000.
- GPU free: 3.1 GB / 32 GB (all in vLLM).

## What was completed this session
1. **F.18** — vLLM 0.10.2 serving qwen3-coder-30b GGUF, all Blackwell/SM_120
   pitfalls documented in DEBUG_LOG (venv orphan, GGUF bf16 rejection,
   triton Python.h, FlashInfer SM_120 whitelist).
2. **F.18b** — Router refactored: `LLM_PRIMARY_BACKEND` env knob, corrected
   defaults, `/v1/models` readiness probe, unit tests (11/11 pass),
   vllm_start/stop/status.sh triad. Commit `025bc3f`.
3. **F.18c** — Router now loads `.env` via `python-dotenv` at import so
   `os.getenv()` sees config that pydantic-settings parses. Commit
   `1a30e4a`.
4. **Head-to-head bench** — 52/52 OK each backend. vLLM wins by 8×-18× on
   every scenario and every concurrency level. Decision recorded in
   BUILD_LOG.
5. **Wiring** — `.env` set to `LLM_PRIMARY_BACKEND=vllm` +
   `VLLM_URL=http://localhost:8500` + `VLLM_FALLBACK_MODEL=qwen3-coder-30b`.
   BFF hard-restarted. Ollama systemd disabled + process killed.
6. **Verified** — `/api/settings/model-routing` returns
   `primaryBackend: vllm`, all 3 probes select `vllm/qwen3-coder-30b`.

## What remains before Definition of Done for the plan
Return to Forge-OH-Action-Plan-v4 **Step 1**: real OpenHands agent-server
exercise. Agent-server is up on :8090; need to smoke-test a real
conversation through `POST /api/conversations` and confirm the LiteLLM
`openai/qwen3-coder-30b` bridge routes to vLLM at :8500 end-to-end.

## Open questions / ambiguity
- Bench scripts `bench_ollama_vs_vllm.sh` and `bench_runner.py` are still
  uncommitted (`~/dev/forge-oh/scripts/`). `.gitignore` excludes `scripts/`
  — commit with `git add -f` once we're confident the scripts won't need
  more changes.
- Ollama fallback path in the router works, but Ollama cannot share VRAM
  with vLLM. Real failover means stopping vLLM first, starting Ollama, and
  we don't have automation for that yet. Acceptable for now (vLLM proven
  stable), but flag for a future ADR: "how do we handle vLLM crash
  recovery when only one backend fits in VRAM?"

## Exact next action
Fire a real conversation through the agent-server → BFF → vLLM path:

```bash
cd ~/dev/forge-oh

# Confirm all four services healthy
~/dev/forge-oh/scripts/vllm_status.sh
curl -sf http://127.0.0.1:8090/health && echo " agent-server OK"
curl -sf http://127.0.0.1:8081/api/settings/model-routing >/dev/null && echo "BFF OK"

# Then run the smoke test (need to check what BFF endpoint kicks off a
# conversation — likely POST /api/runs or /api/conversations).
grep -rn 'route_request\|create_conversation\|POST.*conversation' bff/routers/ | head -10
```

Once we identify the entrypoint, submit a "hello, run `ls`" task and
confirm the agent picks up a vLLM-backed response.

## Key files/refs
- Bench: `~/.forge-oh/bench/20260803_1419/{ollama,vllm}.csv`
- vLLM log: `~/.forge-oh/vllm.log`
- BFF log: `~/dev/forge-oh/.forge-logs/bff.log`
- Agent-server log: `~/dev/forge-oh/.forge-logs/agent-server.log`
- Commits this session: `463ac02`, `025bc3f`, `1a30e4a` on main.
