"""
Phase 2: Data Collection models for external data sources
"""
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Numeric, Date
from sqlalchemy import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class CollectedSource(Base):
    """Track collection status for each external data source"""
    __tablename__ = "collected_sources"
    __table_args__ = (
        # Unique constraint on (submission_id, source_type) combination
        # This allows multiple sources (github, web_search, etc.) per submission
        {'extend_existing': True},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    submission_id = Column(
        String(36),
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
    linkedin_data = relationship(
        "LinkedInData",
        back_populates="source",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CollectedSource {self.source_type} - {self.status}>"


class GitHubData(Base):
    """GitHub profile and repository data"""
    __tablename__ = "github_data"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    source_id = Column(
        String(36),
        ForeignKey("collected_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    submission_id = Column(
        String(36),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
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
    repositories = Column(JSON)  # Array of repo objects
    languages = Column(JSON)  # Language statistics
    top_repos = Column(JSON)  # Most starred/forked repos

    # Contribution data
    contributions_last_year = Column(Integer)
    commit_activity = Column(JSON)  # Commit patterns

    # Skills extracted
    technologies = Column(JSON)  # Array of technologies used
    frameworks = Column(JSON)  # Frameworks detected

    # Enhanced data for GPT analysis
    readme_samples = Column(JSON)  # Top repo READMEs with metadata
    commit_samples = Column(JSON)  # Recent commit messages
    commit_statistics = Column(JSON)  # Commit patterns and statistics

    # Metadata
    raw_data = Column(JSON)  # Full API response
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source = relationship("CollectedSource", back_populates="github_data")

    def __repr__(self):
        return f"<GitHubData {self.username}>"


class WebMention(Base):
    """Web articles, interviews, and mentions found via search"""
    __tablename__ = "web_mentions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    source_id = Column(
        String(36),
        ForeignKey("collected_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    submission_id = Column(
        String(36),
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
    topics = Column(JSON)  # Extracted topics
    sentiment = Column(String(50))  # 'positive', 'neutral', 'negative'

    # Credibility
    source_credibility_score = Column(Numeric(5, 2))  # 0-100
    relevance_score = Column(Numeric(5, 2))  # 0-100

    # Metadata
    raw_data = Column(JSON)
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source = relationship("CollectedSource", back_populates="web_mentions")

    def __repr__(self):
        return f"<WebMention {self.title[:50]}>"


class LinkedInData(Base):
    """LinkedIn profile data collected via web search"""
    __tablename__ = "linkedin_data"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    source_id = Column(
        String(36),
        ForeignKey("collected_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    submission_id = Column(
        String(36),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Profile data
    profile_url = Column(String(500), nullable=False)
    username = Column(String(255), index=True)
    full_name = Column(String(255))
    headline = Column(Text)  # Professional headline/tagline
    summary = Column(Text)  # Profile summary/about section

    # Experience (JSONB for flexible storage)
    experience = Column(JSON)  # Array of job objects {title, company, description, dates}
    education = Column(JSON)  # Array of education objects
    certifications = Column(JSON)  # Array of certification objects

    # Skills and endorsements
    skills = Column(JSON)  # Array of skill objects {name, endorsements}

    # Additional content
    recommendations = Column(JSON)  # Array of recommendation texts
    posts_sample = Column(JSON)  # Sample of recent posts (if available)

    # Collection metadata
    data_source = Column(String(50))  # 'tavily_search', 'url_only', 'search_failed'
    collection_method = Column(String(50))  # 'web_search', 'tavily_unavailable', etc.
    error_message = Column(Text)  # If collection failed

    # Raw data
    raw_search_results = Column(JSON)  # Top search results for context
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    source = relationship("CollectedSource", back_populates="linkedin_data")

    def __repr__(self):
        return f"<LinkedInData {self.username}>"


class AggregatedProfile(Base):
    """Aggregated data from all sources for a submission"""
    __tablename__ = "aggregated_profile"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    submission_id = Column(
        String(36),
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
    all_skills = Column(JSON)  # All skills from all sources before extraction

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


class GitHubAnalysis(Base):
    """GPT-4o analysis results for GitHub data"""
    __tablename__ = "github_analysis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    submission_id = Column(
        String(36),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    github_data_id = Column(
        String(36),
        ForeignKey("github_data.id", ondelete="CASCADE"),
        nullable=False
    )

    # Skills Analysis (from GPT-4o)
    technical_skills = Column(JSON)  # [{"name": "Python", "proficiency": "advanced", "years_inferred": 3}]
    frameworks = Column(JSON)  # [{"name": "React", "category": "web"}]
    languages = Column(JSON)  # [{"name": "Python", "proficiency": "advanced", "projects_count": 5}]
    tools = Column(JSON)  # ["Git", "Docker", "VS Code"]
    domains = Column(JSON)  # ["Machine Learning", "Web Development"]
    soft_skills = Column(JSON)  # ["Problem Solving", "Communication"]
    skill_summary = Column(Text)  # AI-generated skills summary

    # Activity Analysis (from GPT-4o)
    activity_level = Column(String(50))  # low/medium/high/very_high
    commit_quality_score = Column(Integer)  # 0-100
    contribution_consistency = Column(String(50))  # regular/irregular/sporadic
    collaboration_score = Column(Integer)  # 0-100
    project_diversity = Column(Integer)  # 0-100

    # Strengths and Growth Areas
    strengths = Column(JSON)  # ["strength1", "strength2"]
    areas_for_growth = Column(JSON)  # ["area1", "area2"]

    # Detailed Insights
    activity_insights = Column(Text)
    commit_quality_insights = Column(Text)
    collaboration_insights = Column(Text)
    project_insights = Column(Text)

    # Professional Summary
    professional_summary = Column(Text)  # AI-generated compelling summary
    recommended_roles = Column(JSON)  # ["Software Engineer", "Data Scientist"]

    # Metadata
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    raw_analysis = Column(JSON)  # Full GPT-4o response

    def __repr__(self):
        return f"<GitHubAnalysis for submission {self.submission_id}>"


class StackOverflowData(Base):
    """Phase 3: Stack Overflow profile and activity data"""
    __tablename__ = "stackoverflow_data"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    submission_id = Column(
        String(36),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Profile information
    profile_url = Column(String(1000))
    username = Column(String(255), index=True)
    user_id = Column(String(50))  # Stack Overflow user ID
    display_name = Column(String(255))

    # Statistics
    reputation = Column(Integer, index=True)
    gold_badges = Column(Integer)
    silver_badges = Column(Integer)
    bronze_badges = Column(Integer)

    # Activity metrics
    total_questions = Column(Integer)
    total_answers = Column(Integer)
    accepted_answers = Column(Integer)
    upvotes_received = Column(Integer)
    downvotes_received = Column(Integer)

    # Account metadata
    account_age_years = Column(Numeric(5, 2))
    last_seen_date = Column(DateTime(timezone=True))
    member_since = Column(Date)

    # Activity level
    activity_level = Column(String(50))  # high/medium/low/inactive
    posts_per_month_avg = Column(Numeric(10, 2))

    # Top tags and skills (JSON arrays)
    top_tags = Column(JSON)  # [{"tag": "python", "count": 50, "score": 200}]
    skills_from_tags = Column(JSON)  # ["Python", "JavaScript", "React"]

    # Notable contributions
    notable_questions = Column(JSON)  # Top upvoted questions
    notable_answers = Column(JSON)  # Top upvoted/accepted answers

    # Full profile data
    raw_data = Column(JSON)  # Complete API response

    # Metadata
    discovered_via = Column(String(50))  # 'chatgpt_search', 'manual', 'profile_link'
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<StackOverflowData {self.username} - {self.reputation} rep>"


class SkillWebMention(Base):
    """Phase 3: Web mentions of specific skills discovered via ChatGPT search"""
    __tablename__ = "skill_web_mentions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    submission_id = Column(
        String(36),
        ForeignKey("cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Skill being mentioned
    skill_name = Column(String(255), nullable=False, index=True)
    canonical_skill = Column(String(255), index=True)  # Normalized skill name

    # Web mention details
    url = Column(String(2000), nullable=False)
    title = Column(String(1000))
    excerpt = Column(Text)  # Relevant excerpt where skill is mentioned
    full_content = Column(Text)  # Full content if available

    # Source information
    source_type = Column(String(50), index=True)  # 'article', 'blog', 'talk', 'interview', 'portfolio', 'other'
    source_platform = Column(String(100))  # 'Medium', 'Dev.to', 'Personal Blog', etc.
    author = Column(String(255))
    published_date = Column(Date, index=True)

    # Context and evidence
    mention_context = Column(Text)  # How the skill was mentioned (writing about it, using it, etc.)
    evidence_type = Column(String(50))  # 'wrote_article', 'built_project', 'gave_talk', 'mentioned_by_others'

    # Credibility scoring
    credibility = Column(String(20))  # high/medium/low
    credibility_score = Column(Numeric(5, 2))  # 0-100
    relevance_score = Column(Numeric(5, 2))  # 0-100

    # Skill proficiency indicators
    skill_depth = Column(String(50))  # beginner/intermediate/advanced/expert
    confidence_level = Column(String(50))  # how confident we are about this skill

    # Additional metadata
    tags = Column(JSON)  # Related tags/topics
    related_skills = Column(JSON)  # Other skills mentioned alongside this one

    # Discovery metadata
    discovered_via = Column(String(50))  # 'chatgpt_search', 'blog_discovery', 'web_mentions_search'
    search_query = Column(Text)  # Query that found this mention
    raw_data = Column(JSON)  # Full search result data

    # Timestamps
    collected_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<SkillWebMention {self.skill_name} from {self.source_type}>"
