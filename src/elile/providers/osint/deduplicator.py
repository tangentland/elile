"""Deduplication for OSINT results.

This module provides deduplication logic for OSINT results,
identifying and merging duplicate entries across sources.
"""

from difflib import SequenceMatcher
from typing import Any, TypeVar
from uuid import uuid7

from pydantic import BaseModel

from .types import (
    DuplicateGroup,
    NewsMention,
    ProfessionalInfo,
    PublicRecord,
    SocialMediaProfile,
)

T = TypeVar("T", bound=BaseModel)


class DeduplicationResult(BaseModel):
    """Result of deduplication.

    Attributes:
        total_input: Total items before dedup.
        total_output: Total items after dedup.
        duplicates_removed: Number of duplicates removed.
        duplicate_groups: Groups of duplicates found.
        items: Deduplicated items.
    """

    total_input: int = 0
    total_output: int = 0
    duplicates_removed: int = 0
    duplicate_groups: list[DuplicateGroup] = []
    items: list[Any] = []


class OSINTDeduplicator:
    """Deduplicates OSINT results across sources.

    This class identifies duplicate entries across different sources
    and merges them into canonical records.

    Attributes:
        similarity_threshold: Minimum similarity for duplicate detection.
    """

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        """Initialize the deduplicator.

        Args:
            similarity_threshold: Minimum similarity for duplicates.
        """
        self.similarity_threshold = similarity_threshold

    def deduplicate_profiles(
        self,
        profiles: list[SocialMediaProfile],
    ) -> DeduplicationResult:
        """Deduplicate social media profiles.

        Args:
            profiles: List of profiles to deduplicate.

        Returns:
            Deduplication result with unique profiles.
        """
        if not profiles:
            return DeduplicationResult(items=[])

        groups: list[list[SocialMediaProfile]] = []
        used: set[int] = set()

        for i, profile in enumerate(profiles):
            if i in used:
                continue

            group = [profile]
            used.add(i)

            for j, other in enumerate(profiles):
                if j in used:
                    continue

                if self._profiles_match(profile, other):
                    group.append(other)
                    used.add(j)

            groups.append(group)

        # Merge groups into canonical profiles
        result_profiles = []
        duplicate_groups = []

        for group in groups:
            if len(group) == 1:
                result_profiles.append(group[0])
            else:
                canonical = self._merge_profiles(group)
                result_profiles.append(canonical)
                duplicate_groups.append(
                    DuplicateGroup(
                        group_id=uuid7(),
                        item_type="social_profile",
                        canonical_item_id=canonical.profile_id,
                        duplicate_item_ids=[p.profile_id for p in group[1:]],
                        similarity_scores={
                            str(p.profile_id): self._profile_similarity(canonical, p)
                            for p in group[1:]
                        },
                    )
                )

        return DeduplicationResult(
            total_input=len(profiles),
            total_output=len(result_profiles),
            duplicates_removed=len(profiles) - len(result_profiles),
            duplicate_groups=duplicate_groups,
            items=result_profiles,
        )

    def deduplicate_news(
        self,
        mentions: list[NewsMention],
    ) -> DeduplicationResult:
        """Deduplicate news mentions.

        Args:
            mentions: List of news mentions to deduplicate.

        Returns:
            Deduplication result with unique mentions.
        """
        if not mentions:
            return DeduplicationResult(items=[])

        groups: list[list[NewsMention]] = []
        used: set[int] = set()

        for i, mention in enumerate(mentions):
            if i in used:
                continue

            group = [mention]
            used.add(i)

            for j, other in enumerate(mentions):
                if j in used:
                    continue

                if self._news_matches(mention, other):
                    group.append(other)
                    used.add(j)

            groups.append(group)

        # Merge groups into canonical mentions
        result_mentions = []
        duplicate_groups = []

        for group in groups:
            if len(group) == 1:
                result_mentions.append(group[0])
            else:
                canonical = self._merge_news(group)
                result_mentions.append(canonical)
                duplicate_groups.append(
                    DuplicateGroup(
                        group_id=uuid7(),
                        item_type="news_mention",
                        canonical_item_id=canonical.mention_id,
                        duplicate_item_ids=[n.mention_id for n in group[1:]],
                        similarity_scores={
                            str(n.mention_id): self._news_similarity(canonical, n)
                            for n in group[1:]
                        },
                    )
                )

        return DeduplicationResult(
            total_input=len(mentions),
            total_output=len(result_mentions),
            duplicates_removed=len(mentions) - len(result_mentions),
            duplicate_groups=duplicate_groups,
            items=result_mentions,
        )

    def deduplicate_records(
        self,
        records: list[PublicRecord],
    ) -> DeduplicationResult:
        """Deduplicate public records.

        Args:
            records: List of records to deduplicate.

        Returns:
            Deduplication result with unique records.
        """
        if not records:
            return DeduplicationResult(items=[])

        groups: list[list[PublicRecord]] = []
        used: set[int] = set()

        for i, record in enumerate(records):
            if i in used:
                continue

            group = [record]
            used.add(i)

            for j, other in enumerate(records):
                if j in used:
                    continue

                if self._records_match(record, other):
                    group.append(other)
                    used.add(j)

            groups.append(group)

        # Merge groups into canonical records
        result_records = []
        duplicate_groups = []

        for group in groups:
            if len(group) == 1:
                result_records.append(group[0])
            else:
                canonical = self._merge_records(group)
                result_records.append(canonical)
                duplicate_groups.append(
                    DuplicateGroup(
                        group_id=uuid7(),
                        item_type="public_record",
                        canonical_item_id=canonical.record_id,
                        duplicate_item_ids=[r.record_id for r in group[1:]],
                        similarity_scores={
                            str(r.record_id): self._record_similarity(canonical, r)
                            for r in group[1:]
                        },
                    )
                )

        return DeduplicationResult(
            total_input=len(records),
            total_output=len(result_records),
            duplicates_removed=len(records) - len(result_records),
            duplicate_groups=duplicate_groups,
            items=result_records,
        )

    def deduplicate_professional(
        self,
        infos: list[ProfessionalInfo],
    ) -> DeduplicationResult:
        """Deduplicate professional information.

        Args:
            infos: List of professional info to deduplicate.

        Returns:
            Deduplication result with unique info.
        """
        if not infos:
            return DeduplicationResult(items=[])

        groups: list[list[ProfessionalInfo]] = []
        used: set[int] = set()

        for i, info in enumerate(infos):
            if i in used:
                continue

            group = [info]
            used.add(i)

            for j, other in enumerate(infos):
                if j in used:
                    continue

                if self._professional_matches(info, other):
                    group.append(other)
                    used.add(j)

            groups.append(group)

        # Merge groups into canonical info
        result_infos = []
        duplicate_groups = []

        for group in groups:
            if len(group) == 1:
                result_infos.append(group[0])
            else:
                canonical = self._merge_professional(group)
                result_infos.append(canonical)
                duplicate_groups.append(
                    DuplicateGroup(
                        group_id=uuid7(),
                        item_type="professional_info",
                        canonical_item_id=canonical.info_id,
                        duplicate_item_ids=[p.info_id for p in group[1:]],
                        similarity_scores={
                            str(p.info_id): self._professional_similarity(canonical, p)
                            for p in group[1:]
                        },
                    )
                )

        return DeduplicationResult(
            total_input=len(infos),
            total_output=len(result_infos),
            duplicates_removed=len(infos) - len(result_infos),
            duplicate_groups=duplicate_groups,
            items=result_infos,
        )

    def _string_similarity(self, s1: str | None, s2: str | None) -> float:
        """Calculate string similarity using SequenceMatcher.

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Similarity ratio between 0 and 1.
        """
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def _profiles_match(
        self,
        p1: SocialMediaProfile,
        p2: SocialMediaProfile,
    ) -> bool:
        """Check if two profiles are likely the same person.

        Args:
            p1: First profile.
            p2: Second profile.

        Returns:
            True if profiles likely match.
        """
        # Same source and username is definitely a match
        if p1.source == p2.source and p1.username and p1.username == p2.username:
            return True

        # Check display name similarity
        name_sim = self._string_similarity(p1.display_name, p2.display_name)
        if name_sim >= self.similarity_threshold:
            # Additional signals
            location_match = p1.location and p1.location == p2.location
            bio_sim = self._string_similarity(p1.bio, p2.bio) >= 0.7
            if location_match or bio_sim:
                return True

        return False

    def _profile_similarity(
        self,
        p1: SocialMediaProfile,
        p2: SocialMediaProfile,
    ) -> float:
        """Calculate similarity between two profiles.

        Args:
            p1: First profile.
            p2: Second profile.

        Returns:
            Similarity score.
        """
        scores = []
        scores.append(self._string_similarity(p1.display_name, p2.display_name))
        scores.append(self._string_similarity(p1.username, p2.username))
        scores.append(self._string_similarity(p1.bio, p2.bio))
        scores.append(self._string_similarity(p1.location, p2.location))

        valid_scores = [s for s in scores if s > 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    def _merge_profiles(
        self,
        profiles: list[SocialMediaProfile],
    ) -> SocialMediaProfile:
        """Merge multiple profiles into canonical profile.

        Args:
            profiles: Profiles to merge.

        Returns:
            Merged canonical profile.
        """
        # Use the one with highest confidence as base
        profiles_sorted = sorted(
            profiles,
            key=lambda p: (p.match_confidence, p.follower_count or 0),
            reverse=True,
        )
        canonical = profiles_sorted[0]

        # Merge missing data from others
        for profile in profiles_sorted[1:]:
            if not canonical.bio and profile.bio:
                canonical = canonical.model_copy(update={"bio": profile.bio})
            if not canonical.location and profile.location:
                canonical = canonical.model_copy(update={"location": profile.location})
            # Merge raw data
            merged_raw = {**canonical.raw_data, **profile.raw_data}
            canonical = canonical.model_copy(update={"raw_data": merged_raw})

        return canonical

    def _news_matches(self, n1: NewsMention, n2: NewsMention) -> bool:
        """Check if two news mentions are duplicates.

        Args:
            n1: First mention.
            n2: Second mention.

        Returns:
            True if mentions are duplicates.
        """
        # Same URL is definitely a match
        if n1.url and n1.url == n2.url:
            return True

        # Check headline similarity
        headline_sim = self._string_similarity(n1.headline, n2.headline)
        if (
            headline_sim >= self.similarity_threshold
            and n1.published_at
            and n2.published_at
        ):
            days_diff = abs((n1.published_at - n2.published_at).days)
            if days_diff <= 1:
                return True

        # Check snippet similarity for syndicated content
        snippet_sim = self._string_similarity(n1.snippet, n2.snippet)
        return snippet_sim >= 0.9

    def _news_similarity(self, n1: NewsMention, n2: NewsMention) -> float:
        """Calculate similarity between news mentions.

        Args:
            n1: First mention.
            n2: Second mention.

        Returns:
            Similarity score.
        """
        scores = []
        scores.append(self._string_similarity(n1.headline, n2.headline))
        scores.append(self._string_similarity(n1.snippet, n2.snippet))

        valid_scores = [s for s in scores if s > 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    def _merge_news(self, mentions: list[NewsMention]) -> NewsMention:
        """Merge duplicate news mentions.

        Args:
            mentions: Mentions to merge.

        Returns:
            Merged canonical mention.
        """
        # Prefer higher reliability source
        mentions_sorted = sorted(
            mentions,
            key=lambda m: (
                m.source_reliability.value if m.source_reliability else "z",
                len(m.full_text or ""),
            ),
        )
        canonical = mentions_sorted[0]

        # Merge full text if missing
        for mention in mentions_sorted[1:]:
            if not canonical.full_text and mention.full_text:
                canonical = canonical.model_copy(update={"full_text": mention.full_text})
            # Merge entities mentioned
            all_entities = set(canonical.entities_mentioned + mention.entities_mentioned)
            canonical = canonical.model_copy(update={"entities_mentioned": list(all_entities)})

        return canonical

    def _records_match(self, r1: PublicRecord, r2: PublicRecord) -> bool:
        """Check if two public records are duplicates.

        Args:
            r1: First record.
            r2: Second record.

        Returns:
            True if records are duplicates.
        """
        # Same case number in same jurisdiction
        if (
            r1.case_number
            and r1.case_number == r2.case_number
            and r1.jurisdiction
            and r1.jurisdiction == r2.jurisdiction
        ):
            return True

        # Same URL
        if r1.url and r1.url == r2.url:
            return True

        # Similar title with same filing date
        title_sim = self._string_similarity(r1.title, r2.title)
        return (
            title_sim >= self.similarity_threshold
            and r1.filing_date is not None
            and r1.filing_date == r2.filing_date
        )

    def _record_similarity(self, r1: PublicRecord, r2: PublicRecord) -> float:
        """Calculate similarity between records.

        Args:
            r1: First record.
            r2: Second record.

        Returns:
            Similarity score.
        """
        scores = []
        scores.append(self._string_similarity(r1.title, r2.title))
        scores.append(self._string_similarity(r1.summary, r2.summary))
        if r1.case_number and r2.case_number:
            scores.append(1.0 if r1.case_number == r2.case_number else 0.0)

        valid_scores = [s for s in scores if s > 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    def _merge_records(self, records: list[PublicRecord]) -> PublicRecord:
        """Merge duplicate public records.

        Args:
            records: Records to merge.

        Returns:
            Merged canonical record.
        """
        # Prefer authoritative sources
        records_sorted = sorted(
            records,
            key=lambda r: (
                r.source_reliability.value if r.source_reliability else "z",
                len(r.summary or ""),
            ),
        )
        canonical = records_sorted[0]

        # Merge parties
        all_parties: set[str] = set()
        for record in records_sorted:
            all_parties.update(record.parties)
        canonical = canonical.model_copy(update={"parties": list(all_parties)})

        return canonical

    def _professional_matches(
        self,
        p1: ProfessionalInfo,
        p2: ProfessionalInfo,
    ) -> bool:
        """Check if two professional info entries match.

        Args:
            p1: First info.
            p2: Second info.

        Returns:
            True if entries match.
        """
        # Same current company and title
        if (
            p1.current_company
            and p1.current_title
            and p1.current_company == p2.current_company
            and p1.current_title == p2.current_title
        ):
            return True

        # Check company URL match
        if p1.company_url and p1.company_url == p2.company_url:
            title_sim = self._string_similarity(p1.current_title, p2.current_title)
            if title_sim >= 0.8:
                return True

        return False

    def _professional_similarity(
        self,
        p1: ProfessionalInfo,
        p2: ProfessionalInfo,
    ) -> float:
        """Calculate similarity between professional info.

        Args:
            p1: First info.
            p2: Second info.

        Returns:
            Similarity score.
        """
        scores = []
        scores.append(self._string_similarity(p1.current_title, p2.current_title))
        scores.append(self._string_similarity(p1.current_company, p2.current_company))

        valid_scores = [s for s in scores if s > 0]
        return sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    def _merge_professional(self, infos: list[ProfessionalInfo]) -> ProfessionalInfo:
        """Merge duplicate professional info.

        Args:
            infos: Professional info to merge.

        Returns:
            Merged canonical info.
        """
        # Prefer LinkedIn as authoritative
        from .types import OSINTSource

        infos_sorted = sorted(
            infos,
            key=lambda i: (
                0 if i.source == OSINTSource.LINKEDIN else 1,
                len(i.employment_history),
            ),
        )
        canonical = infos_sorted[0]

        # Merge skills, certifications, etc.
        all_skills: set[str] = set()
        all_certs: set[str] = set()
        all_boards: set[str] = set()
        all_advisory: set[str] = set()

        for info in infos_sorted:
            all_skills.update(info.skills)
            all_certs.update(info.certifications)
            all_boards.update(info.board_positions)
            all_advisory.update(info.advisory_roles)

        canonical = canonical.model_copy(
            update={
                "skills": list(all_skills),
                "certifications": list(all_certs),
                "board_positions": list(all_boards),
                "advisory_roles": list(all_advisory),
            }
        )

        return canonical


def create_deduplicator(similarity_threshold: float = 0.85) -> OSINTDeduplicator:
    """Create an OSINT deduplicator.

    Args:
        similarity_threshold: Similarity threshold for dedup.

    Returns:
        Configured deduplicator.
    """
    return OSINTDeduplicator(similarity_threshold=similarity_threshold)
