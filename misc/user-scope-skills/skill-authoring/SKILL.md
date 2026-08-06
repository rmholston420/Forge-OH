---
name: skill-authoring
description: How to author a well-formed OpenHands SKILL.md file. Use whenever creating a new skill, editing an existing SKILL.md, refining a skill's triggers, deciding whether a skill should be user-scope or project-scope, or reviewing a proposed skill draft. Covers YAML frontmatter, trigger selection, description writing, structural template, testing that a skill loads, and anti-patterns.
license: MIT
triggers:
  - SKILL.md
  - skill authoring
  - agent skill
  - new skill
  - skill frontmatter
  - skill triggers
  - "load_public"
  - "~/.agents/skills"
  - ".agents/skills"
  - agentskills
  - is_agentskills_format
---

# Skill Authoring

How to write a SKILL.md that the OpenHands SDK (`openhands.sdk.skills`) will load, index, and fire correctly.

## The Format

A skill is a directory containing `SKILL.md`. The file has YAML frontmatter and a Markdown body:

```markdown
---
name: my-skill
description: One paragraph. What this skill does AND when to use it.
license: MIT
triggers:
  - keyword-one
  - keyword-two
---

# Skill title (H1)

Body content in Markdown.
```

Optional additional files in the skill directory: `references/`, `templates/`, other markdown files linked from `SKILL.md`. The SDK loads `SKILL.md` as the primary content; other files are referenced but not auto-injected.

## Frontmatter Fields

### Required

- **`name`** — kebab-case identifier. Must be unique within scope. Should match the directory name.
- **`description`** — one paragraph. Two parts: WHAT the skill enforces + WHEN to use it. This is what the SDK shows in the `<available_skills>` block, so the agent decides whether to load based on this text.
- **`triggers`** — list of strings. When any trigger appears in the run context (task, tool output, code), the skill's content is auto-injected.

### Optional

- **`license`** — SPDX identifier. Use `MIT` unless you have a specific reason not to.
- **`compatibility`** — free-form string describing prerequisites ("Requires Python 3.11+", "Requires vLLM 0.10+").
- **`paths`** — comma-separated glob patterns. If set, the skill fires when the agent edits files matching these paths, INSTEAD of trigger-based firing. `paths:` and `triggers:` are mutually exclusive — the SDK warns and picks `paths:`.
- **`disable_model_invocation`** — bool. Default false. If true, the model cannot invoke this skill explicitly — it only fires on triggers/paths.

## Writing a Good `description`

The description is the skill's ad copy. If the agent doesn't understand WHEN to load it from the description, the skill never fires.

Template:

```
description: <One sentence stating the enforced discipline>. Use whenever <list of scenarios>. <One sentence on what it prevents or the leverage it provides>.
```

Example (good):

```yaml
description: Enforce first-fail triage, mock-at-the-boundary, and fixture-scope reasoning for pytest suites. Use when writing new tests, diagnosing failing tests, adding a fixture, or mocking an external dependency. Prevents testing implementation details, leaking state across tests, mocking too deep, and drowning in 60-failure runs where only the first 3 matter.
```

Example (bad):

```yaml
description: A skill about Python testing best practices.
```

The second one tells the agent nothing about WHEN it applies.

## Choosing Triggers

Triggers are matched as substrings against the run context (case-insensitive in most implementations, but write them lowercased for portability). The SDK does not tokenize — `"json"` triggers on `"json"`, `"jsonl"`, `"jsonify"`, etc.

### Rules

1. **Single-token triggers beat multi-word phrases.** `"pytest"` fires more reliably than `"pytest test"`.
2. **Include class names, error strings, and function names the agent will actually see** in tracebacks and tool outputs.
3. **Avoid words too common to be useful.** `"error"` fires in almost every session and is a useless trigger — pair it with something specific if you must include it.
4. **Include synonyms.** `"failing"`, `"broken"`, `"crashed"`, `"not working"` should all trigger a debugging skill.
5. **6–15 triggers is a good range.** Fewer than 4 → too narrow. More than 20 → the description is doing the work anyway.
6. **Test triggers against real sessions.** If the skill isn't firing on tasks where it should, look at what words the agent actually sees and add them.

### Trigger Selection by Skill Type

| Skill type | Trigger examples |
|---|---|
| Language / framework | `pytest`, `FastAPI`, `React`, `useQuery`, `zod` |
| Tool / CLI | `docker run`, `git commit`, `pip install`, `curl` |
| Domain concept | `benchmark`, `quantization`, `hydration`, `idempotency` |
| Error class | `ImportError`, `TypeError`, `ConnectionError`, `CUDA out of memory` |
| File / path | `SKILL.md`, `.env`, `BUILD_LOG`, `Dockerfile` |

### Path-Based Firing

For skills that only apply when specific files are being edited:

```yaml
paths: bff/routers/*.py, src/features/**/*.ts
```

`paths` fires on file-edit events. `triggers` fires on text-in-context matches. Path-based is more precise but only fires during file edits; trigger-based fires broadly.

Use paths when: the skill is about ONE specific area of the codebase.
Use triggers when: the skill is domain / concept oriented and could apply anywhere.

## Structural Template

Every skill body follows this shape:

```markdown
# <Human Title>

<One-line purpose sentence.>

## When to Use This Skill

<Bullet the exact scenarios. Match the description's "use whenever" list.>

## Non-Negotiable Rules / Hard Rules

<Numbered list of the 3–7 rules the skill enforces. Each rule = one line, one concept.>

## <Domain-specific sections>

<Rules → Examples → Explanations. Not the other way around.>

## Anti-Patterns

<Bullet list of things NOT to do. Each starts with ❌.>

## Checklist

<Numbered actionable steps for applying the skill.>
```

### Rules go BEFORE examples

Bad:
> Here's a long story about a bug we hit last week. Anyway, the point is, don't do X.

Good:
> Never do X. Reason: <one line>. Example of what happens if you do:
> ```code showing the failure```

Rules-first respects the agent's context budget. If the agent trims your skill, it should still get the rules.

### Show, don't lecture

```markdown
✅ Good — shows both patterns side by side

```python
# ❌ Blocking call in async endpoint
async def bad():
    result = requests.get(url)   # blocks the event loop

# ✅ Async client
async def good():
    async with httpx.AsyncClient() as c:
        result = await c.get(url)
```
```

## Length Discipline

- **Sweet spot**: 150–350 lines of Markdown
- **Under 50 lines**: probably too vague; skill won't have enough content to be useful
- **Over 500 lines**: probably too broad; split into 2 skills, or move detail into `references/`

## Testing a New Skill

### 1. Verify frontmatter parses

```bash
python -c "import frontmatter; print(frontmatter.load('SKILL.md').metadata)"
```

Should print a dict with `name`, `description`, `triggers`. If it errors, YAML is broken (usually indentation or unquoted colons).

### 2. Install and check it loads

```bash
# User scope
mkdir -p ~/.agents/skills/my-skill
cp SKILL.md ~/.agents/skills/my-skill/SKILL.md

# Verify agent-server sees it
curl -sf -X POST http://127.0.0.1:8090/api/skills \
  -H 'Content-Type: application/json' \
  -d '{"load_public":false,"load_user":true,"load_project":false,"load_org":false}' \
  | jq '.skills[] | select(.name=="my-skill") | {name, triggers, source}'
```

Should print your skill's metadata. If `null`, either the file is missing, the frontmatter didn't parse, or the SDK is looking in a different directory.

### 3. Verify it fires

Run a task that mentions one of the triggers. Check the run's `activated_skills` list. If your skill isn't there, the trigger didn't match — usually because the word is different from what appears in context.

## Install Locations

| Scope | Location | Who benefits |
|---|---|---|
| User | `~/.agents/skills/{name}/SKILL.md` | You, across all projects |
| Project | `{workspace}/.agents/skills/{name}/SKILL.md` | Anyone working on this repo |
| Installed marketplace | `~/.openhands/skills/installed/{name}/` | You, but managed via `/api/skills/install` |

The SDK docstring says "Use .agents/skills for new skills. .openhands/skills is the legacy OpenHands path." Follow this: use `.agents/skills/` for anything you author fresh.

## When to Create a New Skill vs Edit an Existing One

**Create new** when:
- The topic doesn't overlap with any existing skill's description
- The triggers would be substantially different
- Combining would push the existing skill over 500 lines

**Edit existing** when:
- The new content is a natural extension of an existing skill
- The new triggers should still fire the same skill
- The existing skill's description already covers the scenario

**Never** create a second skill covering the same domain from a different angle. The agent will load both and burn context. Merge instead.

## Anti-Patterns

- ❌ Vague `description` that doesn't say WHEN to use the skill
- ❌ 1–2 triggers only (skill rarely fires)
- ❌ Triggers so broad they fire in unrelated contexts (`error`, `code`, `run` alone)
- ❌ Skills that duplicate another skill's coverage
- ❌ Skills over 500 lines (too broad — split)
- ❌ Skills under 50 lines (too vague — expand or delete)
- ❌ Body is all prose, no rules, no examples
- ❌ Examples without labeled ✅/❌ (agent can't tell which is the recommended pattern)
- ❌ Missing "Anti-Patterns" section
- ❌ Frontmatter with unquoted colons or unquoted strings starting with `!` or `&`
- ❌ Storing frontmatter fields the SDK doesn't recognize (they're preserved but do nothing)
- ❌ Skills that describe tools the agent doesn't have access to
- ❌ Auto-generating skills without human review (see: skill-proposal-pipeline in Forge-OH backlog)

## Checklist for a New Skill

1. Kebab-case name matches directory name
2. Description has both WHAT and WHEN
3. 6–15 triggers, covering error class names, tool names, and domain words
4. Frontmatter parses cleanly (verify with the frontmatter Python lib)
5. Body follows the template: When-to-use → Rules → Examples → Anti-Patterns → Checklist
6. Rules come before examples
7. Anti-Patterns section is present and honest
8. Length is 150–350 lines
9. Installed to the right scope (user vs project)
10. Verified to appear in `POST /api/skills` response
11. Verified to fire in a test run whose task mentions a trigger

## References

- SDK source: `openhands/sdk/skills/skill.py` — the `Skill.load()` method shows exactly what fields are parsed and how
- Example: `~/.openhands/cache/skills/public-skills/skills/add-javadoc/SKILL.md` — canonical minimal format
- Backlog: `~/dev/forge-oh/proposed-skills/BACKLOG.md` (or wherever this repo lives) — future skills + skill-proposal-pipeline feature
