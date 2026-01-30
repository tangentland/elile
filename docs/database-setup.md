# Database Setup Guide

## Overview

This guide covers setting up the PostgreSQL database for Elile, running migrations, and understanding the core data model.

## Prerequisites

- PostgreSQL 15+ installed
- Python 3.12+ with Elile dependencies installed
- Redis 7.0+ (for caching)

## Database Installation

### macOS (Homebrew)

```bash
brew install postgresql@15
brew services start postgresql@15

# Create database and user
createdb elile_dev
psql elile_dev -c "CREATE USER elile_user WITH PASSWORD 'elile_pass';"
psql elile_dev -c "GRANT ALL PRIVILEGES ON DATABASE elile_dev TO elile_user;"
```

### Docker

```bash
docker run -d \
  --name elile-postgres \
  -e POSTGRES_USER=elile_user \
  -e POSTGRES_PASSWORD=elile_pass \
  -e POSTGRES_DB=elile_dev \
  -p 5432:5432 \
  postgres:15
```

## Configuration

Update your `.env` file with database connection details:

```bash
DATABASE_URL=postgresql+asyncpg://elile_user:elile_pass@localhost:5432/elile_dev
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

## Running Migrations

Initialize the database schema using Alembic:

```bash
# Run all pending migrations
alembic upgrade head

# Verify tables were created
psql elile_dev -c "\dt"
```

Expected tables:
- `entities` - Core entity records (people, organizations, addresses)
- `entity_profiles` - Versioned snapshots of entity investigations
- `entity_relations` - Relationships between entities
- `cached_data_sources` - Cached provider data with freshness tracking

## Database Schema

### Core Tables

#### entities

Stores the fundamental objects being investigated.

| Column | Type | Description |
|--------|------|-------------|
| entity_id | UUID (PK) | Unique identifier |
| entity_type | VARCHAR(50) | Type: individual, organization, address |
| canonical_identifiers | JSONB | Encrypted identifiers (SSN, EIN, etc.) |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

**Indexes:**
- `idx_entity_type` on `entity_type`
- `idx_entity_created` on `created_at`

#### entity_profiles

Versioned snapshots of investigations, enabling temporal tracking and comparison.

| Column | Type | Description |
|--------|------|-------------|
| profile_id | UUID (PK) | Unique identifier |
| entity_id | UUID (FK) | Reference to entity |
| version | INTEGER | Version number (incremental) |
| trigger_type | VARCHAR(50) | screening, monitoring, manual |
| trigger_id | UUID | ID of triggering investigation |
| findings | JSONB | Array of investigation findings |
| risk_score | JSONB | Computed risk assessment |
| connections | JSONB | Network graph of connections |
| connection_count | INTEGER | Count of discovered connections |
| data_sources_used | JSONB | List of data sources consulted |
| stale_data_used | JSONB | Flagged stale data sources |
| previous_version | INTEGER | Link to prior version |
| delta | JSONB | Changes from previous version |
| evolution_signals | JSONB | Detected evolution patterns |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

**Indexes:**
- `idx_profile_entity` on `entity_id`
- `idx_profile_version` (unique) on `(entity_id, version)`
- `idx_profile_trigger` on `(trigger_type, trigger_id)`
- `idx_profile_created` on `created_at`

#### entity_relations

Tracks discovered relationships between entities.

| Column | Type | Description |
|--------|------|-------------|
| relation_id | UUID (PK) | Unique identifier |
| from_entity_id | UUID (FK) | Source entity |
| to_entity_id | UUID (FK) | Target entity |
| relation_type | VARCHAR(100) | employer, household, etc. |
| confidence_score | FLOAT | 0.0-1.0 confidence |
| discovered_in_screening | UUID (FK) | Profile that discovered this |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

**Indexes:**
- `idx_from_entity` on `from_entity_id`
- `idx_to_entity` on `to_entity_id`
- `idx_relation_type` on `relation_type`

#### cached_data_sources

Stores cached provider responses to minimize API calls and costs.

| Column | Type | Description |
|--------|------|-------------|
| cache_id | UUID (PK) | Unique identifier |
| entity_id | UUID (FK) | Reference to entity |
| provider_id | VARCHAR(100) | Provider identifier |
| check_type | VARCHAR(100) | Type of check performed |
| data_origin | VARCHAR(50) | paid_external or customer_provided |
| customer_id | UUID (FK) | Customer ID (if customer_provided) |
| acquired_at | TIMESTAMP | When data was acquired |
| freshness_status | VARCHAR(50) | fresh, stale, expired |
| fresh_until | TIMESTAMP | Freshness expiration |
| stale_until | TIMESTAMP | Staleness expiration |
| raw_response | BYTEA | Encrypted provider response |
| normalized_data | JSONB | Normalized data structure |
| cost_incurred | NUMERIC(10,2) | Cost of this check |
| cost_currency | VARCHAR(3) | Currency code (USD, EUR, etc.) |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

**Indexes:**
- `idx_cache_entity_check` on `(entity_id, check_type)`
- `idx_cache_freshness` on `(freshness_status, fresh_until)`
- `idx_cache_provider` on `provider_id`
- `idx_cache_customer` on `customer_id`
- `idx_cache_origin` on `data_origin`

## Creating Migrations

When you modify models, create a new migration:

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new field to entity"

# Review the generated migration in migrations/versions/
# Edit if needed, then apply:
alembic upgrade head
```

## Rollback

To rollback the last migration:

```bash
alembic downgrade -1
```

To rollback to a specific version:

```bash
alembic downgrade <revision_id>
```

## Testing Database

For running tests, configure a test database:

```bash
DATABASE_URL=postgresql+asyncpg://elile_user:elile_pass@localhost:5432/elile_test
ENVIRONMENT=test
```

## Common Operations

### Check Migration Status

```bash
alembic current
```

### View Migration History

```bash
alembic history
```

### Generate SQL for Migration (without applying)

```bash
alembic upgrade head --sql > migration.sql
```

## Troubleshooting

### Connection Refused

Verify PostgreSQL is running:

```bash
pg_isready
```

### Permission Denied

Grant appropriate permissions:

```bash
psql elile_dev -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO elile_user;"
```

### Migration Conflicts

If you have conflicting migrations, merge them:

```bash
alembic merge <rev1> <rev2> -m "Merge migrations"
```

## Production Considerations

1. **Connection Pooling**: Configure `DATABASE_POOL_SIZE` based on expected load
2. **SSL**: Use `?ssl=require` in production DATABASE_URL
3. **Backups**: Set up automated backups with point-in-time recovery
4. **Monitoring**: Monitor connection pool utilization and query performance
5. **Encryption**: Ensure encryption at rest is enabled on PostgreSQL

## Next Steps

- Set up Redis for caching (see `redis-setup.md`)
- Configure audit logging (Task 1.2)
- Implement encryption utilities (Task 1.6)
