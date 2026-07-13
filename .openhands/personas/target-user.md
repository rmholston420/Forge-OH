# Target User Persona

## Primary: The Independent Developer / LMS Builder

**Name:** Independent developer building or extending a learning management system.

**Context:**
- Working on a local machine with Ollama running Devstral or Qwen3.
- May not have reliable internet access or budget for cloud LLM APIs.
- Building Rigpa-LMS: a Tibetan Buddhist curriculum delivery platform.
- Values privacy: no source code leaves the local machine.

**Goals:**
- Delegate well-scoped coding tasks to the AI agent and review the results.
- See exactly what the agent did: file diffs, terminal output, browser snapshots.
- Approve agent actions before they are committed (human-in-the-loop).
- Track agent performance over time (token cost, loop detection, success rate).

**Pain Points:**
- Agents that loop indefinitely without detecting they're stuck.
- Tools that require cloud credentials or send code to external servers.
- UIs that hide what the agent is doing behind opaque "thinking" states.

**Success Looks Like:**
- Submitting a task, watching the event stream, approving a diff, committing.
- Zero cloud dependencies for a full coding session.
