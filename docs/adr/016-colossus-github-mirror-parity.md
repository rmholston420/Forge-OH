# ADR-016 — Colossus and GitHub must be exact mirrors

**Status:** Ratified
**Lock-in phase:** Cross-cutting (applies to every subsequent commit)
**Supersedes:** —
**Related:** ADR-015 (Stage-1H), all prior ADRs (this makes their tracking explicit)

## Context

Forge-OH is developed on Colossus (`~/dev/forge-oh/`) and mirrored to `github.com/rmholston420/Forge-OH`. A parity audit on 2026-08-05 revealed silent drift:

- **35 files** in `docs/proposals/` on Colossus, not on GitHub, not in `.gitignore`.
- **1 file** at `docs/selfeval/2026-08-04-selfeval.json` on Colossus, sibling directory tracked on GitHub, itself untracked.
- **9 runtime artifacts** in `.forge-logs/`, `.forge-oh/`, `workspaces/forge-oh-smoke/` — regenerable state but not explicitly gitignored.
- **Stale `.gitignore` rules:** `tests/` (directory doesn't exist on Colossus) and `scripts/` (force-tracked despite being listed as ignored). Both are dead declarations that create confusion about what's actually mirrored.

Silent drift is a policy failure. Every file on Colossus falls into exactly one of two categories, and the current state must make that explicit.

## Decision

**Colossus `~/dev/forge-oh/` and GitHub `rmholston420/Forge-OH` are exact mirrors modulo an explicit `.gitignore`.** Every path present on Colossus is either:

1. **Tracked in git**, or
2. **Explicitly matched by a `.gitignore` pattern with a comment justifying why.**

No untracked-but-not-ignored files. No implicit divergence.

**Every commit must push same turn.** No "commit locally, push later." A commit that isn't pushed is drift-in-waiting.

**Perplexity Computer commits directly to GitHub via `bash` with `api_credentials=["github"]`; the user pulls.** No paste-block-for-commit workflows. This is already the standing rule in `forge-oh-slice-driver` skill ("You do it and push it — never ask them to do what you can do for them"). ADR-016 makes it a hard invariant.

**Explicit sensitive-exclusion list** (patterns that MUST stay ignored, with rationale, codified in `.gitignore`):

- Local env with API keys: `.env`, `.env.local`, `.env.*.local`, `.env.neo4j` — contains OpenAI/Anthropic/HF tokens, DB passwords.
- Auth artifacts: `.auth/`, `*.pem` — session tokens, private keys.
- Runtime databases: `bff/data/`, `data/` — user conversations, preset state, could contain accidentally-typed secrets.
- Local venvs: `.oh-venv/`, `.venv/`, `venv/`, `env/` — regenerable from `requirements.txt`, huge, machine-specific.
- Build/dependency output: `node_modules/`, `.next/`, `out/`, `build/`, `dist/`, `__pycache__/`, `*.egg-info/`, `*.tsbuildinfo`, `next-env.d.ts` — regenerable.
- Runtime logs: `.forge-logs/` — contain prompt/response text (potentially sensitive user input).
- Bench outputs: `~/.forge-oh/bench_*/` — per `forge-oh-bench-methodology` skill: bench artifacts stay local, only ADR verdicts commit.
- Runtime scratch: `.forge-oh/` (trajectory sidecar + verify state), `workspace/`, `workspaces/`, `worktrees/`, `test-results/`, `playwright-report/`, `blob-report/`, `screenshots/`, `playwright-artifacts/`, `playwright-next-debug.log` — runtime state, regeneratable.
- Backups + local machine noise: `.ai-backups/`, `*.bak`, `.DS_Store`, `.vercel` — machine-local.

**Everything else** — including `docs/`, `bff/`, `src/`, `scripts/`, `tests/`, all `.md` logs, all ADRs, all specs — belongs on GitHub.

## Rationale

**Why exact mirror:**
- The user explicitly stated (2026-08-05): "we need to make sure that the files on github and collosus are always the same, unless there is something truly sensitive that should remain on collosus and not on github."
- Drift compounds silently. 35 files drifted in one day. Without a rule + enforcement, it would continue.
- The GitHub repo is the durable record. Colossus is the working machine. If they diverge, the working machine's state is not recoverable if the disk fails.

**Why direct-to-GitHub commits (not paste blocks):**
- Perplexity Computer has GitHub CLI access via `api_credentials=["github"]`. Paste blocks are strictly worse: fragile to shell quoting, can kill the operator's bash session on `set -e` failures, force manual re-execution on retry.
- The user pulls on Colossus with a single `git pull` — atomic, reversible via `git reset`, no partial-state risk.
- Aligns with `forge-oh-slice-driver`: "You do it and push it — never ask them to do what you can do for them."

**Why explicit ignore rationale:**
- Discovering `scripts/` was force-tracked despite being listed as ignored took a GitHub API probe. The `.gitignore` was lying.
- A comment next to every rule ("why is this ignored?") makes stale rules easy to spot.

**Why enforcement in three layers (belt + suspenders):**
- ADR-016 (this file): the durable "why."
- `AGENTS.md` extension: the operational "remind me every session."
- `scripts/forge-doctor.sh` drift-check section: passive surface — surfaces drift when you run doctor.
- `.pre-commit-config.yaml` + `scripts/pre_commit_drift_check.sh`: active gate — blocks accidental commits that would leave drift behind. Overridable with `--no-verify` for legitimate WIP.

## Alternatives considered

1. **Just document the rule in AGENTS.md, no tooling.** Rejected — that's what we already had implicitly, and it produced 35 drifted files in one day. Discipline without tooling doesn't scale across sessions.
2. **Pre-commit hook only, no doctor extension.** Rejected — pre-commit fires only at `git commit` time. If you never commit for a day, drift accumulates unseen. The doctor extension surfaces drift on every diagnostic run.
3. **Track everything, gitignore nothing.** Rejected — would commit `.env` files with real API keys. Some things genuinely must stay local.
4. **Continue paste-block-for-commit workflow.** Rejected — killed the operator's bash session on the previous attempt, adds fragility with zero upside.
5. **Squash the current 35 proposals + 1 JSON into commit history.** Rejected — those files are all failure noise from the 2026-08-04 double-fault (vLLM :8501 down + proposer LLM down). Committing them sets a precedent that every failed selfeval run's noise gets checked in.

## Consequences

**Enforced by:**
1. This ADR (durable rule).
2. `AGENTS.md` Non-Negotiable Rules #9 (parity) + #10 (selfeval retention) — session-start reminder.
3. `scripts/forge-doctor.sh` Section 10: mirror drift check (passive detection).
4. `.pre-commit-config.yaml` + `scripts/pre_commit_drift_check.sh` (active block at commit time).

**New files (this commit):**
- `docs/adr/016-colossus-github-mirror-parity.md` (this file)
- `docs/proposals/.gitkeep` — directory tracked, empty until real proposals land.
- `.pre-commit-config.yaml`
- `scripts/pre_commit_drift_check.sh`

**Modified files (this commit):**
- `.gitignore` — full refactor with section comments + rationale per rule.
- `AGENTS.md` — add Non-Negotiable Rules #9 + #10 (mirror parity + selfeval retention).
- `scripts/forge-doctor.sh` — add Section 10 (mirror drift check).
- `docs/adr/README.md` — index row for ADR-016.
- `BUILD_LOG.md` — this-turn entry.
- `SESSION_HANDOFF.md` — overwritten.

**Deleted (on Colossus, after user pulls this commit — files never existed on GitHub):**
- 35 files under `docs/proposals/2026-08-04-smoke-*.md` — all failed-proposer noise from 2026-08-04. NOT in this GitHub commit (never were); user removes them locally with `rm docs/proposals/2026-08-04-smoke-*.md` after pulling.
- `docs/selfeval/2026-08-04-selfeval.json` — same failure event's summary. Same: user removes locally after pull.
- After removal, `.gitignore` and drift-check surface will treat these as never-existed rather than untracked-drift.

**Explicit selfeval-artifact retention policy** (codified in AGENTS.md, referenced here):
- `docs/selfeval/*.md` analysis or scope docs → always tracked.
- `docs/selfeval/*.json` result summaries → tracked ONLY if at least one task in the run produced meaningful signal (i.e., not all-environmental-error).
- `docs/proposals/*.md` proposer LLM output → tracked ONLY if the proposer LLM was healthy for that run (i.e., not `[Errno 111] Connection refused` proposals).

**Downstream:**
- ADR-013, ADR-015 remain unaffected.
- Stage-1H impl slices (per ADR-015) inherit this parity rule.
- Every future BUILD_LOG entry must reflect files touched in a way that matches what got committed and pushed.

## Lock-in phase

Cross-cutting — takes effect on this commit and applies to every commit thereafter.

## References

- User directive, 2026-08-05: "we need to make sure that the files on github and collosus are always the same, unless there is something truly sensitive that should remain on collosus and not on github"
- User directive, 2026-08-05: "why are you giving me this to paste when you should be doing this on github so i can just pull it?" — codified in this ADR as the direct-to-GitHub rule.
- ADR-015 (Stage-1H) — establishes the split-track plan this parity policy protects.
- Parity audit output, 2026-08-05 05:51 EDT (in BUILD_LOG.md).
- `.gitignore` — updated this commit to reflect explicit-ignore-with-rationale rule.
- `AGENTS.md` — Non-Negotiable Rules #9 + #10 (added this commit).
- `scripts/forge-doctor.sh` Section 10 (added this commit).
- `scripts/pre_commit_drift_check.sh` (created this commit).
