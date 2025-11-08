-- SkillSense Phase 3: Processing Layer
-- Run this script AFTER completing Phases 1 & 2 (or use mocks)

\c skillsense;

-- Check if cv_submissions exists (Phase 1)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cv_submissions') THEN
        RAISE NOTICE 'Phase 1 tables not found. You can still proceed with mock data.';
    END IF;
END $$;

-- Create extracted_skills table
CREATE TABLE IF NOT EXISTS extracted_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID, -- Will be FK when Phase 1 complete

    skill_name VARCHAR(255) NOT NULL,
    skill_name_normalized VARCHAR(255) NOT NULL,
    skill_category VARCHAR(100),
    skill_subcategory VARCHAR(100),

    proficiency_level VARCHAR(50),
    proficiency_score DECIMAL(5,2),

    confidence_score DECIMAL(5,2) NOT NULL,
    is_validated BOOLEAN DEFAULT FALSE,
    validation_status VARCHAR(50) DEFAULT 'pending',

    evidence_count INTEGER DEFAULT 0,
    primary_evidence TEXT,

    esco_skill_id VARCHAR(100),
    esco_skill_uri VARCHAR(500),
    onet_code VARCHAR(50),

    extracted_by VARCHAR(100),
    extraction_method VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skill_evidence table
CREATE TABLE IF NOT EXISTS skill_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES extracted_skills(id) ON DELETE CASCADE,
    submission_id UUID,

    source_type VARCHAR(50) NOT NULL,
    source_id UUID,
    source_url VARCHAR(1000),

    evidence_text TEXT NOT NULL,
    context_text TEXT,

    evidence_strength VARCHAR(50),
    evidence_type VARCHAR(50),
    relevance_score DECIMAL(5,2),

    recency_date DATE,
    frequency INTEGER DEFAULT 1,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skill_validations table
CREATE TABLE IF NOT EXISTS skill_validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES extracted_skills(id) ON DELETE CASCADE,
    submission_id UUID,

    sources_found_in TEXT[],
    source_count INTEGER,
    source_agreement_score DECIMAL(5,2),

    is_hallucination BOOLEAN DEFAULT FALSE,
    hallucination_score DECIMAL(5,2),
    hallucination_reason TEXT,

    is_outdated BOOLEAN DEFAULT FALSE,
    last_used_date DATE,

    is_overstated BOOLEAN DEFAULT FALSE,

    requires_manual_review BOOLEAN DEFAULT FALSE,
    manual_review_notes TEXT,
    verified_by VARCHAR(100),
    verified_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skill_profiles table
CREATE TABLE IF NOT EXISTS skill_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID UNIQUE,

    total_skills_extracted INTEGER,
    total_skills_validated INTEGER,
    total_skills_rejected INTEGER,

    skills_by_category JSONB,
    skills_by_proficiency JSONB,
    top_skills JSONB,

    overall_skill_confidence DECIMAL(5,2),
    cross_validation_rate DECIMAL(5,2),
    hallucination_rate DECIMAL(5,2),

    profile_completeness DECIMAL(5,2),
    missing_categories TEXT[],

    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    processing_duration_seconds INTEGER,

    skill_relationships JSONB,

    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create skill_taxonomy_mapping table
CREATE TABLE IF NOT EXISTS skill_taxonomy_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID REFERENCES extracted_skills(id) ON DELETE CASCADE,

    taxonomy_type VARCHAR(50),
    taxonomy_id VARCHAR(100),
    taxonomy_uri VARCHAR(500),
    taxonomy_label VARCHAR(500),
    taxonomy_description TEXT,

    mapping_confidence DECIMAL(5,2),
    mapping_method VARCHAR(100),

    parent_taxonomy_id VARCHAR(100),
    skill_level INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_extracted_skills_submission_id ON extracted_skills(submission_id);
CREATE INDEX IF NOT EXISTS idx_extracted_skills_skill_name ON extracted_skills(skill_name_normalized);
CREATE INDEX IF NOT EXISTS idx_extracted_skills_category ON extracted_skills(skill_category);
CREATE INDEX IF NOT EXISTS idx_extracted_skills_confidence ON extracted_skills(confidence_score);

CREATE INDEX IF NOT EXISTS idx_skill_evidence_skill_id ON skill_evidence(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_evidence_submission_id ON skill_evidence(submission_id);
CREATE INDEX IF NOT EXISTS idx_skill_evidence_source_type ON skill_evidence(source_type);

CREATE INDEX IF NOT EXISTS idx_skill_validations_skill_id ON skill_validations(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_validations_submission_id ON skill_validations(submission_id);

CREATE INDEX IF NOT EXISTS idx_skill_profiles_submission_id ON skill_profiles(submission_id);
CREATE INDEX IF NOT EXISTS idx_skill_profiles_status ON skill_profiles(processing_status);

CREATE INDEX IF NOT EXISTS idx_skill_taxonomy_skill_id ON skill_taxonomy_mapping(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_taxonomy_type ON skill_taxonomy_mapping(taxonomy_type);

-- Add foreign key constraints if Phase 1 tables exist
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cv_submissions') THEN
        -- Check if constraint doesn't already exist before adding
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_extracted_skills_submission'
        ) THEN
            ALTER TABLE extracted_skills ADD CONSTRAINT fk_extracted_skills_submission
                FOREIGN KEY (submission_id) REFERENCES cv_submissions(id) ON DELETE CASCADE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_skill_evidence_submission'
        ) THEN
            ALTER TABLE skill_evidence ADD CONSTRAINT fk_skill_evidence_submission
                FOREIGN KEY (submission_id) REFERENCES cv_submissions(id) ON DELETE CASCADE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_skill_validations_submission'
        ) THEN
            ALTER TABLE skill_validations ADD CONSTRAINT fk_skill_validations_submission
                FOREIGN KEY (submission_id) REFERENCES cv_submissions(id) ON DELETE CASCADE;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_name = 'fk_skill_profiles_submission'
        ) THEN
            ALTER TABLE skill_profiles ADD CONSTRAINT fk_skill_profiles_submission
                FOREIGN KEY (submission_id) REFERENCES cv_submissions(id) ON DELETE CASCADE;
        END IF;
    END IF;
END $$;

-- Success message
SELECT 'Phase 3 database tables created successfully!' as message;
