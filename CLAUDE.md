# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Elile is an employee risk assessment platform for organizations with critical roles in government, energy, finance, and other sensitive sectors. The system conducts comprehensive background investigations for pre-employment screening and ongoing employee monitoring at global scale.

### Primary Use Cases

1. **Pre-Employment Screening**: Comprehensive background checks before hiring for critical positions
2. **Ongoing Monitoring**: Continuous screening of current employees for emerging risks

### Key Requirements

- **Locale-Aware Compliance**: All operations require target employee locale specification to enforce jurisdiction-specific compliance rules (FCRA, GDPR, PIPEDA, etc.)
- **Consent Management**: Consent is required and managed through HRIS workflow integration (assume consent granted; HRIS connectors are a planned integration)
- **Audit Trail**: Complete logging of all research activities for compliance and accountability

## Core Architecture

- **Modular Monolith**: Single deployable unit with well-defined module boundaries; simpler operations, easier debugging, future extraction path
- **Multi-Model Integration**: Integrates multiple AI models (Claude, GPT-4, Gemini) for analysis redundancy and specialized tasks
- **LangGraph Orchestration**: Workflow management with conditional routing and state persistence
- **Compliance Engine**: Locale-based rules engine that filters permitted checks by jurisdiction and role type
- **Data Provider Abstraction**: Unified interface for multiple background check data sources

## Data Source Categories

### Biographical / Identity Verification
- Government ID databases, address verification
- Sanctions/PEP lists (OFAC, UN, EU, World-Check)
- Watchlists (Interpol, national law enforcement)

### Professional / Employment
- Employment verification (The Work Number, direct verification)
- Education verification (National Student Clearinghouse, registrars)
- Professional licenses (state boards, FINRA, medical boards)
- LinkedIn (official API with consent)

### Financial
- Credit reports (jurisdiction-dependent - US: FCRA; EU: generally prohibited)
- Bankruptcy and insolvency records
- Liens, judgments, regulatory actions

### Legal / Criminal
- Criminal records (jurisdiction-dependent restrictions)
- Civil litigation records
- Regulatory enforcement actions
- Adverse media monitoring

## Compliance Framework

| Locale | Key Restrictions |
|--------|------------------|
| US | FCRA (7-year lookback, adverse action notices), state ban-the-box laws |
| EU/UK | GDPR Art. 6/9, criminal data only for regulated roles, right to erasure |
| Canada | PIPEDA, RCMP for criminal checks |
| APAC | Highly variable by country |
| LATAM | Brazil LGPD, Argentina strict privacy |

## Planned Integrations

### HRIS Platforms (Consent & Workflow)
- Workday
- SAP SuccessFactors
- Oracle HCM
- ADP
- BambooHR

### Background Check Data Providers
- Sterling, Checkr, HireRight (aggregated providers)
- Direct court/registry access where available

## Development Commands

### Code Formatting
```bash
black . --line-length 100 --target-version py314
```

### Linting
```bash
ruff check .
```

### Type Checking
```bash
mypy src/elile
```

### Testing
```bash
pytest -v
```

## Project Structure

```
src/elile/
├── agent/          # LangGraph workflow orchestration
├── config/         # Configuration and settings
├── models/         # AI model adapters (Claude, OpenAI, Gemini)
├── search/         # Search query building and execution
├── risk/           # Risk analysis and scoring
├── compliance/     # Locale-aware compliance engine (planned)
├── providers/      # Data provider integrations (planned)
├── hris/           # HRIS platform connectors (planned)
└── utils/          # Shared utilities and exceptions
```

## Development Guidelines

- Python 3.14 target version
- Line length: 100 characters (Black formatting)
- Strict type hints (mypy strict mode)
- All operations must accept locale parameter
- Comprehensive audit logging for all data access
- Rate limiting and retry logic for external APIs

## Architecture Document

See `docs/architecture.md` for detailed system design including:

- **Service Model**: Tiers (Standard/Enhanced), Vigilance (V0-V3), Degrees (D1-D3)
- **Data Sources**: Core (T1) and Premium (T2) provider categories
- **Data Persistence**: Entity data lake, caching, freshness, and evolution analytics
- **Modular Monolith**: Module structure, communication patterns, process model, deployment options
- **Per-Persona Reports**: HR Summary, Compliance Audit, Security Investigation, Subject Disclosure, Executive Portfolio
- **User Interfaces**: Screening Portal, Review Dashboard, Monitoring Console, Admin Console, Subject Portal

## Report Types

| Persona | Report | Purpose |
|---------|--------|---------|
| HR Manager | Summary Report | Risk level, recommendation, key flags for hiring decisions |
| Compliance | Audit Report | Data sources, consent, compliance checks for audit trail |
| Security | Investigation Report | Detailed findings, connections, threat assessment |
| Investigator | Case File | Complete findings with raw data for deep investigation |
| Subject | Disclosure Report | FCRA-compliant summary for candidates (adverse action) |
| Executive | Portfolio Report | Aggregate metrics, trends, organizational risk posture |
