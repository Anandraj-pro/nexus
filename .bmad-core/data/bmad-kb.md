# BMAD Method Knowledge Base

## What is BMAD?
BMAD (Better Method for Agile Development) is a structured AI-assisted development workflow. It uses specialised AI personas (agents) to guide a project through each phase of the software development lifecycle, from initial research through deployment.

## Core Philosophy
- Each phase of development has a dedicated expert persona
- Work flows sequentially through the BMAD workflow (but can loop back)
- Every deliverable is a concrete document that feeds the next phase
- Quality is enforced through checklists at key transitions

## The Standard BMAD Workflow
```
Analyst -> PM -> Architect -> UX Expert -> PO -> Dev -> QA -> SM
```

## Agents

| Agent | Persona | Key Output |
|-------|---------|------------|
| analyst | Mary | Project Brief, Research Reports |
| architect | Winston | Architecture Doc, ADRs |
| dev | James | Code, Tests, Implementation Plans |
| pm | Michael | PRD, Roadmap |
| po | Sarah | User Stories, Epics, Sprint Plans |
| qa | Quinn | Test Plans, Bug Reports, QA Checklists |
| sm | Alex | Sprint ceremonies, Retrospectives |
| ux-expert | Aria | User Flows, Wireframe Specs, Design System |
| bmad-master | BMad | Anything — universal expert |
| bmad-orchestrator | Orchestrator | Multi-agent workflow coordination |

## How to Invoke an Agent
In Claude Code, start your message with the agent name or say "Act as [agent name]". For example:
- "Act as the analyst. I want to research..."
- "Switch to architect mode..."
- "As the dev agent, implement..."

Or use the BMAD commands:
- `*task {task name}` to execute a predefined task
- `*create-doc {template name}` to start a document from a template
- `*execute-checklist {checklist name}` to run a quality checklist

## Key Documents
| Document | Created By | Template |
|----------|-----------|----------|
| Project Brief | Analyst | project-brief.md |
| PRD | PM | prd.md |
| Architecture Doc | Architect | architecture-doc.md |
| User Story | PO | user-story.md |
| Test Plan | QA | test-plan.md |

## Checklists
| Checklist | Used By | When |
|-----------|---------|------|
| story-dod | PO / Dev | Before marking a story Done |
| architecture-review | Architect | Before finalising arch doc |
| pr-review | Dev | During code review |

## Tips for Python Projects
- The dev agent defaults to pytest for testing
- Use type hints; the dev agent will enforce them
- Architecture docs should specify Python version and package manager
- The QA agent will check for PEP 8 compliance by default
