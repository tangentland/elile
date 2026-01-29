"""Search query building and refinement."""

from __future__ import annotations

from pydantic import BaseModel, Field

from elile.agent.state import InformationType


class SearchQuery(BaseModel):
    """A structured search query with metadata and enrichment capabilities."""

    query: str
    category: str  # e.g., "biographical", "financial", "professional", "legal"
    info_type: InformationType | None = None  # The information type this query is for
    priority: int = 1
    parent_query: str | None = None  # Query that led to this one

    # Enrichment context
    name_variants: list[str] = Field(default_factory=list)
    counties: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)
    context_terms: list[str] = Field(default_factory=list)  # Additional search context

    # Query metadata
    iteration: int = 0  # Which SAR iteration this query belongs to
    is_gap_fill: bool = False  # Whether this query is filling a gap from prior iteration

    def with_name_variant(self, name: str) -> SearchQuery:
        """Create a new query with an additional name variant.

        Args:
            name: Name variant to add to the query.

        Returns:
            New SearchQuery with the name variant incorporated.
        """
        # Create enriched query string
        enriched_query = self.query.replace(self._get_primary_name(), name)

        return SearchQuery(
            query=enriched_query,
            category=self.category,
            info_type=self.info_type,
            priority=self.priority,
            parent_query=self.query,
            name_variants=[*self.name_variants, name],
            counties=self.counties.copy(),
            states=self.states.copy(),
            context_terms=self.context_terms.copy(),
            iteration=self.iteration,
            is_gap_fill=self.is_gap_fill,
        )

    def with_county(self, county: str) -> SearchQuery:
        """Create a new query targeting a specific county.

        Args:
            county: County name to target.

        Returns:
            New SearchQuery with county context.
        """
        # Add county to query if not already present
        county_normalized = county.lower().strip()
        if county_normalized in self.query.lower():
            return self

        enriched_query = f"{self.query} {county} county"

        return SearchQuery(
            query=enriched_query,
            category=self.category,
            info_type=self.info_type,
            priority=self.priority,
            parent_query=self.query,
            name_variants=self.name_variants.copy(),
            counties=[*self.counties, county],
            states=self.states.copy(),
            context_terms=self.context_terms.copy(),
            iteration=self.iteration,
            is_gap_fill=self.is_gap_fill,
        )

    def with_state(self, state: str) -> SearchQuery:
        """Create a new query targeting a specific state.

        Args:
            state: State name or abbreviation to target.

        Returns:
            New SearchQuery with state context.
        """
        state_normalized = state.lower().strip()
        if state_normalized in self.query.lower():
            return self

        enriched_query = f"{self.query} {state}"

        return SearchQuery(
            query=enriched_query,
            category=self.category,
            info_type=self.info_type,
            priority=self.priority,
            parent_query=self.query,
            name_variants=self.name_variants.copy(),
            counties=self.counties.copy(),
            states=[*self.states, state],
            context_terms=self.context_terms.copy(),
            iteration=self.iteration,
            is_gap_fill=self.is_gap_fill,
        )

    def with_context(self, context: str) -> SearchQuery:
        """Create a new query with additional context terms.

        Args:
            context: Context term to add (e.g., employer name, school name).

        Returns:
            New SearchQuery with context incorporated.
        """
        context_normalized = context.lower().strip()
        if context_normalized in self.query.lower():
            return self

        enriched_query = f"{self.query} {context}"

        return SearchQuery(
            query=enriched_query,
            category=self.category,
            info_type=self.info_type,
            priority=self.priority,
            parent_query=self.query,
            name_variants=self.name_variants.copy(),
            counties=self.counties.copy(),
            states=self.states.copy(),
            context_terms=[*self.context_terms, context],
            iteration=self.iteration,
            is_gap_fill=self.is_gap_fill,
        )

    def with_priority(self, priority: int) -> SearchQuery:
        """Create a new query with different priority.

        Args:
            priority: New priority level (lower = higher priority).

        Returns:
            New SearchQuery with updated priority.
        """
        return SearchQuery(
            query=self.query,
            category=self.category,
            info_type=self.info_type,
            priority=priority,
            parent_query=self.parent_query,
            name_variants=self.name_variants.copy(),
            counties=self.counties.copy(),
            states=self.states.copy(),
            context_terms=self.context_terms.copy(),
            iteration=self.iteration,
            is_gap_fill=self.is_gap_fill,
        )

    def as_gap_fill(self) -> SearchQuery:
        """Mark this query as a gap-fill query.

        Returns:
            New SearchQuery marked as gap-fill.
        """
        return SearchQuery(
            query=self.query,
            category=self.category,
            info_type=self.info_type,
            priority=self.priority,
            parent_query=self.parent_query,
            name_variants=self.name_variants.copy(),
            counties=self.counties.copy(),
            states=self.states.copy(),
            context_terms=self.context_terms.copy(),
            iteration=self.iteration,
            is_gap_fill=True,
        )

    def for_iteration(self, iteration: int) -> SearchQuery:
        """Create a new query for a specific iteration.

        Args:
            iteration: Iteration number.

        Returns:
            New SearchQuery for the specified iteration.
        """
        return SearchQuery(
            query=self.query,
            category=self.category,
            info_type=self.info_type,
            priority=self.priority,
            parent_query=self.parent_query,
            name_variants=self.name_variants.copy(),
            counties=self.counties.copy(),
            states=self.states.copy(),
            context_terms=self.context_terms.copy(),
            iteration=iteration,
            is_gap_fill=self.is_gap_fill,
        )

    def _get_primary_name(self) -> str:
        """Extract the primary name from the query.

        This is a simple heuristic - in practice, this would use
        NER or the subject name from state.

        Returns:
            Best guess at the primary name in the query.
        """
        # Simple extraction - first quoted string or first two capitalized words
        if '"' in self.query:
            start = self.query.index('"') + 1
            end = self.query.index('"', start)
            return self.query[start:end]

        # Fall back to returning empty string if no name found
        words = self.query.split()
        capitalized = [w for w in words if w[0].isupper() if w.isalpha()]
        if len(capitalized) >= 2:
            return " ".join(capitalized[:2])

        return ""


class QueryBuilder:
    """Builder for constructing and refining search queries."""

    def __init__(self, target: str, info_type: InformationType | None = None) -> None:
        """Initialize the query builder.

        Args:
            target: The entity being researched.
            info_type: The information type these queries are for.
        """
        self.target = target
        self.info_type = info_type
        self._queries: list[SearchQuery] = []

    def add_query(
        self,
        query: str,
        category: str,
        priority: int = 1,
        parent_query: str | None = None,
    ) -> QueryBuilder:
        """Add a query to the builder.

        Args:
            query: The search query string.
            category: Category of the query.
            priority: Priority level (1 = highest).
            parent_query: The query that led to this one.

        Returns:
            Self for chaining.
        """
        self._queries.append(
            SearchQuery(
                query=query,
                category=category,
                info_type=self.info_type,
                priority=priority,
                parent_query=parent_query,
            )
        )
        return self

    def add_search_query(self, query: SearchQuery) -> QueryBuilder:
        """Add a pre-constructed SearchQuery to the builder.

        Args:
            query: The SearchQuery to add.

        Returns:
            Self for chaining.
        """
        self._queries.append(query)
        return self

    def build(self) -> list[SearchQuery]:
        """Build and return the list of queries.

        Returns:
            Sorted list of queries by priority.
        """
        return sorted(self._queries, key=lambda q: q.priority)

    def clear(self) -> QueryBuilder:
        """Clear all queries.

        Returns:
            Self for chaining.
        """
        self._queries = []
        return self


# Query category constants for consistency
class QueryCategory:
    """Standard query category names."""

    BIOGRAPHICAL = "biographical"
    FINANCIAL = "financial"
    PROFESSIONAL = "professional"
    LEGAL = "legal"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    CRIMINAL = "criminal"
    CIVIL = "civil"
    REGULATORY = "regulatory"
    SANCTIONS = "sanctions"
    MEDIA = "media"
    DIGITAL = "digital"
    NETWORK = "network"
