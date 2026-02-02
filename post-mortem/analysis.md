# Simulated API Analysis & Conversion Effort Estimate

**Date:** 2026-02-02
**Author:** Development Team
**Status:** Planning Document

---

## Executive Summary

This document analyzes all instances where external API calls are simulated in the Elile codebase (excluding tests) and provides effort estimates for converting these simulations to real/production implementations.

**Key Findings:**
- **7 providers** contain simulated external API calls
- **5,177 lines of code** involved in simulations
- **103-156 dev days** estimated for full conversion
- **$75k-$150k/year** in API subscription costs

---

## Simulated External API Calls

### Summary Table

| Provider | File | Lines | Simulated Methods | External APIs Required |
|----------|------|-------|-------------------|----------------------|
| **LLM Synthesis** | `providers/synthesis/provider.py` | 1,424 | 12+ methods | LinkedIn API, News APIs, SEC EDGAR |
| **OSINT Aggregator** | `providers/osint/provider.py` | 924 | 4 search methods | Social media APIs, News APIs, Public records |
| **Dark Web Monitoring** | `providers/darkweb/provider.py` | 749 | 4 search methods | Have I Been Pwned, Dark web intel services |
| **Breach Database** | `providers/darkweb/breach_database.py` | 269 | Static data | Breach notification feeds |
| **Education Verification** | `providers/education/provider.py` | 855 | 1 explicit simulate | National Student Clearinghouse API |
| **Diploma Mill Detection** | `providers/education/diploma_mill.py` | 302 | Static lookup | Accreditation databases |
| **Sanctions & Watchlist** | `providers/sanctions/provider.py` | 654 | Static data load | OFAC, UN, EU, World-Check APIs |
| **Total** | | **5,177** | | |

---

## Detailed Breakdown by Provider

### 1. LLM Synthesis Provider (HIGH EFFORT)

**File:** `src/elile/providers/synthesis/provider.py` (1,424 lines)

**Purpose:** Synthesizes verification data from public sources using LLM models for extraction and cross-validation. Serves as fallback when paid providers are unavailable.

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 266 | `health_check` always returns HEALTHY | Actual API health checks |
| 305-308 | `_generate_simulated_employers` | Remove - not needed with real data |
| 367-416 | `_gather_employment_sources` | LinkedIn API, News APIs, SEC EDGAR |
| 420-461 | Template generators for recommendations, news, SEC | LLM-based extraction from real data |
| 463-510 | `_generate_simulated_*` methods | Remove - not needed |
| 549-627 | Education simulation | Real education data sources |
| 700-711 | Adverse media (10% hash-based) | Real news/media APIs |
| 738-749 | License lookup (50% hash-based) | State license board APIs |
| 768-786 | Social media profiles (hash-based) | Social media APIs |
| 804-823 | Corporate affiliations (20% hash-based) | SEC EDGAR, corporate databases |

**Simulation Pattern:** Uses MD5 hash of subject name for deterministic-but-random-looking results.

**Real APIs Needed:**
- LinkedIn Official API (OAuth 2.0, rate-limited)
- News APIs (NewsAPI, GDELT, Bing News)
- SEC EDGAR API (free, rate-limited)
- Professional license databases (state-specific)

---

### 2. OSINT Aggregator Provider (HIGH EFFORT)

**File:** `src/elile/providers/osint/provider.py` (924 lines)

**Purpose:** Aggregates open-source intelligence from multiple sources including social media, news, public records, and professional networks.

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 187-197 | `health_check` with 10ms sleep, returns HEALTHY | Real API connectivity checks |
| 406-481 | `_search_social_media` - LinkedIn 80%, Twitter 50%, GitHub 30% | Social media APIs |
| 499-556 | `_search_news` - 0-5 random articles | News aggregation APIs |
| 573-620 | `_search_public_records` - 0-3 random records | LexisNexis, public records APIs |
| 637-739 | `_search_professional` - 80% chance profile | LinkedIn API, professional databases |

**Simulation Pattern:** Uses MD5 hash seeding with random number generation for reproducible fake data.

**Real APIs Needed:**
- LinkedIn API
- Twitter/X API v2
- GitHub API
- NewsAPI / GDELT / Bing News
- LexisNexis or similar public records service

---

### 3. Dark Web Monitoring Provider (MEDIUM-HIGH EFFORT)

**File:** `src/elile/providers/darkweb/provider.py` (749 lines)

**Purpose:** Monitors dark web sources for credential leaks, marketplace activity, and threat intelligence.

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 226-233 | `health_check` always HEALTHY, 200ms latency | Real API health checks |
| 357-404 | `_search_credential_leaks` - 30% chance fake leak | Have I Been Pwned API or SpyCloud |
| 406-450 | `_search_marketplaces` - 10% chance fake listing | Dark web intel services |
| 452-494 | `_search_forums` - 5% chance fake mention | Dark web monitoring services |
| 496-536 | `_get_threat_indicators` - 15% chance fake indicator | Threat intel feeds |

**Simulation Pattern:** Uses MD5 hash modulo for probabilistic simulation based on email/name.

**Real APIs Needed:**
- Have I Been Pwned API ($3.50/month per domain)
- SpyCloud or similar breach monitoring service
- Recorded Future / Flashpoint / Intel471 (expensive - $50k+/year)

---

### 4. Breach Database (LOW EFFORT)

**File:** `src/elile/providers/darkweb/breach_database.py` (269 lines)

**Purpose:** Database of known data breaches for reference in dark web monitoring.

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 25-137 | Static `KNOWN_BREACHES` dict with 10 entries | Dynamic loading from breach feeds |
| 139-152 | Static `DOMAIN_MAPPINGS` dict | Auto-generated from breach data |

**Current Sample Data:**
- LinkedIn 2021 (700M records)
- Facebook 2019 (533M records)
- Adobe 2013, Dropbox 2012, Equifax 2017
- Yahoo 2013 (3B records), Marriott 2018, Twitter 2022
- Capital One 2019, Experian 2020

**Real Implementation:**
- Subscribe to breach notification service
- Database storage for breach records
- Scheduled updates from feeds (daily/weekly)

---

### 5. Education Verification Provider (MEDIUM EFFORT)

**File:** `src/elile/providers/education/provider.py` (855 lines)

**Purpose:** Verifies education credentials through institution matching and National Student Clearinghouse.

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 82-83 | In-memory institution database (comment: "In production, would be populated from actual data sources") | Real institution database |
| 251-257 | `health_check` always HEALTHY, 100ms latency | NSC API connectivity check |
| 389-390 | Calls `_simulate_nsc_verification` | Real NSC API call |
| 420-472 | `_simulate_nsc_verification` - 80% success rate, hash-based | National Student Clearinghouse API |
| 650-810 | `_load_sample_institutions` - hard-coded MIT, Harvard, Stanford, etc. | Load from IPEDS or accreditation databases |

**Real APIs Needed:**
- National Student Clearinghouse (NSC) API (contract required)
- IPEDS (Integrated Postsecondary Education Data System) - free
- Regional accreditation databases

---

### 6. Diploma Mill Detection (LOW EFFORT)

**File:** `src/elile/providers/education/diploma_mill.py` (302 lines)

**Purpose:** Detects diploma mills and fake credentials through pattern matching and database lookups.

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 29-78 | Static `KNOWN_DIPLOMA_MILLS` set (~40 entries) | Database with regular updates |
| 81-88 | Static `SUSPICIOUS_DOMAINS` regex patterns | Could remain static with updates |
| 91-102 | Static `RED_FLAG_PATTERNS` | Could remain static |
| 104-124 | Static `LEGITIMATE_ACCREDITORS` set | CHEA/USDE accreditation database |
| 127-137 | Static `FAKE_ACCREDITORS` set (~9 entries) | Curated list with updates |

**Real Implementation:**
- CHEA (Council for Higher Education Accreditation) database
- USDE recognized accreditors list
- Periodic manual curation of diploma mill list

---

### 7. Sanctions & Watchlist Provider (MEDIUM EFFORT)

**File:** `src/elile/providers/sanctions/provider.py` (654 lines)

**Purpose:** Screens subjects against global sanctions and watchlists (OFAC, UN, EU, PEP lists).

| Line | Simulation | Real Implementation Required |
|------|------------|------------------------------|
| 119-125 | In-memory sanctions database (comment: "In production, would be populated from actual OFAC/UN/EU feeds") | Database with live feed updates |
| 302-309 | `health_check` always HEALTHY, 50ms latency | Real API/feed connectivity |
| 505-614 | `_load_sample_data` - hard-coded entries (Kim Jong Un, Putin, etc.) | OFAC, UN, EU, World-Check feeds |

**Sample Data Includes:**
- OFAC SDN entries
- UN Consolidated List entries
- EU Consolidated List entries
- World PEP sample entries

**Real APIs/Feeds Needed:**
- OFAC SDN List (free, daily updates from Treasury)
- UN Consolidated List (free)
- EU Consolidated List (free)
- World-Check / Dow Jones Risk & Compliance (expensive - $25k+/year)

---

## Effort Estimation

### Conversion Effort by Provider

| Provider | Complexity | Dev Days | Dependencies | Risk Level |
|----------|------------|----------|--------------|------------|
| **Sanctions** | Medium | 5-8 | OFAC/UN/EU feeds (free) | Low |
| **Education** | Medium | 8-12 | NSC contract required | Medium |
| **Diploma Mill** | Low | 2-3 | CHEA database | Low |
| **Breach Database** | Low | 3-5 | HIBP API subscription | Low |
| **Dark Web** | High | 15-20 | Expensive intel services | High |
| **OSINT** | High | 20-30 | Multiple API contracts | High |
| **LLM Synthesis** | High | 25-35 | LinkedIn API, News APIs | High |

### Total Effort Summary

| Category | Effort | Cost Considerations |
|----------|--------|---------------------|
| **Development** | 78-113 dev days | ~$78k-$170k at $150-200/hr |
| **API Subscriptions** | - | $75k-$150k/year (varies by volume) |
| **Infrastructure** | 5-10 days | Database, caching, rate limiting |
| **Testing** | 15-25 days | Integration tests, mocking for CI |
| **Documentation** | 5-8 days | API docs, runbooks, error handling |
| **Total** | **103-156 dev days** | ~$100k-$250k initial + $75k-$150k/year |

---

## Recommended Conversion Order

### Phase 1 - Low Risk, Quick Wins (2-3 weeks)

**Priority:** High compliance value, low cost, minimal risk

1. **Sanctions Provider** (5-8 days)
   - Free government feeds (OFAC, UN, EU)
   - High compliance/regulatory value
   - Well-documented APIs

2. **Diploma Mill Detection** (2-3 days)
   - Static data with periodic updates
   - CHEA database is accessible
   - Low maintenance burden

3. **Breach Database** (3-5 days)
   - HIBP API is cheap ($3.50/month/domain)
   - Well-documented, reliable service
   - Immediate security value

### Phase 2 - Medium Complexity (4-6 weeks)

**Priority:** Core verification capabilities

4. **Education Verification** (8-12 days)
   - Requires NSC contract negotiation (start early)
   - IPEDS data is freely available
   - Core verification use case

5. **Dark Web Provider - Basic** (5-8 days)
   - HIBP integration only
   - Defer expensive intel services
   - Provides 80% of value at 20% of cost

### Phase 3 - High Complexity (8-12 weeks)

**Priority:** Enhanced capabilities, premium features

6. **OSINT Provider** (20-30 days)
   - Multiple API integrations
   - Complex rate limiting and caching
   - Consider phased rollout by source

7. **LLM Synthesis Provider** (25-35 days)
   - Complex extraction logic
   - LLM prompt engineering
   - Multiple fallback strategies

8. **Dark Web Provider - Full** (10-15 days)
   - Premium intel services (Recorded Future, Flashpoint)
   - High cost, evaluate ROI carefully
   - Consider as optional premium tier

---

## API Cost Estimates

### Free/Low-Cost APIs

| API | Cost | Notes |
|-----|------|-------|
| OFAC SDN List | Free | Daily XML/CSV downloads |
| UN Consolidated List | Free | XML format |
| EU Consolidated List | Free | XML format |
| SEC EDGAR | Free | Rate limited (10 req/sec) |
| IPEDS | Free | Annual data releases |
| Have I Been Pwned | $3.50/domain/month | Volume discounts available |

### Premium APIs (Estimated)

| API | Cost | Notes |
|-----|------|-------|
| LinkedIn API | $10k-50k/year | Depends on volume, partnership tier |
| World-Check | $25k-100k/year | Volume-based pricing |
| Recorded Future | $50k-150k/year | Enterprise threat intel |
| Flashpoint | $50k-100k/year | Dark web monitoring |
| LexisNexis | $20k-80k/year | Public records |
| NewsAPI | $449-4,999/month | Depends on requests |

---

## Key Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **API Rate Limits** | High | High | Implement caching, request queuing, backoff |
| **API Costs Exceed Budget** | High | Medium | Volume-based negotiation, tiered rollout |
| **Contract Negotiation Delays** | Medium | High | Start NSC, World-Check negotiations early |
| **Data Quality Variance** | Medium | Medium | Confidence scoring, multi-source validation |
| **API Deprecation** | Low | Low | Provider abstraction already in place |
| **Compliance Requirements** | High | Medium | Legal review for each data source |

---

## Architecture Assessment

### Current Strengths

The codebase is **well-prepared** for real API integration:

- ✅ **Provider Abstraction Layer** - `BaseDataProvider` protocol cleanly separates interface from implementation
- ✅ **Configuration via Pydantic** - Each provider has typed config models
- ✅ **Circuit Breaker Pattern** - Already implemented in `providers/circuit_breaker.py`
- ✅ **Caching Infrastructure** - Redis-based caching ready
- ✅ **Rate Limiting Support** - Per-provider rate limit configuration
- ✅ **Confidence Scoring** - All providers return confidence scores
- ✅ **Audit Logging** - Data access logging in place

### Conversion Strategy

The simulation methods are cleanly isolated, making replacement straightforward:

```python
# Current (simulated)
async def _simulate_nsc_verification(self, ...) -> VerifiedEducation:
    # Hash-based fake response
    ...

# Converted (real)
async def _verify_via_nsc(self, ...) -> VerifiedEducation:
    async with self._http_client as client:
        response = await client.post(self._config.nsc_api_url, ...)
        return self._parse_nsc_response(response)
```

### Recommended Infrastructure Additions

| Component | Purpose | Effort |
|-----------|---------|--------|
| API Key Management | Secure storage for API credentials | 2-3 days |
| Request Queue | Rate limit compliance | 3-5 days |
| Response Cache | Reduce API calls, improve latency | 2-3 days |
| Webhook Handlers | Receive real-time updates | 3-5 days |
| Health Dashboard | Monitor API status | 2-3 days |

---

## Appendix: Files Requiring Changes

```
src/elile/providers/
├── synthesis/
│   └── provider.py          # 1,424 lines - HIGH effort
├── osint/
│   └── provider.py          # 924 lines - HIGH effort
├── darkweb/
│   ├── provider.py          # 749 lines - MEDIUM-HIGH effort
│   └── breach_database.py   # 269 lines - LOW effort
├── education/
│   ├── provider.py          # 855 lines - MEDIUM effort
│   └── diploma_mill.py      # 302 lines - LOW effort
└── sanctions/
    └── provider.py          # 654 lines - MEDIUM effort

Total: 5,177 lines across 7 files
```

---

*Document Version: 1.0*
*Last Updated: 2026-02-02*
