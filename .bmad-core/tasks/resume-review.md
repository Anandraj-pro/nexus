# Task: resume-review

## Purpose
Deliver a comprehensive, scored critique of a resume across six quality dimensions. Every piece of feedback is tied to specific text in the resume — no generic advice. The output is a prioritised action plan the candidate can work through immediately.

## Inputs Required
1. **Resume** — full text (paste or file path). Default: `resources/resumes/resume_path_b.md`
2. **Target role** (optional) — if provided, calibrate feedback toward that role's expectations

If the resume is not provided, prompt before proceeding.

## Steps

### Step 1 — Read and Map
Read the full resume. Identify:
- Total sections present
- Number of roles / experience entries
- Number of bullets per role
- Which bullets contain a metric vs. which are action-only

### Step 2 — Score Each Dimension (1–10)

#### Dimension 1 — Impact & Quantification (weight: 25%)
- 10: Every bullet has a metric (%, $, time, scale, count)
- 7–9: Most bullets quantified; a few are weak
- 4–6: Some quantification; majority are action-only
- 1–3: Almost no metrics; reads like a job description not an achievement list

For each unquantified bullet, suggest a metric and rewrite.

#### Dimension 2 — Keyword Density & Relevance (weight: 20%)
- 10: Skills section covers the full stack for the target seniority; keywords appear naturally in bullets
- 7–9: Good coverage with minor gaps
- 4–6: Key tools/methods missing or only mentioned once
- 1–3: Sparse or wrong-level keywords for target role

List the top 5 missing keywords for the target seniority level.

#### Dimension 3 — Structure & Scannability (weight: 20%)
- 10: Clean order (Contact → Summary → Experience → Skills → Education); consistent formatting; each role has title, company, date, location
- 7–9: Minor inconsistencies
- 4–6: Missing elements or non-standard order
- 1–3: Hard to scan; inconsistent or missing role metadata

#### Dimension 4 — Summary Strength (weight: 15%)
- 10: Opens with seniority level + domain expertise + 1–2 unique differentiators + value to employer
- 7–9: Solid but misses one element
- 4–6: Generic ("results-driven professional…") or too long
- 1–3: Missing, vague, or reads like an objective statement

Provide a rewritten summary if score < 8.

#### Dimension 5 — Experience Depth (weight: 15%)
- 10: Every role has: scope (team size / budget / scale), key actions, measurable outcomes
- 7–9: Most roles cover all three; some thin
- 4–6: Scope missing from most roles; outcomes vague
- 1–3: Bullet lists of duties, no ownership or outcome

Pick the 2 weakest bullets and rewrite them with scope + action + outcome.

#### Dimension 6 — Skills Completeness (weight: 5%)
- 10: Explicit tools, languages, frameworks, methodologies, certifications all listed
- 7–9: Good but missing a sub-category
- 4–6: Too sparse or lumped together
- 1–3: No dedicated skills section or just a word cloud

### Step 3 — Overall Score
```
Overall = (D1×0.25 + D2×0.20 + D3×0.20 + D4×0.15 + D5×0.15 + D6×0.05) × 10
```
Map to a grade:
- 85–100: Strong — minor polish only
- 70–84: Good — targeted improvements needed
- 55–69: Fair — significant rework on 2–3 dimensions
- <55: Weak — needs a full rewrite session (`*resume`)

### Step 4 — Top 3 Priority Actions
Ordered by weighted score impact. Each action must include:
- Which dimension it addresses
- Exact text to change (quote the current text)
- Rewritten version
- Estimated score delta

## Output Format

```
## Resume Review — [Candidate Name]
**Target Role:** [if provided, else "General"]
**Overall Score: XX/100 — [Grade]**

### Score Card
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Impact & Quantification | X/10 | 25% | X.X |
| Keyword Density | X/10 | 20% | X.X |
| Structure & Scannability | X/10 | 20% | X.X |
| Summary Strength | X/10 | 15% | X.X |
| Experience Depth | X/10 | 15% | X.X |
| Skills Completeness | X/10 | 5% | X.X |

### Dimension Findings
[Detail per dimension with specific quotes from the resume]

### Top 3 Priority Actions
**Action 1 — [Dimension]: [Title]**
Current: "..."
Rewrite: "..."
Impact: +X pts

**Action 2 — ...**
**Action 3 — ...**

### What's Working Well
[2–3 specific strengths — be concrete, not generic]

### Next Steps
- If score < 70: run `*resume` to work through a section rewrite
- Update resume files: `resources/resumes/resume_path_a.md` / `resume_path_b.md`
- Run `*ats-check` against your top target JD to validate keyword coverage
```