# Task: resume-write

## Purpose
Guide the user through writing or substantially improving a resume, section by section. Every output is Markdown-formatted and directly compatible with Nexus resume files (`resume_path_a.md` / `resume_path_b.md`).

## Inputs Required
1. **Target role** — what role/path is this resume for? (Path A stretch role or Path B primary?)
2. **Current resume** (optional) — existing text to improve. If not provided, build from scratch.
3. **Key career highlights** — if building from scratch, ask for 3–5 bullet points per role before writing

If starting from scratch, run the intake interview in Step 1. If improving an existing resume, skip to Step 3.

## Steps

### Step 1 — Intake Interview (scratch only)
Ask these questions one group at a time. Do not fire all at once.

**Group A — Target & Positioning:**
1. What is the target role title? (e.g. "Senior QE Manager at a Series B fintech")
2. What is your biggest differentiator from other candidates at this level?
3. What outcome are you most proud of in the last 3 years?

**Group B — Experience (per role, most recent first):**
For each role:
- Company name, your title, dates (start–end or "present"), location
- Team size you led / scope (budget, geography, product lines)
- 3 biggest things you shipped, fixed, or changed — with numbers if possible
- Any promotions, recognition, or notable outcomes

**Group C — Skills & Tools:**
- Primary automation tools/frameworks
- Languages (with proficiency: advanced / proficient / familiar)
- Cloud/DevOps stack
- Certifications

**Group D — Education:**
- Degree, institution, year (only if < 10 years ago or prestigious)

### Step 2 — Draft Outline
Before writing, present a one-line outline of every section and ask the user to confirm or adjust.

### Step 3 — Write / Rewrite Section by Section
Process in this order:
1. **Contact & Header**
2. **Professional Summary**
3. **Core Competencies** (keyword-dense, scannable)
4. **Experience** (each role)
5. **Technical Stack**
6. **Education & Certifications**

For each section, present the draft and ask for approval before moving to the next.

#### Writing Rules

**Summary:**
- Max 4 sentences
- Open with: seniority + domain + years
- Include 1–2 concrete outcomes from career
- Close with value proposition to employer (what you bring, not what you want)
- No "results-driven", "passionate", "dynamic" — ban list applies

**Experience bullets — CAR format:**
```
[Context/Scope] + [Action] + [Result with metric]
```
Examples:
- ✅ "Led 8-engineer QE team across 3 squads; introduced shift-left gates that cut defect escape rate 40% in 12 months."
- ❌ "Responsible for managing QA team and improving quality."

Rules:
- 4–6 bullets per role (not more — quality over quantity)
- Lead each bullet with a strong past-tense verb (see verb bank below)
- Every bullet should answer: "So what?" — what changed because of your work?
- At least 3 of 4 bullets must contain a metric

**Power verb bank by function:**
| Function | Verbs |
|----------|-------|
| Leadership | Led, Built, Scaled, Hired, Mentored, Grew, Championed |
| Strategy | Defined, Established, Designed, Architected, Drove, Owned |
| Execution | Delivered, Shipped, Launched, Implemented, Reduced, Cut |
| Improvement | Improved, Optimised, Accelerated, Streamlined, Transformed |
| Collaboration | Partnered, Aligned, Coordinated, Influenced, Facilitated |

**Technical Stack section:**
- Group by category: Automation | Languages | CI/CD | Performance | Observability | Cloud | Domains
- One line per category, comma-separated tools
- No ratings or percentages — just tool names

### Step 4 — Full Draft Assembly
After all sections are approved, assemble the complete resume in Markdown. Apply:
- Consistent heading levels (`##` for sections, `###` for roles)
- Bold for company name and title
- Dates right-aligned via em dash: `Company Name *(Date – Date)*`
- Horizontal rules (`---`) between major sections

### Step 5 — Self-Review Checklist
Before presenting the final draft, check:
- [ ] Every role has: title, company, date range, location
- [ ] Summary is ≤ 4 sentences and contains a metric
- [ ] At least 75% of bullets have a measurable outcome
- [ ] No first-person pronouns ("I", "my", "me")
- [ ] No present tense for past roles
- [ ] Skills section has explicit tool names, not categories only
- [ ] Total length: 1 page for < 10 years experience, 2 pages for 10+ years

### Step 6 — Output and Save Instructions
Present the final resume in a markdown code block. Then:

```
### Save Instructions
- Path A (stretch/senior roles): resources/resumes/resume_path_a.md
- Path B (primary auto-apply): resources/resumes/resume_path_b.md

Or paste into the Nexus UI → Resumes page.

### Recommended Next Steps
1. Run `*ats-check` against your top target JD to verify keyword coverage
2. Run `*review` to get a scored quality check
3. Run `*resume-to-form` to sync extracted skills to your Nexus profile
```