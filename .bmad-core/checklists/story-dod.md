# Checklist: Story Definition of Done

Use this checklist before marking any user story as Done.

## Code Quality
- [ ] Code follows project style guide (PEP 8 for Python)
- [ ] No commented-out code left in place
- [ ] No TODO comments without associated tickets
- [ ] Type hints present on all functions/methods
- [ ] Docstrings on public functions/classes

## Testing
- [ ] Unit tests written for all new functions
- [ ] Unit tests passing locally (`pytest`)
- [ ] Code coverage has not decreased
- [ ] Edge cases covered in tests
- [ ] No test skips added without justification

## Integration
- [ ] Feature branch merged to main/develop without conflicts
- [ ] CI pipeline green
- [ ] No new linting errors (`ruff` / `flake8` / `pylint`)
- [ ] No new type errors (`mypy`)

## Acceptance
- [ ] All acceptance criteria from the story verified
- [ ] PO has reviewed and accepted the work
- [ ] Demo-ready (can be shown in sprint review)

## Documentation
- [ ] Inline comments updated
- [ ] Any impacted docs in `docs/` updated
- [ ] CHANGELOG entry added (if applicable)

## Deployment
- [ ] Feature deployed to staging
- [ ] No regressions found in smoke test
- [ ] Feature flag / rollback plan in place (if applicable)
