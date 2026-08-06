# OpenHands Agent Skills — Future Authoring Backlog

Skills to author in future sessions. All user-scope (`~/.agents/skills/`) unless noted.

## Requested 2026-08-06

### Additional skills (user scope, `~/.agents/skills/`)

- **python-coding-best-practices** — Idiomatic Python: type hints, dataclasses vs pydantic, pathlib over os.path, contextlib, comprehensions over map/filter, when to reach for `@cached_property` vs `functools.cache`, structural pattern matching, dunder discipline. Complements `python-testing-discipline` (this is authoring; that is testing).
- **python-debugging-best-practices** — `pdb` / `breakpoint()`, `rich.traceback`, `logging` config that actually helps, `sys.settrace`, `py-spy` / `austin` for live processes, `memray` for memory, when to reach for each. Complements `debug-first-response` (this is Python-specific tooling; that is universal protocol).
- **gui-ux-best-practices** — Loading states, empty states, error states, optimistic updates, focus management, keyboard shortcuts, aria-labels, contrast ratios, motion + reduced-motion, form validation UX, destructive-action confirms. Complements `web-frontend-authoring` (this is design/interaction; that is code structure).

### Meta-skill

- **skill-authoring** — Teaches an agent how to write a well-formed OpenHands SKILL.md. Content:
  - YAML frontmatter fields (`name`, `description`, `triggers`, optional `license`, `compatibility`, `paths`, `mcp_tools`)
  - Trigger selection heuristics: choose words the agent will actually see in tool outputs; single tokens beat phrases; avoid overly common words that fire in unrelated contexts
  - Description-writing rules: state WHEN to use and WHAT it enforces
  - Structural template: When-to-use → Rules → Examples → Anti-Patterns → Checklist
  - How to test a new skill loads (`POST /api/skills` with default flags)
  - How to install: user scope (`~/.agents/skills/{name}/SKILL.md`) vs project scope (`{workspace}/.agents/skills/{name}/SKILL.md`)
  - Anti-patterns: over-broad triggers, prose-first (no rules), duplicating an existing skill
  - Firing-rate expectations: how often should the trigger words appear in a typical run?

### Forge-OH feature: automatic skill proposal from sessions

A new stage (likely Stage 7+ after current UI work) that mines completed Forge-OH runs and proposes SKILL.md drafts for review.

**Signal sources:**
- `~/.forge-oh/*.log` — BFF and next logs
- Run events (from `bff/services/event_normalize.py`) — `activated_skills`, error events, tool-call sequences
- DEBUG_LOG.md — recurring symptom → fix pairs
- BUILD_LOG.md — successful decision patterns
- Trajectory memory — what the agent actually reads/writes

**Detection heuristics:**
- **Recurring error + fix**: same or similar error text appears in DEBUG_LOG ≥ 3 times, with a documented fix each time → propose a skill codifying the fix
- **Repeated tool-call sequence**: same tool sequence appears in ≥ 5 runs solving similar problems → propose a skill documenting the pattern
- **Trigger-word gap**: an existing skill fired < N times but the run mentioned words that SHOULD have triggered it → propose adding triggers to existing skill
- **Uncovered domain**: many runs touch a topic (e.g., a new library, a new file type) with no skill firing → propose a new skill

**Output shape:**
- New endpoint: `GET /api/skills/proposals` returning skill drafts
- New page: `/skills/proposals` showing candidate drafts + evidence (which runs, which events)
- Each proposal has: draft SKILL.md, list of evidence run IDs, one-click "install to ~/.agents/skills/" or "install to project"
- Human review is mandatory — the system NEVER installs skills automatically, only proposes

**Storage:**
- Draft SKILL.md files land in `~/dev/forge-oh/skills/proposed/{skill-name}/SKILL.md`
- Proposal metadata (evidence, score, status) in a SQLite table `skill_proposals`

**Success metric:**
- Proposed skills accepted ≥ 30% (below that, the heuristics are too noisy)
- Fewer repeated fixes for the same class of issue after installation

**Prerequisites before this feature is worth building:**
- Stage 6.6 (skills page) shipped — need the UI substrate for /skills/proposals to reuse
- Enough completed Forge-OH runs (≥ 100) to have statistical signal
- DEBUG_LOG discipline in place (already true)
- Trajectory memory landed (already true per Stage F)

## Other candidates flagged but not yet requested

- `docker-compose-authoring` — only if Forge-OH or another project starts using compose
- `sql-authoring` — if a project takes on non-trivial SQL (Kosmos may)
- `security-basics` — currently too broad; would benefit from a specific angle first (e.g. `secrets-in-code`, `csrf-and-cors`, `input-validation`)
- `observability-basics` — logs / metrics / traces / dashboards discipline
- `refactoring-discipline` — rename-before-restructure, characterization tests, feature-flag-based rollouts

## Not planned (deliberate exclusions)

- Mirrors of the Perplexity Computer space skills — different agent context, different tools; would duplicate my coordination discipline into the coder agent uselessly
- Framework-specific skills for frameworks not in use (Flask, Django, Vue, Svelte, etc.)
- Cloud-provider skills (AWS/GCP/Azure) — local-first workstation, no fit
