-- SkillSense Phase 2: Data Collection Layer
-- Run this script AFTER completing Phase 1

-- Check if Phase 1 tables exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cv_submissions') THEN
        RAISE EXCEPTION 'Phase 1 tables not found. Please run Phase 1 init_db.sql first.';
    END IF;
END $$;

-- Create collected_sources table
CREATE TABLE IF NOT EXISTS collected_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES cv_submissions(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL, -- 'github', 'web_search'
    source_url VARCHAR(1000),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'collecting', 'completed', 'failed', 'skipped'

    -- Collection metadata
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,

    -- Rate limiting
    last_request_at TIMESTAMP WITH TIME ZONE,
    rate_limit_reset_at TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create github_data table
CREATE TABLE IF NOT EXISTS github_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES collected_sources(id) ON DELETE CASCADE,
    submission_id UUID REFERENCES cv_submissions(id) ON DELETE CASCADE,

    -- Profile data
    username VARCHAR(255),
    name VARCHAR(255),
    bio TEXT,
    location VARCHAR(255),
    company VARCHAR(255),
    blog VARCHAR(500),
    email VARCHAR(255),

    -- Statistics
    public_repos INTEGER,
    public_gists INTEGER,
    followers INTEGER,
    following INTEGER,

    -- Repository data (JSONB for flexible storage)
    repositories JSONB, -- Array of repo objects
    languages JSONB, -- Language statistics
    top_repos JSONB, -- Most starred/forked repos

    -- Contribution data
    contributions_last_year INTEGER,
    commit_activity JSONB, -- Commit patterns

    -- Skills extracted
    technologies JSONB, -- Array of technologies used
    frameworks JSONB, -- Frameworks detected

    -- Metadata
    raw_data JSONB, -- Full API response
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create web_mentions table
CREATE TABLE IF NOT EXISTS web_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES collected_sources(id) ON DELETE CASCADE,
    submission_id UUID REFERENCES cv_submissions(id) ON DELETE CASCADE,

    -- Article/mention info
    title VARCHAR(1000),
    url VARCHAR(2000) NOT NULL,
    snippet TEXT,
    full_content TEXT,

    -- Source metadata
    source_name VARCHAR(255), -- 'TechCrunch', 'Medium', etc.
    source_type VARCHAR(50), -- 'article', 'interview', 'podcast', 'conference', 'award'
    author VARCHAR(255),
    published_date DATE,

    -- Context
    mention_context TEXT, -- Surrounding text where person is mentioned
    topics JSONB, -- Extracted topics
    sentiment VARCHAR(50), -- 'positive', 'neutral', 'negative'

    -- Credibility
    source_credibility_score DECIMAL(5,2), -- 0-100
    relevance_score DECIMAL(5,2), -- 0-100

    -- Metadata
    raw_data JSONB,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create aggregated_profile table
CREATE TABLE IF NOT EXISTS aggregated_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID REFERENCES cv_submissions(id) ON DELETE CASCADE UNIQUE,

    -- Aggregated personal info (best across sources)
    verified_name VARCHAR(255),
    verified_email VARCHAR(255),
    verified_location VARCHAR(255),

    -- Source diversity metrics
    sources_collected INTEGER, -- How many sources successfully collected
    total_sources_attempted INTEGER,
    collection_completeness DECIMAL(5,2), -- Percentage of successful collections

    -- Cross-source validation
    name_consistency_score DECIMAL(5,2), -- How consistent is name across sources
    location_consistency_score DECIMAL(5,2),
    skills_cross_validated INTEGER, -- Skills found in multiple sources

    -- Aggregated skills (preliminary - before Phase 3 extraction)
    all_skills JSONB, -- All skills from all sources before extraction

    -- External visibility metrics
    github_contributions INTEGER,
    linkedin_connections INTEGER,
    web_mentions_count INTEGER,
    conferences_spoken INTEGER,
    articles_published INTEGER,

    -- Overall data quality
    overall_quality_score DECIMAL(5,2), -- 0-100
    data_freshness_score DECIMAL(5,2), -- How recent is the data

    -- Timestamps
    last_aggregated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_collected_sources_submission_id ON collected_sources(submission_id);
CREATE INDEX IF NOT EXISTS idx_collected_sources_status ON collected_sources(status);
CREATE INDEX IF NOT EXISTS idx_collected_sources_source_type ON collected_sources(source_type);

CREATE INDEX IF NOT EXISTS idx_github_data_submission_id ON github_data(submission_id);
CREATE INDEX IF NOT EXISTS idx_github_data_username ON github_data(username);
CREATE INDEX IF NOT EXISTS idx_github_data_source_id ON github_data(source_id);

CREATE INDEX IF NOT EXISTS idx_web_mentions_submission_id ON web_mentions(submission_id);
CREATE INDEX IF NOT EXISTS idx_web_mentions_source_type ON web_mentions(source_type);
CREATE INDEX IF NOT EXISTS idx_web_mentions_published_date ON web_mentions(published_date);
CREATE INDEX IF NOT EXISTS idx_web_mentions_source_id ON web_mentions(source_id);

CREATE INDEX IF NOT EXISTS idx_aggregated_profile_submission_id ON aggregated_profile(submission_id);

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Phase 2 database tables created successfully!';
    RAISE NOTICE 'Tables: collected_sources, github_data, web_mentions, aggregated_profile';
    RAISE NOTICE 'Ready for data collection implementation.';
END $$;
