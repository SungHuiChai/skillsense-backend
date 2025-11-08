"""
Phase 2: Data Collection models for external data sources
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class CollectedSource(Base):
    """Track collection status for each external data source"""
    __tablename__ = "collected_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    source_type = Column(String(50), nullable=False, index=True)
    # Values: 'github', 'web_search'
    source_url = Column(String(1000))
    status = Column(String(50), default="pending", index=True)
    # Values: 'pending', 'collecting', 'completed', 'failed', 'skipped'

    # Collection metadata
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)

    # Rate limiting
    last_request_at = Column(DateTime(timezone=True))
    rate_limit_reset_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    github_data = relationship(
        "GitHubData",
        back_populates="source",
        uselist=False,
        cascade="all, delete-orphan"
    )
    web_mentions = relationship(
        "WebMention",
        back_populates="source",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CollectedSource {self.source_type} - {self.status}>"


class GitHubData(Base):
    """GitHub profile and repository data"""
    __tablename__ = "github_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collected_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Profile data
    username = Column(String(255), index=True)
    name = Column(String(255))
    bio = Column(Text)
    location = Column(String(255))
    company = Column(String(255))
    blog = Column(String(500))
    email = Column(String(255))

    # Statistics
    public_repos = Column(Integer)
    public_gists = Column(Integer)
    followers = Column(Integer)
    following = Column(Integer)

    # Repository data (JSONB for flexible storage)
    repositories = Column(JSONB)  # Array of repo objects
    languages = Column(JSONB)  # Language statistics
    top_repos = Column(JSONB)  # Most starred/forked repos

    # Contribution data
    contributions_last_year = Column(Integer)
    commit_activity = Column(JSONB)  # Commit patterns

    # Skills extracted
    technologies = Column(JSONB)  # Array of technologies used
    frameworks = Column(JSONB)  # Frameworks detected

    # Metadata
    raw_data = Column(JSONB)  # Full API response
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source = relationship("CollectedSource", back_populates="github_data")

    def __repr__(self):
        return f"<GitHubData {self.username}>"


class WebMention(Base):
    """Web articles, interviews, and mentions found via search"""
    __tablename__ = "web_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("collected_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Article/mention info
    title = Column(String(1000))
    url = Column(String(2000), nullable=False)
    snippet = Column(Text)
    full_content = Column(Text)

    # Source metadata
    source_name = Column(String(255))  # 'TechCrunch', 'Medium', etc.
    source_type = Column(String(50), index=True)  # 'article', 'interview', 'podcast', etc.
    author = Column(String(255))
    published_date = Column(Date, index=True)

    # Context
    mention_context = Column(Text)  # Surrounding text where person is mentioned
    topics = Column(JSONB)  # Extracted topics
    sentiment = Column(String(50))  # 'positive', 'neutral', 'negative'

    # Credibility
    source_credibility_score = Column(Numeric(5, 2))  # 0-100
    relevance_score = Column(Numeric(5, 2))  # 0-100

    # Metadata
    raw_data = Column(JSONB)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source = relationship("CollectedSource", back_populates="web_mentions")

    def __repr__(self):
        return f"<WebMention {self.title[:50]}>"


class AggregatedProfile(Base):
    """Aggregated data from all sources for a submission"""
    __tablename__ = "aggregated_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    submission_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Aggregated personal info (best across sources)
    verified_name = Column(String(255))
    verified_email = Column(String(255))
    verified_location = Column(String(255))

    # Source diversity metrics
    sources_collected = Column(Integer)  # How many sources successfully collected
    total_sources_attempted = Column(Integer)
    collection_completeness = Column(Numeric(5, 2))  # Percentage of successful collections

    # Cross-source validation
    name_consistency_score = Column(Numeric(5, 2))  # How consistent is name across sources
    location_consistency_score = Column(Numeric(5, 2))
    skills_cross_validated = Column(Integer)  # Skills found in multiple sources

    # Aggregated skills (preliminary - before Phase 3 extraction)
    all_skills = Column(JSONB)  # All skills from all sources before extraction

    # External visibility metrics
    github_contributions = Column(Integer)
    linkedin_connections = Column(Integer)
    web_mentions_count = Column(Integer)
    conferences_spoken = Column(Integer)
    articles_published = Column(Integer)

    # Overall data quality
    overall_quality_score = Column(Numeric(5, 2))  # 0-100
    data_freshness_score = Column(Numeric(5, 2))  # How recent is the data

    # Timestamps
    last_aggregated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AggregatedProfile {self.verified_name}>"
