# Target User

## Primary: Rigpa-LMS Instructor / Course Author

- **Role**: Creating coding exercises, reviewing student submissions, authoring lesson content
- **Technical level**: Comfortable with code, not a full-stack engineer
- **Primary need**: Supervise AI agents doing pedagogical content work without getting lost in raw LLM output
- **Key frustration**: Agents that loop silently, make invisible changes, or produce outputs that don't fit the LMS

## Secondary: Software Developer (standalone use)

- **Role**: Using Forge-OH as a standalone code agent supervision console
- **Technical level**: Developer-grade; reads diffs, understands git, reviews PRs
- **Primary need**: See what the agent is doing, pause/approve/reject steps, export artifacts

## Design Implications

- Supervision-first: the most important action is always visible and one click away
- Status is conveyed by text + icon, never color alone (accessibility)
- Approval banners are full-width, amber, unmissable — never buried in the event stream
