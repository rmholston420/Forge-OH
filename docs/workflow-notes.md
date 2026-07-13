# Forge-OH Workflow Notes

## Purpose

This document records the working conventions for modifying this repository without manual editing. Every change should be reproducible through pastable insertion scripts plus explicit verification commands.

## User workflow contract

- Always provide pastable insertion scripts.
- Never require manual editing.
- Inspect relevant files before modifying them.
- Prefer the safest and most reproducible approach when there is any doubt.
- Keep scripts self-contained and rerunnable.

## Preferred write pattern

Use one Python stdin script to write files with Path(...).write_text(..., encoding="utf-8", newline="\n").

Why this pattern is preferred:

- It avoids most nested shell quoting problems.
- It keeps newline handling explicit.
- It can write one or more files in one pass.
- It is easier to rerun safely than ad hoc shell patching.

Recommended pattern:

```bash
cd ~/Forge-OH

python3 - <<'__PY_WRITE_FILE__'
from pathlib import Path

content = (
    "first line\\n"
    "second line\\n"
)

Path("some/file.txt").write_text(content, encoding="utf-8", newline="\\n")
__PY_WRITE_FILE__
```

## String construction rules

- Prefer parenthesized Python string concatenation for long content.
- Keep content ASCII-only unless Unicode is explicitly required.
- Do not include tabs.
- Use spaces only for indentation.
- Escape backslashes deliberately in shell examples.
- Avoid smart quotes and non-breaking spaces.

## Required script order

Every modification script should follow this order:

1. Change to the repository root.
2. Inspect the target files first.
3. Back up important files when the rewrite is substantial.
4. Apply the modification with a single script.
5. Re-inspect the changed files.
6. Run targeted verification commands.

## Inspection patterns

Use explicit inspection commands before modifying files:

```bash
cd ~/Forge-OH
pwd
ls
sed -n '1,220p' path/to/file
```

For whitespace and encoding checks:

```bash
LC_ALL=C sed -n '1,220l' path/to/file
grep -n $'\\u00A0' path/to/file || echo "No NBSP found"
```

## Verification patterns

After writing files, verify with both normal and diagnostic views:

```bash
cat path/to/file
printf '\n--- HIDDEN ---\n'
LC_ALL=C sed -n '1,220l' path/to/file
```

For code changes, run the narrowest useful validation first, then broader checks only if needed:

```bash
npx vitest path/to/test
python3 -m pytest path/to/test
npm run build
```

## Failure modes seen here

### Wrapped transcript text pasted into files

Symptoms:

- Words split across lines, such as `supe` followed by `rvision-first`.
- Mid-command fragments appended after the intended script body.

Likely cause:

- Copying from wrapped terminal transcript output instead of the original literal script block.

Response:

- Reissue the script as a fresh insertion block.
- Do not reuse text copied from terminal output.

### Heredoc delimiter collisions

Symptoms:

- The shell exits the heredoc too early.
- Trailing Python or shell lines run as separate commands.

Likely cause:

- The heredoc delimiter also appears inside the document content or example text.

Response:

- Use a unique delimiter that will not appear in the generated file.
- Do not show the same outer delimiter inside examples.

### Unicode whitespace corruption

Symptoms:

- Indented bullets look normal but fail whitespace checks.
- Hidden spaces appear in copied commands or markdown.

Response:

- Rewrite the file with ASCII-only scripted content.
- Optionally normalize with:

```bash
perl -CSDA -0pi -e 's/\\x{00A0}/ /g; s/[ \t]+\n/\n/g' path/to/file
```

## Decision rules

- For multi-line file content, prefer Python write scripts.
- For small targeted replacements, `perl -0pi -e` is acceptable when the match is narrow and verified.
- For structural rewrites, overwrite the whole file rather than patching brittle fragments.
- If a previous paste failed, simplify the next script instead of making it more clever.

## Response standard

For this repository, the expected response format is:

1. One sentence naming the change.
2. One pastable inspection-and-apply script.
3. One pastable verification block.
4. Brief notes on what success should look like.

No manual editing steps should be included.


## Explicit workflow rules

The following rules are mandatory for all changes and interactions with this repository:

- never ask me to make manual edits
- always give me pastable insertion scripts i can paste directly into my bash shell
- always give me pastable step-by-step commands i can paste directly into my bash shell
- never guess
- always inspect files before modifying or editing them
- when in doubt always make the optimal choice
- always push to main when pushing to my repo
- always try to give me insertion scripts that avoid browser-based corruption entirely
- when you need something from me always give me exact step-by-step commands i can paste directly into my bash shell
