# BMAD Core Index

This directory contains all BMAD agent definitions, tasks, templates, checklists, and knowledge base files for the Jireh project.

## Structure

```
.bmad-core/
  agents/          — Agent persona definitions
  tasks/           — Reusable task definitions
  templates/       — Document templates
  checklists/      — Quality checklists
  data/            — Knowledge base and reference data
  index.md         — This file
```

## Agents
- [analyst](agents/analyst.md) — Mary, Business Analyst
- [architect](agents/architect.md) — Winston, Solution Architect
- [dev](agents/dev.md) — James, Senior Developer
- [pm](agents/pm.md) — Michael, Product Manager
- [po](agents/po.md) — Sarah, Product Owner
- [qa](agents/qa.md) — Quinn, QA Engineer
- [resume-agent](agents/resume-agent.md) — Ria, Career Intelligence & Resume Specialist
- [sm](agents/sm.md) — Alex, Scrum Master
- [ux-expert](agents/ux-expert.md) — Aria, UX Designer
- [bmad-master](agents/bmad-master.md) — BMad, Universal Expert
- [bmad-orchestrator](agents/bmad-orchestrator.md) — Orchestrator

## Tasks
- [ats-check](tasks/ats-check.md) — ATS keyword gap analysis and score
- [create-doc](tasks/create-doc.md)
- [document-project](tasks/document-project.md)
- [execute-checklist](tasks/execute-checklist.md)
- [resume-review](tasks/resume-review.md) — scored 6-dimension resume critique
- [resume-to-form](tasks/resume-to-form.md) — extract profile YAML from resume text
- [resume-write](tasks/resume-write.md) — guided resume writing/rewriting
- [shard-doc](tasks/shard-doc.md)

## Templates
- [project-brief](templates/project-brief.md)
- [prd](templates/prd.md)
- [architecture-doc](templates/architecture-doc.md)
- [user-story](templates/user-story.md)
- [test-plan](templates/test-plan.md)

## Checklists
- [story-dod](checklists/story-dod.md)
- [architecture-review](checklists/architecture-review.md)
- [pr-review](checklists/pr-review.md)

## Knowledge Base
- [bmad-kb](data/bmad-kb.md)
