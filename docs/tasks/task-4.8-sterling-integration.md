# Task 4.8: Sterling Integration (T1 Core Provider)

## Overview

Implement Sterling Background Check integration as Tier 1 core provider. Sterling provides comprehensive background checks including criminal, employment, and identity verification. See [06-data-sources.md](../architecture/06-data-sources.md#tier-1-core) for T1 provider requirements.

**Priority**: P0 | **Effort**: 4 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 4.3: Rate Limiter
- Task 4.4: Response Normalizer
- Task 4.6: Error Handler

## Implementation Checklist

- [ ] Implement SterlingProvider class
- [ ] Add API authentication (OAuth 2.0)
- [ ] Build check type mappings
- [ ] Implement response parsing
- [ ] Create normalization schemas
- [ ] Add error handling for Sterling-specific errors
- [ ] Write Sterling integration tests

## Key Implementation

```python
# src/elile/providers/sterling.py
import httpx
from typing import Literal

SterlingCheckType = Literal[
    "criminal_search",
    "employment_verification",
    "education_verification",
    "identity_verification",
    "credit_report",
    "drug_screening"
]

class SterlingConfig(BaseModel):
    """Sterling API configuration."""
    api_key: str
    api_secret: str
    base_url: str = "https://api.sterlingcheck.com/v4"
    timeout: int = 30

class SterlingProvider(DataProvider):
    """Sterling Background Check provider."""

    provider_id = "sterling"
    provider_name = "Sterling Background Check"
    check_types = {
        "criminal", "employment", "education",
        "identity", "credit", "drug_screening"
    }
    cost_per_query = Decimal("25.00")  # Average cost
    rate_limit = 60  # 60 requests per minute

    def __init__(self, config: SterlingConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
            headers=self._get_auth_headers()
        )

    def _get_auth_headers(self) -> dict:
        """Generate authentication headers."""
        # Sterling uses API key authentication
        return {
            "Authorization": f"Basic {self._encode_credentials()}",
            "Content-Type": "application/json",
        }

    def _encode_credentials(self) -> str:
        """Encode API credentials for basic auth."""
        import base64
        creds = f"{self.config.api_key}:{self.config.api_secret}"
        return base64.b64encode(creds.encode()).decode()

    async def query(
        self,
        entity: Entity,
        check_type: str,
        ctx: RequestContext
    ) -> ProviderResponse:
        """Execute Sterling background check."""
        start_time = datetime.utcnow()

        # Map check type to Sterling package
        sterling_package = self._map_check_type(check_type)

        # Build request payload
        payload = self._build_request(entity, sterling_package)

        try:
            # Submit background check
            response = await self.client.post(
                "/screenings",
                json=payload
            )
            response.raise_for_status()

            screening_id = response.json()["id"]

            # Poll for results (Sterling is async)
            raw_data = await self._poll_results(screening_id)

            # Calculate response time
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ProviderResponse(
                provider_id=self.provider_id,
                check_type=check_type,
                query_timestamp=start_time,
                raw_data=raw_data,
                records_found=len(raw_data.get("results", [])),
                cost_incurred=self._calculate_cost(raw_data),
                response_time_ms=response_time,
                metadata={"screening_id": screening_id}
            )

        except httpx.HTTPStatusError as e:
            self._handle_http_error(e)

    def _map_check_type(self, check_type: str) -> str:
        """Map internal check type to Sterling package."""
        mapping = {
            "criminal": "criminal_search",
            "employment": "employment_verification",
            "education": "education_verification",
            "identity": "identity_verification",
            "credit": "credit_report",
        }
        return mapping.get(check_type, check_type)

    def _build_request(self, entity: Entity, package: str) -> dict:
        """Build Sterling API request payload."""
        return {
            "package": package,
            "candidate": {
                "first_name": entity.name_first,
                "last_name": entity.name_last,
                "middle_name": entity.name_middle,
                "date_of_birth": entity.dob.isoformat() if entity.dob else None,
                "ssn": entity.ssn,
                "email": entity.email,
                "phone": entity.phone,
                "address": {
                    "street": entity.address_line1,
                    "city": entity.address_city,
                    "state": entity.address_state,
                    "zip": entity.address_postal,
                    "country": entity.address_country,
                }
            },
            "options": {
                "consent_obtained": True,
                "purpose": "employment",
            }
        }

    async def _poll_results(self, screening_id: str, max_attempts: int = 30) -> dict:
        """Poll Sterling for screening results."""
        for attempt in range(max_attempts):
            response = await self.client.get(f"/screenings/{screening_id}")
            response.raise_for_status()
            data = response.json()

            status = data.get("status")
            if status == "completed":
                return data
            elif status == "failed":
                raise ProviderError(self.provider_id, "Screening failed")

            # Wait before next poll
            await asyncio.sleep(2)

        raise TimeoutError(self.provider_id, "Screening timed out")

    def _calculate_cost(self, raw_data: dict) -> Decimal:
        """Calculate cost based on Sterling response."""
        # Sterling returns cost in response
        cost = raw_data.get("cost", {}).get("total", 0)
        return Decimal(str(cost))

    def _handle_http_error(self, error: httpx.HTTPStatusError):
        """Handle Sterling HTTP errors."""
        status_code = error.response.status_code

        if status_code == 401:
            raise AuthenticationError(self.provider_id, "Invalid credentials")
        elif status_code == 429:
            retry_after = int(error.response.headers.get("Retry-After", 60))
            raise RateLimitError(self.provider_id, retry_after)
        elif status_code >= 500:
            raise ServiceUnavailableError(self.provider_id, "Sterling service unavailable")
        else:
            raise ProviderError(self.provider_id, f"HTTP {status_code}: {error.response.text}")

    def normalize_response(self, response: ProviderResponse) -> NormalizedData:
        """Normalize Sterling response."""
        records = []

        for result in response.raw_data.get("results", []):
            records.extend(self._normalize_result(result))

        return NormalizedData(
            check_type=response.check_type,
            records=records,
            confidence=0.95,  # Sterling is high confidence
            metadata=response.metadata
        )

    def _normalize_result(self, result: dict) -> list[NormalizedRecord]:
        """Normalize single Sterling result."""
        records = []

        result_type = result.get("type")
        if result_type == "criminal":
            records.extend(self._normalize_criminal(result))
        elif result_type == "employment":
            records.append(self._normalize_employment(result))
        elif result_type == "education":
            records.append(self._normalize_education(result))

        return records

    def _normalize_criminal(self, result: dict) -> list[NormalizedRecord]:
        """Normalize criminal records."""
        records = []

        for charge in result.get("charges", []):
            severity_map = {
                "felony": SeverityLevel.HIGH,
                "misdemeanor": SeverityLevel.MEDIUM,
                "infraction": SeverityLevel.LOW,
            }

            records.append(NormalizedRecord(
                record_id=charge.get("id", str(uuid4())),
                category=RecordCategory.CRIMINAL,
                record_type=charge.get("type", "criminal"),
                severity=severity_map.get(charge.get("type"), SeverityLevel.MEDIUM),
                description=charge.get("description", ""),
                date=self._parse_date(charge.get("date")),
                location=f"{charge.get('city', '')}, {charge.get('state', '')}",
                source=self.provider_id,
                confidence=0.95,
                raw_data=charge
            ))

        return records

    def _normalize_employment(self, result: dict) -> NormalizedRecord:
        """Normalize employment verification."""
        return NormalizedRecord(
            record_id=result.get("id", str(uuid4())),
            category=RecordCategory.EMPLOYMENT,
            record_type="employment_verification",
            severity=None,
            description=f"Verified employment at {result.get('employer', 'Unknown')}",
            date=self._parse_date(result.get("start_date")),
            location=result.get("location"),
            source=self.provider_id,
            confidence=0.95,
            raw_data=result
        )

    def _normalize_education(self, result: dict) -> NormalizedRecord:
        """Normalize education verification."""
        return NormalizedRecord(
            record_id=result.get("id", str(uuid4())),
            category=RecordCategory.EDUCATION,
            record_type="degree_verification",
            severity=None,
            description=f"{result.get('degree')} from {result.get('institution')}",
            date=self._parse_date(result.get("graduation_date")),
            location=result.get("location"),
            source=self.provider_id,
            confidence=0.95,
            raw_data=result
        )

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse Sterling date format."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            return None

    async def health_check(self) -> ProviderHealthStatus:
        """Check Sterling API health."""
        try:
            start = datetime.utcnow()
            response = await self.client.get("/health")
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000

            return ProviderHealthStatus(
                provider_id=self.provider_id,
                available=response.status_code == 200,
                last_check=datetime.utcnow(),
                response_time_ms=elapsed,
                error_rate=0.0,
                consecutive_failures=0
            )
        except Exception as e:
            return ProviderHealthStatus(
                provider_id=self.provider_id,
                available=False,
                last_check=datetime.utcnow(),
                response_time_ms=None,
                error_rate=1.0,
                consecutive_failures=1
            )
```

## Testing Requirements

### Unit Tests
- Request payload building
- Response normalization
- Error handling for HTTP errors
- Date parsing
- Cost calculation

### Integration Tests
- Full Sterling API workflow (with mock)
- Polling mechanism
- Rate limiting
- Authentication

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] SterlingProvider implements DataProvider interface
- [ ] API authentication works
- [ ] Async polling for results implemented
- [ ] Response normalization for all check types
- [ ] Error handling for Sterling-specific errors
- [ ] Unit tests pass with 85%+ coverage

## Deliverables

- `src/elile/providers/sterling.py`
- `tests/unit/test_sterling_provider.py`
- `tests/integration/test_sterling_integration.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#tier-1-core)
- API: Sterling API Documentation
- Dependencies: Tasks 4.1, 4.3, 4.4, 4.6

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
