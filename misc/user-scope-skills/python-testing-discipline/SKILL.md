---
name: python-testing-discipline
description: Enforce first-fail triage, mock-at-the-boundary, and fixture-scope reasoning for Python (pytest) test suites. Use when writing new tests, diagnosing failing tests, adding a fixture, mocking an external dependency, or deciding what a test is actually verifying. Prevents the common failure modes of testing implementation details, leaking state across tests, mocking too deep, and drowning in a pytest run with 60 failures where only the first 3 matter.
license: MIT
triggers:
  - pytest
  - python test
  - failing test
  - fixture
  - mock
  - AsyncMock
  - MagicMock
  - conftest
  - unittest
---

# Python Testing Discipline

Applies to any pytest-based Python codebase.

## First-Fail Triage — Never Read a 60-Failure Log

When more than one test fails, run again with `-x --lf --tb=short` before doing anything else:

```bash
pytest -x --lf --tb=short
```

- `-x` stops at first failure — you fix errors in dependency order, not report order
- `--lf` re-runs only last-failed after each fix so you converge quickly
- `--tb=short` cuts the noise; use `--tb=long` only when the short form is genuinely unclear

Reading the full log first is almost always wasted effort. 90% of the time, the first failure is the cause and the rest are symptoms.

## Mock at the Boundary, Not Below It

The boundary is the outermost seam owned by *your* code — usually an HTTP client, a DB session, a filesystem call, or a subprocess.

- ✅ Mock `httpx.AsyncClient.get` when testing a function that calls an HTTP API
- ❌ Do NOT mock `httpx._transports.default.HTTPTransport.handle_request` — you're testing httpx, not your code
- ✅ Mock `Path.read_text` when testing a config loader
- ❌ Do NOT mock `open` globally — you'll break pytest's own file handling

Rule of thumb: if a mock has to know about the internals of a library, you're mocking too deep.

## Fixture Scope Reasoning

pytest fixture scopes: `function` (default), `class`, `module`, `session`.

- **`function`** — default. Use unless you have a specific reason not to.
- **`module`** — expensive setup shared across tests in one file (e.g., a compiled model). Every test must tolerate observing state from previous tests.
- **`session`** — process-wide singletons only. Every use is a landmine for parallel test runners (`pytest-xdist`).

If you find yourself reaching for `session` scope to make tests faster, first check whether you can parallelize with `pytest-xdist` (`pip install pytest-xdist; pytest -n auto`) — that's usually the right answer.

## Async Tests

For `async def` tests you need one of:

- `pytest-asyncio` with `@pytest.mark.asyncio` on each test, OR
- `pytest-asyncio` with `asyncio_mode = "auto"` in pytest.ini/pyproject.toml

For async mocks:

```python
from unittest.mock import AsyncMock, patch

fake_client = AsyncMock()
fake_client.get = AsyncMock(return_value=some_response)
with patch.object(module_under_test, "get_client", return_value=fake_client):
    ...
```

`AsyncMock().foo` returns a coroutine. `MagicMock().foo` returns a MagicMock. Mixing them silently gives `<coroutine object never awaited>` warnings that don't fail the test.

## Test Naming — Encode the Contract

Test names describe behavior, not implementation:

- ✅ `test_returns_502_when_upstream_unreachable`
- ✅ `test_reshapes_snake_case_to_camel_case`
- ❌ `test_get_skills` (says nothing about what it verifies)
- ❌ `test_line_47` (implementation detail, brittle)

## What NOT to Test

- Framework behavior (pytest, FastAPI, Pydantic already have their own suites)
- Third-party library internals
- Trivial getters/setters — cover them via the integration test that exercises real behavior
- Type annotations — that's mypy's job

## Anti-Patterns

- ❌ `assert result` when you mean `assert result == expected` (any truthy value passes)
- ❌ Catching `Exception` in a test — you'll swallow the failure you were trying to catch
- ❌ Time-dependent tests without `freezegun` or a mockable clock
- ❌ Tests that pass in isolation but fail in the suite — always a fixture-scope bug
- ❌ `assert True  # TODO: real test` — delete the test or write it

## When Something Fails, In Order

1. Read the error text verbatim
2. Reproduce the failure in isolation: `pytest path/to/test_file.py::test_name -x`
3. If it passes in isolation but fails in the suite, look for shared state (module-level globals, `session`-scoped fixtures, environment vars)
4. If it fails in isolation, form ONE hypothesis, verify it, fix it, re-run
5. Never "fix" a test by loosening the assertion unless you're certain the old assertion was wrong
