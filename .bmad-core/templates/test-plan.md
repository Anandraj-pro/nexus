# Test Plan: {FEATURE_OR_SPRINT_NAME}

## Scope
{What is being tested and what is out of scope}

## Test Approach
| Level | Tool | Coverage Target |
|-------|------|----------------|
| Unit | pytest | 80%+ |
| Integration | pytest | Key flows |
| E2E | {tool} | Critical paths |
| Manual | QA checklist | Edge cases |

## Test Environments
- **Dev**: local
- **Staging**: {URL or description}

## Entry Criteria
- [ ] Code complete and in staging
- [ ] All unit tests passing in CI
- [ ] Build green

## Exit Criteria
- [ ] All P0/P1 test cases passing
- [ ] No open critical or major defects
- [ ] Coverage targets met
- [ ] PO sign-off

## Test Cases

### Feature: {Feature Name}
| ID | Description | Steps | Expected Result | Priority |
|----|-------------|-------|-----------------|----------|
| TC-001 | {description} | 1. {step} | {expected} | P0 |

## Risks
- {risk and mitigation}

## Schedule
| Activity | Start | End | Owner |
|----------|-------|-----|-------|
| Test case design | | | |
| Test execution | | | |
| Bug fix verification | | | |
| Sign-off | | | |
