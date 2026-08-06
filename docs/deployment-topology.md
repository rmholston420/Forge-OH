# Forge-OH Deployment Topology (Colossus, single-host, single-user)

> Target: `Collosus` (RTX 5090, 32 GB VRAM, 128 GB RAM, Blackwell SM_120).
> Ratified by [ADR-028](./adr/028-stage-7-deviation-topology-first-capability-slices-renumbered.md) §2 Stage 7.1.
> Observed baseline dump: 2026-08-06 14:26 EDT.

## The split at a glance

Forge-OH is **not** fully containerized on Colossus. The system is a
mix of compose-managed containers, standalone compose stacks, Kosmos-owned
shared services, and host processes. This is deliberate — inference
engines and Next.js hot-reload work poorly through Docker on this
workstation, and consolidating everything into one compose file would hide
that reality.

The authoritative split follows.

## Compose-owned (root `docker-compose.yml`)

| Service | Port | Managed by | Notes |
|---|---|---|---|
| `bff` | `8081` | root `docker-compose.yml` | uvicorn `bff.main:app_with_sio`. Consumes host services via `host.docker.internal` (Linux gateway). |
| `qdrant` | `6333` (REST) / `6334` (gRPC) | root `docker-compose.yml` | VectorPort backend (Stage 5.2). Not shared with `kosmos-qdrant`. |

Bring up: `cd ~/dev/forge-oh && docker compose up -d`.

## Standalone compose stack (independent lifecycle)

| Service | Port | Managed by | Notes |
|---|---|---|---|
| `forge-oh-searxng` | `127.0.0.1:18888` | `ops/compose/searxng.yml` | SearchPort backend (Stage 6.1). Deliberately loopback-bound. Standalone so it can be bounced without touching BFF/Qdrant. See `ops/compose/README.md`. |

Bring up: `cd ~/dev/forge-oh && docker compose -f ops/compose/searxng.yml up -d`.

## Kosmos-owned shared services (not managed by Forge-OH)

| Service | Port | Image | Notes |
|---|---|---|---|
| `kosmos-dozerdb` | `7474` (HTTP) / `7687` (Bolt) | `graphstack/dozerdb:5.26.27` | Kosmos-canonical DozerDB (ADR-019 consolidation). Forge-OH connects using `.env.neo4j` at repo root. Started from the Kosmos monorepo compose. |

Forge-OH does **not** start or stop this container. If it is not up, the
MemoryPort adapter fails at BFF import time; bring up the Kosmos compose
first.

## Host-side containers (managed outside compose)

| Service | Port | Image | Managed by | Notes |
|---|---|---|---|---|
| `forge-vllm-planner` | `8511 → 8000` | `vllm/vllm-openai:latest` | `scripts/vllm_start.sh` / `scripts/vllm_stop.sh` | Planner role (ADR-012 dual-mode routing). Cold-start ~3 min — do NOT bounce as part of routine restarts. Bind-mounts `/home/rmholston/models` (read-only). |

## Host processes (not containerized)

| Service | Port | Managed by | Notes |
|---|---|---|---|
| Ollama | `11434` | system service | `ollama serve`. Local ad-hoc model runtime. |
| vLLM coder | `8000` | `scripts/vllm-coder-bringup.sh` family | Coder role. At observed baseline (2026-08-06 14:26 EDT) running `deepseek-r1-distill-qwen-32b-awq --served-model-name deepseek-r1-distill-32b-awq --port 8000` — see "Deviations from spec" below. |
| OpenHands agent-server | `8090` | `scripts/forge-up.sh` (via `.oh-venv/bin/python -m openhands.agent_server`) | SDK we consume. Started with `--config .openhands.toml`. |
| Next.js dev | `3000` | `scripts/forge-up.sh` (via `pnpm dev`) | Everyday dev. HMR websocket. |
| Next.js prod | `3100` | `npx next start -H 127.0.0.1 -p 3100` (from repo root) | Playwright visual checks only. |

## Deviations from spec at observed baseline

The observed 2026-08-06 14:26 EDT dump shows deviations from what
`forge-oh-colossus-ops` skill and ADR-013 encode as canonical. These are
**recorded but not fixed** by Stage 7.1 — corrections belong to later
stages:

1. **Coder role on port 8000, not 8501.** Skill "Verified Canonical Ports"
   table has vLLM coder at 8501; the running process is on 8000.
2. **Coder model is `deepseek-r1-distill-qwen-32b-awq`, not the ADR-013
   canonical Qwen3-coder-30b-a3b (F.1b)**. `scripts/vllm-coder-bringup.sh`
   comments describe reconciling the BFF with the `vllm-bench` container
   on 8000 serving `qwen3.6-27b-int4-autoround` — neither of which matches
   the current process argv. History: the coder role appears to have been
   swapped between models multiple times without updating the skill or
   the canonical ADR.
3. **Two Qdrant instances co-resident** — `forge-oh-qdrant-1` on 6333/6334
   (Forge-OH-owned, ADR-028 §Q1 kept as-is) and `kosmos-qdrant` on
   6339/6340 (Kosmos-owned). No consolidation is in scope for Stage 7.1.

Recording these deviations here is the whole point of §7.1 —
`docker-compose.yml` was previously lying about the real topology (it
claimed to own an `openhands` service and a `frontend` service that don't
exist that way), and the fix is not to hide the mismatch but to state it
plainly so later cleanup work has a target.

## Start order (cold boot)

1. Kosmos compose (external): `kosmos-dozerdb` (must be up before BFF can
   import MemoryPort). This is a prerequisite Forge-OH cannot start on
   its own.
2. Root Forge-OH compose: `docker compose up -d` — brings up `bff` + `qdrant`.
3. Standalone SearXNG: `docker compose -f ops/compose/searxng.yml up -d`.
4. Host-side inference: `bash scripts/start-host-services.sh` — best-effort
   idempotent orchestrator for Ollama, vLLM planner container, and vLLM
   coder process. Does NOT start agent-server or Next.js.
5. Host-side dev stack: `bash scripts/forge-up.sh` — brings up agent-server
   (host, `.oh-venv`), BFF (host uvicorn, if not container-BFF path), and
   `pnpm dev`.

`forge-up.sh` remains the operator-facing single-command dev bring-up; it
starts agent-server + BFF (uvicorn on host) + `pnpm dev`. The
container-BFF path via `docker compose up -d bff` is a separate,
production-style alternative — do not use both in the same session or
port 8081 collides.

## Health probes

- `curl -sf http://127.0.0.1:8081/socket.io/?EIO=4\&transport=polling | head -c 40` — BFF Socket.IO reachable (should be 200).
- `curl -sf http://127.0.0.1:6333/collections | jq '.status'` — Qdrant reachable.
- `curl -sf 'http://127.0.0.1:18888/search?q=probe&format=json' | jq '.query'` — SearXNG reachable.
- `curl -sf http://127.0.0.1:7474/ | head -c 40` — DozerDB HTTP reachable.
- `curl -sf http://127.0.0.1:11434/api/tags | jq '.models | length'` — Ollama reachable.
- `curl -sf http://127.0.0.1:8511/v1/models | jq '.data[0].id'` — vLLM planner reachable.
- `curl -sf http://127.0.0.1:8000/v1/models | jq '.data[0].id'` — vLLM coder reachable.
- `curl -sf http://127.0.0.1:8090/api/health | head -c 40` — agent-server reachable.
- `curl -sf http://127.0.0.1:3000/ | head -c 40` — Next.js dev reachable.

Run `bash scripts/forge-doctor.sh` for the packaged read-only diagnostic —
it wraps most of the above.
