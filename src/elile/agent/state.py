"""TypedDict state definitions for the research agent workflow."""

from datetime import date
from enum import Enum
from typing import Annotated, Literal, TypedDict
from uuid import UUID, uuid7

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# =============================================================================
# Core Search Models
# =============================================================================


class SearchResult(BaseModel):
    """A single search result with source and extracted information."""

    query: str
    source: str
    content: str
    relevance_score: float
    timestamp: str


class RiskFinding(BaseModel):
    """A risk indicator or red flag identified during research."""

    category: str
    description: str
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float
    sources: list[str]
    metadata: dict[str, str] = Field(default_factory=dict)


class EntityConnection(BaseModel):
    """A connection between two entities discovered during research."""

    source_entity: str
    target_entity: str
    relationship_type: str
    description: str
    confidence: float
    sources: list[str]


class Finding(BaseModel):
    """A structured fact or piece of information discovered during research."""

    fact_type: str  # e.g., "employment", "education", "address"
    description: str
    value: str
    source: str
    confidence: float
    date_discovered: str | None = None
    date_relevant: str | None = None  # When this fact was true (e.g., employment dates)


# =============================================================================
# Information Types and Search Phases
# =============================================================================


class InformationType(str, Enum):
    """Information types in search sequence."""

    # Phase 1: Foundation (sequential, must complete)
    IDENTITY = "identity"
    EMPLOYMENT = "employment"
    EDUCATION = "education"

    # Phase 2: Records (parallel within phase)
    CRIMINAL = "criminal"
    CIVIL = "civil"
    FINANCIAL = "financial"
    LICENSES = "licenses"
    REGULATORY = "regulatory"
    SANCTIONS = "sanctions"

    # Phase 3: Intelligence (uses all prior phases)
    ADVERSE_MEDIA = "adverse_media"
    DIGITAL_FOOTPRINT = "digital_footprint"  # Enhanced only

    # Phase 4: Network (expands from discovered entities)
    NETWORK_D2 = "network_d2"
    NETWORK_D3 = "network_d3"  # Enhanced only

    # Phase 5: Reconciliation
    RECONCILIATION = "reconciliation"


class SearchPhase(str, Enum):
    """Major phases of the search process."""

    FOUNDATION = "foundation"
    RECORDS = "records"
    INTELLIGENCE = "intelligence"
    NETWORK = "network"
    RECONCILIATION = "reconciliation"


# Phase to information type mapping
PHASE_TYPES: dict[SearchPhase, list[InformationType]] = {
    SearchPhase.FOUNDATION: [
        InformationType.IDENTITY,
        InformationType.EMPLOYMENT,
        InformationType.EDUCATION,
    ],
    SearchPhase.RECORDS: [
        InformationType.CRIMINAL,
        InformationType.CIVIL,
        InformationType.FINANCIAL,
        InformationType.LICENSES,
        InformationType.REGULATORY,
        InformationType.SANCTIONS,
    ],
    SearchPhase.INTELLIGENCE: [
        InformationType.ADVERSE_MEDIA,
        InformationType.DIGITAL_FOOTPRINT,
    ],
    SearchPhase.NETWORK: [
        InformationType.NETWORK_D2,
        InformationType.NETWORK_D3,
    ],
    SearchPhase.RECONCILIATION: [
        InformationType.RECONCILIATION,
    ],
}

# Types that require Enhanced tier
ENHANCED_ONLY_TYPES: set[InformationType] = {
    InformationType.DIGITAL_FOOTPRINT,
    InformationType.NETWORK_D3,
}


# =============================================================================
# Type Progress Tracking
# =============================================================================


class TypeProgress(BaseModel):
    """Progress tracking for a single information type."""

    info_type: InformationType
    status: Literal["pending", "in_progress", "complete"] = "pending"
    iterations: int = 0
    confidence: float = 0.0
    completion_reason: Literal["threshold", "max_iter", "diminishing", "skipped"] | None = None

    findings: list[Finding] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    discovered_entities: list["Entity"] = Field(default_factory=list)

    # Metrics for the current/last iteration
    queries_executed: int = 0
    results_received: int = 0
    info_gain_rate: float = 0.0  # new facts / total queries


# =============================================================================
# Inconsistency Detection and Risk Analysis
# =============================================================================


class InconsistencyType(str, Enum):
    """Categories of inconsistencies with different risk implications."""

    # Lower risk - common data entry issues
    DATE_MINOR = "date_minor"  # Off by days/weeks
    SPELLING_VARIANT = "spelling"  # Name spelling differences
    ADDRESS_FORMAT = "address_format"  # Same address, different format

    # Medium risk - requires explanation
    DATE_SIGNIFICANT = "date_significant"  # Off by months (gap hiding?)
    TITLE_MISMATCH = "title_mismatch"  # Different job titles reported
    DEGREE_MISMATCH = "degree_mismatch"  # Different degree types
    EMPLOYER_DISCREPANCY = "employer"  # Employer name doesn't match

    # Higher risk - potential deception indicators
    EMPLOYMENT_GAP_HIDDEN = "gap_hidden"  # Dates stretched to cover gap
    EDUCATION_INFLATED = "edu_inflated"  # Claimed degree not verified
    EMPLOYER_FABRICATED = "emp_fabricated"  # Employer doesn't exist
    TIMELINE_IMPOSSIBLE = "timeline"  # Overlapping or impossible dates
    IDENTITY_MISMATCH = "identity"  # Core identity facts don't match

    # Critical - strong deception signals
    MULTIPLE_IDENTITIES = "multi_identity"  # Evidence of multiple identities
    SYSTEMATIC_PATTERN = "systematic"  # Pattern of inconsistencies across types


class Inconsistency(BaseModel):
    """Detected inconsistency between information sources.

    IMPORTANT: Inconsistencies are themselves risk signals, not just data
    quality issues. Patterns of incongruency can indicate falsification,
    identity fraud, or deliberate obfuscation.
    """

    inconsistency_id: UUID = Field(default_factory=uuid7)
    type_a: InformationType
    type_b: InformationType
    field: str  # e.g., "employment_dates", "degree_type"
    value_a: str
    value_b: str
    sources: list[str]

    # Risk assessment of the inconsistency itself
    inconsistency_type: InconsistencyType
    risk_severity: Literal["low", "medium", "high", "critical"]
    risk_rationale: str  # Why this inconsistency is concerning

    # Resolution tracking
    resolved: bool = False
    resolution: str | None = None
    resolution_outcome: (
        Literal["explained", "confirmed_error", "confirmed_deception"] | None
    ) = None


# =============================================================================
# Entity Models (for network expansion)
# =============================================================================


class Address(BaseModel):
    """A physical address."""

    street: str | None = None
    city: str | None = None
    state: str | None = None
    county: str | None = None
    postal_code: str | None = None
    country: str = "US"


class Entity(BaseModel):
    """Base entity discovered during research."""

    entity_id: UUID = Field(default_factory=uuid7)
    name: str
    entity_type: Literal["person", "organization"]
    relationship_to_subject: str | None = None
    source: str
    confidence: float = 0.5


class PersonEntity(Entity):
    """A person entity discovered during research."""

    entity_type: Literal["person"] = "person"
    role: str | None = None  # e.g., "colleague", "supervisor", "business_partner"
    employer: str | None = None
    dates_known: str | None = None  # When associated with subject


class OrgEntity(Entity):
    """An organization entity discovered during research."""

    entity_type: Literal["organization"] = "organization"
    org_type: str | None = None  # e.g., "employer", "school", "business_partner"
    location: Address | None = None


# =============================================================================
# Knowledge Base (Cross-Type Accumulated Facts)
# =============================================================================


class EmployerRecord(BaseModel):
    """Employment record from verification."""

    employer_name: str
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    location: Address | None = None
    verified: bool = False
    source: str


class EducationRecord(BaseModel):
    """Education record from verification."""

    institution_name: str
    degree_type: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    graduated: bool | None = None
    verified: bool = False
    source: str


class LicenseRecord(BaseModel):
    """Professional license record."""

    license_type: str
    license_number: str | None = None
    jurisdiction: str | None = None
    status: str | None = None  # active, expired, revoked
    issue_date: str | None = None
    expiry_date: str | None = None
    source: str


class KnowledgeBase(BaseModel):
    """Accumulated knowledge for query enrichment.

    This grows as each information type completes, and is used to
    enrich queries for subsequent types.
    """

    # Identity facts
    confirmed_names: list[str] = Field(default_factory=list)  # Including variants, maiden names
    confirmed_dob: date | None = None
    confirmed_ssn_last4: str | None = None  # Last 4 only for verification
    confirmed_addresses: list[Address] = Field(default_factory=list)

    # Employment facts
    employers: list[EmployerRecord] = Field(default_factory=list)

    # Education facts
    schools: list[EducationRecord] = Field(default_factory=list)

    # Professional facts
    licenses: list[LicenseRecord] = Field(default_factory=list)

    # Discovered entities (for network expansion)
    discovered_people: list[PersonEntity] = Field(default_factory=list)
    discovered_orgs: list[OrgEntity] = Field(default_factory=list)

    # Jurisdictions for targeted searches
    known_counties: list[str] = Field(default_factory=list)
    known_states: list[str] = Field(default_factory=list)

    def add_address(self, address: Address) -> None:
        """Add an address and update known jurisdictions."""
        if address not in self.confirmed_addresses:
            self.confirmed_addresses.append(address)
            if address.county and address.county not in self.known_counties:
                self.known_counties.append(address.county)
            if address.state and address.state not in self.known_states:
                self.known_states.append(address.state)


# =============================================================================
# Subject and Service Configuration
# =============================================================================


class SubjectInfo(BaseModel):
    """Information about the subject being screened."""

    subject_id: UUID = Field(default_factory=uuid7)
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    date_of_birth: date | None = None
    ssn_last4: str | None = None
    email: str | None = None
    phone: str | None = None
    locale: str = "US"  # Jurisdiction for compliance

    # Initial information provided
    provided_addresses: list[Address] = Field(default_factory=list)
    provided_employers: list[str] = Field(default_factory=list)
    provided_schools: list[str] = Field(default_factory=list)


class ServiceTier(str, Enum):
    """Service tier determining depth of investigation."""

    STANDARD = "standard"
    ENHANCED = "enhanced"


class SearchDegree(str, Enum):
    """Search degree determining relationship breadth."""

    D1 = "d1"  # Subject only
    D2 = "d2"  # Direct connections
    D3 = "d3"  # Extended network (Enhanced only)


class VigilanceLevel(str, Enum):
    """Monitoring frequency level."""

    V0 = "v0"  # Pre-screen only
    V1 = "v1"  # Annual
    V2 = "v2"  # Monthly
    V3 = "v3"  # Bi-monthly


class ServiceConfiguration(BaseModel):
    """Complete service configuration for a screening."""

    tier: ServiceTier = ServiceTier.STANDARD
    vigilance: VigilanceLevel = VigilanceLevel.V0
    degrees: SearchDegree = SearchDegree.D1

    # Custom overrides
    additional_checks: list[InformationType] = Field(default_factory=list)
    excluded_checks: list[InformationType] = Field(default_factory=list)

    def validate_configuration(self) -> bool:
        """Validate configuration constraints."""
        # D3 requires Enhanced tier
        if self.degrees == SearchDegree.D3 and self.tier != ServiceTier.ENHANCED:
            return False
        return True

    def is_type_enabled(self, info_type: InformationType) -> bool:
        """Check if an information type is enabled for this configuration."""
        # Check explicit exclusions
        if info_type in self.excluded_checks:
            return False

        # Check explicit additions
        if info_type in self.additional_checks:
            return True

        # Enhanced-only types
        if info_type in ENHANCED_ONLY_TYPES and self.tier != ServiceTier.ENHANCED:
            return False

        # Network degree checks
        if info_type == InformationType.NETWORK_D2 and self.degrees == SearchDegree.D1:
            return False
        if info_type == InformationType.NETWORK_D3 and self.degrees != SearchDegree.D3:
            return False

        return True


# =============================================================================
# Report Models
# =============================================================================


class Report(BaseModel):
    """Compiled research report."""

    subject: SubjectInfo
    summary: str
    risk_score: float
    risk_level: Literal["low", "medium", "high", "critical"]
    findings: list[Finding]
    risk_findings: list[RiskFinding]
    connections: list[EntityConnection]
    inconsistencies: list[Inconsistency]
    type_confidence: dict[str, float]  # Confidence per information type
    generated_at: str


# =============================================================================
# Iterative Search State (Main Workflow State)
# =============================================================================


class IterativeSearchState(TypedDict):
    """Extended state for iterative search process.

    This is the main state object for the LangGraph workflow, supporting
    phased search with cross-type knowledge accumulation.
    """

    # Message history (for LangGraph)
    messages: Annotated[list, add_messages]

    # Subject info
    subject: SubjectInfo
    service_config: ServiceConfiguration

    # Phase tracking
    current_phase: SearchPhase
    current_type: InformationType | None
    type_progress: dict[str, TypeProgress]  # Keyed by InformationType.value

    # Cross-type knowledge base (grows as types complete)
    knowledge_base: KnowledgeBase

    # Queues for later phases
    inconsistency_queue: list[Inconsistency]
    entity_queue: list[Entity]  # Discovered entities for D2/D3

    # Current iteration state (within a single type's SAR loop)
    current_iteration: int
    current_queries: list[str]  # Query strings for current iteration
    current_results: list[SearchResult]
    iteration_findings: list[Finding]
    iteration_info_gain: float  # New facts / queries this iteration

    # Outputs (accumulated across all phases)
    all_findings: list[Finding]
    risk_findings: list[RiskFinding]
    connections: list[EntityConnection]

    # Final output
    final_report: Report | None


# =============================================================================
# Legacy AgentState (for backwards compatibility)
# =============================================================================


class AgentState(TypedDict):
    """Main state for the research agent workflow.

    DEPRECATED: Use IterativeSearchState for the new phased workflow.

    Attributes:
        messages: Conversation history with add semantics.
        target: The entity being researched.
        search_queries: Generated search queries to execute.
        search_results: Results from executed searches.
        findings: Extracted facts and information.
        risk_findings: Identified risk indicators.
        connections: Mapped entity connections.
        search_depth: Current depth of search iteration.
        should_continue: Whether to continue searching.
        final_report: The compiled research report.
    """

    messages: Annotated[list, add_messages]
    target: str
    search_queries: list[str]
    search_results: list[SearchResult]
    findings: list[str]
    risk_findings: list[RiskFinding]
    connections: list[EntityConnection]
    search_depth: int
    should_continue: bool
    final_report: str | None
