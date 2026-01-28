"""Search query building and refinement."""

from pydantic import BaseModel


class SearchQuery(BaseModel):
    """A structured search query with metadata."""

    query: str
    category: str  # e.g., "biographical", "financial", "professional", "legal"
    priority: int = 1
    parent_query: str | None = None  # Query that led to this one


class QueryBuilder:
    """Builder for constructing and refining search queries."""

    def __init__(self, target: str) -> None:
        """Initialize the query builder.

        Args:
            target: The entity being researched.
        """
        self.target = target
        self._queries: list[SearchQuery] = []

    def add_query(
        self,
        query: str,
        category: str,
        priority: int = 1,
        parent_query: str | None = None,
    ) -> "QueryBuilder":
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
                priority=priority,
                parent_query=parent_query,
            )
        )
        return self

    def build(self) -> list[SearchQuery]:
        """Build and return the list of queries.

        Returns:
            Sorted list of queries by priority.
        """
        return sorted(self._queries, key=lambda q: q.priority)

    def clear(self) -> "QueryBuilder":
        """Clear all queries.

        Returns:
            Self for chaining.
        """
        self._queries = []
        return self
