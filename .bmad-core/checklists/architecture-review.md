# Checklist: Architecture Review

Use before finalising an architecture document or major technical decision.

## Requirements Coverage
- [ ] All functional requirements addressed
- [ ] All non-functional requirements addressed (performance, security, scalability)
- [ ] Edge cases and failure modes considered

## Design Quality
- [ ] Single responsibility principle respected at component level
- [ ] Clear separation of concerns
- [ ] No circular dependencies between components
- [ ] Interfaces clearly defined

## Technology Choices
- [ ] Technology choices justified with explicit trade-offs documented
- [ ] No unnecessary dependencies introduced
- [ ] Chosen technologies are actively maintained
- [ ] Licences compatible with project

## Security
- [ ] Authentication and authorisation design documented
- [ ] Sensitive data identified and protection mechanism specified
- [ ] No secrets hardcoded; secrets management strategy defined
- [ ] Input validation strategy defined

## Operability
- [ ] Logging and observability strategy defined
- [ ] Error handling and alerting considered
- [ ] Deployment and rollback procedure documented
- [ ] Backup and recovery considered

## Scalability & Performance
- [ ] Expected load documented
- [ ] Bottlenecks identified
- [ ] Scaling strategy (vertical/horizontal) defined
- [ ] Caching strategy considered

## Documentation
- [ ] Architecture document complete and current
- [ ] Key decisions captured as ADRs
- [ ] Diagrams present and accurate
- [ ] Reviewed by at least one other engineer
