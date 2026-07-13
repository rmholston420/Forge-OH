# Target User Persona: The Supervising Engineer

## Primary Persona: The Operator

**Name**: Maya  
**Role**: Senior software engineer or technical lead  
**Context**: Working on a complex, multi-day software project with an autonomous agent doing the heavy lifting

### Goals
- Launch agent runs without writing prompt boilerplate every time
- Stay informed about what the agent is doing without watching every event
- Catch loops, bad decisions, or risky changes before they compound
- Review and approve file diffs before they're committed
- Export artifacts (patches, reports) for review or handoff

### Pain Points
- Agent loops are invisible until they've wasted 30+ minutes of compute
- Event timelines are information dumps — hard to find what actually matters
- No way to inject project-specific constraints ("don't touch the auth layer")
- Multi-session tasks lose context — the agent re-discovers facts it already knew

### How Forge-OH Helps
- Loop guard surfaces repeated action patterns and escalates before wasted compute
- Summary-first event cards show what matters without expanding every raw event
- Context loader injects ADRs and conventions before each planning step
- Episodic memory persists key facts and decisions across sessions

## Secondary Persona: The Learner (Rigpa-LMS Context)

**Name**: Kenji  
**Role**: Student in a Rigpa-LMS coding course  
**Context**: Using Forge-OH as a pedagogical coding copilot embedded in the LMS

### Goals
- Understand what the agent is doing, not just accept its output
- Build mental models of software engineering practices through agent observation
- Get unstuck on exercises without being handed the answer

### How Forge-OH (Rigpa Layer) Helps
- Course ribbon shows learning objective context for each agent task
- Artifact packaging wraps agent output in reflection prompts
- Approval gates give learners decision points rather than passive observation
- Agent preset library includes "teaching mode" presets that explain decisions
