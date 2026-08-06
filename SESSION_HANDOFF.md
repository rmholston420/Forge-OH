# Forge-OH Session Handoff

**Last update**: 2026-08-06 14:36 EDT

## Current build-sequencing stage/plugin/port
Stage 7 (deviated per [ADR-028](docs/adr/028-stage-7-deviation-topology-first-capability-slices-renumbered.md)) — companion §7.1 (docker-compose topology reconciliation) code-complete, awaiting operator `docker compose up -d` verification on Colossus. Companion §7.4 (documentation + PORTING_LEDGER + `.gitignore` audit) **passes** as read-only audit. All Stage 7 DoD items met code-side.

**Next**: Stage 8 initialization — the 1-hour SDK-native investigation spike (does OpenHands SDK 1.40+ Microagents / Context Condensation / Pluggable Runtime already cover Council-Synthesis 8.1 / 8.6 / 8.2?) followed by Slice 8.0 (vLLM serving-infra bundle).

## What was completed this session
- Filed [ADR-028](docs/adr/028-stage-7-deviation-topology-first-capability-slices-renumbered.md) — Stage 7 deviation, canonical §7.2–§7.6 folded to renumbered deferred tail §7.6–§7.10, Council-Synthesis capability slices renumbered to Stage 8, 30/500 SWE-bench gate waived for the transition.
- Canonicalized workspace-draft `Forge-OH-reconciliation-plan-v1-stage-7.md` as `docs/reconciliation-plan-stage-7.md`.
- Rewrote `docs/reconciliation-plan-v1.md` §7 + §Recommended Execution Order item 7 to reflect new sequencing.
- Council-Synthesis document (7.x → 8.x renumbering) pre-applied in the Perplexity project files repo at commit `8e093bc`.
- **Completed companion §7.1** — rewrote root `docker-compose.yml` to a truthful two-service topology (`bff` + `qdrant`); removed the broken `openhands:` service (wrong upstream image) and `frontend:` service (nonexistent `Dockerfile.frontend`); added `docs/deployment-topology.md` with authoritative host-vs-container split and observed 2026-08-06 14:26 EDT baseline; added `scripts/start-host-services.sh` as idempotent orchestrator for Ollama + vLLM planner + vLLM coder wrapping existing supervisor scripts.
- **Completed companion §7.4** — all commit hashes in `PORTING_LEDGER.md` resolve against their stated upstreams (`rmholston420/kosmos` c455165, `oraios/serena` c7af2c0, `FloridSleeves/LLMDebugger` 49ac191); file-content and image sha256 digests correctly labeled; no `.env`-family secret file staged or tracked; `.gitignore` coverage complete.

## What remains before Stage 7 Definition of Done is met (per ADR-028 §6)
1. **Operator verification of §7.1 on Colossus.** Recipe below. Zero-code path on the operator side.

## Open question / ambiguity
None. Stage 7 DoD code-complete; only operator verification remains.

## Exact next action

Operator: run this exact block on Colossus and paste the last line's output:

```bash
cd ~/dev/forge-oh && git pull && \
  fuser -k 8081/tcp 2>/dev/null; sleep 2 && \
  docker compose up -d --build && \
  sleep 8 && \
  echo "===compose ps===" && docker compose ps && \
  echo "===bff socketio probe===" && curl -sf -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8081/socket.io/?EIO=4&transport=polling" && \
  echo "===qdrant probe===" && curl -sf http://127.0.0.1:6333/collections | jq '.status // .result.status'
```

Expected: compose ps shows `bff` + `qdrant` healthy; socketio probe returns `200`; qdrant probe returns `"ok"`. If green, Stage 7 DoD is fully met and Stage 8 initialization begins.

After Stage 7 DoD is met:

- Load `explore-memory` skill to review Perplexity project files repo's Council-Synthesis doc (`Forge-OH-Improvements-Research-Model-Council-Synthesis.md` at commit `8e093bc`) for the Stage 8 slice contract.
- Execute the 1-hour SDK-native investigation spike (does OpenHands SDK ≥1.40 already provide Microagents / Context Condensation / Pluggable Runtime?) before writing any Stage 8.0 code.
