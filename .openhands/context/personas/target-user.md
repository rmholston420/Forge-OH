# Target User Persona — Forge-OH

## Primary: The Supervising Developer

**Name**: Alex  
**Role**: Senior software engineer or technical lead  
**Context**: Working on a complex, multi-file codebase with AI assistance

**Goals**:
- Delegate well-scoped programming tasks to an autonomous agent
- Maintain clear visibility into what the agent is doing at all times
- Intervene quickly when the agent goes off-course or loops
- Review and approve file changes before they land in the codebase
- Export clean artifacts (patches, reports) for PR review

**Pain points with existing tools**:
- Agent tools are either too opaque (black box execution) or too verbose (raw JSON logs)
- No clear way to pause, inspect, and redirect a running agent
- Approval flows are buried or missing
- No persistent memory across sessions — agent re-learns the same context every time

**What Forge-OH gives Alex**:
- Summary-first event stream: understands what happened without reading raw logs
- Plan rail: knows exactly which step the agent is on and what's next
- Approval banners: unmissable, actionable, never buried
- Loop guard: automatic escalation before the agent wastes 20 iterations
- Episodic memory: agent remembers past decisions, failed approaches, and project conventions

## Secondary: The LMS Student (Rigpa-LMS Context)

**Name**: Sam  
**Role**: Student in a software engineering or AI course  
**Context**: Working on course projects with an embedded AI coding assistant

**Goals**:
- Get meaningful coding help on assignments without just getting the answer
- Understand what the AI agent did and why
- Submit artifact bundles (patches, reports) that demonstrate learning

**What Forge-OH gives Sam**:
- Course ribbon showing current assignment context injected into every agent session
- Artifact packaging for assignment submission
- Learning-mode agent presets (explain-as-you-go, hint-first policies)
