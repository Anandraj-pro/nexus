# Task: resume-to-form

## Purpose
Parse a resume and extract structured profile data in the exact format Nexus config files expect. The output is copy-pasteable YAML blocks for `skills_profile.yaml`, ready to replace or merge with the existing file.

## Inputs Required
1. **Resume text** — paste the full resume, provide a file path, or confirm use of `resources/resumes/resume_path_b.md`

If not provided, prompt the user.

## Steps

### Step 1 — Extract Personal Profile
From the resume, extract:

| Field | Source hint |
|-------|------------|
| `name` | First heading or top line |
| `title` | Most recent job title |
| `location` | Address / location line near contact info |
| `email` | Contact section |
| `phone` | Contact section (include country code) |
| `experience_years` | Sum of role durations, or explicit "X years" statement |
| `summary` | Summary/objective section, or synthesise from career arc if absent |

### Step 2 — Extract Preferred Locations
Look for:
- Current city (from contact block or most recent role location)
- Remote/hybrid indicators ("Remote OK", "open to remote", "hybrid")
- Relocation signals ("willing to relocate", "open to relocation")

### Step 3 — Infer Skill Ratings (1–10)
For each Nexus skill, rate based on resume evidence:

**Rating scale:**
- **9–10**: Named as a core competency AND appears in 3+ role bullets with specific outcomes
- **7–8**: Explicitly mentioned in bullets with some context or outcome
- **5–6**: Mentioned once or implied by adjacent skills
- **3–4**: Role type implies it but not explicitly named
- **1–2**: Not found; infer only if the role makes it impossible to have lacked it

**Skill categories and what to look for:**

| Category | Skill | Look for in resume |
|----------|-------|-------------------|
| leadership | team_building | "built team", "hired", "grew team", headcount numbers |
| leadership | strategy | "quality strategy", "roadmap", "OKR", "executive" |
| leadership | stakeholder_management | "stakeholder", "exec reporting", "alignment" |
| leadership | cross_functional | "cross-functional", "PM", "product", "engineering partner" |
| leadership | agile_scrum | "agile", "scrum", "sprint", "kanban", "SAFe" |
| qa_engineering | test_automation | "automation", "framework", "test architecture" |
| qa_engineering | api_testing | "API", "REST", "GraphQL", "Postman", "REST Assured" |
| qa_engineering | ui_automation | "Selenium", "Playwright", "Cypress", "Appium", "UI test" |
| qa_engineering | performance_testing | "JMeter", "k6", "Gatling", "load test", "performance" |
| qa_engineering | shift_left | "shift-left", "TDD", "BDD", "ATDD", "Pact", "contract test" |
| cicd_devops | cicd_pipeline | "CI/CD", "pipeline", "Jenkins", "GitHub Actions", "continuous" |
| cicd_devops | github_actions | "GitHub Actions", "GHA", "workflow" |
| cicd_devops | docker | "Docker", "container", "Kubernetes", "k8s" |
| cicd_devops | aws | "AWS", "EC2", "S3", "Lambda", "Azure", "GCP", "cloud" |
| tools | selenium | "Selenium", "WebDriver" |
| tools | pytest | "pytest", "unittest" |
| tools | jira | "Jira", "issue tracking", "ticket" |
| tools | postman | "Postman", "API client" |
| languages | python | "Python" |
| languages | java | "Java", "Maven", "TestNG" |
| languages | sql | "SQL", "database", "query" |
| soft_skills | communication | "presentation", "stakeholder", "exec", "report" |
| soft_skills | mentoring | "mentor", "coach", "career development", "grew engineers" |

### Step 4 — Validate and Clarify
Before outputting, flag any fields where confidence is low:
- If experience_years cannot be calculated, ask the user
- If email/phone not found, note it as missing
- If location is ambiguous, note it

### Step 5 — Generate YAML Output

Output three blocks:

**Block A** — `profile:` section for `skills_profile.yaml`
**Block B** — `skills:` section for `skills_profile.yaml`
**Block C** — Environment variable summary for `.env`

## Output Format

````
## Resume → Nexus Config Extraction

### Confidence Summary
| Field | Value | Confidence |
|-------|-------|------------|
| name | ... | High / Medium / Low |
| email | ... | ... |
| phone | ... | ... |
| title | ... | ... |
| location | ... | ... |
| experience_years | ... | ... |

---

### Block A — Paste into `resources/skills/skills_profile.yaml` (profile section)

```yaml
profile:
  name: "..."
  title: "..."
  location: "..."
  experience_years: X
  email: "..."

summary: >
  ...

preferences:
  preferred_locations: ["...", "Remote"]
  remote_ok: true
  relocation_ok: false
  notice_period_days: 30
```

---

### Block B — Paste into `resources/skills/skills_profile.yaml` (skills section)

```yaml
leadership:
  team_building:
    rating: X
    keywords: ["team building", "hiring", "QA org"]
  strategy:
    rating: X
    keywords: ["quality strategy", "test strategy", "QA roadmap"]
  stakeholder_management:
    rating: X
    keywords: ["stakeholder", "executive reporting", "OKR"]
  cross_functional:
    rating: X
    keywords: ["cross-functional", "PM alignment"]
  agile_scrum:
    rating: X
    keywords: ["agile", "scrum", "sprint", "kanban"]

qa_engineering:
  test_automation:
    rating: X
    keywords: ["automation architecture", "test framework"]
  api_testing:
    rating: X
    keywords: ["API testing", "REST", "GraphQL", "Postman"]
  ui_automation:
    rating: X
    keywords: ["UI automation", "Selenium", "Playwright", "Cypress"]
  performance_testing:
    rating: X
    keywords: ["performance testing", "load testing", "JMeter", "k6"]
  shift_left:
    rating: X
    keywords: ["shift-left", "TDD", "BDD", "ATDD"]

cicd_devops:
  cicd_pipeline:
    rating: X
    keywords: ["CI/CD", "pipeline", "continuous integration"]
  github_actions:
    rating: X
    keywords: ["GitHub Actions", "workflow"]
  docker:
    rating: X
    keywords: ["Docker", "containerization"]
  aws:
    rating: X
    keywords: ["AWS", "cloud"]

tools:
  selenium:
    rating: X
    keywords: ["Selenium", "WebDriver"]
  pytest:
    rating: X
    keywords: ["pytest", "Python testing"]
  jira:
    rating: X
    keywords: ["Jira", "issue tracking"]
  postman:
    rating: X
    keywords: ["Postman", "API client"]

languages:
  python:
    rating: X
    keywords: ["Python", "scripting"]
  java:
    rating: X
    keywords: ["Java", "Maven"]
  sql:
    rating: X
    keywords: ["SQL", "database testing"]

soft_skills:
  communication:
    rating: X
    keywords: ["communication", "presentation", "stakeholder"]
  mentoring:
    rating: X
    keywords: ["mentoring", "coaching", "career development"]
```

---

### Block C — Environment variables for `.env`

```
CANDIDATE_NAME=...
CANDIDATE_EMAIL=...
CANDIDATE_PHONE=...
```

---

### Next Steps
1. Copy Block A + Block B into `resources/skills/skills_profile.yaml`
2. Copy Block C values into your `.env` file (or use the Nexus UI → Profile page)
3. Run `python orchestrator.py run --dry-run` to validate the scorer picks up the updated profile
4. Run `*review` or `*ats-check` on this resume for quality feedback
````