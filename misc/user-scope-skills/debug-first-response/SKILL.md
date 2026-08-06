---
name: debug-first-response
description: The read-the-error-first debugging protocol. Use whenever an error, exception, traceback, test failure, or unexpected behavior appears. Enforces capture-verbatim, reproduce-minimally, hypothesize-one-thing, bisect discipline. Prevents the "let me try random fixes and see what sticks" failure mode that wastes context.
license: MIT
triggers:
  - error
  - exception
  - traceback
  - stack trace
  - failing
  - broken
  - debug
  - not working
  - crashed
  - "500"
  - segfault
  - ImportError
  - TypeError
  - AttributeError
  - ConnectionError
  - "why is"
  - "why does"
---

# Debug First Response

## Rule 0 — Read the Error Verbatim

Before doing ANYTHING else, capture the exact error text. Do not paraphrase.

- Full exception class name (`ConnectionResetError`, not "network error")
- Full message (not "some string about a socket")
- Full traceback if there is one
- Exact command that produced it
- Exit code if it's a process

Paraphrasing the error is the single most common way debugging goes off the rails. The exact class name and message are what you'll grep for in prior debug logs, GitHub issues, and library source.

## The 5-Step Protocol

### 1. Capture

Copy the error verbatim. If it's a long traceback, keep the last 20 lines minimum.

### 2. Search prior context

Before diagnosing from scratch:
- If there's a `DEBUG_LOG.md` in the repo, `grep -in "<key phrase>" DEBUG_LOG.md`
- Grep the codebase for the error message (someone may have already handled it)
- Search the library's GitHub issues for the class + a few key words

If a prior fix exists, reuse it. Reference it in whatever log you write.

### 3. Reproduce minimally

- Can you trigger the error with a single command? If yes, save that command.
- If it only fires in a full test suite, run it in isolation: `pytest path/to/test::specific_test -x`
- If it only fires in production, try to reproduce locally with the same inputs
- If you can't reproduce, you can't fix — stop and gather more logs

### 4. Hypothesize ONE thing

Form a single hypothesis. Write it down (mentally or in comments):

> "I think this fails because X." → what would prove it? → check that.

Do NOT try multiple fixes simultaneously. If you fix three things and the error goes away, you don't know which one mattered — and one of the three may have introduced a new bug you'll find next week.

### 5. Verify

Never assume the fix worked. Re-run the failing command. Re-run the test.

If the error is gone, add a regression test that would have caught it.

## Common Diagnostic Techniques

### Print debugging is fine — but structured

```python
# ❌ scattered noise
print(x)
print("here")
print(y)

# ✅ labeled and traceable
print(f"[fn=my_func step=after_validate] x={x!r} y={y!r}")
```

`!r` (repr) reveals types and quotes strings so you can tell `"5"` from `5`.

### Git bisect for regressions

If it worked last week and doesn't now:

```bash
git bisect start
git bisect bad HEAD
git bisect good <known-good-sha>
# git checks out midpoint; you run the test; mark bad or good; repeat
```

Bisect is O(log n) instead of O(n) — a 200-commit range converges in 8 tests.

### Bisect within a file

If a test fails when run with the suite but passes alone, half-and-half the test list until you find the offender:

```bash
pytest tests/ -k "not test_a and not test_b and not test_c ..." -x
```

### Read the library source

If a library is doing something unexpected, `python -c "import lib; print(lib.__file__)"` and read the actual source. Library README examples lie by omission all the time.

## When to Stop and Ask

- The user has more context than the logs (they know why they made a config choice)
- The fix would require reversing an architectural decision
- The error involves an API/service you can't reproduce locally
- You've spent >30 min on a single error with no hypothesis narrowing

Stopping to ask is cheap. Guessing wrong is expensive.

## Anti-Patterns

- ❌ "Let me try a few things" (variable-manipulation-driven debugging)
- ❌ Paraphrasing the error before searching
- ❌ Fixing symptoms without a root-cause hypothesis
- ❌ Multiple simultaneous "fixes" — you can't attribute the improvement
- ❌ Removing an assertion to make a test pass (unless the assertion was wrong)
- ❌ Adding `try/except: pass` to silence an error you don't understand
- ❌ Fixing something in code when the fix belongs in the config, or vice versa
- ❌ Not writing down the fix — you or someone else will hit the same error again

## Debug Log Entry Format (if the repo maintains one)

```markdown
## YYYY-MM-DD HH:MM TZ — <short title>

**Symptom** (verbatim):
```
<exact error text or observed behavior>
```

**Affected**: <component / file / port>

**Root cause**: <one paragraph>

**Fix applied**: <what changed>

**Files changed**: `<paths>`
**Verified by**: <command that now succeeds>
```

Keep entries append-only. Even a bad fix is worth logging — the next debugger benefits from knowing what didn't work.
