# Forge-OH Session Handoff

**Last update**: 2026-08-06 14:48 EDT

## Current build-sequencing stage/plugin/port
**Stage 7 DoD MET.** ADR-028 §6 all four items cleared:
- §6.1 companion §7.1 exit checklist — passed on Colossus at 2026-08-06 14:47 EDT (`docker compose ps` green, socketio probe `200`, qdrant probe `"ok"`).
- §6.2 companion §7.4 exit checklist — passed (documentation + PORTING_LEDGER + `.gitignore` audit).
- §6.3 BUILD_LOG entries appended.
- §6.4 this file overwritten as the session-end step.

**Next**: **Stage 8 initialization.** Begin with 1-hour SDK-native investigation spike, then Slice 8.0 (vLLM serving-infra bundle).

## What was completed this session
- Filed [ADR-028](docs/adr/028-stage-7-deviation-topology-first-capability-slices-renumbered.md) — Stage 7 deviation, canonical §7.2–§7.6 folded to renumbered deferred tail §7.6–§7.10, Council-Synthesis capability slices renumbered to Stage 8, 30/500 SWE-bench Verified gate waived for the transition.
- Canonicalized workspace-draft `Forge-OH-reconciliation-plan-v1-stage-7.md` as `docs/reconciliation-plan-stage-7.md`.
- Rewrote `docs/reconciliation-plan-v1.md` §7 + Recommended Execution Order item 7.
- **Stage 7.1 shipped** (`6200028` + `365ec15` + `fe833b9`): rewrote root `docker-compose.yml` to truthful two-service topology (bff + qdrant); removed broken `openhands:` / `frontend:` services; added `docs/deployment-topology.md`, `scripts/start-host-services.sh`, `.dockerignore`; fixed `bff/Dockerfile` build context (repo root, COPY bff + openhands_tools_ext).
- **Stage 7.4 shipped** — read-only audit confirmed every PORTING_LEDGER commit hash resolves; `.env`-family clean; `.gitignore` complete.
- **Stage 7 DoD verified on Colossus**: `forge-oh-bff-1` + `forge-oh-qdrant-1` both `Up`; BFF exposes `/socket.io/` (200); Qdrant serves `/collections` (ok).
- Filed two non-blocking cosmetic issues to `KNOWN_ISSUES.md` (Dockerfile HEALTHCHECK probes `/health` → 404; trajectory drain fails on missing `/home/bff`). Neither impacts DoD.

## What remains before current DoD is met
Nothing. Stage 7 DoD is met.

## Open question / ambiguity awaiting user answer
None.

## Exact next action

1. Load `explore-memory` skill and read the Perplexity project files repo's `Forge-OH-Improvements-Research-Model-Council-Synthesis.md` at commit `8e093bc` for the Stage 8 slice contract (which capability slices, in what order, with what stop conditions).

2. Execute the **1-hour SDK-native investigation spike** before writing any Stage 8.0 code. Concrete question:

   > Does OpenHands SDK 1.40+ (currently pinned in `bff/requirements.txt` and `.oh-venv`) already provide **Microagents** (Council-Synthesis 8.1), **Context Condensation** (Council-Synthesis 8.6), and **Pluggable Runtime** (Council-Synthesis 8.2)?

   Investigation deliverable: an ADR (`ADR-029`) that either (a) accepts SDK-native adoption and reduces Stage 8 scope to the non-covered slices, or (b) documents why hand-build is required for each and preserves the full Stage 8 slice list.

3. Only after ADR-029 is filed, start **Slice 8.0** (vLLM serving-infra bundle: Automatic Prefix Caching + Speculative Decoding + fp8 KV-cache + Chunked Prefill). Note: Stage 8.0.5 (measurement hardening) re-baselines with ≥100-task SWE-bench Verified smoke + McNemar telemetry as its first act — the 30/500 gate waiver from ADR-028 §5 is a one-time bridge, not a permanent lower bar.

## Known non-blocking issues carried into Stage 8
- Coder port 8000 (spec says 8501) — see `docs/deployment-topology.md` deviation table. Fold into a Stage 8 slice that touches the vLLM coder anyway.
- Coder model deepseek-r1-distill-qwen-32b-awq (ADR-013 says Qwen3-coder-30b-a3b) — same treatment.
- Two Qdrant instances co-resident (forge-oh-qdrant-1 on 6333, kosmos-qdrant on 6339) — deliberate per ADR-028 §Q1; documented in deployment-topology.md.
- BFF Dockerfile HEALTHCHECK 404 + trajectory drain `/home/bff` errno 13 — cosmetic, KNOWN_ISSUES entries filed 2026-08-06 14:47 EDT.
