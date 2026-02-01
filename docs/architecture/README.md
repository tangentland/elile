# Elile Architecture Documentation

This directory contains the architecture documentation for the Elile employee risk assessment platform, organized by domain for easier navigation and maintenance.


## Background & High-Level Requirements:
Design and implement an autonomous research agent capable of conducting comprehensive investigations
on individuals or entities to uncover hidden connections, potential risks, and strategic insights.
This challenge simulates real-world intelligence gathering scenarios critical to risk assessment
and due diligence operations.

### Technical Requirements:
Before starting make sure to develop an evaluation set, have a name with deeply hidden facts about
the person that one can find with so many searches and use those as evaluation of your AI agent.
Audit each steps, read about 'prompt design' and make sure yours is up for the task.

**Core Architecture**
- Multi-Model Integration: Implement at least two distinct AI models with diﬀerent
  capabilities (Gemini 2.5, Claude Opus 4, OpenAI 4.1,..)
- Consecutive Search Strategy: Design an intelligent search progression that builds upon previous findings
- Dynamic Query Refinement: Agent must adapt search strategies based on discovered information

**Functional Specifications**
- Deep Fact Extraction: Identify and verify biographical details, professional history, financial connections,
  and behavioral patterns
- Risk Pattern Recognition: Flag potential red flags, inconsistencies, or concerning associations
- Connection Mapping: Trace relationships between entities, organizations, and events
- Source Validation: Implement confidence scoring and cross-referencing mechanisms

### Implementation Guidelines:
**Technical Stack**
- Use LangGraph for agent orchestration
- Leverage available AI APIs, search engines, and real online data
- Implement proper error handling and rate limiting
- Design for scalability and maintainability

### Deliverables:

**Phase 1: Development**
- Complete codebase with comprehensive documentation
- Three test persona profiles with expected findings
- Execution logs demonstrating agent performance
- Risk assessment reports for each test case with details

**Phase 2: Live Demonstration**
- Real-time execution on provided test case
- Code walkthrough and architectural explanation
- Discussion of design decisions and trade-oﬀs
- Q&A on scalability and production considerations

### Evaluation Criteria

**Technical Excellence**
- Code quality, architecture, and best practices
  - Eﬀective multi-model orchestration
  - Intelligent search progression logic
  - Error handling and edge case management

**Research Capability**
- Depth and accuracy of information gathering
  - Quality of risk assessment insights
  - Ability to uncover non-obvious connections
  - Source verification and confidence scoring

**Innovation & Eﬃciency**
- Creative approaches to complex research challenges
  - Optimization of search strategies
  - Novel use of available tools and APIs
  - Scalability considerations


# Architecture 
| Document | Description |
|----------|-------------|
| [01-design.md](01-design.md) | Design principles, system philosophy, "why" decisions |
| [02-core-system.md](02-core-system.md) | Storage, database, API structure, data models |
| [03-screening.md](03-screening.md) | Service tiers, degrees, pre-employment screening |
| [04-monitoring.md](04-monitoring.md) | Vigilance levels, ongoing monitoring, alerts |
| [05-investigation.md](05-investigation.md) | Screening engine, SAR loop, risk analysis |
| [06-data-sources.md](06-data-sources.md) | Core/premium providers, entity resolution |
| [07-compliance.md](07-compliance.md) | Compliance engine, security, data retention |
| [08-reporting.md](08-reporting.md) | Per-persona report types, generation architecture |
| [09-integration.md](09-integration.md) | API endpoints, HRIS gateway, webhooks |
| [10-platform.md](10-platform.md) | Module structure, deployment, scaling |
| [11-interfaces.md](11-interfaces.md) | User interfaces (5 portals/dashboards) |
| [12-roadmap.md](12-roadmap.md) | Open questions, implementation phases |

## Domain Dependency Diagram

```
                    ┌─────────────┐
                    │   README    │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌───────────┐    ┌─────────────┐    ┌──────────┐
   │  design   │    │ core-system │    │ roadmap  │
   │  (why)    │    │  (shared)   │    │ (future) │
   └─────┬─────┘    └──────┬──────┘    └──────────┘
         │                 │
         └────────┬────────┘
                  │ (all domains depend on design + core)
    ┌─────────────┼─────────────┬─────────────┐
    ▼             ▼             ▼             ▼
┌─────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐
│screening│ │monitoring│ │compliance │ │data-sources│
└────┬────┘ └────┬─────┘ └───────────┘ └─────┬──────┘
     │           │                           │
     └─────┬─────┘                           │
           ▼                                 │
    ┌─────────────┐                          │
    │investigation│◄─────────────────────────┘
    └──────┬──────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐ ┌───────────┐
│reporting│ │integration│
└─────────┘ └───────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌──────────┐ ┌──────────┐
│interfaces│ │ platform │
└──────────┘ └──────────┘
```

## Reading Order:

### For New Team Members:
1. **[01-design.md](01-design.md)** - Understand the "why" behind architectural decisions
2. **[02-core-system.md](02-core-system.md)** - Learn the foundational data and API patterns
3. **[03-screening.md](03-screening.md)** - Understand the core business domain
4. **[05-investigation.md](05-investigation.md)** - Deep dive into the screening engine
5. **[10-platform.md](10-platform.md)** - Learn how modules are structured

### For Backend Engineers:
- Start with **[02-core-system.md](02-core-system.md)** for data models
- Review **[05-investigation.md](05-investigation.md)** for workflow details
- Check **[06-data-sources.md](06-data-sources.md)** for provider integration

### For Frontend Engineers:
- Start with **[11-interfaces.md](11-interfaces.md)** for UI requirements
- Review **[08-reporting.md](08-reporting.md)** for report structures
- Check **[09-integration.md](09-integration.md)** for API contracts

### For Compliance Officers:
- Start with **[07-compliance.md](07-compliance.md)** for rules engine
- Review **[08-reporting.md](08-reporting.md)** for audit reports
- Check **[06-data-sources.md](06-data-sources.md)** for data handling

### For Product Managers:
- Start with **[03-screening.md](03-screening.md)** for service model
- Review **[04-monitoring.md](04-monitoring.md)** for vigilance levels
- Check **[08-reporting.md](08-reporting.md)** for persona reports

## Cross-Reference Guide:
Each document includes:
- **Prerequisites** header listing required prior reading
- **See also** links to related sections in other documents
- Internal anchor links for easy navigation

# Source Section Mapping:

| New Document | Original Sections |
|--------------|-------------------|
| 01-design.md | §1 (Overview), §11.1 (Why Monolith) |
| 02-core-system.md | §5.1-5.11 (Data Persistence), §8 (API structure), §10 (Tech Stack) |
| 03-screening.md | §2.1, 2.3-2.7 (Service Model), §6.1 (Flow), §6.1 (Config Mgr) |
| 04-monitoring.md | §2.2 (Vigilance), §6.2 (Monitoring Flow), §6.6 (Scheduler) |
| 05-investigation.md | §6.2 (Screening Engine), §6.5 (SAR Loop), §6.5 (Connection Mapper), §6.7 (Risk) |
| 06-data-sources.md | §4 (Data Sources), §6.4 (Provider Gateway), §5.6 (Entity Resolution) |
| 07-compliance.md | §6.3 (Compliance Engine), §9 (Security), §5.9-5.10 (Retention) |
| 08-reporting.md | §14 (Per-Persona Reports) |
| 09-integration.md | §7 (API Design), §6.8 (HRIS Gateway) |
| 10-platform.md | §11.2-11.7 (Modular Monolith) |
| 11-interfaces.md | §15 (User Interfaces) |
| 12-roadmap.md | §12 (Open Questions), §13 (Phases) |

---

*Document Version: 1.0.1*
*Last Updated: 2025-02-01*
