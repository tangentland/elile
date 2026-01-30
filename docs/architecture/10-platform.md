# Platform Architecture

> **Prerequisites**: [01-design.md](01-design.md), [02-core-system.md](02-core-system.md)
>
> **See also**: [09-integration.md](09-integration.md) for API configuration

This document covers the modular monolith structure, process model, deployment options, and scaling strategy.

## Module Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ELILE MODULAR MONOLITH                           │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         API LAYER (FastAPI)                         │ │
│  │   /v1/screenings  /v1/subjects  /v1/reports  /v1/admin  /v1/webhooks│
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      APPLICATION SERVICES                           │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │  Screening   │ │  Monitoring  │ │   Report     │ │   Admin    │ │ │
│  │  │   Service    │ │   Service    │ │   Service    │ │  Service   │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        DOMAIN MODULES                               │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ SCREENING MODULE                                              │  │ │
│  │  │ • ScreeningEngine (LangGraph workflow)                       │  │ │
│  │  │ • QueryGenerator                                              │  │ │
│  │  │ • ResultAnalyzer                                              │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ COMPLIANCE MODULE                                             │  │ │
│  │  │ • RuleEngine                                                  │  │ │
│  │  │ • LocaleResolver                                              │  │ │
│  │  │ • ConsentValidator                                            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ RISK MODULE                                                   │  │ │
│  │  │ • RiskAnalyzer                                                │  │ │
│  │  │ • EvolutionDetector                                           │  │ │
│  │  │ • ConnectionMapper                                            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ ENTITY MODULE                                                 │  │ │
│  │  │ • EntityRegistry                                              │  │ │
│  │  │ • ProfileVersioning                                           │  │ │
│  │  │ • EntityResolution                                            │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  │  ┌──────────────────────────────────────────────────────────────┐  │ │
│  │  │ REPORT MODULE                                                 │  │ │
│  │  │ • ReportGenerator                                             │  │ │
│  │  │ • PersonaFilter                                               │  │ │
│  │  │ • PDFRenderer                                                 │  │ │
│  │  └──────────────────────────────────────────────────────────────┘  │ │
│  │                                                                      │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     INTEGRATION ADAPTERS                            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │   Provider   │ │    HRIS      │ │  AI Model    │ │Notification│ │ │
│  │  │   Adapters   │ │   Adapters   │ │   Adapters   │ │  Adapters  │ │ │
│  │  │              │ │              │ │              │ │            │ │ │
│  │  │ • Sterling   │ │ • Workday    │ │ • Claude     │ │ • Email    │ │ │
│  │  │ • Checkr     │ │ • SAP SF     │ │ • GPT-4      │ │ • Webhook  │ │ │
│  │  │ • PACER      │ │ • Oracle     │ │ • Gemini     │ │ • SMS      │ │ │
│  │  │ • World-Check│ │ • ADP        │ │              │ │            │ │ │
│  │  │ • Acxiom     │ │              │ │              │ │            │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     INFRASTRUCTURE LAYER                            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │ │
│  │  │  Repository  │ │    Cache     │ │  Job Queue   │ │   Audit    │ │ │
│  │  │  (SQLAlchemy)│ │   (Redis)    │ │   (ARQ)      │ │   Logger   │ │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Module Boundaries & Communication

Modules communicate through well-defined interfaces, not direct imports of internal classes:

```python
# Module public interface (elile/screening/__init__.py)
from .service import ScreeningService
from .models import ScreeningRequest, ScreeningResult, ScreeningStatus

__all__ = ["ScreeningService", "ScreeningRequest", "ScreeningResult", "ScreeningStatus"]

# Internal implementation details are NOT exported
# Other modules import only from the public interface
```

### Communication Patterns

| Pattern | Use Case | Example |
|---------|----------|---------|
| **Direct call** | Synchronous, in-request | `compliance.validate(request)` |
| **Domain events** | Async notification, decoupled | `ScreeningCompleted` event triggers report generation |
| **Job queue** | Background processing | Provider data fetching, PDF generation |

```
┌─────────────────────────────────────────────────────────────────┐
│                  MODULE COMMUNICATION PATTERNS                   │
│                                                                  │
│  SYNCHRONOUS (in-process function calls)                        │
│  ─────────────────────────────────────────                      │
│                                                                  │
│  API Request                                                     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐  validate()  ┌─────────────┐                  │
│  │  Screening  │─────────────►│ Compliance  │                  │
│  │  Service    │◄─────────────│   Module    │                  │
│  └─────────────┘   result     └─────────────┘                  │
│       │                                                          │
│       │ analyze()                                                │
│       ▼                                                          │
│  ┌─────────────┐                                                │
│  │    Risk     │                                                │
│  │   Module    │                                                │
│  └─────────────┘                                                │
│                                                                  │
│  ASYNCHRONOUS (domain events via in-memory bus)                 │
│  ───────────────────────────────────────────────                │
│                                                                  │
│  ┌─────────────┐  ScreeningCompleted  ┌─────────────┐          │
│  │  Screening  │─────────────────────►│   Report    │          │
│  │  Service    │      (event)         │   Module    │          │
│  └─────────────┘                      └─────────────┘          │
│                          │                                       │
│                          ▼                                       │
│                   ┌─────────────┐                               │
│                   │Notification │                               │
│                   │   Module    │                               │
│                   └─────────────┘                               │
│                                                                  │
│  BACKGROUND (job queue for heavy/external work)                 │
│  ──────────────────────────────────────────────                 │
│                                                                  │
│  ┌─────────────┐   enqueue()   ┌─────────────┐  fetch  ┌─────┐ │
│  │  Screening  │──────────────►│  Job Queue  │────────►│Worker│ │
│  │  Service    │               │   (Redis)   │         │     │ │
│  └─────────────┘               └─────────────┘         └─────┘ │
│                                                            │     │
│                                                            ▼     │
│                                                    ┌───────────┐ │
│                                                    │ Provider  │ │
│                                                    │ Adapter   │ │
│                                                    └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Process Model

The application runs as two process types that can be scaled independently:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          PROCESS MODEL                                   │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        WEB PROCESS                                  │ │
│  │                                                                      │ │
│  │  uvicorn elile.main:app --workers N                                │ │
│  │                                                                      │ │
│  │  Responsibilities:                                                  │ │
│  │  • HTTP API requests (FastAPI)                                      │ │
│  │  • WebSocket connections (alerts, real-time updates)               │ │
│  │  • Webhook receivers (HRIS events)                                 │ │
│  │  • Health checks                                                    │ │
│  │                                                                      │ │
│  │  Scaling: Horizontal via process count (--workers) or load balancer│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                       WORKER PROCESS                                │ │
│  │                                                                      │ │
│  │  arq elile.worker.WorkerSettings --concurrency N                   │ │
│  │                                                                      │ │
│  │  Responsibilities:                                                  │ │
│  │  • Provider data fetching (HTTP calls to external APIs)            │ │
│  │  • LangGraph workflow execution (screening pipeline)               │ │
│  │  • Report generation (PDF rendering)                               │ │
│  │  • Vigilance scheduled checks                                       │ │
│  │  • Entity resolution (background deduplication)                    │ │
│  │                                                                      │ │
│  │  Scaling: Horizontal via worker count or concurrency setting       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                     SCHEDULER PROCESS (optional)                    │ │
│  │                                                                      │ │
│  │  python -m elile.scheduler                                         │ │
│  │                                                                      │ │
│  │  Responsibilities:                                                  │ │
│  │  • Vigilance cron jobs (V1/V2/V3 check triggers)                   │ │
│  │  • Data freshness expiration checks                                │ │
│  │  • Cleanup jobs (cache pruning, audit log rotation)                │ │
│  │                                                                      │ │
│  │  Note: Can be embedded in worker process for simpler deployments   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Deployment Options

The modular monolith supports multiple deployment targets:

### Option A: Single VM / Bare Metal (Simplest)

```
┌─────────────────────────────────────────────────────────────────┐
│                         SINGLE SERVER                            │
│                                                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │   Web   │  │ Worker  │  │ Worker  │  │Scheduler│            │
│  │ Process │  │   #1    │  │   #2    │  │         │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
│       │            │            │            │                   │
│       └────────────┴────────────┴────────────┘                   │
│                         │                                         │
│                    ┌────┴────┐                                   │
│                    │  Redis  │                                   │
│                    └─────────┘                                   │
│                                                                   │
│  Managed: PostgreSQL (RDS/Cloud SQL)                            │
│  Process Manager: systemd / supervisord                         │
└─────────────────────────────────────────────────────────────────┘
```

### Option B: Container (Docker Compose / ECS / Cloud Run)

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTAINER ORCHESTRATION                      │
│                                                                   │
│  ┌───────────────────┐  ┌───────────────────┐                   │
│  │   Web Container   │  │  Worker Container │                   │
│  │   (2-4 replicas)  │  │   (2-4 replicas)  │                   │
│  │                   │  │                   │                   │
│  │  CMD: uvicorn     │  │  CMD: arq         │                   │
│  │       --workers 2 │  │       --concurrency 10                │
│  └───────────────────┘  └───────────────────┘                   │
│           │                      │                               │
│           └──────────┬───────────┘                               │
│                      ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              MANAGED SERVICES                             │   │
│  │  PostgreSQL (RDS)  │  Redis (ElastiCache)  │  S3 (Reports)│   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Option C: Platform-as-a-Service (Railway, Render, Fly.io)

```
┌─────────────────────────────────────────────────────────────────┐
│                         PAAS PLATFORM                            │
│                                                                   │
│  Service: elile-web          Service: elile-worker              │
│  ┌───────────────────┐       ┌───────────────────┐              │
│  │ Procfile: web     │       │ Procfile: worker  │              │
│  │ Instances: 2      │       │ Instances: 2      │              │
│  └───────────────────┘       └───────────────────┘              │
│                                                                   │
│  Addons: PostgreSQL, Redis, S3-compatible storage               │
└─────────────────────────────────────────────────────────────────┘
```

## Scaling Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SCALING STRATEGY                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  VERTICAL SCALING (Scale Up)                                            │
│  ──────────────────────────                                             │
│  • Increase CPU/RAM on web and worker processes                        │
│  • Increase database connection pool size                              │
│  • Increase Redis memory                                                │
│                                                                          │
│  Suitable for: Initial growth, up to ~1000 concurrent screenings       │
│                                                                          │
│  HORIZONTAL SCALING (Scale Out)                                         │
│  ─────────────────────────────                                          │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     LOAD BALANCER                                │    │
│  │                   (nginx / ALB / Cloud LB)                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│         │              │              │              │                   │
│         ▼              ▼              ▼              ▼                   │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │  Web #1   │  │  Web #2   │  │  Web #3   │  │  Web #4   │            │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │
│                                                                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐            │
│  │ Worker #1 │  │ Worker #2 │  │ Worker #3 │  │ Worker #4 │            │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘            │
│         │              │              │              │                   │
│         └──────────────┴──────────────┴──────────────┘                   │
│                              │                                           │
│                    ┌─────────┴─────────┐                                │
│                    ▼                   ▼                                 │
│             ┌───────────┐       ┌───────────┐                           │
│             │  Redis    │       │ PostgreSQL│                           │
│             │ (Cluster) │       │ (Primary/ │                           │
│             │           │       │  Replica) │                           │
│             └───────────┘       └───────────┘                           │
│                                                                          │
│  Suitable for: High volume, ~10,000+ concurrent screenings             │
│                                                                          │
│  FUTURE: MODULAR EXTRACTION                                             │
│  ─────────────────────────                                              │
│  If specific modules become bottlenecks, they can be extracted:        │
│  • Provider Gateway → Separate service (high external API load)        │
│  • Report Generator → Separate service (CPU-intensive PDF rendering)   │
│  • Module boundaries already defined; extraction is straightforward    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Configuration Management

```python
# elile/config/settings.py

class Settings(BaseSettings):
    """Application configuration via environment variables."""

    # Database
    database_url: PostgresDsn
    database_pool_size: int = 20
    database_pool_overflow: int = 10

    # Redis
    redis_url: RedisDsn
    redis_pool_size: int = 10

    # API Keys (secrets)
    anthropic_api_key: SecretStr
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # Provider API Keys
    sterling_api_key: SecretStr | None = None
    world_check_api_key: SecretStr | None = None
    # ... other providers

    # Feature Flags
    enable_enhanced_tier: bool = True
    enable_evolution_analytics: bool = True
    enable_human_review_queue: bool = True

    # Process Configuration
    web_workers: int = 4
    worker_concurrency: int = 10
    scheduler_enabled: bool = True

    # Observability
    otel_endpoint: str | None = None
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

### Environment-based Deployment

```bash
# .env.production
DATABASE_URL=postgresql://user:pass@db.example.com:5432/elile
REDIS_URL=redis://redis.example.com:6379/0
ANTHROPIC_API_KEY=sk-ant-...
LOG_LEVEL=INFO
LOG_FORMAT=json
WEB_WORKERS=4
WORKER_CONCURRENCY=20
```

---

*See [09-integration.md](09-integration.md) for API configuration*
*See [11-interfaces.md](11-interfaces.md) for UI deployment*
