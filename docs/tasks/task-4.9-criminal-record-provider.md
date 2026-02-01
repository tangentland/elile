# Task 4.9: Criminal Record Provider (T1 Core)

## Overview

Implement direct criminal record database integration (county/state/federal courts). Provides direct access to criminal records beyond aggregated providers. See [06-data-sources.md](../architecture/06-data-sources.md#criminal-records) for criminal record requirements.

**Priority**: P0 | **Effort**: 5 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 4.4: Response Normalizer
- Task 2.5: Compliance Rules

## Implementation Checklist

- [ ] Implement CriminalRecordProvider base
- [ ] Add jurisdiction-specific adapters (county/state/federal)
- [ ] Build record type classification
- [ ] Implement FCRA compliance (7-year lookback)
- [ ] Add conviction vs arrest filtering
- [ ] Create charge severity mapping
- [ ] Write criminal provider tests

## Key Implementation

```python
# src/elile/providers/criminal.py

class JurisdictionLevel(str, Enum):
    """Court jurisdiction levels."""
    COUNTY = "county"
    STATE = "state"
    FEDERAL = "federal"

class RecordStatus(str, Enum):
    """Criminal record status."""
    CONVICTION = "conviction"
    ARREST = "arrest"
    DISMISSED = "dismissed"
    EXPUNGED = "expunged"
    SEALED = "sealed"

class CriminalRecord(BaseModel):
    """Criminal record data structure."""
    record_id: str
    jurisdiction: JurisdictionLevel
    status: RecordStatus
    charge_type: str  # felony, misdemeanor, infraction
    offense: str
    offense_code: str | None
    offense_date: date
    disposition_date: date | None
    disposition: str | None
    sentence: str | None
    court: str
    case_number: str
    location: str

class CriminalRecordProvider(DataProvider):
    """Direct criminal record database provider."""

    provider_id = "criminal_direct"
    provider_name = "Direct Criminal Records"
    check_types = {"criminal"}
    cost_per_query = Decimal("15.00")
    rate_limit = 100

    def __init__(self, config: dict):
        self.config = config
        # Initialize jurisdiction-specific clients
        self.clients = self._init_clients()

    def _init_clients(self) -> dict:
        """Initialize jurisdiction-specific API clients."""
        return {
            "county": CountyCriminalClient(self.config),
            "state": StateCriminalClient(self.config),
            "federal": FederalCriminalClient(self.config),
        }

    async def query(
        self,
        entity: Entity,
        check_type: str,
        ctx: RequestContext
    ) -> ProviderResponse:
        """Query criminal records across jurisdictions."""
        start_time = datetime.utcnow()
        all_records = []

        # Query federal records
        federal_records = await self._query_federal(entity, ctx)
        all_records.extend(federal_records)

        # Query state records
        if entity.address_state:
            state_records = await self._query_state(entity, entity.address_state, ctx)
            all_records.extend(state_records)

        # Query county records
        if entity.address_county:
            county_records = await self._query_county(
                entity, entity.address_state, entity.address_county, ctx
            )
            all_records.extend(county_records)

        # Apply compliance filters
        filtered_records = self._apply_compliance_filters(all_records, ctx)

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        return ProviderResponse(
            provider_id=self.provider_id,
            check_type=check_type,
            query_timestamp=start_time,
            raw_data={"records": [r.dict() for r in filtered_records]},
            records_found=len(filtered_records),
            cost_incurred=self._calculate_cost(len(filtered_records)),
            response_time_ms=response_time,
            metadata={"jurisdictions_searched": self._get_jurisdictions_searched(entity)}
        )

    async def _query_federal(self, entity: Entity, ctx: RequestContext) -> list[CriminalRecord]:
        """Query federal criminal records (PACER)."""
        client = self.clients["federal"]
        try:
            results = await client.search(
                first_name=entity.name_first,
                last_name=entity.name_last,
                dob=entity.dob
            )
            return [self._parse_federal_record(r) for r in results]
        except Exception as e:
            logger.error(f"Federal criminal search failed: {e}")
            return []

    async def _query_state(
        self,
        entity: Entity,
        state: str,
        ctx: RequestContext
    ) -> list[CriminalRecord]:
        """Query state criminal records."""
        client = self.clients["state"]
        try:
            results = await client.search(
                state=state,
                first_name=entity.name_first,
                last_name=entity.name_last,
                dob=entity.dob
            )
            return [self._parse_state_record(r) for r in results]
        except Exception as e:
            logger.error(f"State criminal search failed: {e}")
            return []

    async def _query_county(
        self,
        entity: Entity,
        state: str,
        county: str,
        ctx: RequestContext
    ) -> list[CriminalRecord]:
        """Query county criminal records."""
        client = self.clients["county"]
        try:
            results = await client.search(
                state=state,
                county=county,
                first_name=entity.name_first,
                last_name=entity.name_last,
                dob=entity.dob
            )
            return [self._parse_county_record(r) for r in results]
        except Exception as e:
            logger.error(f"County criminal search failed: {e}")
            return []

    def _apply_compliance_filters(
        self,
        records: list[CriminalRecord],
        ctx: RequestContext
    ) -> list[CriminalRecord]:
        """Apply jurisdiction-specific compliance filters."""
        filtered = []

        for record in records:
            # Filter expunged/sealed records (never report)
            if record.status in (RecordStatus.EXPUNGED, RecordStatus.SEALED):
                continue

            # FCRA 7-year rule for US
            if ctx.locale.country == "US":
                if not self._passes_fcra_lookback(record):
                    continue

            # Conviction vs arrest filtering
            if not self._should_report_record(record, ctx):
                continue

            filtered.append(record)

        return filtered

    def _passes_fcra_lookback(self, record: CriminalRecord) -> bool:
        """Check FCRA 7-year lookback period."""
        if record.status != RecordStatus.CONVICTION:
            # Arrests have different rules
            return False

        # Convictions have 7-year lookback (with exceptions)
        years_ago = (date.today() - record.offense_date).days / 365.25

        # Felonies may exceed 7 years depending on state
        if record.charge_type == "felony" and years_ago > 7:
            # Check state-specific rules
            return False

        return years_ago <= 7

    def _should_report_record(self, record: CriminalRecord, ctx: RequestContext) -> bool:
        """Determine if record should be reported based on status."""
        # Only report convictions for most checks
        if record.status == RecordStatus.CONVICTION:
            return True

        # Arrests only for specific high-security roles
        if record.status == RecordStatus.ARREST:
            # Check if role allows arrest reporting
            return ctx.metadata.get("report_arrests", False)

        # Dismissed cases generally not reported
        return False

    def _parse_federal_record(self, raw: dict) -> CriminalRecord:
        """Parse federal court record."""
        return CriminalRecord(
            record_id=raw["case_number"],
            jurisdiction=JurisdictionLevel.FEDERAL,
            status=RecordStatus(raw["status"].lower()),
            charge_type=raw["charge_type"],
            offense=raw["offense"],
            offense_code=raw.get("usc_code"),
            offense_date=datetime.fromisoformat(raw["offense_date"]).date(),
            disposition_date=self._parse_date(raw.get("disposition_date")),
            disposition=raw.get("disposition"),
            sentence=raw.get("sentence"),
            court=raw["court"],
            case_number=raw["case_number"],
            location=raw["location"]
        )

    def _parse_state_record(self, raw: dict) -> CriminalRecord:
        """Parse state court record."""
        # Similar to federal parsing, state-specific
        pass

    def _parse_county_record(self, raw: dict) -> CriminalRecord:
        """Parse county court record."""
        # Similar to federal parsing, county-specific
        pass

    def normalize_response(self, response: ProviderResponse) -> NormalizedData:
        """Normalize criminal records."""
        records = []

        severity_map = {
            "felony": SeverityLevel.HIGH,
            "misdemeanor": SeverityLevel.MEDIUM,
            "infraction": SeverityLevel.LOW,
        }

        for raw_record in response.raw_data["records"]:
            record = CriminalRecord(**raw_record)

            # Only report convictions in normalized output
            if record.status != RecordStatus.CONVICTION:
                continue

            records.append(NormalizedRecord(
                record_id=record.record_id,
                category=RecordCategory.CRIMINAL,
                record_type=record.charge_type,
                severity=severity_map.get(record.charge_type, SeverityLevel.MEDIUM),
                description=f"{record.offense} ({record.case_number})",
                date=record.offense_date,
                location=record.location,
                source=self.provider_id,
                confidence=0.90,
                raw_data=raw_record,
                metadata={
                    "jurisdiction": record.jurisdiction,
                    "court": record.court,
                    "disposition": record.disposition,
                }
            ))

        return NormalizedData(
            check_type=response.check_type,
            records=records,
            confidence=0.90,
            metadata=response.metadata
        )

    async def health_check(self) -> ProviderHealthStatus:
        """Check criminal database connectivity."""
        # Check all jurisdiction clients
        all_healthy = all([
            await client.health_check()
            for client in self.clients.values()
        ])

        return ProviderHealthStatus(
            provider_id=self.provider_id,
            available=all_healthy,
            last_check=datetime.utcnow(),
            response_time_ms=50.0,
            error_rate=0.0 if all_healthy else 1.0,
            consecutive_failures=0 if all_healthy else 1
        )
```

## Testing Requirements

### Unit Tests
- FCRA 7-year lookback filtering
- Expunged/sealed record filtering
- Conviction vs arrest filtering
- Jurisdiction-specific parsing
- Compliance rule application

### Integration Tests
- Multi-jurisdiction search
- Federal/state/county query flow
- Record normalization

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] Multi-jurisdiction criminal search implemented
- [ ] FCRA compliance filters work correctly
- [ ] Expunged/sealed records filtered out
- [ ] Conviction vs arrest distinction enforced
- [ ] Severity classification accurate
- [ ] Unit tests pass with 90%+ coverage

## Deliverables

- `src/elile/providers/criminal.py`
- `tests/unit/test_criminal_provider.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#criminal-records)
- Compliance: [07-compliance.md](../architecture/07-compliance.md#fcra-rules)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
