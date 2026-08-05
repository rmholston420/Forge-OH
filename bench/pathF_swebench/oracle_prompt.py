"""Oracle-retrieval prompt builder for SWE-bench Verified.

Oracle-retrieval means: instead of running BM25 or embedding retrieval over the
repo, we hand the model the exact files the ground-truth patch touches. This
isolates the model's *code-editing* skill from its retrieval skill.

We do NOT hand the model the ground-truth patch itself — only the pre-patch
contents of the files the ground-truth patch touches. The model has to
reproduce a correct fix from those files + the issue text.

Prompt shape follows the SWE-bench-Lite/Verified prompt template used by the
public leaderboard's most-cited papers (issue body → repo/file context →
"return a unified diff") so results are comparable in structure.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


PROMPT_TEMPLATE = """\
You are a Python software engineer. Fix the bug described in the GitHub issue below.

# Issue

{issue}

# Repository files relevant to this issue

{files_block}

# Instructions

Return a single unified diff patch (`diff --git ... +++ ...`) that fixes the issue.
Do not include any explanation, prose, or code fences — output the diff ONLY.
Preserve indentation, whitespace, and file paths exactly. Include full context
lines for the diff to apply cleanly with `git apply`.
"""


_PATCH_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def files_touched_by_patch(patch_text: str) -> list[str]:
    """Return the list of file paths the ground-truth patch modifies."""
    paths = _PATCH_FILE_RE.findall(patch_text)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for p in paths:
        if p not in seen and p != "/dev/null":
            seen.add(p)
            ordered.append(p)
    return ordered


def read_files_at_commit(repo_root: Path, commit: str, paths: list[str]) -> dict[str, str]:
    """Return {path: pre-patch content} by `git show <commit>:<path>` for each."""
    out: dict[str, str] = {}
    for p in paths:
        try:
            content = subprocess.check_output(
                ["git", "show", f"{commit}:{p}"],
                cwd=repo_root,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            # New-file additions in the patch → no pre-image. Skip cleanly.
            if "exists on disk, but not in" in (e.stderr or ""):
                content = "(new file — did not exist at base commit)"
            else:
                raise
        out[p] = content
    return out


def build_prompt(task: dict, file_contents: dict[str, str]) -> str:
    """Assemble the final oracle-retrieval prompt."""
    parts = []
    for path, content in file_contents.items():
        parts.append(f"### `{path}`\n\n```python\n{content}\n```\n")
    files_block = "\n".join(parts) if parts else "(no files identified — model has issue text only)"
    return PROMPT_TEMPLATE.format(
        issue=task["problem_statement"].strip(),
        files_block=files_block,
    )
