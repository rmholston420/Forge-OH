# Forge-OH Skills Index

Custom Perplexity Computer skills that assist work on this repo. Skills are
Markdown instruction bundles that models load on demand to specialize their
behavior for a specific domain, project, or workflow.

Two scopes are relevant to Forge-OH:

- **space** — attached to the Forge-OH project (formerly called Space). Loaded
  automatically or on demand when working on Forge-OH sessions.
- **user** — attached to rmholston personally. Loaded on demand across any
  session.

## space-scope skills (Forge-OH project)

| Name | Purpose | Load when |
| ---- | ------- | --------- |
| `forge-oh-slice-driver` | Non-negotiable protocol for every build slice: SESSION_HANDOFF entry, scope restatement, BUILD_LOG append, PORTING_LEDGER update, SESSION_HANDOFF rewrite, commit + push. | Every session that touches BUILD_LOG.md, DEBUG_LOG.md, SESSION_HANDOFF.md, or PORTING_LEDGER.md. |
| `forge-oh-colossus-ops` | Colossus paths, ports, forge-up/down/restart/status/doctor scripts, and runtime triage playbook (Next.js orphan reap, agentPresetId 422, `transport error:` diagnosis). | Anything touching Colossus paths, port numbers, service management, restart scripts, or a runtime-symptom the triage playbook covers. |
| `forge-oh-debug-driver` | DEBUG_LOG.md-first bug investigation: search prior symptoms before re-diagnosing. | Before investigating any new error or unexpected behavior. |
| `forge-oh-llm-serving` | Local vLLM stack: coder vs planner containers, model routing, GPU budget on the RTX 5090. | Anything touching the coder or planner service, model choice, or the model-router adapter. |
| `forge-oh-porting` | Vendor-first workflow: verifying licenses, recording ports in PORTING_LEDGER.md, tracking modifications. | Before vendoring OSS code; when updating PORTING_LEDGER.md. |
| `forge-oh-playwright-visual` | Playwright specs, screenshots, and visual regression conventions. | When writing or updating Playwright e2e tests, or capturing GUI screenshots. |
| `forge-oh-bench-methodology` | Benchmarking methodology: warm-up, per-task caps, timing conventions, comparability across runs. | When designing benchmarks, comparing model latencies, or interpreting bench numbers. |

## user-scope skills (rmholston)

| Name | Purpose | Load when |
| ---- | ------- | --------- |
| `kosmos-adr-authoring` | ADR template, authoring workflow, and stop conditions for the Kosmos codebase. | When authoring or amending an ADR in Kosmos. |
| `kosmos-port-workflow` | End-to-end port workflow for bringing OSS components into Kosmos: license check, vendor placement, PORTING_LEDGER entry. | When vendoring a component into Kosmos. |

## Adding a skill

New Forge-OH skills should be created under the `space` scope so every
Forge-OH session picks them up automatically. Skill files are Markdown with a
frontmatter header — see `~/.perplexity/skills/` or the Perplexity Skills GUI.
When a new skill lands, add a row above and reference it from README.md.

## Related surfaces

- `docs/adr/` — architecture decisions, indexed by ADR-000 (if extant) or by
  Slice Ledger. See ADR-011 for the self-eval harness.
- `SESSION_HANDOFF.md` — reflects current in-flight session state (single
  file, overwritten each session).
- `BUILD_LOG.md`, `DEBUG_LOG.md` — append-only logs of every slice / diagnosis.
