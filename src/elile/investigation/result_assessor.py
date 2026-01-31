"""Result assessor for SAR loop investigation.

This module implements the ASSESS phase of the SAR loop, analyzing query results
to extract findings, calculate confidence scores, identify gaps, and detect
inconsistencies. The assessment determines whether another iteration is needed.

The assessor:
1. Extracts structured facts from provider results
2. Calculates confidence score with weighted factors
3. Identifies gaps in expected information
4. Detects inconsistencies between sources
5. Discovers entities for network expansion
6. Updates the knowledge base with new findings
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import (
    Address,
    EmployerRecord,
    InconsistencyType,
    InformationType,
    KnowledgeBase,
)
from elile.core.logging import get_logger
from elile.investigation.query_executor import QueryResult, QueryStatus

logger = get_logger(__name__)


@dataclass
class Fact:
    """An extracted fact from provider data.

    Facts are the atomic units of information discovered during queries.
    They include source tracking and confidence for corroboration.
    """

    fact_id: UUID
    fact_type: str  # e.g., "name_variant", "address", "employer"
    value: Any
    source_provider: str
    confidence: float  # 0.0-1.0
    discovered_at: datetime

    @classmethod
    def create(
        cls,
        fact_type: str,
        value: Any,
        source_provider: str,
        confidence: float = 0.85,
    ) -> "Fact":
        """Create a new fact with auto-generated ID and timestamp."""
        return cls(
            fact_id=uuid7(),
            fact_type=fact_type,
            value=value,
            source_provider=source_provider,
            confidence=confidence,
            discovered_at=datetime.now(UTC),
        )


class ConfidenceFactors(BaseModel):
    """Contributing factors to confidence score.

    Each factor is weighted to produce the final confidence score.
    """

    completeness: float = Field(default=0.0, ge=0.0, le=1.0)
    corroboration: float = Field(default=0.0, ge=0.0, le=1.0)
    query_success: float = Field(default=0.0, ge=0.0, le=1.0)
    fact_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_diversity: float = Field(default=0.0, ge=0.0, le=1.0)

    def calculate_weighted_score(self) -> float:
        """Calculate weighted confidence score.

        Weights:
        - completeness: 30% - How much of expected info was found
        - corroboration: 25% - Multi-source verification
        - query_success: 20% - Successful query rate
        - fact_confidence: 15% - Average fact confidence
        - source_diversity: 10% - Number of different sources
        """
        return (
            self.completeness * 0.30
            + self.corroboration * 0.25
            + self.query_success * 0.20
            + self.fact_confidence * 0.15
            + self.source_diversity * 0.10
        )


@dataclass
class Gap:
    """A gap in expected information.

    Gaps identify what information is missing that could improve confidence.
    They can be used to generate targeted queries in the next iteration.
    """

    gap_id: UUID
    gap_type: str  # e.g., "no_employment_found", "missing_education"
    description: str
    info_type: InformationType
    priority: int = 1  # 1=high, 2=medium, 3=low
    can_query: bool = True  # Can we query for this gap?

    @classmethod
    def create(
        cls,
        gap_type: str,
        description: str,
        info_type: InformationType,
        priority: int = 1,
        can_query: bool = True,
    ) -> "Gap":
        """Create a new gap with auto-generated ID."""
        return cls(
            gap_id=uuid7(),
            gap_type=gap_type,
            description=description,
            info_type=info_type,
            priority=priority,
            can_query=can_query,
        )


@dataclass
class DetectedInconsistency:
    """A detected inconsistency between sources.

    Inconsistencies can indicate data quality issues or potential
    falsification. They're scored by severity and deception likelihood.
    """

    inconsistency_id: UUID
    field: str
    claimed_value: Any
    found_value: Any
    source_a: str
    source_b: str
    severity: Literal["minor", "moderate", "significant", "critical"]
    inconsistency_type: InconsistencyType
    deception_score: float  # 0.0-1.0, likelihood of intentional deception

    @classmethod
    def create(
        cls,
        field: str,
        claimed_value: Any,
        found_value: Any,
        source_a: str,
        source_b: str,
        severity: Literal["minor", "moderate", "significant", "critical"],
        inconsistency_type: InconsistencyType,
        deception_score: float = 0.0,
    ) -> "DetectedInconsistency":
        """Create a new inconsistency with auto-generated ID."""
        return cls(
            inconsistency_id=uuid7(),
            field=field,
            claimed_value=claimed_value,
            found_value=found_value,
            source_a=source_a,
            source_b=source_b,
            severity=severity,
            inconsistency_type=inconsistency_type,
            deception_score=deception_score,
        )


@dataclass
class DiscoveredEntity:
    """An entity discovered during assessment.

    Discovered entities can be used for network expansion in D2/D3 searches.
    """

    entity_id: UUID
    entity_type: Literal["person", "organization"]
    name: str
    relationship_to_subject: str | None
    discovered_from: str  # fact_type that discovered this entity
    source_provider: str

    @classmethod
    def create(
        cls,
        entity_type: Literal["person", "organization"],
        name: str,
        discovered_from: str,
        source_provider: str,
        relationship_to_subject: str | None = None,
    ) -> "DiscoveredEntity":
        """Create a new discovered entity with auto-generated ID."""
        return cls(
            entity_id=uuid7(),
            entity_type=entity_type,
            name=name,
            relationship_to_subject=relationship_to_subject,
            discovered_from=discovered_from,
            source_provider=source_provider,
        )


@dataclass
class AssessmentResult:
    """Complete assessment of query results for an information type.

    This is the output of the ASSESS phase, providing all information
    needed for the SAR loop to decide whether to continue iterating.
    """

    info_type: InformationType
    iteration_number: int
    assessment_id: UUID = field(default_factory=uuid7)
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Findings
    facts_extracted: list[Fact] = field(default_factory=list)
    new_facts_count: int = 0
    total_facts_count: int = 0  # Including facts from previous iterations

    # Confidence
    confidence_score: float = 0.0
    confidence_factors: ConfidenceFactors = field(default_factory=ConfidenceFactors)

    # Gaps
    gaps_identified: list[Gap] = field(default_factory=list)
    queryable_gaps: int = 0  # Gaps that can be addressed with more queries

    # Information gain
    info_gain_rate: float = 0.0  # new_facts / queries_executed
    queries_executed: int = 0
    queries_successful: int = 0

    # Discoveries
    discovered_entities: list[DiscoveredEntity] = field(default_factory=list)
    inconsistencies: list[DetectedInconsistency] = field(default_factory=list)

    @property
    def should_continue(self) -> bool:
        """Suggest whether another iteration might be beneficial.

        Returns True if:
        - Confidence is below 0.85
        - There are queryable gaps
        - Info gain rate is still reasonable (> 0.1)
        """
        return (
            self.confidence_score < 0.85
            and self.queryable_gaps > 0
            and (self.iteration_number == 1 or self.info_gain_rate > 0.1)
        )


# Expected fact counts per information type (for completeness calculation)
EXPECTED_FACTS_BY_TYPE: dict[InformationType, int] = {
    InformationType.IDENTITY: 5,  # name, dob, ssn_last4, address, phone
    InformationType.EMPLOYMENT: 3,  # employer, title, dates
    InformationType.EDUCATION: 3,  # school, degree, dates
    InformationType.LICENSES: 2,  # license, status
    InformationType.CRIMINAL: 1,  # records (can be 0)
    InformationType.CIVIL: 1,  # litigation (can be 0)
    InformationType.FINANCIAL: 2,  # credit, bankruptcy
    InformationType.REGULATORY: 1,  # regulatory actions
    InformationType.SANCTIONS: 1,  # sanctions status
    InformationType.ADVERSE_MEDIA: 1,  # media mentions
    InformationType.DIGITAL_FOOTPRINT: 2,  # social, digital presence
    InformationType.NETWORK_D2: 2,  # direct associates
    InformationType.NETWORK_D3: 3,  # extended network
    InformationType.RECONCILIATION: 5,  # all verified facts
}


class ResultAssessor:
    """Assesses query results and extracts structured findings.

    The ResultAssessor is the core of the ASSESS phase, responsible for:
    1. Extracting structured facts from raw provider data
    2. Calculating confidence scores with weighted factors
    3. Identifying gaps in expected information
    4. Detecting inconsistencies between sources
    5. Discovering entities for network expansion

    Usage:
        assessor = ResultAssessor(knowledge_base=kb)
        assessment = assessor.assess_results(
            info_type=InformationType.CRIMINAL,
            results=query_results,
            iteration_number=1,
        )
        if assessment.confidence_score >= 0.85:
            # Complete this type
            ...
        else:
            # Generate more queries targeting gaps
            ...
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        """Initialize result assessor.

        Args:
            knowledge_base: Knowledge base to update with findings.
        """
        self._kb = knowledge_base
        self._facts_by_type: dict[InformationType, list[Fact]] = defaultdict(list)

    def assess_results(
        self,
        info_type: InformationType,
        results: list[QueryResult],
        iteration_number: int,
    ) -> AssessmentResult:
        """Assess query results for an information type.

        Extracts facts, calculates confidence, identifies gaps,
        and detects inconsistencies.

        Args:
            info_type: Information type being assessed.
            results: Query results to assess.
            iteration_number: Current SAR iteration.

        Returns:
            Complete assessment with findings, confidence, and gaps.
        """
        # Extract facts from successful results
        all_facts: list[Fact] = []
        for result in results:
            if result.status == QueryStatus.SUCCESS and result.normalized_data:
                extracted = self._extract_facts(
                    info_type=info_type,
                    data=result.normalized_data,
                    provider_id=result.provider_id or "unknown",
                )
                all_facts.extend(extracted)

        # Identify new facts (not already in knowledge base)
        new_facts = self._identify_new_facts(info_type, all_facts)

        # Calculate confidence
        confidence_factors = self._calculate_confidence_factors(
            info_type=info_type,
            facts=all_facts,
            results=results,
        )
        confidence_score = confidence_factors.calculate_weighted_score()

        # Identify gaps
        gaps = self._identify_gaps(info_type, all_facts)
        queryable_gaps = sum(1 for g in gaps if g.can_query)

        # Calculate info gain
        queries_executed = len(results)
        info_gain_rate = len(new_facts) / queries_executed if queries_executed > 0 else 0.0

        # Detect inconsistencies
        inconsistencies = self._detect_inconsistencies(info_type, all_facts)

        # Discover entities
        discovered_entities = self._discover_entities(all_facts)

        # Update knowledge base with new facts
        self._update_knowledge_base(info_type, new_facts)

        # Store facts for later reference
        self._facts_by_type[info_type].extend(new_facts)

        # Build assessment result
        assessment = AssessmentResult(
            info_type=info_type,
            iteration_number=iteration_number,
            facts_extracted=all_facts,
            new_facts_count=len(new_facts),
            total_facts_count=len(self._facts_by_type[info_type]),
            confidence_score=confidence_score,
            confidence_factors=confidence_factors,
            gaps_identified=gaps,
            queryable_gaps=queryable_gaps,
            info_gain_rate=info_gain_rate,
            queries_executed=queries_executed,
            queries_successful=sum(1 for r in results if r.status == QueryStatus.SUCCESS),
            discovered_entities=discovered_entities,
            inconsistencies=inconsistencies,
        )

        logger.info(
            "Assessment complete",
            info_type=info_type.value,
            iteration=iteration_number,
            facts_extracted=len(all_facts),
            new_facts=len(new_facts),
            confidence=f"{confidence_score:.2f}",
            gaps=len(gaps),
            inconsistencies=len(inconsistencies),
        )

        return assessment

    def get_facts_for_type(self, info_type: InformationType) -> list[Fact]:
        """Get all facts extracted for an information type.

        Args:
            info_type: Information type to get facts for.

        Returns:
            List of facts for the type.
        """
        return list(self._facts_by_type.get(info_type, []))

    def _extract_facts(
        self,
        info_type: InformationType,
        data: dict[str, Any],
        provider_id: str,
    ) -> list[Fact]:
        """Extract structured facts from provider data.

        Args:
            info_type: Information type being extracted.
            data: Normalized data from provider.
            provider_id: ID of the provider.

        Returns:
            List of extracted facts.
        """
        facts: list[Fact] = []

        if info_type == InformationType.IDENTITY:
            facts.extend(self._extract_identity_facts(data, provider_id))
        elif info_type == InformationType.EMPLOYMENT:
            facts.extend(self._extract_employment_facts(data, provider_id))
        elif info_type == InformationType.EDUCATION:
            facts.extend(self._extract_education_facts(data, provider_id))
        elif info_type == InformationType.CRIMINAL:
            facts.extend(self._extract_criminal_facts(data, provider_id))
        elif info_type == InformationType.FINANCIAL:
            facts.extend(self._extract_financial_facts(data, provider_id))
        elif info_type == InformationType.SANCTIONS:
            facts.extend(self._extract_sanctions_facts(data, provider_id))
        elif info_type == InformationType.ADVERSE_MEDIA:
            facts.extend(self._extract_media_facts(data, provider_id))
        else:
            # Generic extraction for other types
            facts.extend(self._extract_generic_facts(data, provider_id, info_type))

        return facts

    def _extract_identity_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract identity-related facts."""
        facts: list[Fact] = []

        # Name variants
        for name in data.get("name_variants", []):
            facts.append(Fact.create("name_variant", name, provider_id, confidence=0.95))

        if data.get("full_name"):
            facts.append(Fact.create("name_variant", data["full_name"], provider_id, confidence=0.95))

        # Date of birth
        if data.get("date_of_birth"):
            facts.append(Fact.create("dob", data["date_of_birth"], provider_id, confidence=0.95))

        # SSN last 4
        if data.get("ssn_last4"):
            facts.append(Fact.create("ssn_last4", data["ssn_last4"], provider_id, confidence=0.98))

        # Addresses
        for addr in data.get("addresses", []):
            facts.append(Fact.create("address", addr, provider_id, confidence=0.90))

        # Phone
        if data.get("phone"):
            facts.append(Fact.create("phone", data["phone"], provider_id, confidence=0.85))

        return facts

    def _extract_employment_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract employment-related facts."""
        facts: list[Fact] = []

        for emp in data.get("employers", data.get("records", [])):
            if isinstance(emp, dict):
                facts.append(Fact.create("employer", emp, provider_id, confidence=0.85))
            else:
                facts.append(Fact.create("employer", {"name": emp}, provider_id, confidence=0.80))

        if data.get("verified"):
            facts.append(Fact.create("employment_verified", data["verified"], provider_id, confidence=0.90))

        return facts

    def _extract_education_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract education-related facts."""
        facts: list[Fact] = []

        for school in data.get("schools", data.get("records", [])):
            if isinstance(school, dict):
                facts.append(Fact.create("school", school, provider_id, confidence=0.85))
            else:
                facts.append(Fact.create("school", {"name": school}, provider_id, confidence=0.80))

        if data.get("degrees"):
            for degree in data["degrees"]:
                facts.append(Fact.create("degree", degree, provider_id, confidence=0.90))

        return facts

    def _extract_criminal_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract criminal record facts."""
        facts: list[Fact] = []

        for record in data.get("records", data.get("cases", [])):
            facts.append(Fact.create("criminal_record", record, provider_id, confidence=0.90))

        if data.get("clear") is True:
            facts.append(Fact.create("criminal_clear", True, provider_id, confidence=0.85))

        return facts

    def _extract_financial_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract financial facts."""
        facts: list[Fact] = []

        if data.get("credit_score"):
            facts.append(Fact.create("credit_score", data["credit_score"], provider_id, confidence=0.95))

        if data.get("bankruptcies"):
            for bk in data["bankruptcies"]:
                facts.append(Fact.create("bankruptcy", bk, provider_id, confidence=0.90))

        if data.get("liens"):
            for lien in data["liens"]:
                facts.append(Fact.create("lien", lien, provider_id, confidence=0.90))

        return facts

    def _extract_sanctions_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract sanctions/watchlist facts."""
        facts: list[Fact] = []

        if data.get("clear") is True:
            facts.append(Fact.create("sanctions_clear", True, provider_id, confidence=0.95))
        else:
            for match in data.get("matches", []):
                facts.append(Fact.create("sanctions_match", match, provider_id, confidence=0.90))

        return facts

    def _extract_media_facts(self, data: dict[str, Any], provider_id: str) -> list[Fact]:
        """Extract adverse media facts."""
        facts: list[Fact] = []

        for article in data.get("articles", data.get("mentions", [])):
            facts.append(Fact.create("media_mention", article, provider_id, confidence=0.75))

        return facts

    def _extract_generic_facts(
        self, data: dict[str, Any], provider_id: str, info_type: InformationType
    ) -> list[Fact]:
        """Generic fact extraction for unhandled types."""
        facts: list[Fact] = []

        for key in ("records", "results", "matches", "items"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    facts.append(
                        Fact.create(f"{info_type.value}_{key}", item, provider_id, confidence=0.80)
                    )

        return facts

    def _identify_new_facts(
        self,
        info_type: InformationType,
        facts: list[Fact],
    ) -> list[Fact]:
        """Identify facts that are new (not already in knowledge base).

        Args:
            info_type: Information type.
            facts: Extracted facts.

        Returns:
            List of new facts.
        """
        existing_facts = self._facts_by_type.get(info_type, [])
        existing_values = {str(f.value) for f in existing_facts}

        new_facts = [f for f in facts if str(f.value) not in existing_values]
        return new_facts

    def _calculate_confidence_factors(
        self,
        info_type: InformationType,
        facts: list[Fact],
        results: list[QueryResult],
    ) -> ConfidenceFactors:
        """Calculate confidence score factors.

        Args:
            info_type: Information type.
            facts: Extracted facts.
            results: Query results.

        Returns:
            ConfidenceFactors with all components.
        """
        factors = ConfidenceFactors()

        # Completeness: How much of expected info was found
        expected_count = EXPECTED_FACTS_BY_TYPE.get(info_type, 3)
        actual_count = len(facts)
        factors.completeness = min(actual_count / expected_count, 1.0) if expected_count > 0 else 0.0

        # Corroboration: Multi-source verification
        factors.corroboration = self._calculate_corroboration(facts)

        # Query success: Percentage of successful queries
        successful = sum(1 for r in results if r.status == QueryStatus.SUCCESS)
        factors.query_success = successful / len(results) if results else 0.0

        # Fact confidence: Average confidence of facts
        if facts:
            factors.fact_confidence = sum(f.confidence for f in facts) / len(facts)
        else:
            factors.fact_confidence = 0.0

        # Source diversity: Number of different sources
        unique_sources = {f.source_provider for f in facts}
        # Normalize: 1 source = 0.5, 2+ sources = higher
        factors.source_diversity = min(len(unique_sources) / 2, 1.0) if unique_sources else 0.0

        return factors

    def _calculate_corroboration(self, facts: list[Fact]) -> float:
        """Calculate corroboration score based on multi-source verification.

        Args:
            facts: Extracted facts.

        Returns:
            Corroboration score (0.0-1.0).
        """
        if not facts:
            return 0.0

        # Group facts by type and value
        fact_groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for fact in facts:
            value_key = str(fact.value)
            fact_groups[fact.fact_type][value_key].append(fact.source_provider)

        # Calculate corroboration
        corroborated_count = 0
        total_unique_facts = 0

        for _fact_type, values in fact_groups.items():
            for _value, sources in values.items():
                total_unique_facts += 1
                if len(set(sources)) > 1:  # Multiple sources confirm same fact
                    corroborated_count += 1

        return corroborated_count / total_unique_facts if total_unique_facts > 0 else 0.0

    def _identify_gaps(
        self,
        info_type: InformationType,
        facts: list[Fact],
    ) -> list[Gap]:
        """Identify gaps in expected information.

        Args:
            info_type: Information type.
            facts: Extracted facts.

        Returns:
            List of identified gaps.
        """
        gaps: list[Gap] = []
        fact_types = {f.fact_type for f in facts}

        if info_type == InformationType.IDENTITY:
            if "address" not in fact_types:
                gaps.append(Gap.create(
                    "missing_address",
                    "No address information found",
                    info_type,
                    priority=1,
                ))
            if "dob" not in fact_types:
                gaps.append(Gap.create(
                    "missing_dob",
                    "Date of birth not verified",
                    info_type,
                    priority=2,
                ))

        elif info_type == InformationType.EMPLOYMENT:
            employer_facts = [f for f in facts if f.fact_type == "employer"]
            if not employer_facts:
                gaps.append(Gap.create(
                    "no_employment_found",
                    "No employment records found",
                    info_type,
                    priority=1,
                ))
            else:
                # Check for missing dates
                for emp in employer_facts:
                    if isinstance(emp.value, dict) and not emp.value.get("end_date") and not emp.value.get("current"):
                        gaps.append(Gap.create(
                            "missing_end_date",
                            f"Missing end date for employer: {emp.value.get('name', 'Unknown')}",
                            info_type,
                            priority=2,
                        ))

        elif info_type == InformationType.EDUCATION:
            if "school" not in fact_types and "degree" not in fact_types:
                gaps.append(Gap.create(
                    "no_education_verified",
                    "No education records verified",
                    info_type,
                    priority=1,
                ))

        elif info_type == InformationType.CRIMINAL:
            # For criminal, "no records" is a valid outcome
            if not facts:
                gaps.append(Gap.create(
                    "criminal_incomplete",
                    "Criminal search returned no data (may need county-level)",
                    info_type,
                    priority=2,
                ))

        return gaps

    def _detect_inconsistencies(
        self,
        _info_type: InformationType,
        facts: list[Fact],
    ) -> list[DetectedInconsistency]:
        """Detect inconsistencies between sources.

        Args:
            info_type: Information type.
            facts: Extracted facts.

        Returns:
            List of detected inconsistencies.
        """
        inconsistencies: list[DetectedInconsistency] = []

        # Group facts by type
        fact_groups: dict[str, list[Fact]] = defaultdict(list)
        for fact in facts:
            fact_groups[fact.fact_type].append(fact)

        # Check for conflicts within groups
        for fact_type, group in fact_groups.items():
            if len(group) > 1:
                # Group by source to find conflicts between sources
                source_values: dict[str, list[Fact]] = defaultdict(list)
                for fact in group:
                    source_values[fact.source_provider].append(fact)

                # Compare values between sources
                sources = list(source_values.keys())
                for i, source_a in enumerate(sources):
                    for source_b in sources[i + 1 :]:
                        values_a = {str(f.value) for f in source_values[source_a]}
                        values_b = {str(f.value) for f in source_values[source_b]}

                        # Check if there are conflicting values
                        if values_a and values_b and values_a != values_b:
                            # Determine severity based on fact type
                            severity, inc_type, deception = self._categorize_inconsistency(
                                fact_type, values_a, values_b
                            )

                            inconsistencies.append(
                                DetectedInconsistency.create(
                                    field=fact_type,
                                    claimed_value=list(values_a)[0],
                                    found_value=list(values_b)[0],
                                    source_a=source_a,
                                    source_b=source_b,
                                    severity=severity,
                                    inconsistency_type=inc_type,
                                    deception_score=deception,
                                )
                            )

        return inconsistencies

    def _categorize_inconsistency(
        self,
        fact_type: str,
        _values_a: set[str],
        _values_b: set[str],
    ) -> tuple[Literal["minor", "moderate", "significant", "critical"], InconsistencyType, float]:
        """Categorize an inconsistency by severity.

        Args:
            fact_type: Type of fact with inconsistency.
            values_a: Values from source A.
            values_b: Values from source B.

        Returns:
            Tuple of (severity, inconsistency_type, deception_score).
        """
        # Default categorization based on fact type
        if fact_type in ("name_variant", "address"):
            return "minor", InconsistencyType.SPELLING_VARIANT, 0.1
        elif fact_type in ("employer", "employer_name"):
            return "moderate", InconsistencyType.EMPLOYER_DISCREPANCY, 0.3
        elif fact_type in ("degree", "school"):
            return "moderate", InconsistencyType.DEGREE_MISMATCH, 0.3
        elif fact_type in ("dob", "ssn_last4"):
            return "significant", InconsistencyType.IDENTITY_MISMATCH, 0.6
        elif fact_type in ("employment_dates", "start_date", "end_date"):
            return "moderate", InconsistencyType.DATE_SIGNIFICANT, 0.4
        else:
            return "minor", InconsistencyType.SPELLING_VARIANT, 0.1

    def _discover_entities(self, facts: list[Fact]) -> list[DiscoveredEntity]:
        """Discover entities from facts for network expansion.

        Args:
            facts: Extracted facts.

        Returns:
            List of discovered entities.
        """
        entities: list[DiscoveredEntity] = []

        for fact in facts:
            if fact.fact_type == "employer" and isinstance(fact.value, dict):
                name = fact.value.get("name")
                if name:
                    entities.append(
                        DiscoveredEntity.create(
                            entity_type="organization",
                            name=name,
                            discovered_from=fact.fact_type,
                            source_provider=fact.source_provider,
                            relationship_to_subject="employer",
                        )
                    )

            elif fact.fact_type == "school" and isinstance(fact.value, dict):
                name = fact.value.get("name")
                if name:
                    entities.append(
                        DiscoveredEntity.create(
                            entity_type="organization",
                            name=name,
                            discovered_from=fact.fact_type,
                            source_provider=fact.source_provider,
                            relationship_to_subject="school",
                        )
                    )

            elif fact.fact_type in ("associate", "colleague", "supervisor"):
                name = fact.value.get("name") if isinstance(fact.value, dict) else str(fact.value)
                if name:
                    entities.append(
                        DiscoveredEntity.create(
                            entity_type="person",
                            name=name,
                            discovered_from=fact.fact_type,
                            source_provider=fact.source_provider,
                            relationship_to_subject=fact.fact_type,
                        )
                    )

        return entities

    def _update_knowledge_base(
        self,
        _info_type: InformationType,
        facts: list[Fact],
    ) -> None:
        """Update knowledge base with new facts.

        Args:
            info_type: Information type.
            facts: New facts to add.
        """
        for fact in facts:
            if fact.fact_type == "name_variant":
                if fact.value not in self._kb.confirmed_names:
                    self._kb.confirmed_names.append(fact.value)

            elif fact.fact_type == "address" and isinstance(fact.value, dict):
                addr = Address(
                    street=fact.value.get("street"),
                    city=fact.value.get("city"),
                    state=fact.value.get("state"),
                    county=fact.value.get("county"),
                    postal_code=fact.value.get("postal_code"),
                    country=fact.value.get("country", "US"),
                )
                self._kb.add_address(addr)

            elif fact.fact_type == "employer" and isinstance(fact.value, dict):
                emp = EmployerRecord(
                    name=fact.value.get("name", "Unknown"),
                    title=fact.value.get("title"),
                    start_date=fact.value.get("start_date"),
                    end_date=fact.value.get("end_date"),
                    verified=fact.value.get("verified", False),
                )
                if emp not in self._kb.employers:
                    self._kb.employers.append(emp)


def create_result_assessor(knowledge_base: KnowledgeBase) -> ResultAssessor:
    """Factory function to create a result assessor.

    Args:
        knowledge_base: Knowledge base to use for fact storage.

    Returns:
        Configured ResultAssessor instance.
    """
    return ResultAssessor(knowledge_base=knowledge_base)
