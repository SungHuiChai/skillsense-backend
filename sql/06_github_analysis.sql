-- GitHub Analysis Table (GPT-4o Analysis Results)
-- Stores comprehensive analysis of GitHub profiles using GPT-4o

CREATE TABLE IF NOT EXISTS github_analysis (
    id VARCHAR(36) PRIMARY KEY,
    submission_id VARCHAR(36) NOT NULL UNIQUE,
    github_data_id VARCHAR(36) NOT NULL,

    -- Skills Analysis (from GPT-4o)
    technical_skills JSON,  -- [{"name": "Python", "proficiency": "advanced", "years_inferred": 3}]
    frameworks JSON,        -- [{"name": "React", "category": "web"}]
    languages JSON,         -- [{"name": "Python", "proficiency": "advanced", "projects_count": 5}]
    tools JSON,             -- ["Git", "Docker", "VS Code"]
    domains JSON,           -- ["Machine Learning", "Web Development"]
    soft_skills JSON,       -- ["Problem Solving", "Communication"]
    skill_summary TEXT,     -- AI-generated skills summary

    -- Activity Analysis (from GPT-4o)
    activity_level VARCHAR(50),              -- low/medium/high/very_high
    commit_quality_score INTEGER,            -- 0-100
    contribution_consistency VARCHAR(50),    -- regular/irregular/sporadic
    collaboration_score INTEGER,             -- 0-100
    project_diversity INTEGER,               -- 0-100

    -- Strengths and Growth Areas
    strengths JSON,          -- ["strength1", "strength2"]
    areas_for_growth JSON,   -- ["area1", "area2"]

    -- Detailed Insights
    activity_insights TEXT,
    commit_quality_insights TEXT,
    collaboration_insights TEXT,
    project_insights TEXT,

    -- Professional Summary
    professional_summary TEXT,    -- AI-generated compelling summary
    recommended_roles JSON,       -- ["Software Engineer", "Data Scientist"]

    -- Metadata
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    raw_analysis JSON,            -- Full GPT-4o response

    -- Foreign Keys
    FOREIGN KEY (submission_id) REFERENCES cv_submissions(id) ON DELETE CASCADE,
    FOREIGN KEY (github_data_id) REFERENCES github_data(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_github_analysis_submission_id ON github_analysis(submission_id);
CREATE INDEX idx_github_analysis_github_data_id ON github_analysis(github_data_id);
CREATE INDEX idx_github_analysis_activity_level ON github_analysis(activity_level);
CREATE INDEX idx_github_analysis_analyzed_at ON github_analysis(analyzed_at);

-- Comments
COMMENT ON TABLE github_analysis IS 'Stores GPT-4o analysis results for GitHub profiles including skills, activity patterns, and professional insights';
COMMENT ON COLUMN github_analysis.technical_skills IS 'Structured technical skills extracted by GPT-4o with proficiency levels';
COMMENT ON COLUMN github_analysis.activity_level IS 'Developer activity level: low/medium/high/very_high';
COMMENT ON COLUMN github_analysis.professional_summary IS 'AI-generated professional summary highlighting unique value proposition';
