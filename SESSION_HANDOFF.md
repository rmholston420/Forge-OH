# SESSION_HANDOFF

**Last updated:** 2026-08-03 18:38 EDT
**Current stage:** F.19 (Coder/Planner router rewire), sub-slice **1b in retry**.

## Recently completed this session

- F.19-pre closeout: ADR-009, scores, logs (`4cb2a09`).
- ADR-009 amendment (§3a topology, §3b budgets, BFF port): `e9cb0c6`.
- **F.19.1a**: dual-port vLLM launchers + supervisor (`0297221`) — later found to be venv-based, incompatible with Colossus's vLLM 0.10.2. Rewritten in-place.
- **F.19.2a**: role-based router API in `bff/services/model_router.py` — `route_by_role`, `RoleRoute` dataclass, supervisor invoker; 20/20 tests pass (`58458a7`).
- **F.19.1b fix (this commit, PENDING PUSH)**: rewrote launchers + supervisor for Docker; corrected ADR-009 §5 quantization bullet; added F.19.5 to Follow-ups.

## Current sub-slice: F.19.1b live smoke retry

**Blocker resolved:**
- Root cause 1: launchers targeted native venv `~/venv/vllm-new` (vLLM 0.10.2) which does not support `qwen3_5_moe`. Fix: switch to `vllm/vllm-openai:latest` Docker (matches bench).
- Root cause 2: F.18 `vllm_stop.sh` didn't fully release :8502. Fix: `_stop_role` does `docker rm -f` + `fuser -k` + `ss -ltn` poll.

**Next action for user (paste into Colossus):**
```bash
cd ~/dev/forge-oh && git pull
./ops/vllm_supervisor.sh up coder
curl -s http://127.0.0.1:8501/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh up planner
curl -s http://127.0.0.1:8502/v1/models | python3 -m json.tool
./ops/vllm_supervisor.sh down
./ops/vllm_supervisor.sh status
```

Expected: coder container reports `qwen3.6-35b-nvfp4` in `/v1/models` data; `up planner` stops coder container, brings up planner container reporting `qwen3-thinking-2507-awq`; `down` removes both; `status` exits 2 with `live_role: none`.

If either role fails, the launch log at `~/.forge-oh/vllm-{coder,planner}.log` shows the `docker run` handshake; the container's runtime log is `docker logs -f forge-vllm-{coder,planner}`.

## F.19 remaining slate

- **F.19.1b** (in progress) — Docker smoke on Colossus.
- **F.19.2b** — migrate `bff/routers/runs.py:185` from `route_request(task_complexity, ctx)` to `route_by_role(role, ctx)`; fix the `base_url=_OLLAMA_BASE` bug at line 236; plumb `route.max_tokens` into LiteLLM.
- **F.19.2c** — extend `/api/settings/model-routing` with per-role probes.
- **F.19.3** — expand tests (role-based tests already landed in F.19.2a).
- **F.19.4** — live P1/P2/P3 smoke through rewired router.
- **F.19.5 (deferred)** — native venv upgrade to vLLM ≥ 0.26.0 so we can drop Docker for the role servers.

## Open questions / ambiguities

None — F.19.1b Docker fix is a mechanical port of the bench template, no new decisions required.
