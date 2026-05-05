# Task: execute-checklist

## Purpose
Systematically work through a BMAD checklist, gathering evidence for each item, and producing a pass/fail report.

## Steps
1. If no checklist is specified, list available checklists from `.bmad-core/checklists/`
2. Load the requested checklist
3. For each item:
   a. State the checklist item clearly
   b. Gather evidence (ask the user, read files, or reason from context)
   c. Mark as PASS, FAIL, N/A, or NEEDS-REVIEW
   d. Note any action items for FAIL / NEEDS-REVIEW items
4. Produce a summary report with overall status
5. List all action items that need resolution

## Output Format
```
## Checklist: [Name]
### Summary
- Total items: N
- Passed: N
- Failed: N
- N/A: N
- Needs Review: N
- Overall Status: PASS / FAIL / PARTIAL

### Results
- [PASS] Item description
- [FAIL] Item description — Action: ...
- [N/A]  Item description
```
