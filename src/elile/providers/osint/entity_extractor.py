"""Entity and relationship extraction for OSINT data.

This module provides extraction of entities and relationships
from OSINT data using pattern matching and NLP techniques.
"""

import re
from datetime import datetime
from uuid import uuid7

from .types import (
    EntityType,
    ExtractedEntity,
    ExtractedRelationship,
    NewsMention,
    OSINTSource,
    ProfessionalInfo,
    PublicRecord,
    RelationshipType,
    SocialMediaProfile,
)


class EntityExtractor:
    """Extract entities from OSINT data.

    This class identifies and extracts named entities from
    various OSINT data sources.
    """

    # Email pattern
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

    # Phone pattern (US format)
    PHONE_PATTERN = re.compile(r"\b(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b")

    # URL pattern
    URL_PATTERN = re.compile(
        r"https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}"
        r"\b(?:[-a-zA-Z0-9()@:%_+.~#?&/=]*)"
    )

    # Social handle pattern
    SOCIAL_HANDLE_PATTERN = re.compile(r"@[A-Za-z0-9_]{1,30}")

    # Money pattern
    MONEY_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|M|B|K))?")

    # Date patterns
    DATE_PATTERNS = [
        re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"
        ),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
        re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    ]

    # Common job titles
    JOB_TITLES = {
        "ceo",
        "cfo",
        "cto",
        "coo",
        "cio",
        "cmo",
        "president",
        "vice president",
        "vp",
        "director",
        "manager",
        "head of",
        "founder",
        "co-founder",
        "cofounder",
        "chairman",
        "board member",
        "advisor",
        "partner",
        "principal",
        "associate",
        "analyst",
        "engineer",
        "developer",
        "consultant",
        "executive",
    }

    def __init__(self) -> None:
        """Initialize the entity extractor."""
        self._entity_cache: dict[str, ExtractedEntity] = {}

    def extract_from_profiles(
        self,
        profiles: list[SocialMediaProfile],
    ) -> list[ExtractedEntity]:
        """Extract entities from social media profiles.

        Args:
            profiles: Social media profiles to process.

        Returns:
            List of extracted entities.
        """
        entities: list[ExtractedEntity] = []

        for profile in profiles:
            # Extract person entity from profile
            if profile.display_name:
                entity = self._get_or_create_entity(
                    name=profile.display_name,
                    entity_type=EntityType.PERSON,
                    source=profile.source,
                    context=f"Profile: {profile.username or 'unknown'} on {profile.source.value}",
                )
                entities.append(entity)

            # Extract location
            if profile.location:
                entity = self._get_or_create_entity(
                    name=profile.location,
                    entity_type=EntityType.LOCATION,
                    source=profile.source,
                    context=f"Location from {profile.source.value} profile",
                )
                entities.append(entity)

            # Extract from bio
            if profile.bio:
                entities.extend(self._extract_from_text(profile.bio, profile.source))

        return self._dedupe_entities(entities)

    def extract_from_news(
        self,
        mentions: list[NewsMention],
    ) -> list[ExtractedEntity]:
        """Extract entities from news mentions.

        Args:
            mentions: News mentions to process.

        Returns:
            List of extracted entities.
        """
        entities: list[ExtractedEntity] = []

        for mention in mentions:
            # Process headline
            if mention.headline:
                entities.extend(self._extract_from_text(mention.headline, mention.source))

            # Process snippet
            if mention.snippet:
                entities.extend(self._extract_from_text(mention.snippet, mention.source))

            # Process mentioned entities
            for entity_name in mention.entities_mentioned:
                entity = self._get_or_create_entity(
                    name=entity_name,
                    entity_type=self._infer_entity_type(entity_name),
                    source=mention.source,
                    context=f"Mentioned in: {mention.headline or 'news article'}",
                )
                entities.append(entity)

            # Extract author
            if mention.author:
                entity = self._get_or_create_entity(
                    name=mention.author,
                    entity_type=EntityType.PERSON,
                    source=mention.source,
                    context=f"Author of: {mention.headline or 'news article'}",
                )
                entities.append(entity)

            # Extract publication
            if mention.publication:
                entity = self._get_or_create_entity(
                    name=mention.publication,
                    entity_type=EntityType.ORGANIZATION,
                    source=mention.source,
                    context="News publication",
                )
                entities.append(entity)

        return self._dedupe_entities(entities)

    def extract_from_records(
        self,
        records: list[PublicRecord],
    ) -> list[ExtractedEntity]:
        """Extract entities from public records.

        Args:
            records: Public records to process.

        Returns:
            List of extracted entities.
        """
        entities: list[ExtractedEntity] = []

        for record in records:
            # Extract parties
            for party in record.parties:
                entity_type = self._infer_entity_type(party)
                entity = self._get_or_create_entity(
                    name=party,
                    entity_type=entity_type,
                    source=record.source,
                    context=f"Party in: {record.title or 'public record'}",
                )
                entities.append(entity)

            # Extract from title
            if record.title:
                entities.extend(self._extract_from_text(record.title, record.source))

            # Extract from summary
            if record.summary:
                entities.extend(self._extract_from_text(record.summary, record.source))

            # Extract amount as money entity
            if record.amount:
                entity = self._get_or_create_entity(
                    name=f"${record.amount:,.2f}",
                    entity_type=EntityType.MONEY,
                    source=record.source,
                    context=f"Amount in: {record.title or 'public record'}",
                )
                entities.append(entity)

            # Extract jurisdiction as location
            if record.jurisdiction:
                entity = self._get_or_create_entity(
                    name=record.jurisdiction,
                    entity_type=EntityType.LOCATION,
                    source=record.source,
                    context="Court jurisdiction",
                )
                entities.append(entity)

        return self._dedupe_entities(entities)

    def extract_from_professional(
        self,
        infos: list[ProfessionalInfo],
    ) -> list[ExtractedEntity]:
        """Extract entities from professional information.

        Args:
            infos: Professional info to process.

        Returns:
            List of extracted entities.
        """
        entities: list[ExtractedEntity] = []

        for info in infos:
            # Current company
            if info.current_company:
                entity = self._get_or_create_entity(
                    name=info.current_company,
                    entity_type=EntityType.ORGANIZATION,
                    source=info.source,
                    context="Current employer",
                )
                entities.append(entity)

            # Current title
            if info.current_title:
                entity = self._get_or_create_entity(
                    name=info.current_title,
                    entity_type=EntityType.TITLE,
                    source=info.source,
                    context=f"Title at {info.current_company or 'current company'}",
                )
                entities.append(entity)

            # Employment history
            for job in info.employment_history:
                if company := job.get("company"):
                    entity = self._get_or_create_entity(
                        name=company,
                        entity_type=EntityType.ORGANIZATION,
                        source=info.source,
                        context="Past employer",
                    )
                    entities.append(entity)
                if title := job.get("title"):
                    entity = self._get_or_create_entity(
                        name=title,
                        entity_type=EntityType.TITLE,
                        source=info.source,
                        context=f"Title at {company or 'past company'}",
                    )
                    entities.append(entity)

            # Education
            for edu in info.education:
                if school := edu.get("school"):
                    entity = self._get_or_create_entity(
                        name=school,
                        entity_type=EntityType.ORGANIZATION,
                        source=info.source,
                        context="Educational institution",
                    )
                    entities.append(entity)

            # Board positions
            for position in info.board_positions:
                entity = self._get_or_create_entity(
                    name=position,
                    entity_type=EntityType.ORGANIZATION,
                    source=info.source,
                    context="Board position",
                )
                entities.append(entity)

        return self._dedupe_entities(entities)

    def _extract_from_text(
        self,
        text: str,
        source: OSINTSource,
    ) -> list[ExtractedEntity]:
        """Extract entities from raw text.

        Args:
            text: Text to process.
            source: Source of the text.

        Returns:
            List of extracted entities.
        """
        entities: list[ExtractedEntity] = []

        # Extract emails
        for match in self.EMAIL_PATTERN.finditer(text):
            entity = self._get_or_create_entity(
                name=match.group(),
                entity_type=EntityType.EMAIL,
                source=source,
                context=self._get_context(text, match.start(), match.end()),
            )
            entities.append(entity)

        # Extract phones
        for match in self.PHONE_PATTERN.finditer(text):
            entity = self._get_or_create_entity(
                name=match.group(),
                entity_type=EntityType.PHONE,
                source=source,
                context=self._get_context(text, match.start(), match.end()),
            )
            entities.append(entity)

        # Extract URLs
        for match in self.URL_PATTERN.finditer(text):
            entity = self._get_or_create_entity(
                name=match.group(),
                entity_type=EntityType.URL,
                source=source,
                context=self._get_context(text, match.start(), match.end()),
            )
            entities.append(entity)

        # Extract social handles
        for match in self.SOCIAL_HANDLE_PATTERN.finditer(text):
            entity = self._get_or_create_entity(
                name=match.group(),
                entity_type=EntityType.SOCIAL_HANDLE,
                source=source,
                context=self._get_context(text, match.start(), match.end()),
            )
            entities.append(entity)

        # Extract money
        for match in self.MONEY_PATTERN.finditer(text):
            entity = self._get_or_create_entity(
                name=match.group(),
                entity_type=EntityType.MONEY,
                source=source,
                context=self._get_context(text, match.start(), match.end()),
            )
            entities.append(entity)

        # Extract dates
        for pattern in self.DATE_PATTERNS:
            for match in pattern.finditer(text):
                entity = self._get_or_create_entity(
                    name=match.group(),
                    entity_type=EntityType.DATE,
                    source=source,
                    context=self._get_context(text, match.start(), match.end()),
                )
                entities.append(entity)

        return entities

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get context around a match.

        Args:
            text: Full text.
            start: Match start position.
            end: Match end position.
            window: Context window size.

        Returns:
            Context string.
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()

    def _get_or_create_entity(
        self,
        name: str,
        entity_type: EntityType,
        source: OSINTSource,
        context: str,
    ) -> ExtractedEntity:
        """Get existing entity or create new one.

        Args:
            name: Entity name.
            entity_type: Type of entity.
            source: Source of the entity.
            context: Context where found.

        Returns:
            Extracted entity.
        """
        normalized = self._normalize_name(name)
        cache_key = f"{entity_type.value}:{normalized}"

        if cache_key in self._entity_cache:
            entity = self._entity_cache[cache_key]
            # Update entity with new source info
            if source not in entity.sources:
                updated_sources = entity.sources + [source]
                entity = entity.model_copy(
                    update={
                        "sources": updated_sources,
                        "source_count": len(updated_sources),
                    }
                )
            if context and context not in entity.context_snippets:
                updated_context = entity.context_snippets + [context]
                entity = entity.model_copy(update={"context_snippets": updated_context[:5]})
            entity = entity.model_copy(update={"last_seen": datetime.utcnow()})
            self._entity_cache[cache_key] = entity
            return entity

        entity = ExtractedEntity(
            entity_id=uuid7(),
            entity_type=entity_type,
            name=name,
            normalized_name=normalized,
            source_count=1,
            sources=[source],
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            confidence=0.8,
            context_snippets=[context] if context else [],
        )
        self._entity_cache[cache_key] = entity
        return entity

    def _normalize_name(self, name: str) -> str:
        """Normalize entity name for comparison.

        Args:
            name: Name to normalize.

        Returns:
            Normalized name.
        """
        # Remove extra whitespace, lowercase
        normalized = " ".join(name.split()).lower()
        # Remove common prefixes/suffixes
        for prefix in ["the ", "a ", "an "]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
        return normalized

    def _infer_entity_type(self, name: str) -> EntityType:
        """Infer entity type from name.

        Args:
            name: Entity name.

        Returns:
            Inferred entity type.
        """
        name_lower = name.lower()

        # Check for organization indicators
        org_indicators = ["inc", "llc", "corp", "ltd", "co.", "company", "corporation"]
        if any(ind in name_lower for ind in org_indicators):
            return EntityType.ORGANIZATION

        # Check for title
        if any(title in name_lower for title in self.JOB_TITLES):
            return EntityType.TITLE

        # Check for email
        if self.EMAIL_PATTERN.match(name):
            return EntityType.EMAIL

        # Check for URL
        if self.URL_PATTERN.match(name):
            return EntityType.URL

        # Check for social handle
        if name.startswith("@"):
            return EntityType.SOCIAL_HANDLE

        # Default to person
        return EntityType.PERSON

    def _dedupe_entities(
        self,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """Remove duplicate entities.

        Args:
            entities: Entities to dedupe.

        Returns:
            Deduplicated entities.
        """
        seen: dict[str, ExtractedEntity] = {}
        for entity in entities:
            key = f"{entity.entity_type.value}:{entity.normalized_name}"
            if key not in seen:
                seen[key] = entity
        return list(seen.values())

    def clear_cache(self) -> None:
        """Clear the entity cache."""
        self._entity_cache.clear()


class RelationshipExtractor:
    """Extract relationships from OSINT data.

    This class identifies and extracts relationships between
    entities from various OSINT data sources.
    """

    def __init__(self) -> None:
        """Initialize the relationship extractor."""
        self._relationship_cache: dict[str, ExtractedRelationship] = {}

    def extract_from_professional(
        self,
        infos: list[ProfessionalInfo],
        subject_name: str,
    ) -> list[ExtractedRelationship]:
        """Extract relationships from professional info.

        Args:
            infos: Professional information.
            subject_name: Name of the subject.

        Returns:
            List of extracted relationships.
        """
        relationships: list[ExtractedRelationship] = []

        for info in infos:
            # Current employment
            if info.current_company and info.current_title:
                rel = self._create_relationship(
                    source_entity=subject_name,
                    source_type=EntityType.PERSON,
                    target_entity=info.current_company,
                    target_type=EntityType.ORGANIZATION,
                    relationship_type=RelationshipType.WORKS_FOR,
                    source=info.source,
                    is_current=True,
                    context=f"Currently {info.current_title} at {info.current_company}",
                )
                relationships.append(rel)

            # Past employment
            for job in info.employment_history:
                if company := job.get("company"):
                    rel = self._create_relationship(
                        source_entity=subject_name,
                        source_type=EntityType.PERSON,
                        target_entity=company,
                        target_type=EntityType.ORGANIZATION,
                        relationship_type=RelationshipType.WORKED_FOR,
                        source=info.source,
                        is_current=False,
                        start_date=self._parse_date(job.get("start_date")),
                        end_date=self._parse_date(job.get("end_date")),
                        context=f"Former {job.get('title', 'employee')} at {company}",
                    )
                    relationships.append(rel)

            # Education
            for edu in info.education:
                if school := edu.get("school"):
                    rel = self._create_relationship(
                        source_entity=subject_name,
                        source_type=EntityType.PERSON,
                        target_entity=school,
                        target_type=EntityType.ORGANIZATION,
                        relationship_type=RelationshipType.EDUCATED_AT,
                        source=info.source,
                        is_current=False,
                        context=f"Studied {edu.get('degree', 'at')} {school}",
                    )
                    relationships.append(rel)

            # Board positions
            for position in info.board_positions:
                rel = self._create_relationship(
                    source_entity=subject_name,
                    source_type=EntityType.PERSON,
                    target_entity=position,
                    target_type=EntityType.ORGANIZATION,
                    relationship_type=RelationshipType.BOARD_MEMBER,
                    source=info.source,
                    is_current=True,
                    context=f"Board member of {position}",
                )
                relationships.append(rel)

            # Advisory roles
            for role in info.advisory_roles:
                rel = self._create_relationship(
                    source_entity=subject_name,
                    source_type=EntityType.PERSON,
                    target_entity=role,
                    target_type=EntityType.ORGANIZATION,
                    relationship_type=RelationshipType.ADVISOR,
                    source=info.source,
                    is_current=True,
                    context=f"Advisor to {role}",
                )
                relationships.append(rel)

        return self._dedupe_relationships(relationships)

    def extract_from_news(
        self,
        mentions: list[NewsMention],
        subject_name: str,
    ) -> list[ExtractedRelationship]:
        """Extract relationships from news mentions.

        Args:
            mentions: News mentions to process.
            subject_name: Name of the subject.

        Returns:
            List of extracted relationships.
        """
        relationships: list[ExtractedRelationship] = []

        for mention in mentions:
            # Create "mentioned with" relationships
            for entity in mention.entities_mentioned:
                if entity.lower() != subject_name.lower():
                    rel = self._create_relationship(
                        source_entity=subject_name,
                        source_type=EntityType.PERSON,
                        target_entity=entity,
                        target_type=EntityType.PERSON,  # Could be org, but default to person
                        relationship_type=RelationshipType.MENTIONED_WITH,
                        source=mention.source,
                        is_current=True,
                        context=mention.headline or "News article",
                    )
                    relationships.append(rel)

        return self._dedupe_relationships(relationships)

    def extract_from_profiles(
        self,
        profiles: list[SocialMediaProfile],
        subject_name: str,
    ) -> list[ExtractedRelationship]:
        """Extract relationships from social profiles.

        Args:
            profiles: Social media profiles.
            subject_name: Name of the subject.

        Returns:
            List of extracted relationships.
        """
        relationships: list[ExtractedRelationship] = []

        for profile in profiles:
            # Location relationship
            if profile.location:
                rel = self._create_relationship(
                    source_entity=subject_name,
                    source_type=EntityType.PERSON,
                    target_entity=profile.location,
                    target_type=EntityType.LOCATION,
                    relationship_type=RelationshipType.LOCATED_IN,
                    source=profile.source,
                    is_current=True,
                    context=f"Location from {profile.source.value}",
                )
                relationships.append(rel)

        return self._dedupe_relationships(relationships)

    def _create_relationship(
        self,
        source_entity: str,
        source_type: EntityType,
        target_entity: str,
        target_type: EntityType,
        relationship_type: RelationshipType,
        source: OSINTSource,
        is_current: bool,
        context: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> ExtractedRelationship:
        """Create a relationship.

        Args:
            source_entity: Source entity name.
            source_type: Source entity type.
            target_entity: Target entity name.
            target_type: Target entity type.
            relationship_type: Type of relationship.
            source: OSINT source.
            is_current: Whether relationship is current.
            context: Context for the relationship.
            start_date: Start date.
            end_date: End date.

        Returns:
            Extracted relationship.
        """
        cache_key = (f"{source_entity}:{target_entity}:{relationship_type.value}").lower()

        if cache_key in self._relationship_cache:
            rel = self._relationship_cache[cache_key]
            if source not in rel.sources:
                updated_sources = rel.sources + [source]
                rel = rel.model_copy(
                    update={
                        "sources": updated_sources,
                        "source_count": len(updated_sources),
                    }
                )
            if context and context not in rel.context_snippets:
                updated_context = rel.context_snippets + [context]
                rel = rel.model_copy(update={"context_snippets": updated_context[:5]})
            self._relationship_cache[cache_key] = rel
            return rel

        rel = ExtractedRelationship(
            relationship_id=uuid7(),
            relationship_type=relationship_type,
            source_entity=source_entity,
            source_entity_type=source_type,
            target_entity=target_entity,
            target_entity_type=target_type,
            source_count=1,
            sources=[source],
            start_date=start_date,
            end_date=end_date,
            is_current=is_current,
            confidence=0.7,
            context_snippets=[context] if context else [],
        )
        self._relationship_cache[cache_key] = rel
        return rel

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse date string.

        Args:
            date_str: Date string to parse.

        Returns:
            Parsed datetime or None.
        """
        if not date_str:
            return None
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def _dedupe_relationships(
        self,
        relationships: list[ExtractedRelationship],
    ) -> list[ExtractedRelationship]:
        """Remove duplicate relationships.

        Args:
            relationships: Relationships to dedupe.

        Returns:
            Deduplicated relationships.
        """
        seen: dict[str, ExtractedRelationship] = {}
        for rel in relationships:
            key = (f"{rel.source_entity}:{rel.target_entity}:{rel.relationship_type.value}").lower()
            if key not in seen:
                seen[key] = rel
        return list(seen.values())

    def clear_cache(self) -> None:
        """Clear the relationship cache."""
        self._relationship_cache.clear()


def create_entity_extractor() -> EntityExtractor:
    """Create an entity extractor.

    Returns:
        Entity extractor instance.
    """
    return EntityExtractor()


def create_relationship_extractor() -> RelationshipExtractor:
    """Create a relationship extractor.

    Returns:
        Relationship extractor instance.
    """
    return RelationshipExtractor()
