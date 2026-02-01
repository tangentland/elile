# Task 4.10: Employment Verification Provider (T1 Core)

## Overview

Implement employment verification provider using The Work Number and direct employer verification. Validates employment history, titles, and dates. See [06-data-sources.md](../architecture/06-data-sources.md#employment-verification) for requirements.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 4.4: Response Normalizer

## Implementation Checklist

- [ ] Implement EmploymentVerificationProvider
- [ ] Add The Work Number API integration
- [ ] Build direct employer verification workflow
- [ ] Implement employment gap detection
- [ ] Add title/dates verification
- [ ] Create verification confidence scoring
- [ ] Write employment provider tests

## Key Implementation

```python
# src/elile/providers/employment.py

class VerificationStatus(str, Enum):
    """Employment verification status."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNABLE_TO_VERIFY = "unable_to_verify"
    DISCREPANCY = "discrepancy"

class EmploymentRecord(BaseModel):
    """Employment history record."""
    employer_name: str
    employer_id: str | None  # The Work Number employer ID
    position: str
    start_date: date
    end_date: date | None
    current: bool = False
    verified: bool = False
    verification_status: VerificationStatus
    verification_method: str  # "twn", "direct", "payroll"
    salary: Decimal | None = None
    location: str | None = None
    supervisor: str | None = None
    reason_for_leaving: str | None = None
    discrepancies: list[str] = []

class EmploymentVerificationProvider(DataProvider):
    """Employment verification provider."""

    provider_id = "employment_verification"
    provider_name = "Employment Verification"
    check_types = {"employment"}
    cost_per_query = Decimal("10.00")
    rate_limit = 100

    def __init__(self, twn_config: dict):
        self.twn_client = TheWorkNumberClient(twn_config)

    async def query(
        self,
        entity: Entity,
        check_type: str,
        ctx: RequestContext
    ) -> ProviderResponse:
        """Verify employment history."""
        start_time = datetime.utcnow()

        # Get claimed employment history from entity
        claimed_employment = entity.metadata.get("employment_history", [])

        verified_records = []
        for claimed in claimed_employment:
            record = await self._verify_employment(entity, claimed, ctx)
            verified_records.append(record)

        # Detect gaps
        gaps = self._detect_employment_gaps(verified_records)

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ProviderResponse(
            provider_id=self.provider_id,
            check_type=check_type,
            query_timestamp=start_time,
            raw_data={
                "verified_employment": [r.dict() for r in verified_records],
                "gaps": gaps
            },
            records_found=len(verified_records),
            cost_incurred=Decimal(str(len(verified_records))) * self.cost_per_query,
            response_time_ms=response_time,
            metadata={"gaps_detected": len(gaps)}
        )

    async def _verify_employment(
        self,
        entity: Entity,
        claimed: dict,
        ctx: RequestContext
    ) -> EmploymentRecord:
        """Verify single employment record."""
        # Try The Work Number first
        twn_result = await self._verify_via_twn(entity, claimed)
        if twn_result:
            return twn_result

        # Fall back to direct verification
        direct_result = await self._verify_direct(entity, claimed, ctx)
        return direct_result

    async def _verify_via_twn(
        self,
        entity: Entity,
        claimed: dict
    ) -> EmploymentRecord | None:
        """Verify employment via The Work Number."""
        try:
            result = await self.twn_client.verify_employment(
                ssn=entity.ssn,
                employer_name=claimed["employer_name"],
                start_date=claimed["start_date"],
                end_date=claimed.get("end_date")
            )

            if not result:
                return None

            # Check for discrepancies
            discrepancies = []
            if result["position"] != claimed.get("position"):
                discrepancies.append(f"Title mismatch: claimed '{claimed.get('position')}', found '{result['position']}'")

            if result["start_date"] != claimed["start_date"]:
                discrepancies.append("Start date mismatch")

            status = VerificationStatus.VERIFIED if not discrepancies else VerificationStatus.DISCREPANCY

            return EmploymentRecord(
                employer_name=result["employer_name"],
                employer_id=result["employer_id"],
                position=result["position"],
                start_date=result["start_date"],
                end_date=result.get("end_date"),
                current=result.get("current", False),
                verified=True,
                verification_status=status,
                verification_method="twn",
                salary=result.get("salary"),
                location=result.get("location"),
                discrepancies=discrepancies
            )

        except Exception as e:
            logger.error(f"TWN verification failed: {e}")
            return None

    async def _verify_direct(
        self,
        entity: Entity,
        claimed: dict,
        ctx: RequestContext
    ) -> EmploymentRecord:
        """Verify employment via direct employer contact."""
        # This would involve:
        # 1. Looking up employer contact info
        # 2. Sending verification request
        # 3. Waiting for employer response (async, may take days)

        # For now, return unable to verify
        return EmploymentRecord(
            employer_name=claimed["employer_name"],
            employer_id=None,
            position=claimed.get("position", "Unknown"),
            start_date=claimed["start_date"],
            end_date=claimed.get("end_date"),
            current=claimed.get("current", False),
            verified=False,
            verification_status=VerificationStatus.UNABLE_TO_VERIFY,
            verification_method="direct",
            discrepancies=["Pending employer response"]
        )

    def _detect_employment_gaps(self, records: list[EmploymentRecord]) -> list[dict]:
        """Detect unexplained gaps in employment."""
        gaps = []

        # Sort by start date
        sorted_records = sorted(records, key=lambda r: r.start_date)

        for i in range(len(sorted_records) - 1):
            current = sorted_records[i]
            next_job = sorted_records[i + 1]

            # Calculate gap
            gap_start = current.end_date if current.end_date else date.today()
            gap_days = (next_job.start_date - gap_start).days

            # Report gaps > 30 days
            if gap_days > 30:
                gaps.append({
                    "start": gap_start,
                    "end": next_job.start_date,
                    "days": gap_days,
                    "between": f"{current.employer_name} and {next_job.employer_name}"
                })

        return gaps

    def normalize_response(self, response: ProviderResponse) -> NormalizedData:
        """Normalize employment verification results."""
        records = []

        for raw_record in response.raw_data["verified_employment"]:
            emp = EmploymentRecord(**raw_record)

            # Determine severity based on verification status
            severity = None
            if emp.verification_status == VerificationStatus.DISCREPANCY:
                severity = SeverityLevel.MEDIUM
            elif emp.verification_status == VerificationStatus.UNABLE_TO_VERIFY:
                severity = SeverityLevel.LOW

            description = f"Employment at {emp.employer_name} as {emp.position}"
            if emp.discrepancies:
                description += f" - {', '.join(emp.discrepancies)}"

            records.append(NormalizedRecord(
                record_id=str(uuid4()),
                category=RecordCategory.EMPLOYMENT,
                record_type="employment_verification",
                severity=severity,
                description=description,
                date=emp.start_date,
                location=emp.location,
                source=self.provider_id,
                confidence=0.95 if emp.verified else 0.5,
                raw_data=raw_record,
                metadata={
                    "verification_method": emp.verification_method,
                    "verification_status": emp.verification_status,
                    "discrepancies": emp.discrepancies
                }
            ))

        # Add gap records
        for gap in response.raw_data.get("gaps", []):
            records.append(NormalizedRecord(
                record_id=str(uuid4()),
                category=RecordCategory.EMPLOYMENT,
                record_type="employment_gap",
                severity=SeverityLevel.LOW if gap["days"] > 180 else None,
                description=f"Employment gap: {gap['days']} days ({gap['between']})",
                date=gap["start"],
                location=None,
                source=self.provider_id,
                confidence=1.0,
                raw_data=gap
            ))

        return NormalizedData(
            check_type=response.check_type,
            records=records,
            confidence=0.85,
            metadata=response.metadata
        )

    async def health_check(self) -> ProviderHealthStatus:
        """Check TWN API health."""
        healthy = await self.twn_client.health_check()

        return ProviderHealthStatus(
            provider_id=self.provider_id,
            available=healthy,
            last_check=datetime.utcnow(),
            response_time_ms=50.0,
            error_rate=0.0 if healthy else 1.0,
            consecutive_failures=0 if healthy else 1
        )


class TheWorkNumberClient:
    """Client for The Work Number API."""

    def __init__(self, config: dict):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config["base_url"],
            headers={"Authorization": f"Bearer {config['api_key']}"}
        )

    async def verify_employment(
        self,
        ssn: str,
        employer_name: str,
        start_date: date,
        end_date: date | None = None
    ) -> dict | None:
        """Verify employment via TWN."""
        try:
            response = await self.client.post(
                "/verifications",
                json={
                    "ssn": ssn,
                    "employer_name": employer_name,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat() if end_date else None
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def health_check(self) -> bool:
        """Check TWN API health."""
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except:
            return False
```

## Testing Requirements

### Unit Tests
- Employment verification logic
- Gap detection algorithm
- Discrepancy identification
- Confidence scoring

### Integration Tests
- TWN API integration
- Multi-employer verification
- Gap detection with real data

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] TWN integration working
- [ ] Direct verification workflow implemented
- [ ] Employment gap detection accurate
- [ ] Discrepancy detection works
- [ ] Confidence scoring appropriate
- [ ] Unit tests pass with 85%+ coverage

## Deliverables

- `src/elile/providers/employment.py`
- `tests/unit/test_employment_provider.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#employment-verification)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
