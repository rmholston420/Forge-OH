---
name: env-and-secrets-discipline
description: Environment variables, virtualenvs, and secrets management. Use whenever activating a venv, running pip, encountering PEP 668 externally-managed-environment errors, handling API keys or tokens, editing .env files, or wiring a secret into code. Prevents the "committed a secret to git" and "wrong Python in the wrong shell" failure modes.
license: MIT
triggers:
  - venv
  - virtualenv
  - .venv
  - .oh-venv
  - activate
  - PEP 668
  - externally-managed
  - pip install
  - "pip3"
  - .env
  - dotenv
  - API_KEY
  - secret
  - token
  - "os.environ"
  - "os.getenv"
  - direnv
---

# Environment & Secrets Discipline

## Virtualenv Discipline

### One venv per project — always

```bash
cd ~/myproject
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The venv is `.venv/` or a project-specific name like `.oh-venv/`. **Never install packages into system Python.** Modern Debian/Ubuntu enforces this with PEP 668:

```
error: externally-managed-environment

× This environment is externally managed
```

The error message says how to override (`--break-system-packages`). **Never use that.** Use a venv instead.

### Activate discipline

Every new shell needs the venv reactivated. You are NOT in your venv if:

- Your prompt doesn't show `(.venv)` or the project's venv name
- `which python` doesn't include the venv path
- `python -c "import sys; print(sys.prefix)"` doesn't point at the venv

Verify before running anything:

```bash
which python
which pip
python -c "import sys; print(sys.prefix)"
```

### PEP 668 recovery

If you see `externally-managed-environment`:

```bash
# ✅ Right — create and use a venv
python -m venv .venv
source .venv/bin/activate
pip install <pkg>

# ❌ Wrong — bypasses the safety
pip install --break-system-packages <pkg>

# ❌ Wrong — trashes the OS environment
sudo pip install <pkg>
```

### Cross-venv contamination

Symptoms:
- `ModuleNotFoundError` on a package you know is installed
- `command not found` for a CLI tool that pip installed
- `import` succeeds but the wrong version loads

Diagnosis:

```bash
which python           # is this the right python?
which <the-cli>        # is this the venv's binary?
python -c "import <pkg>; print(<pkg>.__file__)"   # where does this come from?
pip list | grep <pkg>  # is it actually installed in THIS venv?
```

Fix: reactivate the venv (`deactivate; source .venv/bin/activate`). If the wrong python is still first, the venv wasn't fully activated — usually a shell that ran before activate.

## Environment Variables

### File hierarchy — pick one convention per project

Standard (12-factor style):

```
.env              — committed, contains DEFAULTS and PLACEHOLDERS only
.env.local        — NEVER committed, contains ACTUAL secrets
.env.example      — committed, DOCUMENTS all required vars with placeholder values
```

`.env.local` overrides `.env`. Some frameworks (Next.js) also support `.env.development.local`, `.env.production.local`.

### The .env format

```
# Comments start with #
DATABASE_URL=postgres://localhost/mydb
API_KEY=abc123
# No spaces around =
# No quotes needed unless value contains spaces or #
MESSAGE="Hello, world"
# Multi-line values are painful — avoid; use a file path instead
```

### Loading .env in code

Python:
```python
from dotenv import load_dotenv
load_dotenv()   # loads .env from cwd
load_dotenv(".env.local", override=True)   # override with local secrets
```

Node.js:
```typescript
import "dotenv/config";  // loads .env
// Next.js loads .env automatically — never call dotenv manually there
```

Never `load_dotenv()` in library code. Only in application entrypoints.

### direnv (recommended for interactive work)

```bash
# ~/.envrc for the project
export DATABASE_URL=postgres://localhost/mydb
export API_KEY=xxx
```

`direnv allow` loads it when you cd into the dir; unloads when you leave. Cleaner than `source .env` and safer than exports in your `.bashrc`.

## Secrets — What NEVER Goes in Git

- API keys, tokens, passwords
- Database URLs with credentials
- Private SSH keys / GPG keys
- OAuth client secrets
- Signing keys, JWT secrets
- Even test/staging credentials

### If you committed a secret

1. **Rotate the credential immediately** — assume it's compromised the moment it hit any git repo, even a private one
2. **Purge from history** — `git filter-repo` (preferred) or BFG Repo-Cleaner
3. **Force-push** to overwrite the remote (see `git-workflow` skill on force-push safety)
4. **Notify collaborators** to re-clone (their local history still has it)

`git filter-repo` example:

```bash
pip install git-filter-repo
git filter-repo --replace-text <(echo 'SECRET_VALUE==>REDACTED')
git push --force-with-lease origin main
```

Removing the file in a new commit does NOT purge history. The secret is still in every clone.

### .gitignore for secrets

```
# Environment
.env.local
.env.*.local
*.env.local

# Credentials
*.pem
*.key
credentials.json
service-account*.json
.aws/
.ssh/

# OS-specific
.DS_Store
Thumbs.db
```

If you're using a monorepo, gitignore secrets at the root (they cover subtrees).

### Loading secrets from env, not from code

```python
# ❌ Never
API_KEY = "sk-abc123..."

# ✅ From env with a clear error if missing
import os

API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY not set — copy .env.example to .env.local and fill it in")
```

For servers, prefer a secrets manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager) over `.env` files.

## os.environ vs os.getenv

```python
os.environ["FOO"]        # raises KeyError if unset
os.environ.get("FOO")    # returns None if unset
os.getenv("FOO", "default")   # returns "default" if unset
```

Rule: use `os.environ["X"]` when the variable is required (fail fast). Use `.get()` with a default when the variable is optional.

## Common Failure Modes

### "It works locally but not in production"

- Missing env var in production → check the deploy config
- Different Python version → check `python --version` in both
- Different venv → prod may not use a venv (it should)

### "hf_transfer ModuleNotFoundError after HF_HUB_ENABLE_HF_TRANSFER=1"

The env var is set but the pip package isn't installed. Install with `pip install hf_transfer` in the active venv.

### `command not found` after `pip install <tool>`

- venv not activated
- tool was installed but `~/.local/bin` isn't on PATH (fix: `pip install --user` puts it there; add `export PATH=$HOME/.local/bin:$PATH` to shell config)

### `.env` values contain a `$` and get expanded

Values with `$` need single quotes or escaping:

```
PASSWORD='p$$word'
# or
PASSWORD=p\$\$word
```

### Two `.env` files disagree

`.env.local` overrides `.env`. If they set the same key differently, `.env.local` wins. Never rely on this — set the value in one place only.

## Anti-Patterns

- ❌ `sudo pip install` (trashes OS Python)
- ❌ `pip install --break-system-packages` (bypasses safety, poisons OS)
- ❌ Committing `.env` (contains real secrets on many teams by accident)
- ❌ Copy-pasting secrets into commit messages, comments, or docs
- ❌ Hardcoding "test" credentials that turn out to be real
- ❌ Global `dotenv.config()` in library code (breaks callers' env)
- ❌ Sharing venvs across projects (dependency version drift)
- ❌ Sharing venvs across Python versions (won't work — venvs are Python-version-specific)
- ❌ Committing lockfile changes without committing the package.json/pyproject.toml/requirements.txt change that caused them (irreproducible builds)

## Checklist for a New Project

1. `.gitignore` has `.venv/`, `.env.local`, `*.pem`, `*.key`, credentials.json
2. `.env.example` exists and documents all required env vars (with placeholder values, NOT real ones)
3. Setup docs say "copy .env.example to .env.local and fill in the values"
4. Code fails loudly if a required env var is missing (not silently continues with `None`)
5. venv is `.venv/` or project-specific (`.oh-venv/`, `.forge-venv/`) — consistent
6. Requirements are pinned in a lockfile (`pip-compile`, `poetry.lock`, `uv.lock`, `pnpm-lock.yaml`)

## Recovery Checklist If You Committed a Secret

1. **Rotate** the credential (revoke, generate new)
2. **Update** any local `.env.local` and secrets-manager entries with the new value
3. **Purge history** with `git filter-repo` or BFG
4. **Force-push** to remote (`--force-with-lease`)
5. **Notify** anyone who has cloned the repo
6. **Audit** logs for unauthorized use during the exposure window
7. **Document** the incident in the repo's SECURITY.md so future work avoids the same mistake
