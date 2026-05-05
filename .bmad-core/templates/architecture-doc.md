# Architecture Document: {PROJECT_NAME}

> Template — replace all `{PLACEHOLDER}` values

## Document Info
- **Version**: 1.0
- **Date**: {date}
- **Architect**: {name}
- **Status**: Draft / Review / Approved

## 1. Overview
{High-level description of the system architecture}

## 2. Goals & Constraints
### Architectural Goals
- {goal}

### Constraints
- {constraint}

## 3. System Context
{Description of the system and its external dependencies/integrations}

```
[System Context Diagram — describe in text or mermaid]
```

## 4. Tech Stack
| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | Python | 3.x | {reason} |
| Framework | {framework} | {version} | {reason} |
| Database | {db} | {version} | {reason} |
| Testing | pytest | latest | {reason} |
| CI/CD | {tool} | | {reason} |

## 5. Component Architecture
{Description of major components and their responsibilities}

### Component: {Name}
- **Responsibility**: {what it does}
- **Interfaces**: {what it exposes}
- **Dependencies**: {what it depends on}

## 6. Data Architecture
### Data Model
{Description of key entities and relationships}

### Data Flow
{How data moves through the system}

## 7. API Design
{REST / GraphQL / gRPC — describe key endpoints or link to spec}

## 8. Security Architecture
- Authentication: {approach}
- Authorisation: {approach}
- Data encryption: {approach}
- Secrets management: {approach}

## 9. Deployment Architecture
- Environment: {cloud/on-prem/hybrid}
- Containerisation: {Docker/none}
- Orchestration: {K8s/none}
- Environments: dev / staging / prod

## 10. Architecture Decision Records
| ADR | Decision | Status |
|-----|----------|--------|
| ADR-001 | {decision title} | Accepted |

## 11. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| {risk} | H/M/L | {mitigation} |

## 12. Future Considerations
- {item}
