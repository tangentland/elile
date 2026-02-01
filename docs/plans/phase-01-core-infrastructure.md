# Phase 1: Core Infrastructure

## Overview

Phase 1 establishes the foundational infrastructure required for all subsequent development. This includes database schema, audit logging, request context propagation, multi-tenancy support, API framework, and core utilities. All P0 tasks in this phase must be completed before moving to Phase 2.

**Duration Estimate**: Foundation for entire system
**Team Size**: 2-3 developers
**Risk Level**: Medium (architectural decisions have long-term impact)

## Phase Goals

- ✓ Establish database schema with proper indexing and constraints
- ✓ Implement comprehensive audit logging for compliance
- ✓ Build request context propagation system for multi-tenant isolation
- ✓ Set up FastAPI framework with authentication middleware
- ✓ Create encryption utilities for PII protection
- ✓ Implement structured error handling and logging

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 1.1 | Database Schema Foundation | P0 | Not Started | None | [task-1.1-database-schema.md](../tasks/task-1.1-database-schema.md) |
| 1.2 | Audit Logging System | P0 | Not Started | 1.1 | [task-1.2-audit-logging.md](../tasks/task-1.2-audit-logging.md) |
| 1.3 | Request Context Framework | P0 | Not Started | 1.1, 1.2 | [task-1.3-request-context.md](../tasks/task-1.3-request-context.md) |
| 1.4 | Multi-Tenancy Infrastructure | P0 | Not Started | 1.1, 1.3 | [task-1.4-multi-tenancy.md](../tasks/task-1.4-multi-tenancy.md) |
| 1.5 | FastAPI Framework Setup | P0 | Not Started | 1.3 | [task-1.5-fastapi-setup.md](../tasks/task-1.5-fastapi-setup.md) |
| 1.6 | Encryption Utilities | P0 | Not Started | None | [task-1.6-encryption.md](../tasks/task-1.6-encryption.md) |
| 1.7 | Error Handling Framework | P0 | Not Started | 1.2 | [task-1.7-error-handling.md](../tasks/task-1.7-error-handling.md) |
| 1.8 | Configuration Management | P0 | Not Started | None | [task-1.8-configuration.md](../tasks/task-1.8-configuration.md) |
| 1.9 | Database Repository Pattern | P1 | Not Started | 1.1 | [task-1.9-repository-pattern.md](../tasks/task-1.9-repository-pattern.md) |
| 1.10 | Redis Cache Setup | P1 | Not Started | 1.8 | [task-1.10-redis-cache.md](../tasks/task-1.10-redis-cache.md) |
| 1.11 | Structured Logging (structlog) | P1 | Not Started | 1.2 | [task-1.11-structured-logging.md](../tasks/task-1.11-structured-logging.md) |
| 1.12 | Health Check Endpoints | P1 | Not Started | 1.5, 1.10 | [task-1.12-health-checks.md](../tasks/task-1.12-health-checks.md) |

## Task Dependency Graph

```
1.1 (Database Schema) ─┬─→ 1.2 (Audit Logging) ─→ 1.3 (Request Context) ─┬─→ 1.4 (Multi-Tenancy)
                       │                                                  │
                       │                                                  └─→ 1.5 (FastAPI Setup)
                       │
                       └─→ 1.9 (Repository Pattern)

1.6 (Encryption) ──────────────────────────────────────────────────────────→ (Independent)

1.7 (Error Handling) ←── 1.2 (Audit Logging)

1.8 (Configuration) ───→ 1.10 (Redis Cache)

1.11 (Structured Logging) ←── 1.2 (Audit Logging)

1.12 (Health Checks) ←── 1.5 (FastAPI Setup) + 1.10 (Redis Cache)
```

## Parallel Work Opportunities

**Stream 1 (Database)**: Tasks 1.1 → 1.2 → 1.3 → 1.4 → 1.5
**Stream 2 (Utilities)**: Tasks 1.6, 1.8 (can work in parallel)
**Stream 3 (Advanced)**: Tasks 1.9, 1.10, 1.11, 1.12 (after core tasks complete)

## Phase Acceptance Criteria

### Functional Requirements
- [x] PostgreSQL database with core tables (entities, profiles, cache, audit_events, tenants)
- [x] All database tables have proper indexes and foreign key constraints
- [x] Audit logging captures all critical operations (screening initiated, data accessed, etc.)
- [x] Request context flows through all layers with tenant isolation
- [x] FastAPI server starts and responds to health check endpoint
- [x] PII data encrypted at rest using AES-256
- [x] All errors generate structured audit events
- [x] Configuration loads from environment variables with validation

### Non-Functional Requirements
- [x] Database migrations use Alembic for version control
- [x] All database queries use parameterized statements (SQL injection protection)
- [x] Audit logs are append-only and encrypted
- [x] Request context is immutable after creation
- [x] API responses include correlation IDs for tracing
- [x] Configuration supports multiple environments (dev, staging, prod)

### Testing Requirements
- [x] Unit test coverage ≥80% for all modules
- [x] Integration tests for database operations
- [x] Integration tests for API endpoints
- [x] Load test: 100 concurrent requests without errors
- [x] Security test: SQL injection, XSS attempts blocked

### Documentation Requirements
- [x] Database schema ERD diagram
- [x] API documentation (OpenAPI/Swagger)
- [x] Environment variable configuration guide
- [x] Development setup instructions (README)

### Review Gates
- [x] Architecture review: Database schema design
- [x] Security review: Encryption implementation, audit logging
- [x] Code review: All tasks reviewed by senior developer

## Technology Stack (Phase 1)

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Database | PostgreSQL | 15+ | Primary data store |
| ORM | SQLAlchemy | 2.0+ | Database access with async support |
| Migrations | Alembic | 1.13+ | Schema version control |
| API Framework | FastAPI | 0.109+ | Async HTTP API |
| Validation | Pydantic | 2.5+ | Data validation and serialization |
| Cache | Redis | 7.0+ | Session state, rate limiting |
| Encryption | cryptography | 41+ | AES-256 encryption for PII |
| Logging | structlog | 24+ | Structured JSON logging |
| Testing | pytest | 7.4+ | Unit and integration tests |
| Async | asyncio | stdlib | Async/await support |

## Setup Instructions

### Prerequisites
```bash
# Install Python 3.14+
python --version  # Should be 3.14+

# Install PostgreSQL
brew install postgresql@15  # macOS
# or use Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:15

# Install Redis
brew install redis  # macOS
# or use Docker: docker run -d -p 6379:6379 redis:7
```

### Initial Project Structure
```
src/elile/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── settings.py          # Task 1.8
│   └── database.py          # Task 1.1
├── models/
│   ├── __init__.py
│   ├── base.py              # Task 1.1
│   ├── entity.py            # Task 1.1
│   ├── profile.py           # Task 1.1
│   ├── cache.py             # Task 1.1
│   ├── audit.py             # Task 1.2
│   └── tenant.py            # Task 1.4
├── core/
│   ├── __init__.py
│   ├── context.py           # Task 1.3
│   ├── encryption.py        # Task 1.6
│   ├── errors.py            # Task 1.7
│   └── audit.py             # Task 1.2
├── repositories/
│   ├── __init__.py
│   ├── base.py              # Task 1.9
│   ├── entity.py            # Task 1.9
│   └── audit.py             # Task 1.9
├── api/
│   ├── __init__.py
│   ├── app.py               # Task 1.5
│   ├── middleware.py        # Task 1.3, 1.4
│   ├── dependencies.py      # Task 1.3
│   └── health.py            # Task 1.12
└── utils/
    ├── __init__.py
    └── logging.py           # Task 1.11

tests/
├── unit/
│   ├── test_context.py
│   ├── test_encryption.py
│   └── test_errors.py
├── integration/
│   ├── test_database.py
│   ├── test_api.py
│   └── test_audit.py
└── conftest.py              # Pytest fixtures

migrations/                  # Alembic migrations
├── versions/
│   └── 001_initial_schema.py
└── env.py

.env.example
pyproject.toml
README.md
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/elile_dev
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
ENCRYPTION_KEY=<32-byte-base64-encoded-key>
API_SECRET_KEY=<random-secret-for-jwt>

# Environment
ENVIRONMENT=development  # development | staging | production
LOG_LEVEL=INFO
DEBUG=true

# Multi-Tenancy
DEFAULT_TENANT_ID=00000000-0000-0000-0000-000000000000
```

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Database schema changes required later | High | Use Alembic migrations from day 1 |
| Audit log becomes bottleneck | Medium | Use async inserts, separate table per year |
| Encryption key compromise | Critical | Use Vault/HSM in production, rotate keys |
| Multi-tenant data leakage | Critical | All queries filter by tenant_id at ORM level |
| Request context mutation | Medium | Make RequestContext frozen dataclass |

## Phase Completion Checklist

Before moving to Phase 2, verify:

- [ ] All P0 tasks marked "Complete"
- [ ] All acceptance criteria checked
- [ ] Integration tests passing
- [ ] Documentation updated
- [ ] Architecture review sign-off
- [ ] Security review sign-off
- [ ] Demo to stakeholders complete

## Next Phase

Once Phase 1 is complete, proceed to:
- **Phase 2: Service Configuration & Compliance** - Build service tier models and compliance engine

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
