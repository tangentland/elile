# Design Principles & System Philosophy

> **Prerequisites**: None - this is the foundational document
>
> **See also**: [02-core-system.md](02-core-system.md) for technical implementation, [10-platform.md](10-platform.md) for module architecture

## Overview

Elile is an employee risk assessment platform that performs comprehensive background investigations for pre-employment screening and ongoing employee monitoring. The system operates at global scale with locale-aware compliance enforcement.

## Design Principles

| Principle | Description |
|-----------|-------------|
| **Compliance-First** | All operations are gated by jurisdiction-specific compliance rules |
| **Audit Everything** | Complete traceability of all data access and decisions |
| **Provider Agnostic** | Abstracted interfaces for data providers and AI models |
| **Resilient** | Graceful degradation when providers are unavailable |
| **Scalable** | Async-first design supporting high-volume concurrent screenings |
| **Configurable** | Flexible service tiers and options to match diverse customer needs |

## Key Actors

| Actor | Description |
|-------|-------------|
| **Requesting System** | HRIS or screening portal initiating background checks |
| **Subject** | Employee or candidate being screened (consent required) |
| **Reviewer** | Human analyst reviewing findings and making decisions |
| **Administrator** | System admin configuring compliance rules and providers |

## Why Modular Monolith?

The platform uses a **modular monolith** architecture rather than microservices:

| Benefit | Description |
|---------|-------------|
| **Simplified Operations** | Single deployment unit; no service mesh, discovery, or inter-service networking |
| **Easier Debugging** | Full stack traces; no distributed tracing required for most issues |
| **Lower Latency** | In-process function calls vs. network hops between services |
| **Transactional Integrity** | Database transactions span module boundaries naturally |
| **Team Efficiency** | Small team can iterate quickly without coordination overhead |
| **Future Flexibility** | Well-defined module boundaries allow extraction to services later if needed |

### When Microservices Make Sense (Future)

The modular monolith is designed with clean boundaries that enable future extraction:

- **Provider Gateway**: If external API load becomes a bottleneck, can be extracted to a separate service with its own scaling
- **Report Generator**: CPU-intensive PDF rendering could run as a separate service
- **Entity Resolution**: Heavy ML workloads could be isolated

The key insight is that module boundaries already exist - extraction is a deployment decision, not an architecture rewrite.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SYSTEMS                                │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│   HRIS Systems  │  Data Providers │   AI Models     │   Notification        │
│   - Workday     │  - Core (T1)    │   - Claude      │   - Email             │
│   - SuccessF.   │  - Premium (T2) │   - GPT-4       │   - Webhooks          │
│   - Oracle HCM  │  - Data Brokers │   - Gemini      │                       │
│   - ADP         │  - OSINT        │                 │                       │
└────────┬────────┴────────┬────────┴────────┬────────┴───────────┬───────────┘
         │                 │                 │                     │
         ▼                 ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            INTEGRATION LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ HRIS Adapter │  │Provider Adpt.│  │ Model Adapter│  │ Notification │     │
│  │   Gateway    │  │   Gateway    │  │   Gateway    │  │   Gateway    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CORE PLATFORM                                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                        API GATEWAY / ORCHESTRATION                      │ │
│  │                         (Request routing, auth, rate limiting)          │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                       │
│    ┌─────────────────────────────────┼─────────────────────────────────┐    │
│    ▼                                 ▼                                 ▼    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Service    │  │  Screening   │  │  Compliance  │  │    Report    │    │
│  │ Config Mgr   │  │   Engine     │  │    Engine    │  │   Generator  │    │
│  │              │  │  (LangGraph) │  │              │  │              │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘  └──────────────┘    │
│         │                 │                                                  │
│         ▼                 ▼                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Query     │  │     Risk     │  │  Connection  │  │    Audit     │    │
│  │  Generator   │  │   Analyzer   │  │    Mapper    │  │    Logger    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Subject    │  │   Screening  │  │   Service    │  │    Audit     │     │
│  │   Records    │  │   Results    │  │   Configs    │  │     Logs     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Architectural Decisions

### 1. Compliance as a First-Class Concern

Every operation in the system requires locale context. The compliance engine is not an afterthought - it's integrated at every layer:

- API requests require locale parameter
- Data queries are filtered through compliance rules before execution
- Reports include compliance attestation
- Audit logs capture compliance decisions

### 2. Multi-Model AI Strategy

The platform integrates multiple AI models for different purposes:

| Model | Use Case |
|-------|----------|
| Claude | Primary analysis, finding extraction, risk assessment |
| GPT-4 | Redundancy, specific domain tasks |
| Gemini | Alternative perspective, validation |

This provides:
- Redundancy if one provider is unavailable
- Ability to choose the best model for specific tasks
- Cross-validation of critical findings

### 3. Async-First Design

Background screening involves many external API calls with variable latency. The system is designed async-first:

- Non-blocking I/O for all external calls
- Job queue for provider queries
- WebSocket notifications for status updates
- Eventual consistency where appropriate

### 4. Provider Abstraction

All data providers implement a common interface, enabling:

- Easy addition of new providers
- Provider-specific rate limiting and retry logic
- Cost tracking per provider
- Graceful fallback when providers fail

## Design Tenets

1. **Never surprise the user** - Make system behavior predictable and documented
2. **Fail safely** - When uncertain, don't proceed; escalate to human review
3. **Minimize data collection** - Only collect what's necessary for the screening
4. **Protect subject rights** - Build FCRA/GDPR requirements into the core, not as bolted-on features
5. **Enable auditability** - Every decision should be traceable and explainable

---

*See [02-core-system.md](02-core-system.md) for technical implementation details*
