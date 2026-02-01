# Task 4.4: Response Normalizer

## Overview

Build response normalizer to convert provider-specific data formats into standardized schema. Enables uniform processing of heterogeneous data sources. See [06-data-sources.md](../architecture/06-data-sources.md#normalization) for normalization requirements.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 4.1: Provider Gateway
- Task 1.1: Database Schema

## Implementation Checklist

- [ ] Define normalized record schemas by category
- [ ] Build field mapping engine
- [ ] Implement data type coercion
- [ ] Add confidence scoring for normalized data
- [ ] Handle missing/incomplete data
- [ ] Create normalization validator
- [ ] Write normalizer tests

## Key Implementation

```python
# src/elile/providers/normalizer.py
from enum import Enum

class RecordCategory(str, Enum):
    """Standard record categories."""
    IDENTITY = "identity"
    CRIMINAL = "criminal"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    FINANCIAL = "financial"
    SANCTION = "sanction"
    LICENSE = "license"
    ADDRESS = "address"

class SeverityLevel(str, Enum):
    """Severity levels for findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class NormalizedRecord(BaseModel):
    """Standardized record format."""
    record_id: str
    category: RecordCategory
    record_type: str  # e.g., "felony", "address_verification"
    severity: SeverityLevel | None
    description: str
    date: date | None
    location: str | None
    source: str
    confidence: float  # 0.0-1.0
    raw_data: dict
    metadata: dict = {}

class FieldMapping(BaseModel):
    """Maps provider field to normalized field."""
    provider_field: str
    normalized_field: str
    transform: str | None = None  # Python expression
    required: bool = False
    default: Any = None

class NormalizationSchema(BaseModel):
    """Schema for normalizing provider responses."""
    provider_id: str
    check_type: str
    category: RecordCategory
    field_mappings: list[FieldMapping]
    severity_mapping: dict[str, SeverityLevel] = {}
    confidence_base: float = 0.8

class ResponseNormalizer:
    """Normalizes provider responses to standard format."""

    def __init__(self):
        self._schemas: dict[tuple[str, str], NormalizationSchema] = {}

    def register_schema(self, schema: NormalizationSchema):
        """Register normalization schema for provider/check type."""
        key = (schema.provider_id, schema.check_type)
        self._schemas[key] = schema

    def normalize(
        self,
        provider_id: str,
        check_type: str,
        raw_records: list[dict]
    ) -> list[NormalizedRecord]:
        """
        Normalize raw provider records.

        Args:
            provider_id: Provider ID
            check_type: Type of check
            raw_records: Raw records from provider

        Returns:
            List of normalized records
        """
        key = (provider_id, check_type)
        schema = self._schemas.get(key)
        if not schema:
            raise ValueError(f"No schema for {provider_id}/{check_type}")

        normalized = []
        for raw in raw_records:
            try:
                record = self._normalize_record(schema, raw)
                normalized.append(record)
            except Exception as e:
                logger.error(f"Failed to normalize record: {e}", extra={"raw": raw})

        return normalized

    def _normalize_record(
        self,
        schema: NormalizationSchema,
        raw: dict
    ) -> NormalizedRecord:
        """Normalize single record."""
        normalized_data = {}

        for mapping in schema.field_mappings:
            value = self._extract_field(raw, mapping)
            if value is not None:
                normalized_data[mapping.normalized_field] = value
            elif mapping.required:
                raise ValueError(f"Required field missing: {mapping.provider_field}")
            elif mapping.default is not None:
                normalized_data[mapping.normalized_field] = mapping.default

        # Calculate confidence
        confidence = self._calculate_confidence(schema, normalized_data)

        # Map severity
        severity = None
        if "severity" in normalized_data:
            severity_str = normalized_data["severity"]
            severity = schema.severity_mapping.get(severity_str)

        return NormalizedRecord(
            record_id=normalized_data.get("record_id", str(uuid4())),
            category=schema.category,
            record_type=normalized_data.get("record_type", schema.check_type),
            severity=severity,
            description=normalized_data.get("description", ""),
            date=normalized_data.get("date"),
            location=normalized_data.get("location"),
            source=schema.provider_id,
            confidence=confidence,
            raw_data=raw,
            metadata=normalized_data.get("metadata", {})
        )

    def _extract_field(self, raw: dict, mapping: FieldMapping) -> Any:
        """Extract and transform field value."""
        # Support nested fields with dot notation
        value = raw
        for part in mapping.provider_field.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        # Apply transformation if specified
        if value is not None and mapping.transform:
            value = self._apply_transform(value, mapping.transform)

        return value

    def _apply_transform(self, value: Any, transform: str) -> Any:
        """Apply transformation expression."""
        # Safe evaluation of simple transforms
        allowed_transforms = {
            "upper": lambda v: v.upper() if isinstance(v, str) else v,
            "lower": lambda v: v.lower() if isinstance(v, str) else v,
            "strip": lambda v: v.strip() if isinstance(v, str) else v,
            "int": lambda v: int(v),
            "float": lambda v: float(v),
            "date": lambda v: datetime.fromisoformat(v).date() if v else None,
        }

        if transform in allowed_transforms:
            return allowed_transforms[transform](value)

        return value

    def _calculate_confidence(
        self,
        schema: NormalizationSchema,
        data: dict
    ) -> float:
        """Calculate confidence score for normalized record."""
        confidence = schema.confidence_base

        # Reduce confidence for missing optional fields
        total_fields = len(schema.field_mappings)
        present_fields = sum(1 for m in schema.field_mappings if m.normalized_field in data)
        completeness = present_fields / total_fields

        confidence *= (0.8 + 0.2 * completeness)

        return min(1.0, max(0.0, confidence))

# Global normalizer instance
response_normalizer = ResponseNormalizer()
```

## Testing Requirements

### Unit Tests
- Field mapping extraction
- Nested field access
- Data type transformations
- Confidence calculation
- Missing field handling
- Severity mapping

### Integration Tests
- Multi-provider normalization
- Schema registration
- Error handling for malformed data

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] NormalizedRecord schema defined
- [ ] FieldMapping supports nested fields and transforms
- [ ] Confidence scoring implemented
- [ ] Severity mapping works correctly
- [ ] Missing/incomplete data handled gracefully
- [ ] Unit tests pass with 90%+ coverage

## Deliverables

- `src/elile/providers/normalizer.py`
- `tests/unit/test_normalizer.py`

## References

- Architecture: [06-data-sources.md](../architecture/06-data-sources.md#normalization)
- Dependencies: Task 4.1 (provider gateway), Task 1.1 (database)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
