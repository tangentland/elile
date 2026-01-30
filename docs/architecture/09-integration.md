# Integration & API

> **Prerequisites**: [01-design.md](01-design.md), [03-screening.md](03-screening.md)
>
> **See also**: [06-data-sources.md](06-data-sources.md) for provider integration, [10-platform.md](10-platform.md) for deployment

## Core API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/screenings` | POST | Initiate new screening with service config |
| `/v1/screenings/{id}` | GET | Get screening status/results |
| `/v1/screenings/{id}/report` | GET | Download screening report |
| `/v1/subjects/{id}/monitor` | POST | Start ongoing monitoring |
| `/v1/subjects/{id}/monitor` | PUT | Update vigilance level |
| `/v1/subjects/{id}/monitor` | DELETE | Stop monitoring |
| `/v1/service-configs` | GET | List available service configurations |
| `/v1/service-configs/validate` | POST | Validate a service configuration |
| `/v1/compliance/rules` | GET | List compliance rules |
| `/v1/audit/events` | GET | Query audit log |

## Screening Request Schema

```python
class ScreeningRequest(BaseModel):
    # Subject identification
    subject: SubjectInfo

    # Compliance context (REQUIRED)
    locale: Locale
    role_category: RoleCategory

    # Service configuration (REQUIRED)
    service_config: ServiceConfiguration

    # Or use preset
    # service_preset: str  # e.g., "government_classified"

    # Workflow
    callback_url: str | None
    priority: Priority = Priority.NORMAL

    # Consent reference
    consent_reference: str


class SubjectInfo(BaseModel):
    # Identity
    first_name: str
    last_name: str
    middle_name: str | None
    date_of_birth: date

    # Identifiers
    ssn: str | None  # Last 4 or full
    passport_number: str | None
    driver_license: str | None

    # Contact
    email: str
    phone: str | None

    # Address
    current_address: Address
    previous_addresses: list[Address] = []


class ServiceConfiguration(BaseModel):
    tier: ServiceTier              # standard | enhanced
    vigilance: VigilanceLevel      # v0 | v1 | v2 | v3
    degrees: SearchDegree          # d1 | d2 | d3
    human_review: ReviewLevel      # automated | analyst | investigator | dedicated

    # Optional customizations
    additional_checks: list[CheckType] = []
    excluded_checks: list[CheckType] = []
```

## Response Schemas

```python
class ScreeningResponse(BaseModel):
    screening_id: UUID
    status: ScreeningStatus
    created_at: datetime
    updated_at: datetime

    # Progress
    progress_percent: int
    current_phase: str
    estimated_completion: datetime | None

    # Results (when complete)
    risk_score: RiskScore | None
    recommendation: Recommendation | None
    findings_summary: FindingsSummary | None

    # Links
    report_url: str | None
    review_url: str | None


class ScreeningStatus(str, Enum):
    PENDING_CONSENT = "pending_consent"
    COLLECTING_DATA = "collecting_data"
    ANALYZING = "analyzing"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    FAILED = "failed"
```

## HRIS Integration Gateway

Connects to HR systems for consent and workflow.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HRIS INTEGRATION GATEWAY                      │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  WEBHOOK RECEIVER                        │    │
│  │                                                          │    │
│  │  Receives events:                                        │    │
│  │  - New hire initiated (includes service config)         │    │
│  │  - Consent granted                                       │    │
│  │  - Position change (may trigger tier change)            │    │
│  │  - Termination (stops monitoring)                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  EVENT PROCESSOR                         │    │
│  │                                                          │    │
│  │  - Validates consent scope matches service config       │    │
│  │  - Maps role to default service configuration           │    │
│  │  - Initiates appropriate screening workflow             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Workday    │     │ SuccessFactors│    │  Oracle HCM  │    │
│  │   Adapter    │     │   Adapter    │     │   Adapter    │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  RESULT PUBLISHER                        │    │
│  │                                                          │    │
│  │  - Status updates                                        │    │
│  │  - Risk summary (detail level configurable)             │    │
│  │  - Monitoring alerts                                     │    │
│  │  - Adverse action workflow triggers                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## HRIS Webhook Events

### Inbound Events (HRIS → Elile)

| Event | Payload | Action |
|-------|---------|--------|
| `hire.initiated` | Candidate info, position, consent | Create screening request |
| `consent.granted` | Consent reference, scope | Start screening |
| `position.changed` | Employee ID, new role | Re-evaluate service config |
| `employee.terminated` | Employee ID, date | Stop monitoring |
| `rehire.initiated` | Employee ID, position | Resume monitoring |

### Outbound Events (Elile → HRIS)

| Event | Payload | Trigger |
|-------|---------|---------|
| `screening.started` | Screening ID, estimated completion | After consent verification |
| `screening.progress` | Screening ID, percent, phase | At each phase transition |
| `screening.complete` | Screening ID, risk level, recommendation | When analysis complete |
| `review.required` | Screening ID, reason | When human review triggered |
| `alert.generated` | Alert details, severity | During ongoing monitoring |
| `adverse_action.pending` | Screening ID, findings | When adverse action initiated |

## HRIS Adapter Interface

```python
class HRISAdapter(Protocol):
    """Interface for HRIS platform adapters."""

    @property
    def platform_id(self) -> str: ...

    async def validate_webhook(
        self,
        headers: dict,
        payload: bytes,
    ) -> bool:
        """Validate webhook signature."""
        ...

    async def parse_event(
        self,
        event_type: str,
        payload: dict,
    ) -> HRISEvent:
        """Parse platform-specific event format."""
        ...

    async def publish_update(
        self,
        employee_id: str,
        update: ScreeningUpdate,
    ) -> bool:
        """Push update to HRIS."""
        ...

    async def get_employee(
        self,
        employee_id: str,
    ) -> EmployeeInfo:
        """Fetch employee details."""
        ...
```

## Supported HRIS Platforms

| Platform | Status | Features |
|----------|--------|----------|
| Workday | Planned | Full integration, custom reports |
| SAP SuccessFactors | Planned | Webhook, API sync |
| Oracle HCM | Planned | Webhook, limited API |
| ADP | Planned | Webhook |
| BambooHR | Planned | Webhook, API sync |

## Callback/Webhook Delivery

For async notification of screening events:

```python
class WebhookConfig(BaseModel):
    url: str
    secret: str  # For HMAC signature
    events: list[EventType]
    retry_policy: RetryPolicy


class WebhookPayload(BaseModel):
    event_type: str
    timestamp: datetime
    screening_id: UUID
    data: dict


class RetryPolicy(BaseModel):
    max_retries: int = 3
    backoff_seconds: list[int] = [30, 300, 3600]  # 30s, 5m, 1h
```

## API Authentication

### API Key Authentication

```http
GET /v1/screenings HTTP/1.1
Host: api.elile.com
Authorization: Bearer sk_live_xxxxxxxxxxxx
Content-Type: application/json
```

### OAuth 2.0 (HRIS Integrations)

```http
POST /oauth/token HTTP/1.1
Host: api.elile.com
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=xxx&client_secret=xxx
```

## Rate Limiting

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Standard API | 1000 requests | Per minute |
| Screening initiation | 100 requests | Per minute |
| Bulk operations | 10 requests | Per minute |
| Webhook delivery | 1000 deliveries | Per minute |

## API Versioning

- Version in URL path: `/v1/screenings`
- Breaking changes increment major version
- Deprecation notice: 6 months minimum
- Sunset notice: 12 months minimum

## Error Responses

```python
class APIError(BaseModel):
    error_code: str
    message: str
    details: dict | None
    request_id: str
    timestamp: datetime


# Example error codes
class ErrorCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    INVALID_CONFIG = "invalid_configuration"
    CONSENT_MISSING = "consent_missing"
    COMPLIANCE_BLOCKED = "compliance_blocked"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
```

---

*See [10-platform.md](10-platform.md) for deployment configuration*
*See [11-interfaces.md](11-interfaces.md) for UI integration points*
