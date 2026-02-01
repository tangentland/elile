# Task 4.7: Mock Provider (Testing)

## Overview

Create mock data provider for testing and development. Generates realistic synthetic data without external API calls. See [06-data-sources.md](../architecture/06-data-sources.md#testing) for testing strategy.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 4.4: Response Normalizer

## Implementation Checklist

- [ ] Create MockProvider implementation
- [ ] Build synthetic data generators
- [ ] Add configurable response scenarios
- [ ] Implement deterministic data generation
- [ ] Add error simulation modes
- [ ] Create test data fixtures
- [ ] Write mock provider tests

## Key Implementation

```python
# src/elile/providers/mock.py
from faker import Faker
import random

class MockProviderConfig(BaseModel):
    """Mock provider configuration."""
    simulate_delays: bool = True
    min_delay_ms: int = 100
    max_delay_ms: int = 500
    error_rate: float = 0.0  # 0.0 - 1.0
    simulate_rate_limits: bool = False

class MockProvider(DataProvider):
    """Mock data provider for testing."""

    provider_id = "mock"
    provider_name = "Mock Provider"
    check_types = {
        "criminal", "employment", "education",
        "credit", "address", "sanctions"
    }
    cost_per_query = Decimal("0.00")
    rate_limit = 1000

    def __init__(self, config: MockProviderConfig = MockProviderConfig()):
        self.config = config
        self.fake = Faker()
        self.call_count = 0

    async def query(
        self,
        entity: Entity,
        check_type: str,
        ctx: RequestContext
    ) -> ProviderResponse:
        """Execute mock query."""
        self.call_count += 1

        # Simulate delays
        if self.config.simulate_delays:
            delay = random.randint(
                self.config.min_delay_ms,
                self.config.max_delay_ms
            ) / 1000.0
            await asyncio.sleep(delay)

        # Simulate errors
        if random.random() < self.config.error_rate:
            raise ServiceUnavailableError(self.provider_id, "Simulated error")

        # Generate mock data
        raw_data = self._generate_data(entity, check_type)

        return ProviderResponse(
            provider_id=self.provider_id,
            check_type=check_type,
            query_timestamp=datetime.utcnow(),
            raw_data=raw_data,
            records_found=len(raw_data.get("records", [])),
            cost_incurred=Decimal("0.00"),
            response_time_ms=50.0,
            metadata={"mock": True}
        )

    def normalize_response(self, response: ProviderResponse) -> NormalizedData:
        """Normalize mock response."""
        records = []

        for raw_record in response.raw_data.get("records", []):
            records.append(NormalizedRecord(
                record_id=raw_record["id"],
                category=RecordCategory(raw_record["category"]),
                record_type=raw_record["type"],
                severity=SeverityLevel(raw_record["severity"]) if raw_record.get("severity") else None,
                description=raw_record["description"],
                date=raw_record.get("date"),
                location=raw_record.get("location"),
                source=self.provider_id,
                confidence=0.95,
                raw_data=raw_record
            ))

        return NormalizedData(
            check_type=response.check_type,
            records=records,
            confidence=0.95,
            metadata=response.metadata
        )

    async def health_check(self) -> ProviderHealthStatus:
        """Mock health check."""
        return ProviderHealthStatus(
            provider_id=self.provider_id,
            available=True,
            last_check=datetime.utcnow(),
            response_time_ms=10.0,
            error_rate=0.0,
            consecutive_failures=0
        )

    def _generate_data(self, entity: Entity, check_type: str) -> dict:
        """Generate synthetic data based on check type."""
        generators = {
            "criminal": self._generate_criminal_data,
            "employment": self._generate_employment_data,
            "education": self._generate_education_data,
            "credit": self._generate_credit_data,
            "address": self._generate_address_data,
            "sanctions": self._generate_sanctions_data,
        }

        generator = generators.get(check_type, self._generate_default_data)
        return generator(entity)

    def _generate_criminal_data(self, entity: Entity) -> dict:
        """Generate mock criminal records."""
        # 20% chance of criminal record
        if random.random() > 0.2:
            return {"records": []}

        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "criminal",
                    "type": random.choice(["misdemeanor", "felony", "violation"]),
                    "severity": random.choice(["low", "medium", "high"]),
                    "description": self.fake.sentence(),
                    "date": self.fake.date_between(start_date="-10y", end_date="today"),
                    "location": f"{self.fake.city()}, {self.fake.state_abbr()}",
                    "case_number": self.fake.bothify("??-####-????"),
                }
            ]
        }

    def _generate_employment_data(self, entity: Entity) -> dict:
        """Generate mock employment verification."""
        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "employment",
                    "type": "employment_verification",
                    "severity": None,
                    "description": f"Verified employment at {self.fake.company()}",
                    "date": self.fake.date_between(start_date="-5y", end_date="today"),
                    "location": f"{self.fake.city()}, {self.fake.state_abbr()}",
                    "employer": self.fake.company(),
                    "position": self.fake.job(),
                    "verified": True,
                }
            ]
        }

    def _generate_education_data(self, entity: Entity) -> dict:
        """Generate mock education verification."""
        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "education",
                    "type": "degree_verification",
                    "severity": None,
                    "description": f"{self.fake.random_element(['BS', 'BA', 'MS', 'MBA', 'PhD'])} from {self.fake.company()} University",
                    "date": self.fake.date_between(start_date="-15y", end_date="-4y"),
                    "location": f"{self.fake.city()}, {self.fake.state_abbr()}",
                    "institution": f"{self.fake.company()} University",
                    "degree": self.fake.random_element(["BS", "BA", "MS", "MBA"]),
                    "verified": True,
                }
            ]
        }

    def _generate_credit_data(self, entity: Entity) -> dict:
        """Generate mock credit report."""
        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "financial",
                    "type": "credit_report",
                    "severity": "info",
                    "description": f"Credit score: {random.randint(550, 850)}",
                    "date": date.today(),
                    "location": None,
                    "score": random.randint(550, 850),
                    "delinquencies": random.randint(0, 3),
                }
            ]
        }

    def _generate_address_data(self, entity: Entity) -> dict:
        """Generate mock address verification."""
        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "address",
                    "type": "address_verification",
                    "severity": None,
                    "description": f"Verified address: {self.fake.address()}",
                    "date": date.today(),
                    "location": self.fake.address(),
                    "verified": True,
                }
            ]
        }

    def _generate_sanctions_data(self, entity: Entity) -> dict:
        """Generate mock sanctions check."""
        # 1% chance of sanctions hit
        if random.random() > 0.01:
            return {"records": []}

        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "sanction",
                    "type": random.choice(["ofac", "un", "eu"]),
                    "severity": "critical",
                    "description": f"Sanctions list match: {self.fake.random_element(['OFAC SDN', 'UN Sanctions', 'EU Sanctions'])}",
                    "date": self.fake.date_between(start_date="-5y", end_date="today"),
                    "location": self.fake.country(),
                    "list": self.fake.random_element(["OFAC SDN", "UN Sanctions"]),
                }
            ]
        }

    def _generate_default_data(self, entity: Entity) -> dict:
        """Generate default mock data."""
        return {"records": []}

# Test fixtures
class MockDataFixtures:
    """Pre-built test data scenarios."""

    @staticmethod
    def clean_record() -> dict:
        """No adverse findings."""
        return {"records": []}

    @staticmethod
    def criminal_felony() -> dict:
        """Felony conviction."""
        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "criminal",
                    "type": "felony",
                    "severity": "high",
                    "description": "Felony conviction - Fraud",
                    "date": date(2018, 6, 15),
                    "location": "Los Angeles, CA",
                    "case_number": "CR-2018-1234",
                }
            ]
        }

    @staticmethod
    def sanctions_hit() -> dict:
        """OFAC sanctions match."""
        return {
            "records": [
                {
                    "id": str(uuid4()),
                    "category": "sanction",
                    "type": "ofac",
                    "severity": "critical",
                    "description": "OFAC SDN List match",
                    "date": date(2020, 1, 1),
                    "location": "Unknown",
                    "list": "OFAC SDN",
                }
            ]
        }
```

## Testing Requirements

### Unit Tests
- Data generation for all check types
- Deterministic seed-based generation
- Error simulation
- Delay simulation

### Integration Tests
- Mock provider registration
- Response normalization
- Provider interface compliance

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] MockProvider implements DataProvider interface
- [ ] Generates realistic data for all check types
- [ ] Configurable delays and error rates
- [ ] Test fixtures for common scenarios
- [ ] Deterministic data generation with seeds
- [ ] Unit tests pass with 85%+ coverage

## Deliverables

- `src/elile/providers/mock.py`
- `tests/unit/test_mock_provider.py`
- Test data fixtures

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#testing)
- Dependencies: Task 4.1 (provider gateway), Task 4.4 (normalizer)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
