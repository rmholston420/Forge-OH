# Rubric — debug.md scoring (0-100)

Score each cell response against `gold/debug.md`. Total = sum of dimensions.

## Dimension A — Root Cause (25 pts)

- 25: names both `runs.py` and `workspaces.py` AND identifies both the import line AND the `Depends(require_role(...))` route params as the failure mechanism
- 18: names both files and both mechanisms but weakly (e.g. mentions Depends without saying "route param" or "parameter")
- 12: names one file OR one mechanism but not both
- 6: identifies the ImportError but not the two-file / two-mechanism structure
- 0: wrong diagnosis (e.g. blames middleware config, blames main.py, proposes restoring the deleted file)

## Dimension B — Fix Correctness (40 pts)

- 40: sed/diff removes BOTH the `from bff.middleware.rbac import require_role` line AND every `Depends(require_role(...))` route param line in BOTH files; also removes now-unused `Depends` from fastapi imports (if not used elsewhere in the file)
- 30: removes both the import and the Depends param lines in both files; leaves orphaned `Depends` in fastapi import (still boots — technically correct)
- 20: removes only the failing import line but leaves `Depends(require_role(...))` params intact (won't boot — NameError at request time or module-level `require_role` reference)
- 10: incomplete — only fixes one file, or only uses a broad `sed '/require_role/d'` that would kill comments/docstrings too
- 0: adds stubs, re-creates the deleted files, adds feature flags, or fix does not compile / breaks syntax

## Dimension C — Command Precision (20 pts)

- 20: sed patterns anchor to real repo shape (module-level imports, standalone param lines with trailing comma), leave signature-valid Python
- 15: sed patterns work but use fragile matches (e.g. no `^`/`$` anchors where anchoring matters)
- 10: works but requires manual patch-up (e.g. leaves trailing commas that need cleaning)
- 0: sed patterns would produce syntactically invalid Python

## Dimension D — Verification (10 pts)

- 10: verification command actually imports the app (e.g. `python -c "from bff.main import app_with_sio"` or `uvicorn bff.main:app_with_sio --port 8081`)
- 5: verification checks something (grep, syntax check) but doesn't actually load the app
- 0: no verification command, or verification is unrelated

## Dimension E — Follows Ground Rules (5 pts)

- 5: no stubs, no re-created files, no feature flags, no comments explaining removals, no unrelated files touched
- 3: minor violation (e.g. adds one comment)
- 0: major violation (adds a stub, adds a flag, touches unrelated file)

## Scoring Notes

- **Extra credit** (not counted, but flag for tiebreak): counts exact handler quantities (7 in runs.py, 4 in workspaces.py) or lists them by name
- **Deduct 5 pts** if response contains hallucinated file paths, decorators, or Python syntax errors
- **Deduct 10 pts** if response is padded with unnecessary framing prose the task explicitly forbade
