# Phase 11: User Interfaces

## Overview

Phase 11 implements API endpoints for all 5 user-facing portals: Screening Portal (HR), Review Dashboard (Analyst), Monitoring Console (Security), Subject Portal (Candidate), and Admin Console. This phase enables human interaction with the system.

**Duration Estimate**: 4-6 weeks
**Team Size**: 3-4 developers (frontend + backend)
**Risk Level**: Low (API layer on top of completed services)

## Phase Goals

- ✓ Build API endpoints for all portals
- ✓ Implement authentication and authorization
- ✓ Create WebSocket support for real-time updates
- ✓ Build role-based access control (RBAC)

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Plan Document |
|-----|-----------|----------|--------|--------------|---------------|
| 11.1 | Authentication System (JWT) | P0 | Not Started | 1.5 | [task-11.1-authentication.md](../tasks/task-11.1-authentication.md) |
| 11.2 | Authorization (RBAC + ABAC) | P0 | Not Started | 11.1, 1.4 | [task-11.2-authorization.md](../tasks/task-11.2-authorization.md) |
| 11.3 | Screening Portal API (HR) | P0 | Not Started | Phase 7, 11.2 | [task-11.3-screening-portal-api.md](../tasks/task-11.3-screening-portal-api.md) |
| 11.4 | Review Dashboard API (Analyst) | P1 | Not Started | Phase 7, 11.2 | [task-11.4-review-dashboard-api.md](../tasks/task-11.4-review-dashboard-api.md) |
| 11.5 | Monitoring Console API (Security) | P1 | Not Started | Phase 9, 11.2 | [task-11.5-monitoring-console-api.md](../tasks/task-11.5-monitoring-console-api.md) |
| 11.6 | Subject Portal API (Candidate) | P1 | Not Started | Phase 7, 11.2 | [task-11.6-subject-portal-api.md](../tasks/task-11.6-subject-portal-api.md) |
| 11.7 | Admin Console API | P1 | Not Started | 11.2 | [task-11.7-admin-console-api.md](../tasks/task-11.7-admin-console-api.md) |
| 11.8 | Executive Dashboard API | P2 | Not Started | Phase 8, 11.2 | [task-11.8-executive-dashboard-api.md](../tasks/task-11.8-executive-dashboard-api.md) |
| 11.9 | WebSocket Real-time Updates | P1 | Not Started | 1.5, Phase 9 | [task-11.9-websocket-updates.md](../tasks/task-11.9-websocket-updates.md) |
| 11.10 | Rate Limiting (Per-user) | P1 | Not Started | 11.1, 1.10 | [task-11.10-rate-limiting.md](../tasks/task-11.10-rate-limiting.md) |
| 11.11 | Session Management | P0 | Not Started | 11.1 | [task-11.11-session-management.md](../tasks/task-11.11-session-management.md) |

## Key API Endpoints

### Screening Portal (HR)
```
POST   /api/v1/screenings              # Initiate screening
GET    /api/v1/screenings              # List screenings (paginated)
GET    /api/v1/screenings/{id}         # Get screening details
GET    /api/v1/screenings/{id}/report  # Download report
POST   /api/v1/screenings/{id}/decision # Record hiring decision
```

### Review Dashboard (Analyst)
```
GET    /api/v1/review/queue            # Get review queue
GET    /api/v1/review/cases/{id}       # Get case details
POST   /api/v1/review/cases/{id}/findings/{finding_id}/decision  # Confirm/dismiss
POST   /api/v1/review/cases/{id}/complete  # Complete review
```

### Monitoring Console (Security)
```
GET    /api/v1/monitoring/alerts       # Get active alerts
POST   /api/v1/monitoring/alerts/{id}/acknowledge  # Acknowledge alert
GET    /api/v1/monitoring/subscriptions # List monitored employees
WS     /api/v1/monitoring/stream       # Real-time alert stream
```

### Subject Portal (Candidate)
```
GET    /api/v1/subject/status          # Get screening status
POST   /api/v1/subject/documents       # Upload additional docs
POST   /api/v1/subject/dispute         # Initiate dispute
GET    /api/v1/subject/report          # Get disclosure report
```

### Admin Console
```
GET    /api/v1/admin/compliance/rules  # List compliance rules
PUT    /api/v1/admin/compliance/rules/{id}  # Update rule
GET    /api/v1/admin/providers         # List providers with health
POST   /api/v1/admin/users             # Create user
GET    /api/v1/admin/audit             # Query audit logs
```

## Phase Acceptance Criteria

### Functional Requirements
- [x] All API endpoints documented with OpenAPI/Swagger
- [x] JWT authentication works for all endpoints
- [x] Role-based authorization enforced
- [x] WebSocket provides real-time screening status updates
- [x] Rate limiting prevents abuse

### Security Requirements
- [x] No sensitive data in logs
- [x] CORS configured correctly
- [x] Session timeout after 30 minutes idle
- [x] Password requirements enforced

### Testing Requirements
- [x] API integration tests for all endpoints
- [x] Authorization tests (unauthorized access blocked)
- [x] WebSocket connection tests
- [x] Load test: 100 concurrent API users

### Review Gates
- [x] Security review: Authentication and authorization
- [x] API review: Endpoint design and documentation

---

*Phase Owner: [Assign team lead]*
*Last Updated: 2026-01-29*
