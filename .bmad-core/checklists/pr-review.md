# Checklist: Pull Request Review

Use when reviewing any pull request.

## Context
- [ ] PR description explains what and why (not just what)
- [ ] Linked to the relevant story/ticket
- [ ] PR is appropriately sized (reviewable in < 60 minutes)

## Correctness
- [ ] Logic is correct for the stated requirements
- [ ] Acceptance criteria are met
- [ ] Edge cases handled
- [ ] Error cases handled gracefully

## Code Quality
- [ ] Code is readable without needing the author to explain it
- [ ] No unnecessary complexity
- [ ] Follows project conventions
- [ ] No magic numbers or strings without named constants

## Tests
- [ ] Tests present for new/changed behaviour
- [ ] Tests are meaningful (not just coverage padding)
- [ ] Tests are independent and repeatable
- [ ] No test data hardcoded to environment-specific values

## Security
- [ ] No sensitive data logged or exposed
- [ ] User input validated/sanitised
- [ ] No new security vulnerabilities introduced

## Performance
- [ ] No obvious N+1 query issues
- [ ] No unnecessary computation in hot paths

## Backwards Compatibility
- [ ] API changes are backwards compatible or versioned
- [ ] Database migrations are reversible

## Final
- [ ] Comments are constructive and specific
- [ ] Approval given or changes requested with clear rationale
