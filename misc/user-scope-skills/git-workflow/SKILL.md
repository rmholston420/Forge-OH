---
name: git-workflow
description: Git workflow discipline — atomic commits, commit message hygiene, branching strategy, safe force-push, .gitignore management, recovering from mistakes. Use when committing, pushing, rebasing, merging, resolving conflicts, or when a git operation fails or leaves the repo in an unexpected state.
license: MIT
triggers:
  - git commit
  - git push
  - git rebase
  - git merge
  - git reset
  - git checkout
  - git stash
  - .gitignore
  - detached HEAD
  - merge conflict
  - force push
  - "fatal:"
  - "warning:"
  - unpushed
  - gitignore
---

# Git Workflow

## Atomic Commits

One commit does one thing. Not "add feature X and also fix typo in Y and also refactor Z."

Reasons:
- `git bisect` needs small commits to isolate a regression
- `git revert` on a small commit is safe; on a mixed commit it's a mess
- Code review is impossible on 50-file commits
- The commit message can be honest about what the commit does

If you find yourself staging unrelated changes, use `git add -p` to stage hunks selectively, or `git stash` the unrelated changes for a separate commit.

## Commit Message Format

```
<type>(<scope>): <short imperative summary>

<optional body — wrap at 72 columns>

<optional footer — refs, breaking-change notes>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `build`.

Examples:

```
feat(bff): add skills router proxy for /api/skills
```

```
fix(fe): unwrap useQuery data shape after v5 migration

react-query v5 returns { data, isLoading, ... } and data is unwrapped
inline; the previous v4 workaround pulled from data.data which broke
after upgrade. Removed the extra unwrap.

Refs #142
```

Imperative mood ("add", not "added" or "adds"). The summary should complete the sentence "If applied, this commit will…"

## Never `git push --force` Onto a Shared Branch

`--force` overwrites history on the remote. If anyone else has pulled from that branch, they now have an orphaned commit and merge chaos.

Safe force-push variants:

- `git push --force-with-lease` — fails if the remote has commits you don't know about (safer)
- `git push --force-with-lease --force-if-includes` — even safer; requires the remote to match what you last fetched

Rules:
- Force-push is fine on YOUR feature branch that nobody else uses
- Force-push is NEVER fine on `main`, `master`, `develop`, or any shared long-lived branch
- If unsure whether a branch is shared, don't force-push

## Recovering from Mistakes

### "I committed to the wrong branch"

```bash
git log --oneline -1                    # note the SHA
git reset HEAD~1                        # remove the commit but keep changes
git stash                               # stash the changes
git checkout correct-branch
git stash pop
git add . && git commit -m "..."
```

### "I need to undo the last commit but keep the changes"

```bash
git reset --soft HEAD~1
# Changes are back in the staging area
```

### "I need to undo the last commit AND the changes"

```bash
git reset --hard HEAD~1
# Changes are GONE from working tree. Use with care.
```

### "I lost work — did I lose it?"

Almost certainly no. `git reflog` shows every HEAD movement in the last 90 days:

```bash
git reflog
# find the SHA you want
git checkout <sha>
# or
git reset --hard <sha>
```

Even `git reset --hard` doesn't delete the old commits — they're just unreferenced. They're garbage-collected only after `git gc`, which usually doesn't run for weeks.

### "I have merge conflicts"

```bash
git status                     # see conflicted files
# Edit each conflicted file — resolve <<<<<<< / ======= / >>>>>>> markers
git add <resolved-files>
git rebase --continue          # or git merge --continue
```

To abort mid-rebase/merge: `git rebase --abort` / `git merge --abort`.

## .gitignore Hygiene

- One `.gitignore` at the repo root covers most projects
- Nested `.gitignore` files for subtrees with unique build outputs (e.g., `frontend/node_modules/`)
- Never `.gitignore` a file that's already committed — it stays tracked. First `git rm --cached <file>`, then add to `.gitignore`.
- Common entries:

```
# Dependencies
node_modules/
.venv/
.oh-venv/
__pycache__/
*.pyc

# Build outputs
dist/
build/
.next/
*.log

# IDE
.vscode/
.idea/
*.swp

# Environment
.env.local
.env.*.local

# OS
.DS_Store
Thumbs.db
```

## Rebase vs Merge

- **Rebase** = replays your commits on top of another branch. Clean linear history. Rewrites SHAs.
- **Merge** = joins two branches with a merge commit. Preserves branch topology. Original SHAs preserved.

Choose per-project. Rebase for feature branches before merging to main (clean history). Merge for long-lived integration branches (preserve context).

**Never rebase a branch anyone else has pulled from.** Rewriting shared history is where teams lose work.

## Signed Commits (Optional But Recommended)

Set up a GPG or SSH signing key and:

```bash
git config --global user.signingkey <key>
git config --global commit.gpgsign true
```

Signed commits show a "Verified" badge on GitHub and make provenance auditable. Especially useful when you're committing on behalf of another identity (e.g., automation).

## Committing as Another Identity

```bash
git -c user.name="Automation Bot" -c user.email="bot@example.com" \
  commit -m "chore: automated update"
```

The `-c` flags override config for one command. Cleaner than mutating global config for a single commit.

## Anti-Patterns

- ❌ `git commit -am "wip"` on a shared branch — noise commits are hard to review
- ❌ `git add .` without inspecting `git status` first — accidentally committed secrets are painful to remove
- ❌ Committing `.env` or credentials — if it happens, `git filter-repo` or BFG to purge; rotate the credential immediately
- ❌ Editing history on a shared branch
- ❌ Merging without reading the diff
- ❌ Rebasing a branch someone else is working on
- ❌ Using `git pull` (which is fetch + merge) when you want `git pull --rebase`
- ❌ Long-lived feature branches — they drift from main and merge painfully

## Safe Command Reference

```bash
git status                              # always start here
git log --oneline --graph --decorate    # visual history
git diff                                # unstaged changes
git diff --staged                       # staged changes
git diff main..HEAD                     # your branch vs main
git reflog                              # every HEAD movement, recover lost work
git stash list                          # stashed work you may have forgotten
git branch -vv                          # branches + upstream tracking
git remote -v                           # remote URLs
```
