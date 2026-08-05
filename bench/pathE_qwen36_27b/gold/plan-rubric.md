# Rubric — plan.md scoring (0-100)

Score each cell response against `gold/plan.md`. Total = sum of dimensions.

Reference: `gold/plan.md` is a 9-commit sequenced plan for implementing Step 3 (real POST /runs → agent-server wiring) after the auth strip and duplicate cleanup. Key contract points the gold enshrines:

1. **`run_id == conversation_id`** identity contract on OpenHands agent-server v1.40.0
2. **Composer form field rename**: `contextPrompt` → `taskPrompt` (frontend contract fix)
3. **9 sequenced commits** with dependency order preserved
4. **Duplicate cleanup FIRST** (before functional changes)
5. **BFF → agent-server → WS event relay → frontend render** in that order

## Dimension A — Contract Fidelity (30 pts)

- 30: response identifies AND enforces both critical contract points: (a) `run_id == conversation_id` identity and (b) composer field rename `contextPrompt → taskPrompt`
- 22: identifies one of the two contract points explicitly
- 15: implicitly follows one (via correct sed pattern or field name) without naming it
- 7: mentions the wiring path but misses both contract points
- 0: violates a contract point (e.g. proposes separate run_id/conversation_id, keeps `contextPrompt`)

## Dimension B — Sequencing Correctness (25 pts)

- 25: presents plan in strict dependency order: duplicate cleanup → real POST /runs → real GET /runs/{id} → WS relay → frontend render → stub removal → verification; 8-10 commits total
- 18: mostly correct order with 1 minor swap (e.g. WS relay before GET /runs status)
- 12: functional pieces present but dependency order broken (e.g. frontend render before backend wiring)
- 6: only 3-4 commits sketched; dependency order incidental
- 0: sequencing would break a build (e.g. frontend before BFF endpoint)

## Dimension C — File Path Precision (15 pts)

- 15: names exact repo paths for all touched files (bff/routers/runs.py, bff/main.py, bff/openhands_client.py, lib/components/RunDetail.tsx or lib/hooks/useRunStream.ts, etc.); no phantom paths
- 10: mostly correct paths, 1-2 minor misspellings or plausible-but-wrong subdirs
- 5: uses correct file names but wrong or vague directories
- 0: hallucinates file paths that don't exist in the repo

## Dimension D — Commit Message Quality (10 pts)

- 10: each commit message is imperative-mood, specific (mentions the endpoint/file/behavior), and would survive `git log --oneline` inspection
- 6: commit messages are specific but inconsistent style
- 3: generic messages like "update runs.py" or "fix things"
- 0: no commit messages, or messages that describe what is NOT changing

## Dimension E — Verification / Definition of Done (10 pts)

- 10: includes a concrete verification step per commit (curl, pytest, uvicorn boot check) OR a final end-to-end verification block that would prove the wiring works
- 6: mentions verification generically ("test it works")
- 3: mentions verification only for the final step
- 0: no verification mentioned

## Dimension F — Scope Discipline (10 pts)

- 10: stays inside Step 3 scope; does not propose adding auth back, adding features, refactoring unrelated code, or breaking Step 4+ boundaries
- 6: mostly in scope, one small drift (e.g. adds one nice-to-have)
- 3: multiple scope drifts
- 0: proposes major out-of-scope work (adds RBAC back, adds new features, does Step 4 work)

## Scoring Notes

- **Extra credit** (tiebreak): identifies the historical hotfix commit 78d525f, mentions the ImportError cascade from Step 2, or cites Forge-OH-Action-Plan-v4.md by section
- **Deduct 10 pts** if response is dominated by `<think>` block leakage (raw internal monologue in output)
- **Deduct 5 pts** if response is padded with framing prose the task didn't ask for
- **Hard gate on contract violation**: if the response proposes `contextPrompt` (old field) or separate run_id/conversation_id, cap total at 40 pts
