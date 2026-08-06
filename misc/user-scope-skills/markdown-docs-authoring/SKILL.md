---
name: markdown-docs-authoring
description: How to write Markdown documentation that a coding agent can navigate, grep, and reuse across sessions. Use whenever authoring or editing README.md, docs/, ADRs, runbooks, spec files, or long-form comments. Enforces grep-friendly headers, front-loaded summaries, minimal linking, code fences with language tags, and consistent structure so the doc is useful for both humans and agents.
license: MIT
triggers:
  - README
  - "docs/"
  - "*.md"
  - "runbook"
  - "spec"
  - "ADR"
  - "changelog"
  - "CHANGELOG"
  - "documentation"
  - markdown
---

# Markdown Docs Authoring

## Rule 0 — Write for a Future Reader Who Will Grep

Your future self and any coding agent will `grep` the doc, not scroll it. Optimize for search:

- Every distinct concept lives under a unique H2 or H3 header
- Headers use natural terms the reader will type ("Health Checks", not "Verifying System State")
- Anchor text is descriptive ("[the Ollama base URL rule](#base-url-discipline)") — never "[click here]"

## Structure

Every non-trivial Markdown doc has this shape:

```markdown
# Title

One-sentence purpose (what this doc is for).

## When to use / Applies to

Bullet the scenarios this doc covers.

## <Main content, H2 sections>

Prose + code + tables.

## Anti-Patterns / Common Mistakes

What NOT to do.

## References

Links to related docs.
```

If a doc doesn't fit this shape, ask whether it should be split.

## Headers

- **H1**: title only, one per file
- **H2**: main sections — the doc's grep-anchors
- **H3**: subsections within a section
- **H4+**: rare; if you need H4 the section is probably too big
- Use sentence case: "Health checks", not "Health Checks"
- No trailing colons: "Anti-patterns", not "Anti-patterns:"

## Front-Load the Summary

The first paragraph after the title should tell the reader whether to keep reading. Never bury the point in section 4.

```markdown
# ADR-017 — Use SQLite for skill index

Skill metadata is small (< 10 MB total), single-writer, and rarely queried
outside of skill-list requests. We reject Postgres/Redis in favor of a
file-backed SQLite database at ~/.openhands/skills.db.
```

Not:

```markdown
# ADR-017 — Skill Index Storage

## Context

For the past several months, the skills system has grown to accommodate ...
[500 more words before the decision is stated]
```

## Code Fences — Always Tag the Language

```markdown
```python
def add(a, b): return a + b
```

```bash
docker run --rm hello-world
```

```json
{"key": "value"}
```

```typescript
type User = { name: string };
```
```

Untagged fences (```` ``` ````) are readable but lose syntax highlighting and are harder for agents to identify as code. Always add the language tag.

For copy-pasteable command blocks, prefer `bash` over `shell` — universally recognized.

## Tables — When and How

Tables are great for structured comparisons. Bad for prose:

```markdown
✅ Good — structured comparison
| Runtime | Port | Auto-detect quant | Native GGUF |
|---|---|---|---|
| Ollama | 11434 | via Modelfile | ✅ |
| vLLM | 8000 | via config.json | ❌ |

❌ Bad — should be bullets
| Feature | Details |
|---|---|
| Setup | run docker |
| Config | edit yaml |
```

Rules:
- Every table has a header row
- Column alignment (`:---`, `:---:`, `---:`) only when it matters (numeric columns)
- Keep cells short — if a cell needs a paragraph, use a section instead
- Emojis in cells (✅ ❌ ⚠️) are fine for status, sparingly

## Links

Two forms — pick per doc, stay consistent:

**Inline** (default):
```markdown
See the [health check pattern](#health-checks) or [the Ollama docs](https://ollama.com/docs).
```

**Reference-style** (for docs with many repeated links):
```markdown
See the [health check pattern][health] or [the Ollama docs][ollama].

[health]: #health-checks
[ollama]: https://ollama.com/docs
```

Rules:
- **Never** "click here" or "read more" — link text describes destination
- Internal links use header anchors (kebab-cased, lowercased header)
- External links to specific documents, not homepages, when possible

## Callouts — Blockquotes

Markdown has no built-in callout syntax. Use blockquotes with a bold label:

```markdown
> **Note:** vLLM 0.10.2+ auto-detects compressed-tensors from recipe.yaml.

> **Warning:** Never launch vLLM while Ollama is running — GPU contention will OOM.

> **⚠️ Deprecated:** The `--dtype half` flag is aliased to `--dtype float16` since 0.9.0.
```

If the doc is rendered on GitHub, you can use their alert syntax:

```markdown
> [!NOTE]
> Useful information.

> [!WARNING]
> Critical warning.
```

But this is GitHub-specific. Blockquote + bold label is universal.

## Lists

- Use `-` for unordered lists (not `*` or `+`)
- Use `1.` for numbered — Markdown auto-renumbers, so `1. 1. 1.` works
- Indent nested lists with 2 spaces
- One blank line between the list and surrounding paragraphs
- Don't mix ordered and unordered at the same level

## Length

Prefer 5 short docs over 1 giant doc. Signs a doc should be split:

- More than 500 lines
- More than 3 distinct "when to use" scenarios
- The table of contents has more than 8 H2 sections
- You find yourself writing "See section X above" more than once

## What NOT to Do

- ❌ No H1 or multiple H1s in one file
- ❌ Anchor text like "here", "this", "click here"
- ❌ Code fences without language tags
- ❌ Long HTML tables inside Markdown (breaks in most renderers)
- ❌ Trailing whitespace (breaks in some renderers)
- ❌ Unwrapped 500-column-wide lines (unreadable in `git diff`)
- ❌ Bare URLs (`https://example.com`) — wrap in `[text](url)` or use `<https://example.com>` autolinks
- ❌ Screenshots as the ONLY documentation of a UI feature (put a text description alongside)
- ❌ Inline HTML unless absolutely necessary (`<details>` / `<summary>` is OK for collapsible sections)
- ❌ "TBD" / "TODO" markers that never get filled in (either fill or delete)

## Runbook Structure

Runbooks describe how to perform an operational task. They follow a stricter format:

```markdown
# Runbook: <Task>

**When to run**: <trigger>
**Estimated time**: <5 min | 30 min | ...>
**Prerequisites**: <what must be true before starting>

## Steps

1. <Step 1 — one command or one clear action per step>
2. <Step 2>
...

## Verification

<Exact commands / output that confirm success>

## Rollback

<Exact commands to undo>

## Common Failure Modes

- <Symptom> → <Fix>
```

## ADR (Architecture Decision Record) Structure

```markdown
# ADR-### — <Title>

**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-###
**Date**: YYYY-MM-DD

## Context
Why this decision is needed. What constraints exist.

## Decision
The decision, in plain language.

## Consequences
What changes: files, tests, downstream ADRs.

## Alternatives Considered
Options rejected and why.
```

Never delete an ADR. Supersede with a new ADR that references the old one.
