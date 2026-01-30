# Elile Architecture Documentation

This directory contains the architecture documentation for the Elile employee risk assessment platform, organized by domain for easier navigation and maintenance.

## Quick Links

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

## Reading Order

### For New Team Members

1. **[01-design.md](01-design.md)** - Understand the "why" behind architectural decisions
2. **[02-core-system.md](02-core-system.md)** - Learn the foundational data and API patterns
3. **[03-screening.md](03-screening.md)** - Understand the core business domain
4. **[05-investigation.md](05-investigation.md)** - Deep dive into the screening engine
5. **[10-platform.md](10-platform.md)** - Learn how modules are structured

### For Backend Engineers

- Start with **[02-core-system.md](02-core-system.md)** for data models
- Review **[05-investigation.md](05-investigation.md)** for workflow details
- Check **[06-data-sources.md](06-data-sources.md)** for provider integration

### For Frontend Engineers

- Start with **[11-interfaces.md](11-interfaces.md)** for UI requirements
- Review **[08-reporting.md](08-reporting.md)** for report structures
- Check **[09-integration.md](09-integration.md)** for API contracts

### For Compliance Officers

- Start with **[07-compliance.md](07-compliance.md)** for rules engine
- Review **[08-reporting.md](08-reporting.md)** for audit reports
- Check **[06-data-sources.md](06-data-sources.md)** for data handling

### For Product Managers

- Start with **[03-screening.md](03-screening.md)** for service model
- Review **[04-monitoring.md](04-monitoring.md)** for vigilance levels
- Check **[08-reporting.md](08-reporting.md)** for persona reports

## Cross-Reference Guide

Each document includes:
- **Prerequisites** header listing required prior reading
- **See also** links to related sections in other documents
- Internal anchor links for easy navigation

## Source Section Mapping

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

*Document Version: 1.0.0*
*Last Updated: 2025-01-29*
