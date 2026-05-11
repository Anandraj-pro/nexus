# Task: ats-check

## Purpose
Check a resume for ATS (Applicant Tracking System) compatibility against a specific job description. Identify keyword gaps, formatting risks, and structural issues that cause ATS rejection before a human ever reads the resume.

## Inputs Required
1. **Job description** — full text of the target JD (paste or file path)
2. **Resume** — full resume text (paste, file path, or use `resources/resumes/resume_path_b.md`)

If either is missing, prompt the user before proceeding.

## Steps

### Step 1 — Parse the JD
Extract from the job description:
- **Required skills** (must-have, often in "Requirements" or "Qualifications")
- **Preferred skills** (nice-to-have, often in "Preferred" or "Bonus")
- **Key role verbs** (e.g. "lead", "architect", "mentor", "own")
- **Domain keywords** (industry, product type, compliance frameworks)
- **Seniority signals** (years of experience, level language like "senior", "principal", "director")
- **Company/team context** (size, stack, methodology)

### Step 2 — Parse the Resume
Extract from the resume:
- Skills and tools explicitly named
- Role titles and seniority progression
- Domains and industries worked in
- Certifications and education
- Years of experience (total and per role)

### Step 3 — Keyword Gap Analysis
Build a three-column table:

| Keyword / Skill | In JD? | In Resume? |
|-----------------|--------|------------|
| [term]          | ✅ Required | ✅ Present |
| [term]          | ✅ Required | ❌ Missing |
| [term]          | ⭐ Preferred | ✅ Present |
| [term]          | ⭐ Preferred | ❌ Missing |

Compute:
- **Required match %** = (required terms present / total required) × 100
- **Preferred match %** = (preferred terms present / total preferred) × 100

### Step 4 — ATS Score (0–100)
Score using these weights:

| Dimension | Weight | Score basis |
|-----------|--------|-------------|
| Required keyword match | 40% | Match % from Step 3 |
| Preferred keyword match | 15% | Match % from Step 3 |
| Formatting safety | 20% | Penalty per risk flag (see below) |
| Structure compliance | 15% | Section presence and order |
| Quantification | 10% | % of experience bullets with a metric |

**Formatting risk flags** (−5 pts each):
- Multi-column layout
- Tables in experience section
- Headers/footers with contact info
- Embedded graphics or logos
- Non-standard section names (e.g. "My Journey" instead of "Experience")
- Missing standard sections (Contact, Summary/Objective, Experience, Skills, Education)

### Step 5 — Quick Wins
List the top 5 highest-impact changes, ordered by ATS score improvement:

For each quick win:
- What to add/change
- Where in the resume (which section, which bullet)
- Example: exact text to insert or reword
- Estimated score impact (+N pts)

### Step 6 — Formatting Audit
Explicitly list every formatting risk found, with the specific element and why it causes ATS problems.

If no risks found, say so clearly.

## Output Format

```
## ATS Compatibility Report

**Target Role:** [title from JD]
**ATS Score: XX/100**

### Keyword Match
Required: X/Y matched (XX%)
Preferred: X/Y matched (XX%)

[keyword gap table]

### Score Breakdown
[dimension table with scores]

### Formatting Risks
[list or "None detected"]

### Top 5 Quick Wins
1. ...
2. ...
3. ...
4. ...
5. ...

### Nexus Config Update
Update `scoring_signals` in `resources/config/career_paths.yaml`:
- Add to strong_positive: [list missing high-value keywords to target in future searches]
```

## Notes
- Focus on keywords as they appear in the JD — exact match matters more than synonyms for most ATS
- Tailor the quick wins to be directly actionable, not generic advice
- If the resume already scores above 80, say so and shift focus to the remaining gaps only