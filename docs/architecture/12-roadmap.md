# Roadmap & Open Questions

> **Prerequisites**: [01-design.md](01-design.md)
>
> **See also**: All other architecture documents for context

## Open Questions / Decisions Needed

1. **Provider Strategy**: Build direct integrations vs. use aggregator (Sterling/HireRight)?
2. **Multi-tenancy**: Single instance multi-tenant vs. tenant-per-deployment?
3. **AI Model Selection**: Which model for which task (extraction vs. scoring)?
4. **Report Format**: PDF generation approach, template system?
5. **Adverse Action Workflow**: Full FCRA workflow in-system vs. HRIS-managed?
6. **Premium Data Consent**: Separate consent flow for Enhanced tier data sources?
7. **Billing Integration**: Usage-based billing hooks for tier/vigilance/degree?

## Implementation Phases

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| **1** | Foundation | Service model, core screening, compliance engine |
| **2** | Standard Tier | Core data providers, D1/D2 connections |
| **3** | Enhanced Tier | Premium providers, D3 network analysis |
| **4** | Vigilance | Scheduler, monitoring, delta detection |
| **5** | HRIS Integration | Workday connector, consent workflow |
| **6** | Production | Security hardening, scalability, observability |

### Phase 1: Foundation

**Scope:**
- Service configuration model (tiers, vigilance, degrees)
- Core screening workflow (LangGraph)
- Compliance engine with basic US/EU rules
- Risk analysis framework
- Basic API endpoints

**Deliverables:**
- Working screening pipeline
- Compliance rule repository
- Risk scoring output
- API for screening initiation and status

### Phase 2: Standard Tier

**Scope:**
- Core data provider integrations
- Entity resolution
- D1/D2 connection mapping
- Basic report generation

**Providers:**
- Court records (PACER)
- Credit bureaus (one to start)
- Employment verification (The Work Number)
- Sanctions (World-Check or OFAC direct)

**Deliverables:**
- Working Standard tier screenings
- HR Summary and Compliance Audit reports
- Subject Disclosure report (FCRA)

### Phase 3: Enhanced Tier

**Scope:**
- Premium data provider integrations
- D3 extended network analysis
- Enhanced adverse media
- Behavioral data handling

**Providers:**
- Data brokers (Acxiom or similar)
- OSINT platforms
- Dark web monitoring
- Location intelligence (if scoped)

**Deliverables:**
- Working Enhanced tier screenings
- Security Investigation report
- Network visualization

### Phase 4: Vigilance

**Scope:**
- Vigilance scheduler implementation
- Delta detection algorithm
- Alert generation and routing
- Evolution analytics (Phase 1 - rules-based)

**Deliverables:**
- V1/V2/V3 monitoring schedules
- Alert dashboard
- Evolution signals in reports

### Phase 5: HRIS Integration

**Scope:**
- Workday adapter (first HRIS)
- Consent workflow integration
- Status sync back to HRIS
- Position change handling

**Deliverables:**
- Working Workday integration
- Consent automation
- HRIS-triggered screenings

### Phase 6: Production

**Scope:**
- Security audit and hardening
- Performance optimization
- Observability (metrics, tracing, logging)
- Disaster recovery planning
- Documentation and runbooks

**Deliverables:**
- Production-ready deployment
- Security certifications (SOC 2 prep)
- Operations runbook
- SLA definitions

## Future Considerations

### Evolution Analytics ML (Post-Phase 4)

Prerequisites:
- Sufficient profile version history (12+ months)
- Labeled outcomes (confirmed risks, false positives)
- Analyst feedback corpus

### Additional HRIS Platforms (Post-Phase 5)

Priority order (based on market share):
1. SAP SuccessFactors
2. Oracle HCM
3. ADP
4. BambooHR

### International Expansion (Post-Phase 6)

New locale support requires:
- Compliance rule development
- Local data provider partnerships
- Language support (reports, UI)
- Data residency compliance

Priority markets:
1. Canada (PIPEDA)
2. UK (post-Brexit specifics)
3. Australia
4. Germany (strict GDPR)

---

*Document Version: 1.0.0*
*Last Updated: 2025-01-29*
