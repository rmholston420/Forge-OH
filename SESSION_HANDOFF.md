# SESSION_HANDOFF

**Last session:** 2026-08-03 22:15 EDT
**Current branch:** `slice/g1-nightly-harness` (name kept for history; module is `selfeval`)
**Branches pushed to origin this session:** `audit/frontend-backend-parity` @ `9058ff6`

## Current stage / plugin / port

**Stage:** G.1 — on-demand self-eval harness.
**Ports touched:** none. Composes with verify + trajectory + hook + model_router.
**ADR:** ADR-011 (Proposed).

## Completed this session

- Audit branch: three parity audits + ADR-010 (Proposed).
- Slice G.1: `openhands_tools_ext/selfeval/` module (4 py files + manifest.toml).
- Slice G.1: 39 module tests + 16 BFF router tests. **All 55 tests passing.**
- Slice G.1: `ops/systemd/forge-oh-selfeval.service` one-shot unit + README.
  **No `.timer`.**
- Slice G.1: `bff/routers/selfeval.py` with 6 endpoints and path-traversal guards.
- Slice G.1: Next.js `/selfeval` + `/selfeval/[date]` pages + sidebar entry.
- Slice G.1: Playwright smoke `src/tests/e2e/selfeval.spec.ts`.
- Slice G.1: ADR-011 authored (Proposed).
- Slice G.1: `docs/skills-index.md` inventorying 7 project + 2 user skills.
- BUILD_LOG appended with audit + G.1 entries.

## Remaining before G.1 Definition of Done is met

Per ADR-011 §DoD:

1. **Live end-to-end cycle on Colossus.** Requires BFF + agent-server + vLLM
   coder up on their canonical ports. Run either:
   - GUI: navigate to `/selfeval`, hit **Run now**.
   - Terminal: `systemctl --user start forge-oh-selfeval.service` after the
     one-time install (`ln -sf ~/dev/forge-oh/ops/systemd/forge-oh-selfeval.service
     ~/.config/systemd/user/ && systemctl --user daemon-reload`).
   - Bypass systemd: `cd ~/dev/forge-oh && .oh-venv/bin/python -m
     openhands_tools_ext.selfeval.cli --limit 3 --sample head`.
   Inspect the generated `docs/selfeval/2026-08-04-selfeval.json` and any
   `docs/proposals/2026-08-04-*.md`.
2. **Flip ADR-011 status Proposed → Accepted** once the live cycle runs green.

## Open questions / ambiguity

None currently. The rename from `nightly` → `selfeval` was completed cleanly;
the only lingering "nightly" reference is in ADR-011's "Alternatives Considered"
section (which explicitly names the rejected fixed-time timer) and in the
branch name `slice/g1-nightly-harness` (kept for git history continuity — will
merge to `main` under the slice tag `slice/g1`).

## Exact next action

**On Colossus:**

```bash
cd ~/dev/forge-oh
git fetch origin
git checkout slice/g1-nightly-harness
mkdir -p ~/.config/systemd/user
ln -sf ~/dev/forge-oh/ops/systemd/forge-oh-selfeval.service ~/.config/systemd/user/
systemctl --user daemon-reload
# Sanity-check unit loads
systemd-analyze --user verify forge-oh-selfeval.service
# Fire a cycle (BFF + agent-server + vLLM coder must be up)
systemctl --user start forge-oh-selfeval.service
journalctl --user -u forge-oh-selfeval.service -f
```

Then inspect `docs/selfeval/*.json` and any `docs/proposals/*.md` written.
If clean, amend ADR-011 status to **Accepted** and append the DoD-met
BUILD_LOG entry.

## Runtime state at handoff

Not verified this session (sandbox, not Colossus). Prior session state
(from BUILD_LOG 2026-08-03 20:55 EDT):
- BFF up on :8081 (no `--reload`)
- forge-vllm-coder up on :8501
- forge-vllm-planner was DOWN (auto-swap on next planner request)
- Ollama :11434 up
- Workspace UUIDs: forge-oh-repo=`18c99443b23c452899010095abd5f29b`,
  forge-oh-smoke=`6dac22aed0e44798b04ea335a405528a`
