---
name: planning
description: How to plan multi-step work before executing. Use whenever a task has 3+ steps, unclear dependencies, uncertain scope, or a risk of doing the wrong thing efficiently. Enforces problem framing, dependency ordering, stop-condition definition, and "when to plan vs jump in" judgment. Prevents wasting a session on the wrong branch of work.
license: MIT
triggers:
  - plan
  - action plan
  - approach
  - break down
  - task decomposition
  - roadmap
  - stop condition
  - definition of done
  - what should I do
  - "where do I start"
  - stage
  - milestone
  - dependency
  - sequencing
---

# Planning

Applies to any work with 3+ non-trivial steps, unclear scope, or risk of building the wrong thing.

## The Fundamental Question

**Am I planning, or am I stalling?**

Planning is high-leverage when:
- The task is unfamiliar
- Steps have dependencies (later steps assume earlier ones are done)
- The wrong first step wastes hours
- Multiple people (or agent sessions) will pick this up

Planning is stalling when:
- The task is a familiar pattern you've done before
- The first step is obvious and cheap
- You're planning to avoid the discomfort of starting

Ask yourself: would 30 seconds of planning save 30 minutes of misdirection? If yes, plan. If not, start.

## When to Use This Skill

- Task has 3+ steps with dependencies
- Requirements are ambiguous
- You've been asked "what's your plan?" or "outline the approach"
- Multi-session work (need to hand off)
- Building something you can't test end-to-end in one action
- Coordinating with humans or other agents on the same repo

**Do NOT use** for:
- Single-tool tasks (search, read a file, fix a typo)
- Well-understood patterns you've executed many times
- Time-critical fixes where iterating beats planning

## Plan Structure

A good plan has four parts:

### 1. Framing — What am I actually building?

One paragraph. Anyone reading it should understand the scope in 30 seconds.

Include:
- **Goal**: what state does the world need to be in when this is done?
- **Non-goals**: what's out of scope? (this is often more important than goals)
- **Success criteria**: how do you know it's done?

Bad framing:
> "Fix the skills page."

Good framing:
> "Build a Skills/Microagents page at /skills that lists all skills from POST /api/skills, filterable by source (public/user/project/org) and status (active/registered). Success = user can see the 78 currently-loaded skills, filter them, and click one to see its content. Non-goals: editing skills in the UI, uploading new skills (both later)."

### 2. Approach — What's the shape of the solution?

Not code. Not the implementation. The shape.

- What data do we need?
- Where does it come from?
- What does the user see?
- What's the interaction model?

Example:
> Fetch /api/skills once on page load → cache in React Query → render a table with search/filter → clicking a row opens a side panel with skill content.

If you can't answer these in 2–3 sentences, either the task isn't well-defined enough to plan, or the design isn't decided yet.

### 3. Steps — Ordered, with dependencies

Numbered list. Each step:
- One deliverable
- Verifiable (you know when it's done)
- 5 min – 2 hours of work (any bigger = decompose)

```markdown
1. Verify POST /api/skills returns what we expect (probe the endpoint, log the shape)
2. Add BFF router bff/routers/skills.py forwarding to :8090
3. Add FE schema src/lib/schemas/skill.ts
4. Add endpoint constant src/lib/api/endpoints.ts
5. Build page src/app/skills/page.tsx (fetch + table)
6. Add sidebar nav link
7. Playwright visual check
8. Commit + push
```

Dependencies matter: step 2 requires 1 (need to know the shape). Step 5 requires 2, 3, 4. Order accordingly.

**Verify order before finalizing**: dependencies come first, no later step contradicts or undoes an earlier step. If the plan changes mid-work, revise the plan document — don't just do the new thing while the old plan lies around.

### 4. Stop Condition

The single hardest part. What is the ONE thing that means "done"?

- Too vague: "The skills page works"
- Better: "Skills page renders the /api/skills response, filters function on source and status, and Playwright screenshot shows all filter chips + at least one skill row"
- Best: "All of the above AND the Playwright screenshot committed AND BUILD_LOG updated AND commit pushed"

If you can't state the stop condition in one paragraph, the scope isn't clear enough to plan.

## Plan Formats

### Inline plan (for chat / short-lived work)

Bullet list. Ordered. No formal structure. Good for 30 min – 2 hour tasks.

### Written plan (for multi-session or handoff work)

Markdown document committed to the repo. Sections: Framing, Approach, Steps, Stop Condition, Open Questions. Persists across sessions.

Example filename pattern: `docs/planning/<topic>-plan-v<n>.md`

### ADR (for architectural decisions)

Different from a plan — an ADR captures a decision and its consequences. Use ADR when the plan requires committing to a design that affects other future work. See `kosmos-adr-authoring` or the project's ADR template.

## Common Failure Modes

### Planning too far ahead

Plans decay. A 30-step plan usually has 15 steps that will be revised before you get to them. Plan the next 3–5 steps concretely; sketch the rest.

### Planning too shallow

"Step 1: build the thing" isn't a plan. If a step is > 2 hours, decompose it.

### Not identifying dependencies

The plan lists 10 steps in random order. Halfway through, step 8 turns out to need something from step 3, but step 3 was skipped as "obvious". Result: rework.

Fix: after writing steps, ask "what does step N need? Was it produced by an earlier step?"

### Skipping "what's the stop condition"

Symptom: work drifts. You keep adding polish. You've been "almost done" for 2 hours.

Fix: define stop condition BEFORE starting. When it's met, ship. Polish goes on the backlog.

### Planning as procrastination

Symptom: 3 hours in, you have a beautiful plan and no code.

Fix: after 20% of the total time budget on planning, start. Refine the plan as you go.

### Not planning at all

Symptom: 3 hours in, you have code that solves the wrong problem.

Fix: 5 minutes of framing before the first line of code.

## Micro-Planning During Work

Even without a formal plan document, ask yourself before each new action:

1. What am I trying to accomplish with this action?
2. Is this the right action to take next?
3. What would I do differently if the last action had gone wrong?

This is planning at the tactical level. It's cheap. It prevents drift.

## When Plans Change

Plans WILL change. That's fine. When they do:

1. Update the plan document (or the todo list)
2. Note WHY the plan changed (usually one line — "discovered X, so Y is now needed before Z")
3. If the change means earlier work is invalidated, explicitly mark what to undo/redo
4. Never leave two contradictory plans lying around — supersede the old one

## Anti-Patterns

- ❌ Starting with code before you can state the goal in one sentence
- ❌ Plans without dependencies (steps look ordered but aren't)
- ❌ Plans without stop conditions (work drifts forever)
- ❌ Plans that specify how to do trivial steps (`open the file, add the import` — waste of tokens)
- ❌ Plans that skip past hard steps (`build the algorithm` as one bullet)
- ❌ Plans in your head that no one else can see (multi-session work needs written plans)
- ❌ Planning for hours to avoid starting
- ❌ Refusing to revise a plan when reality contradicts it
- ❌ Two plans in the repo saying different things

## Checklist Before Starting Work

1. Can I state the goal in one sentence?
2. Do I know what's out of scope?
3. Do I know the stop condition?
4. Have I listed the 3–5 next steps concretely?
5. For each step, do I know what it produces and what it depends on?
6. Have I identified any risky / unknown step and thought about how to de-risk it?
7. Have I committed the plan somewhere visible (chat, doc, todo list)?
8. Am I actually going to start now, or am I still planning?
